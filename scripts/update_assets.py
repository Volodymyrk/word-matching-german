#!/usr/bin/env python3
"""
Scan course lesson JSON files and add/update icon fields based on available assets.
Logs missing icons and audio files to stdout.

Usage (from project root):
    uv run scripts/update_assets.py
"""

import json
import os
import re
import sys
from pathlib import Path

COURSES_DIR = Path("public/configs/courses")
ICONS_DIR   = Path("public/icons")
AUDIO_DIR   = Path("public/audio")


def to_stem(german: str) -> str:
    """Derive asset filename stem from a German word (mirrors normalize_german in asset generator)."""
    s = german.lower()
    for umlaut, rep in [("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")]:
        s = s.replace(umlaut, rep)
    s = s.replace(" ", "_")
    s = re.sub(r"[^\w-]", "", s)
    s = re.sub(r"_+", "_", s)
    return s.strip("_")


def pick(prompt: str, options: list[str]) -> str | None:
    """Prompt user to pick from a numbered list. Returns chosen item or None to quit."""
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    while True:
        raw = input("Enter number (or 0 to quit): ").strip()
        if raw == "0":
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print("  Invalid — try again.")


def process_lesson(lesson_path: Path) -> None:
    with open(lesson_path, encoding="utf-8") as f:
        data = json.load(f)

    changed = 0
    icons_found = 0
    missing_icons: list[str] = []
    missing_audio: list[str] = []

    for sections in data.values():
        for words in sections.values():
            for word in words:
                german = word.get("german", "").strip()
                if not german:
                    continue

                stem = to_stem(german)
                icon_path  = ICONS_DIR / f"{stem}.webp"
                audio_path = AUDIO_DIR / f"{stem}.mp3"

                if icon_path.exists():
                    icons_found += 1
                    new_val = f"{stem}.webp"
                    if word.get("icon") != new_val:
                        word["icon"] = new_val
                        changed += 1
                else:
                    missing_icons.append(f"  MISSING icon:  {stem}.webp  ({german})")

                if not audio_path.exists():
                    missing_audio.append(f"  MISSING audio: {stem}.mp3   ({german})")

    if icons_found == 0:
        print(f"  No changes — {lesson_path.name}. No icons for lesson found")
        return

    if changed:
        with open(lesson_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"  Written {lesson_path.name} — {changed} field(s) updated")
    else:
        print(f"  No changes — {lesson_path.name}")

    for line in missing_icons + missing_audio:
        print(line)


def main() -> None:
    if not COURSES_DIR.is_dir():
        sys.exit(f"Error: {COURSES_DIR} not found. Run from the project root.")

    courses = sorted(d for d in os.listdir(COURSES_DIR) if (COURSES_DIR / d).is_dir())
    if not courses:
        sys.exit("No course directories found.")

    course_name = pick("Select course:", courses)
    if not course_name:
        return

    course_path  = COURSES_DIR / course_name
    lesson_files = sorted(
        f for f in os.listdir(course_path)
        if f.endswith(".json") and f != "course.json"
    )
    if not lesson_files:
        sys.exit(f"No lesson files found in {course_path}.")

    ALL = "[All lessons]"
    choice = pick("Select lesson:", [ALL] + lesson_files)
    if not choice:
        return

    targets = lesson_files if choice == ALL else [choice]

    print()
    for filename in targets:
        print(f"Processing: {filename}")
        process_lesson(course_path / filename)
        print()


if __name__ == "__main__":
    main()
