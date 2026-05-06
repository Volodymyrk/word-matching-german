#!/usr/bin/env python3
"""
Icon Factory v3 — Batch icon generation pipeline.

Usage:
  uv run generate_icons_v3.py <vocab_file>
  uv run generate_icons_v3.py <vocab_file> --preview-prompts
  uv run generate_icons_v3.py <vocab_file> --skip-clip
"""

import json
import uuid
import urllib.request
import urllib.error
import websocket
import time
import os
import sys
import shutil
import random
import argparse
from pathlib import Path

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ── Configuration ──────────────────────────────────────────────────────────────
COMFYUI_HOST   = "127.0.0.1:8000"
WORKFLOW_FILE  = "flux1_icon_factory.json"
OUTPUT_DIR     = "icons_output"
MAX_RETRIES    = 3

PROMPT_NODE_ID = "4"    # CLIPTextEncode positive prompt node
SAVE_NODE_ID   = "10"   # SaveImage node

SIMILARITY_THRESHOLD = 0.92   # above this = duplicate, flag for review
SEMANTIC_THRESHOLD   = 0.20   # below this = image doesn't represent the word, flag for review

STYLE_SUFFIX = (
    ", flat design icon, soft pastel colors, rounded shapes, thick black outlines, "
    "friendly cartoon style, white background, simple clean illustration, "
    "no text, no letters, centered composition, single object"
)
# ──────────────────────────────────────────────────────────────────────────────

# Global CLIP state (initialized by load_clip)
clip_model = None
clip_preprocess = None
device = "cpu"


# ── Step 1: Load Vocabulary ───────────────────────────────────────────────────

