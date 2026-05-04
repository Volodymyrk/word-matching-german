#!/usr/bin/env python3
"""Generate public/configs/index.json from courses/ folder structure.

Run from the project root:
    python3 scripts/generate_index.py

Each course folder under public/configs/courses/ must contain a course.json:
  {
    "id_prefix":  "goethe_a1",          # prepended to lesson number for stable id
    "emoji":      "📖",                 # default emoji for all lessons in this course
    "languages":  ["german", "english"],
    "lessons": {                         # optional per-lesson overrides keyed by filename stem
      "german_1": { "id": "de1", "name": "Lektion 1", "emoji": "👋" }
    }
  }
"""

import json
import os
import re
import sys


CONFIGS_DIR = os.path.join("public", "configs")
COURSES_DIR = os.path.join(CONFIGS_DIR, "courses")
OUTPUT_FILE = os.path.join(CONFIGS_DIR, "index.json")


def natural_key(s):
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r"(\d+)", s)]


def derive_name(key):
    if "_" not in key:
        return key  # already a display name (e.g. "Persönliche Angaben")
    return " ".join(w.capitalize() for w in key.split("_"))


def vocab_files_in(course_path):
    files = [
        f for f in os.listdir(course_path)
        if f.endswith(".json") and f != "course.json"
    ]
    return sorted(files, key=natural_key)


def main():
    if not os.path.isdir(COURSES_DIR):
        sys.exit(f"Error: {COURSES_DIR} not found. Run from the project root.")

    lessons = []

    for course_dir in sorted(os.listdir(COURSES_DIR), key=natural_key):
        course_path = os.path.join(COURSES_DIR, course_dir)
        if not os.path.isdir(course_path):
            continue

        manifest_path = os.path.join(course_path, "course.json")
        if not os.path.exists(manifest_path):
            print(f"  Skipping {course_dir}: no course.json found", file=sys.stderr)
            continue

        with open(manifest_path, encoding="utf-8") as f:
            course = json.load(f)

        overrides    = course.get("lessons", {})
        id_prefix    = course["id_prefix"]
        default_emoji = course.get("emoji", "📚")
        languages    = course["languages"]
        course_id    = course_dir.lower()
        course_name  = course.get("name", course_dir)
        course_emoji = course.get("emoji", "📚")

        files = vocab_files_in(course_path)
        for i, filename in enumerate(files, start=1):
            stem = os.path.splitext(filename)[0]
            rel_path = f"courses/{course_dir}/{filename}"

            with open(os.path.join(course_path, filename), encoding="utf-8") as f:
                vocab = json.load(f)
            top_key = next(iter(vocab))

            ov = overrides.get(stem, {})
            lessons.append({
                "id":           ov.get("id",    f"{id_prefix}_{i}"),
                "name":         ov.get("name",  derive_name(top_key)),
                "emoji":        ov.get("emoji", default_emoji),
                "vocab_file":   rel_path,
                "languages":    languages,
                "course_id":    course_id,
                "course_name":  course_name,
                "course_emoji": course_emoji,
            })

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(lessons, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Generated {OUTPUT_FILE} — {len(lessons)} lessons")


if __name__ == "__main__":
    main()
