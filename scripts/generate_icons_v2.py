"""
ComfyUI batch icon generator for German vocabulary - v2
Handles nouns, verbs, and adjectives with smart visual mappings.

Requirements:
  - ComfyUI running locally at http://127.0.0.1:8188
  - flux1_icon_factory.json in the same folder as this script
  - pip install websocket-client

Usage:
  python generate_icons_v2.py
  python generate_icons_v2.py german3_supermarket2.json   # specify a file
"""

import json
import uuid
import urllib.request
import websocket
import time
import os
import sys

# ── Config ────────────────────────────────────────────────────────────────────
COMFYUI_HOST  = "127.0.0.1:8000"
WORKFLOW_FILE = "flux1_icon_factory.json"
OUTPUT_DIR    = "icons_output"

# Node IDs from flux1_icon_factory.json
PROMPT_NODE_ID = "4"
SAVE_NODE_ID   = "10"

# Style suffix — change this to switch the visual style for ALL icons at once.
# Current: colorful pastel cartoon (friendly, app-appropriate)
STYLE_SUFFIX = (
    ", flat design icon, soft pastel colors, rounded shapes, thick black outlines, "
    "friendly cartoon style, white background, simple clean illustration, "
    "no text, no letters, centered composition, single object"
)
# ─────────────────────────────────────────────────────────────────────────────


# ── Smart prompt mappings ─────────────────────────────────────────────────────
# For abstract words (verbs, adjectives) we map to a concrete visual object
# or scene that clearly communicates the meaning at icon size.
# Nouns not listed here fall through to the default prompt builder.

PROMPT_OVERRIDES = {
    # ── Verbs ────────────────────────────────────────────────────────────────
    "to pay":               "a hand holding a credit card over a payment terminal",
    "to search/look for":   "a magnifying glass",
    "to weigh":             "a kitchen scale with food on it",
    "to choose/select":     "a hand pointing at one item from a row of three products",
    "to pack":              "hands placing items into a shopping bag",
    "to need":              "an empty shopping basket with a question mark above it",
    "to exchange":          "two arrows forming a circular exchange symbol with a product",
    "to recommend":         "a five star rating with a thumbs up",
    "to save (money)":      "a piggy bank with a coin being dropped in",

    # ── Adjectives ───────────────────────────────────────────────────────────
    "fresh":                "a bright green leaf with water droplets",
    "expensive":            "a price tag with a high number and upward arrow",
    "cheap":                "a price tag with a low number and downward arrow",
    "favorable/low-priced": "a shopping tag with a percentage discount symbol",
    "frozen":               "a snowflake over a food package",
    "organic":              "a green leaf with a certification badge",
    "ripe":                 "a perfectly red round apple",
    "durable/long-lasting": "a calendar with a long date range and a checkmark",
    "empty":                "an empty glass jar with nothing inside",
    "full":                 "a glass jar completely filled with contents",

    # ── Specialty nouns (concrete enough but benefit from better description) ─
    "detergent":            "a laundry detergent bottle with bubbles",
    "frozen food":          "a frozen meal package with snowflake symbol",
    "dairy products":       "a milk bottle and a block of cheese side by side",
    "bakery":               "a loaf of bread with steam rising from it",
    "pastry":               "a croissant on a small plate",
    "spices":               "a row of small spice jars with colorful contents",
    "cleaning supplies":    "a spray bottle and a sponge",
    "toilet paper":         "a roll of toilet paper",
    "soap":                 "a bar of soap with bubbles",

    # ── Transactional nouns ──────────────────────────────────────────────────
    "shopping list":        "a notepad with a handwritten checklist and a pen",
    "expiration date":      "a food package with a best before date stamp",
    "ingredient":           "an egg a carrot and flour arranged together",
    "packaging":            "a cardboard box being wrapped and sealed",
    "change (return money)": "a hand receiving coins as change",
    "bottle deposit":       "an empty glass bottle with a deposit return arrow",
    "voucher/coupon":       "a coupon ticket with scissors and a dashed border",
    "quantity":             "three identical product boxes stacked together",
    "total amount":         "a receipt with a total sum at the bottom",
}
# ─────────────────────────────────────────────────────────────────────────────


def build_prompt(english_word: str) -> str:
    """Build icon prompt — uses override if available, otherwise generic."""
    visual = PROMPT_OVERRIDES.get(english_word)
    if visual:
        return f"a minimalist icon of {visual}{STYLE_SUFFIX}"
    # Fallback for plain nouns not in the override map
    return f"a minimalist icon of {english_word}{STYLE_SUFFIX}"