def load_vocab(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = []
    top_keys = list(data.keys())

    if len(top_keys) == 1:
        inner = data[top_keys[0]]
        if isinstance(inner, dict):
            # Lesson wrapper: { "lesson_name": { "section": [...] } }
            for section_key, words in inner.items():
                if isinstance(words, list):
                    for w in words:
                        items.append({**w, "section": section_key})
        elif isinstance(inner, list):
            for w in inner:
                items.append({**w, "section": top_keys[0]})
    else:
        # Direct section structure: { "section1": [...], ... }
        for section_key, words in data.items():
            if isinstance(words, list):
                for w in words:
                    items.append({**w, "section": section_key})
            elif isinstance(words, dict):
                for sub_key, sub_words in words.items():
                    if isinstance(sub_words, list):
                        for w in sub_words:
                            items.append({**w, "section": f"{section_key}/{sub_key}"})

    sections = set(item["section"] for item in items)
    print(f"Loaded {len(items)} words from {len(sections)} sections")
    return items


# ── Step 2: Generate Visual Descriptions via Claude API ───────────────────────

def generate_visual_descriptions(vocab: list[dict]) -> dict[str, str]:
    import anthropic

    client = anthropic.Anthropic()

    word_list = []
    for i, item in enumerate(vocab, 1):
        english = item["english"]
        grammar = item.get("grammar", "")
        if grammar in ("m", "f", "n"):
            label = "noun"
        elif grammar and grammar.lower().startswith("adj"):
            label = "adj"
        elif not grammar:
            label = "phrase"
        else:
            label = grammar
        word_list.append(f'{i}. "{english}" ({label})')

    words_text = "\n".join(word_list)

    user_prompt = f"""Convert each vocabulary word into a concrete visual description for a flat design icon to be used by FLUX 1 image generation model.

Words:
{words_text}

Rules:
- Single concrete object or simple scene
- Maximum 15 words per description
- No text, letters, or numbers visible in the icon
- For verbs: show the action's most iconic object or gesture
- For adjectives: show an object that embodies the quality
- Make each description visually DISTINCT from all others
- Descriptions must work at small icon sizes
- NO metaphors or similes — the image model is literal. Say "a wide river with blue water and green banks", NOT "a winding blue ribbon". Say "a mountain peak with snow", NOT "a jagged triangle piercing clouds".
- Use the actual object's real name, not a poetic substitute

Reply ONLY with a JSON object. No explanation, no markdown.
Example: {{"1": "a hand holding a credit card over a payment terminal", "2": "a bright green apple with a water droplet", "3": "a wide river with blue water flowing between green grassy banks"}}"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system="You generate concise visual descriptions for vocabulary flashcard icons. Return only valid JSON.",
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        numbered = json.loads(raw)
    except json.JSONDecodeError:
        print(f"ERROR: Failed to parse Claude response:\n{raw}")
        raise ValueError("Claude returned invalid JSON")

    result = {}
    for i, item in enumerate(vocab, 1):
        key = str(i)
        result[item["english"]] = numbered.get(key, item["english"])

    return result


# ── Step 3: German Word → Stable Filename Stem ───────────────────────────────

import re as _re

def german_stem(word: str) -> str:
    s = word.lower()
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    s = s.replace(" ", "_")
    s = _re.sub(r"[^\w-]", "", s)   # strip non-alphanumeric except _ and -
    s = _re.sub(r"_+", "_", s)      # collapse consecutive underscores
    return s


# ── Step 4: Build Icon Prompt ─────────────────────────────────────────────────

def build_prompt(visual_description: str) -> str:
    return f"a minimalist icon of {visual_description}{STYLE_SUFFIX}"


# ── Step 4: Load and Convert ComfyUI Workflow ─────────────────────────────────

# Maps node class_type to ordered widget input names
_WIDGET_MAPS = {
    "CheckpointLoaderSimple": ["ckpt_name"],
    "UNETLoader":             ["unet_name", "weight_dtype"],
    "DualCLIPLoader":         ["clip_name1", "clip_name2", "type"],
    "VAELoader":              ["vae_name"],
    "CLIPTextEncode":         ["text"],
    "EmptySD3LatentImage":    ["width", "height", "batch_size"],
    "EmptyLatentImage":       ["width", "height", "batch_size"],
    "KSampler":               ["seed", "control_after_generate", "steps", "cfg",
                               "sampler_name", "scheduler", "denoise"],
    "FluxGuidance":           ["guidance"],
    "SaveImage":              ["filename_prefix"],
    "LoraLoader":             ["lora_name", "strength_model", "strength_clip"],
}


def load_workflow(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "nodes" not in data:
        return data  # already API format

    nodes = data["nodes"]
    links = data.get("links", [])

    # link_id -> (src_node_id, src_slot)
    link_map = {}
    for link in links:
        link_id, src_node_id, src_slot, _dst_node_id, _dst_slot, *_ = link
        link_map[link_id] = (src_node_id, src_slot)

    workflow = {}

    for node in nodes:
        node_id = str(node["id"])
        class_type = node["type"]
        widget_values = node.get("widgets_values", [])
        node_inputs = node.get("inputs", [])

        inputs = {}

        # Map widget values to named inputs
        for idx, key in enumerate(_WIDGET_MAPS.get(class_type, [])):
            if idx < len(widget_values):
                inputs[key] = widget_values[idx]

        # Wire linked inputs
        for inp in node_inputs:
            link_id = inp.get("link")
            if link_id is not None and link_id in link_map:
                src_node_id, src_slot = link_map[link_id]
                inputs[inp["name"]] = [str(src_node_id), src_slot]

        workflow[node_id] = {"class_type": class_type, "inputs": inputs}

    return workflow


# ── Step 5: ComfyUI API ───────────────────────────────────────────────────────

def queue_prompt(workflow: dict, client_id: str) -> str:
    payload = json.dumps({"prompt": workflow, "client_id": client_id}).encode("utf-8")
    req = urllib.request.Request(
        f"http://{COMFYUI_HOST}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    return data["prompt_id"]


def wait_for_completion(ws, prompt_id: str) -> None:
    while True:
        try:
            msg = ws.recv()
            if isinstance(msg, bytes):
                continue
            data = json.loads(msg)
            if (data.get("type") == "executing"
                    and data.get("data", {}).get("node") is None
                    and data.get("data", {}).get("prompt_id") == prompt_id):
                break
        except json.JSONDecodeError:
            continue


def _find_comfyui_output_dir() -> Path | None:
    candidates = [
        Path.home() / "Documents" / "ComfyUI" / "output",
        Path.home() / "ComfyUI" / "output",
        Path("./ComfyUI/output"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def find_output_image(filename_prefix: str, prompt_id: str) -> str | None:
    try:
        url = f"http://{COMFYUI_HOST}/history/{prompt_id}"
        with urllib.request.urlopen(url) as resp:
            history = json.loads(resp.read())

        if prompt_id not in history:
            return None

        outputs = history[prompt_id].get("outputs", {})
        images = outputs.get(SAVE_NODE_ID, {}).get("images", [])

        if not images:
            return None

        img_info = images[0]
        filename = img_info["filename"]
        subfolder = img_info.get("subfolder", "")

        output_dir = _find_comfyui_output_dir()
        if output_dir is None:
            return None

        full_path = output_dir / subfolder / filename if subfolder else output_dir / filename
        if full_path.exists():
            return str(full_path)

        return None

    except Exception:
        # Fallback: glob by prefix
        output_dir = _find_comfyui_output_dir()
        if output_dir is None:
            return None
        matches = sorted(
            output_dir.glob(f"{filename_prefix}*.png"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return str(matches[0]) if matches else None


# ── Step 6: CLIP Quality and Similarity Checks ────────────────────────────────

def load_clip():
    global clip_model, clip_preprocess, device
    import open_clip
    import torch

    print("Loading CLIP model (ViT-B-32)...")
    clip_model, _, clip_preprocess = open_clip.create_model_and_transforms(
        "ViT-B-32", pretrained="openai"
    )
    clip_model.eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    clip_model = clip_model.to(device)
    print(f"CLIP loaded on {device}")



def get_image_embedding(image_path: str):
    import torch
    from PIL import Image

    img = clip_preprocess(Image.open(image_path)).unsqueeze(0).to(device)
    with torch.no_grad():
        emb = clip_model.encode_image(img)
        emb /= emb.norm(dim=-1, keepdim=True)
    return emb.cpu()


def is_too_similar(embedding, accepted_embeddings: dict) -> tuple[bool, str | None]:
    for word, other_emb in accepted_embeddings.items():
        similarity = (embedding @ other_emb.T).item()
        if similarity > SIMILARITY_THRESHOLD:
            return True, word
    return False, None


# ── Step 7: Main Generation Loop ──────────────────────────────────────────────

def generate_all_icons(vocab, workflow_template, visual_descriptions):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    client_id = str(uuid.uuid4())

    ws = websocket.WebSocket()
    ws.connect(f"ws://{COMFYUI_HOST}/ws?clientId={client_id}")

    results = []
    embeddings = {}  # word -> tensor, populated after generation if CLIP is loaded

    for i, item in enumerate(vocab, 1):
        english = item["english"]
        german  = item["german"]
        grammar = item.get("grammar", "")

        visual = visual_descriptions.get(english, english)
        prompt = build_prompt(visual)

        stem = german_stem(german)

        print(f"\n[{i:02d}/{len(vocab)}] {english} ({grammar}) → {german}  [stem: {stem}]")
        print(f"  Visual: {visual}")

        saved = False
        final_path = None
        image_path = None

        for attempt in range(MAX_RETRIES):
            if attempt > 0:
                print(f"  Retry {attempt}/{MAX_RETRIES - 1} (ComfyUI error)...")

            filename_prefix = f"{stem}_attempt{attempt}"

            wf = json.loads(json.dumps(workflow_template))
            wf[PROMPT_NODE_ID]["inputs"]["text"] = prompt
            wf[SAVE_NODE_ID]["inputs"]["filename_prefix"] = filename_prefix

            if attempt > 0:
                for node in wf.values():
                    if node.get("class_type") == "KSampler":
                        node["inputs"]["seed"] = random.randint(0, 2**32)
                        break

            try:
                prompt_id = queue_prompt(wf, client_id)
                wait_for_completion(ws, prompt_id)
            except Exception as e:
                print(f"  ✗ ComfyUI error: {e}")
                continue

            image_path = find_output_image(filename_prefix, prompt_id)
            if not image_path:
                print(f"  ✗ Output file not found")
                continue

            final_name = f"{stem}.png"
            final_path = os.path.join(OUTPUT_DIR, final_name)
            shutil.copy2(image_path, final_path)
            print(f"  ✓ Saved → {final_name}")
            saved = True
            break

        if not saved:
            print(f"  ⚠ Failed after {MAX_RETRIES} attempts — skipping")

        results.append({
            "index": i,
            "word": english,
            "german": german,
            "stem": stem,
            "grammar": grammar,
            "saved": saved,
            "path": final_path,
            "visual": visual,
            "prompt": prompt,
            "flagged": False,
            "flag_reason": None,
        })

        time.sleep(0.3)

    ws.close()
    return results, embeddings


# ── Step 8: Post-generation CLIP Review ──────────────────────────────────────

def review_icons(results: list[dict], embeddings: dict) -> list[dict]:
    """Compute CLIP embeddings for all saved icons, flag semantic mismatches and duplicates."""
    import open_clip
    import torch

    tokenizer = open_clip.get_tokenizer("ViT-B-32")
    print("\nRunning CLIP review pass...")

    # Compute embeddings for all saved images
    for r in results:
        if r["saved"] and r["path"] and r["word"] not in embeddings:
            embeddings[r["word"]] = get_image_embedding(r["path"])

    # Semantic check: image vs "an icon of {word}"
    for r in results:
        if not r["saved"]:
            continue
        emb = embeddings.get(r["word"])
        if emb is None:
            continue

        text_tokens = tokenizer([f"an icon of {r['word']}"]).to(device)
        with torch.no_grad():
            text_feat = clip_model.encode_text(text_tokens)
            text_feat /= text_feat.norm(dim=-1, keepdim=True)

        score = (emb.to(device) @ text_feat.T).item()
        r["semantic_score"] = round(score, 4)

        if score < SEMANTIC_THRESHOLD:
            r["flagged"] = True
            r["flag_reason"] = f"low semantic similarity ({score:.2f} < {SEMANTIC_THRESHOLD})"
            print(f"  ⚑ {r['word']:25s} semantic={score:.2f}  — flagged")
        else:
            print(f"  ✓ {r['word']:25s} semantic={score:.2f}")

    # Duplicate check: pairwise cosine similarity across all embeddings
    words = [r["word"] for r in results if r["saved"] and r["word"] in embeddings]
    for i, w1 in enumerate(words):
        for w2 in words[i + 1:]:
            sim = (embeddings[w1] @ embeddings[w2].T).item()
            if sim > SIMILARITY_THRESHOLD:
                # Flag the one with the lower semantic score (keep the better one)
                r1 = next(r for r in results if r["word"] == w1)
                r2 = next(r for r in results if r["word"] == w2)
                weaker = r1 if r1.get("semantic_score", 0) <= r2.get("semantic_score", 0) else r2
                if not weaker["flagged"]:
                    weaker["flagged"] = True
                    other = w2 if weaker["word"] == w1 else w1
                    weaker["flag_reason"] = f"too similar to '{other}' ({sim:.2f})"
                    print(f"  ⚑ {weaker['word']:25s} duplicate of '{other}' ({sim:.2f})  — flagged")

    flagged = [r for r in results if r["flagged"]]
    print(f"\n  {len(flagged)} flagged out of {len([r for r in results if r['saved']])} images")
    return flagged


# ── Step 9: Re-generate Flagged Icons ────────────────────────────────────────

def regenerate_flagged_icons(flagged: list[dict], vocab: list[dict],
                             workflow_template: dict, embeddings: dict) -> None:
    """Call Claude Sonnet for better prompts, re-run ComfyUI for flagged words only."""
    if not flagged:
        return

    import anthropic
    vocab_dict = {item["english"]: item for item in vocab}

    # Build Sonnet prompt with failure context
    word_list = []
    for i, r in enumerate(flagged, 1):
        item = vocab_dict.get(r["word"], {})
        grammar = item.get("grammar", "")
        word_list.append(
            f'{i}. "{r["word"]}" ({grammar}) [German: {r["german"]}]\n'
            f'   Previous description: {r["visual"]}\n'
            f'   Failure reason: {r["flag_reason"]}'
        )

    user_prompt = f"""These vocabulary icons failed quality review and need better visual descriptions.

{chr(10).join(word_list)}

Rules:
- Single concrete object or simple scene, maximum 15 words
- NO metaphors — use the literal object name (e.g. "a flowing river", NOT "a winding ribbon")
- No text, letters, or numbers in the icon
- For verbs: the action's most iconic object or gesture
- For adjectives: an object that clearly embodies the quality
- Each description must be visually DISTINCT from all others

Reply ONLY with a JSON object mapping number string to new description.
Example: {{"1": "a wide river with blue water flowing between green grassy banks"}}"""

    print(f"\nAsking Claude Sonnet for better descriptions for {len(flagged)} flagged icons...")
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system="You generate improved visual descriptions for flat design icons. Return only valid JSON.",
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        new_descriptions = json.loads(raw)
    except json.JSONDecodeError:
        print(f"ERROR: Sonnet returned invalid JSON:\n{raw}")
        return

    # Re-generate images via ComfyUI
    client_id = str(uuid.uuid4())
    ws = websocket.WebSocket()
    ws.connect(f"ws://{COMFYUI_HOST}/ws?clientId={client_id}")

    for i, r in enumerate(flagged, 1):
        new_visual = new_descriptions.get(str(i), r["visual"])
        new_prompt = build_prompt(new_visual)

        stem = r.get("stem") or german_stem(r["german"])
        filename_prefix = f"{stem}_regen"

        print(f"\n  [{i}/{len(flagged)}] {r['word']} → {new_visual}")

        wf = json.loads(json.dumps(workflow_template))
        wf[PROMPT_NODE_ID]["inputs"]["text"] = new_prompt
        wf[SAVE_NODE_ID]["inputs"]["filename_prefix"] = filename_prefix

        try:
            prompt_id = queue_prompt(wf, client_id)
            wait_for_completion(ws, prompt_id)
        except Exception as e:
            print(f"    ✗ ComfyUI error: {e}")
            continue

        image_path = find_output_image(filename_prefix, prompt_id)
        if not image_path:
            print(f"    ✗ Output file not found")
            continue

        final_name = f"{r['index']:02d}_{safe_name}_{r['german']}.png"
        final_path = os.path.join(OUTPUT_DIR, final_name)
        shutil.copy2(image_path, final_path)

        # Update result in place
        r["visual"] = new_visual
        r["prompt"] = new_prompt
        r["path"] = final_path
        r["flagged"] = False
        r["flag_reason"] = None
        r["regenerated"] = True

        # Update embedding
        embeddings[r["word"]] = get_image_embedding(final_path)
        print(f"    ✓ Saved → {final_name}")

        time.sleep(0.3)

    ws.close()


# ── Step 10: Summary Report ───────────────────────────────────────────────────

def print_summary(results):
    saved    = [r for r in results if r["saved"]]
    flagged  = [r for r in results if r.get("flagged")]
    regen    = [r for r in results if r.get("regenerated")]
    failed   = [r for r in results if not r["saved"]]
    output_path = os.path.abspath(OUTPUT_DIR)

    print()
    print("════════════════════════════════════")
    print(" Icon Factory v3 — Generation Report")
    print("════════════════════════════════════")
    print(f" Total words:      {len(results)}")
    print(f" Saved:            {len(saved)}")
    print(f" Regenerated:      {len(regen)}")
    print(f" Still flagged:    {len(flagged)}")
    print(f" Failed (no img):  {len(failed)}")

    if flagged:
        print()
        print(" Still needs manual review:")
        for r in flagged:
            print(f"   - {r['word']:25s} ({r['german']})  {r.get('flag_reason', '')}")

    if failed:
        print()
        print(" No image generated:")
        for r in failed:
            print(f"   - {r['word']}  ({r['german']})")

    print()
    print(f" Icons saved to: {output_path}\\")
    print("════════════════════════════════════")

    report_path = os.path.join(OUTPUT_DIR, "generation_report.json")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f" Report saved:   {report_path}")


# ── Step 11: Entry Point ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Icon Factory v3 — batch icon generation")
    parser.add_argument("vocab_file", nargs="?", default="german3_supermarket2.json",
                        help="Path to vocabulary JSON file")
    parser.add_argument("--preview-prompts", action="store_true",
                        help="Generate and print prompts without running ComfyUI")
    parser.add_argument("--skip-clip", action="store_true",
                        help="Skip post-generation CLIP review and re-generation")
    parser.add_argument("--review-only", action="store_true",
                        help="Run CLIP review on existing icons from a previous run (no generation)")
    args = parser.parse_args()

    # --review-only: load prior results and run CLIP review, no API calls, no ComfyUI
    if args.review_only:
        report_path = os.path.join(OUTPUT_DIR, "generation_report.json")
        if not os.path.exists(report_path):
            print(f"ERROR: No report found at {os.path.abspath(report_path)}")
            print("Run a full generation pass first.")
            sys.exit(1)

        with open(report_path, "r", encoding="utf-8") as f:
            results = json.load(f)

        # Reset any prior flags so review is clean
        for r in results:
            r["flagged"] = False
            r["flag_reason"] = None

        load_clip()
        review_icons(results, {})
        return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set.")
        print("Get your key from https://console.anthropic.com")
        print('Set it with: $env:ANTHROPIC_API_KEY = "sk-ant-..."')
        sys.exit(1)

    if not os.path.exists(args.vocab_file):
        print(f"ERROR: Vocab file not found: {os.path.abspath(args.vocab_file)}")
        sys.exit(1)

    vocab = load_vocab(args.vocab_file)

    # Phase 0: generate visual descriptions via Claude Haiku
    print("Generating visual descriptions via Claude Sonnet...")
    descriptions = generate_visual_descriptions(vocab)

    if args.preview_prompts:
        print("\n── Prompt Preview ──────────────────────────")
        for item in vocab:
            desc = descriptions.get(item["english"], item["english"])
            print(f"  {item['english']:30s} → {desc}")
        return

    if not os.path.exists(WORKFLOW_FILE):
        print(f"ERROR: Workflow file not found: {os.path.abspath(WORKFLOW_FILE)}")
        sys.exit(1)

    workflow = load_workflow(WORKFLOW_FILE)

    try:
        with urllib.request.urlopen(f"http://{COMFYUI_HOST}/system_stats", timeout=5):
            pass
    except Exception:
        print(f"ERROR: Cannot connect to ComfyUI at http://{COMFYUI_HOST}")
        print("Make sure ComfyUI is running and check the port in COMFYUI_HOST")
        sys.exit(1)

    # Phase 1: generate all icons (retry only on ComfyUI errors)
    print("\n── Phase 1: Generating icons ────────────────")
    results, embeddings = generate_all_icons(vocab, workflow, descriptions)

    if not args.skip_clip:
        # Phase 2: CLIP review — semantic + duplicate checks
        print("\n── Phase 2: CLIP review ─────────────────────")
        load_clip()
        flagged = review_icons(results, embeddings)

        # Phase 3: re-generate flagged icons using Claude Sonnet
        if flagged:
            print(f"\n── Phase 3: Re-generating {len(flagged)} flagged icons ──")
            regenerate_flagged_icons(flagged, vocab, workflow, embeddings)

    print_summary(results)


if __name__ == "__main__":
    main()
