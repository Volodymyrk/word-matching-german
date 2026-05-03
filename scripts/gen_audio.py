#!/usr/bin/env python3
"""
Pre-generate German pronunciation MP3s using edge-tts (de-DE-KatjaNeural).
Reads german_3.json, writes public/audio/de3_XX.mp3 for every entry.

Usage (from project root):
    uv run --with edge-tts scripts/gen_audio.py
"""

import asyncio
import json
import os
from pathlib import Path

import edge_tts

VOICE      = "de-DE-KatjaNeural"
INPUT_FILE = "public/configs/german_3.json"
OUTPUT_DIR = "public/audio"

ARTICLE = {"m": "der", "f": "die", "n": "das"}


def spoken_text(word: dict) -> str:
    """Return the text to speak: article + German word for nouns, bare word otherwise."""
    german  = word["german"]
    article = ARTICLE.get(word.get("grammar", ""), "")
    return f"{article} {german}" if article else german


async def generate_one(text: str, path: str) -> None:
    await edge_tts.Communicate(text, VOICE).save(path)


async def main() -> None:
    with open(INPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    entries = [
        word
        for lesson in data.values()
        for section in lesson.values()
        for word in section
        if word.get("icon")
    ]

    print(f"Generating {len(entries)} files into {OUTPUT_DIR}/")

    for word in entries:
        stem = Path(word["icon"]).stem          # e.g. "de3_01"
        out  = f"{OUTPUT_DIR}/{stem}.mp3"
        text = spoken_text(word)
        print(f"  {stem}.mp3  ←  {text!r}")
        await generate_one(text, out)

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
