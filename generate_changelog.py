"""
Generates CHANGELOG.md from version.py's CHANGELOG list -- the single source
of truth stays version.py (what the app itself reads); this just produces a
human-readable file that doesn't require running the app to check.

Run this after every version bump. Safe to run anytime -- only writes
CHANGELOG.md, never touches the database or any other file.

Usage: python generate_changelog.py
"""
import os
from version import CHANGELOG, APP_VERSION

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(BASE_DIR, "CHANGELOG.md")


def generate():
    lines = ["# ADS OS Changelog", "", f"Current version: **{APP_VERSION}**", ""]

    for version, notes in reversed(CHANGELOG):
        lines.append(f"## {version}")
        lines.append("")
        # Split on ". " roughly into bullet points for readability, since
        # entries in version.py are written as flowing paragraphs, not
        # pre-formatted bullet lists.
        lines.append(notes)
        lines.append("")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Generated {OUTPUT_PATH} with {len(CHANGELOG)} version entries.")


if __name__ == "__main__":
    generate()
