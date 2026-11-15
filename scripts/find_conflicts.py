#!/usr/bin/env python3
"""
Read-only: list candidate `conflicts` pairs and `hard_icon` words for every lesson
file, to be reviewed by hand before adding them to the lesson JSONs.

Usage (from project root):
    uv run scripts/find_conflicts.py [--prompts PATH] [--out REPORT.md]
"""

import argparse
import json
import re
from itertools import combinations
from pathlib import Path

COURSES_DIR = Path("public/configs/courses")
DEFAULT_PROMPTS = Path(r"C:\WS\vocabula_asset_generator\output\prompts_history.json")

STOP = set("""a an the of with and or in on at to into onto over under from by for its
his her their one two small large big white black red blue green yellow showing shown
next beside view top side front simple flat icon single""".split())

ABSTRACT = re.compile(
    r"\b(arrow|arrows|symbol|checkmark|check mark|question mark|exclamation|gesture|sign|"
    r"speech bubble|thought bubble|silhouette|abstract|scale|equals|plus|minus|cross|"
    r"circle|graph|chart|clock|calendar|thumbs)\b",
    re.I,
)


def to_stem(german: str) -> str:
    s = german.lower()
    for umlaut, rep in [("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")]:
        s = s.replace(umlaut, rep)
    s = s.replace(" ", "_")
    s = re.sub(r"[^\w-]", "", s)
    s = re.sub(r"_+", "_", s)
    return s.strip("_")


def norm_en(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"^to\s+", "", s)
    s = re.sub(r"\(.*?\)", "", s)
    return s.strip()


def tokens(prompt: str) -> set[str]:
    return {t for t in re.findall(r"[a-z]+", prompt.lower()) if t not in STOP and len(t) > 2}


def iter_words(data):
    for lk, lv in data.items():
        for sk, words in lv.items():
            for w in words:
                yield f"{lk}/{sk}", w


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", type=Path, default=DEFAULT_PROMPTS)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    prompts = json.loads(args.prompts.read_text(encoding="utf-8")) if args.prompts.exists() else {}
    lines: list[str] = []

    for path in sorted(COURSES_DIR.glob("*/*.json")):
        if path.name == "course.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        words = [(sec, w) for sec, w in iter_words(data) if w.get("german")]
        conflicts, hard = [], []

        for (s1, a), (s2, b) in combinations(words, 2):
            ga, gb = a["german"], b["german"]
            sa, sb = to_stem(ga), to_stem(gb)
            ea, eb = norm_en(a.get("english", "")), norm_en(b.get("english", ""))
            reasons = []
            if ga.lower() == gb.lower() or ea == eb:
                reasons.append("same text")
            short, long_ = sorted((sa, sb), key=len)
            if len(short) >= 4 and long_.startswith(short) and len(long_) - len(short) <= 4:
                reasons.append("stem prefix")
            if ea and eb and ea != eb and min(len(ea), len(eb)) >= 4 and (
                re.search(rf"\b{re.escape(ea)}\b", eb) or re.search(rf"\b{re.escape(eb)}\b", ea)
            ):
                reasons.append("english contains")
            pa, pb = prompts.get(sa), prompts.get(sb)
            if pa and pb:
                ta, tb = tokens(pa), tokens(pb)
                if ta and tb:
                    j = len(ta & tb) / len(ta | tb)
                    if j >= 0.3:
                        reasons.append(f"prompt overlap {j:.2f} [{', '.join(sorted(ta & tb))}]")
            if reasons:
                conflicts.append(f"- {ga} ({a.get('english')}) <-> {gb} ({b.get('english')})"
                                 f"{'' if s1 == s2 else '  [diff section]'}: {'; '.join(reasons)}")

        for sec, w in words:
            if not w.get("icon"):
                continue
            p = prompts.get(to_stem(w["german"]))
            if p and ABSTRACT.search(p):
                hard.append(f"- {w['german']} ({w.get('english')}) [{w.get('grammar','')}]: {p}")

        if conflicts or hard:
            lines.append(f"\n## {path.parent.name}/{path.name}")
            if conflicts:
                lines.append("### conflict candidates")
                lines += conflicts
            if hard:
                lines.append("### hard_icon candidates")
                lines += hard

    report = "\n".join(lines) + "\n"
    if args.out:
        args.out.write_text(report, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(report)


if __name__ == "__main__":
    main()
