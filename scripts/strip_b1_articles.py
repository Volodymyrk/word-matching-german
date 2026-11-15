"""Strip articles from German words and 'the ' from English in B1 vocab files."""
import json
import glob
import os

ARTICLE_MAP = {"m": "der ", "f": "die ", "n": "das "}
B1_DIR = os.path.join(os.path.dirname(__file__), "..", "public", "configs", "courses", "Goethe_B1")

def strip_entry(entry):
    german = entry.get("german", "")
    english = entry.get("english", "")

    for article in ("der ", "die ", "das "):
        if german.startswith(article):
            entry["german"] = german[len(article):]
            break

    if english.startswith("the "):
        entry["english"] = english[4:]

    return entry

def process_file(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    changed = 0
    for lesson_key, sections in data.items():
        for section_key, words in sections.items():
            for entry in words:
                before = (entry.get("german"), entry.get("english"))
                strip_entry(entry)
                after = (entry.get("german"), entry.get("english"))
                if before != after:
                    changed += 1

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return changed

total = 0
for path in sorted(glob.glob(os.path.join(B1_DIR, "DE_Goethe_B1_lesson*.json"))):
    n = process_file(path)
    print(f"{os.path.basename(path)}: {n} entries changed")
    total += n

print(f"\nTotal: {total} entries changed across all B1 lessons")