def load_vocab(path: str) -> list[dict]:
    """Flatten all sections of any vocabulary JSON into a single list."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = []
    # Support both single-lesson and multi-lesson JSON structures
    root = data
    if len(data) == 1:
        root = next(iter(data.values()))

    for section_key, words in root.items():
        if isinstance(words, list):
            for word in words:
                items.append({
                    "english": word["english"],
                    "german":  word["german"],
                    "grammar": word.get("grammar", ""),
                    "section": section_key,
                })
    return items


def queue_prompt(workflow: dict, client_id: str) -> str:
    payload = json.dumps({"prompt": workflow, "client_id": client_id}).encode()
    req = urllib.request.Request(
        f"http://{COMFYUI_HOST}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())["prompt_id"]


def wait_for_completion(ws: websocket.WebSocket, prompt_id: str) -> None:
    while True:
        msg = json.loads(ws.recv())
        if msg.get("type") == "executing":
            data = msg.get("data", {})
            if data.get("node") is None and data.get("prompt_id") == prompt_id:
                break


def convert_ui_to_api_format(raw: dict) -> dict:
    """Convert ComfyUI UI workflow format to API format if needed."""
    if "nodes" not in raw:
        return raw  # already API format

    workflow = {}
    for node in raw["nodes"]:
        node_id   = str(node["id"])
        node_type = node.get("type", "")
        widget_vals = node.get("widgets_values", [])
        inputs = {}

        if node_type == "CLIPTextEncode":
            inputs["text"] = widget_vals[0] if widget_vals else ""
        elif node_type == "UNETLoader":
            inputs["unet_name"]    = widget_vals[0] if widget_vals else ""
            inputs["weight_dtype"] = widget_vals[1] if len(widget_vals) > 1 else "fp8_e4m3fn"
        elif node_type == "DualCLIPLoader":
            inputs["clip_name1"] = widget_vals[0] if widget_vals else ""
            inputs["clip_name2"] = widget_vals[1] if len(widget_vals) > 1 else ""
            inputs["type"]       = widget_vals[2] if len(widget_vals) > 2 else "flux"
        elif node_type == "VAELoader":
            inputs["vae_name"] = widget_vals[0] if widget_vals else ""
        elif node_type == "EmptySD3LatentImage":
            inputs["width"]      = widget_vals[0] if widget_vals else 1024
            inputs["height"]     = widget_vals[1] if len(widget_vals) > 1 else 1024
            inputs["batch_size"] = widget_vals[2] if len(widget_vals) > 2 else 1
        elif node_type == "KSampler":
            keys = ["seed", "control_after_generate", "steps", "cfg",
                    "sampler_name", "scheduler", "denoise"]
            for k, v in zip(keys, widget_vals):
                inputs[k] = v
        elif node_type == "FluxGuidance":
            inputs["guidance"] = widget_vals[0] if widget_vals else 3.5
        elif node_type == "SaveImage":
            inputs["filename_prefix"] = widget_vals[0] if widget_vals else "icon"

        for inp in node.get("inputs", []):
            if inp.get("link") is not None:
                link_id = inp["link"]
                for link in raw.get("links", []):
                    if link[0] == link_id:
                        inputs[inp["name"]] = [str(link[1]), link[2]]
                        break

        workflow[node_id] = {"class_type": node_type, "inputs": inputs}

    return workflow


def generate_icons(vocab: list[dict], workflow_template: dict) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    client_id = str(uuid.uuid4())

    ws = websocket.WebSocket()
    ws.connect(f"ws://{COMFYUI_HOST}/ws?clientId={client_id}")
    print(f"Connected to ComfyUI  •  generating {len(vocab)} icons\n")

    # Print a preview of all prompts before starting
    print("── Prompt preview ───────────────────────────────────────")
    for item in vocab:
        print(f"  {item['english']:30s} → {build_prompt(item['english'])[:70]}…")
    print("─────────────────────────────────────────────────────────\n")

    for i, item in enumerate(vocab, 1):
        english = item["english"]
        german  = item["german"]
        grammar = item.get("grammar", "")
        safe_name = english.replace(" ", "_").replace("/", "-").replace("(", "").replace(")", "")
        filename_prefix = f"{i:02d}_{safe_name}_{german}"

        prompt_text = build_prompt(english)

        wf = json.loads(json.dumps(workflow_template))
        wf[PROMPT_NODE_ID]["inputs"]["text"] = prompt_text
        wf[SAVE_NODE_ID]["inputs"]["filename_prefix"] = filename_prefix

        tag = f"[{grammar}]" if grammar else ""
        print(f"[{i:02d}/{len(vocab)}] {english:30s} {tag:6s} | {german}")
        print(f"          prompt: {prompt_text[:80]}…")

        try:
            prompt_id = queue_prompt(wf, client_id)
            wait_for_completion(ws, prompt_id)
            print(f"          ✓ done\n")
        except Exception as e:
            print(f"          ✗ ERROR: {e}\n")

        time.sleep(0.5)

    ws.close()
    print(f"All done! Icons saved to your ComfyUI output folder.")


def main():
    vocab_file = sys.argv[1] if len(sys.argv) > 1 else "german3_supermarket2.json"

    if not os.path.exists(WORKFLOW_FILE):
        print(f"ERROR: '{WORKFLOW_FILE}' not found. Put it in the same folder as this script.")
        return

    if not os.path.exists(vocab_file):
        print(f"ERROR: '{vocab_file}' not found.")
        return

    with open(WORKFLOW_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    workflow = convert_ui_to_api_format(raw)

    vocab = load_vocab(vocab_file)
    print(f"Loaded {len(vocab)} words from {vocab_file}\n")

    generate_icons(vocab, workflow)


if __name__ == "__main__":
    main()
