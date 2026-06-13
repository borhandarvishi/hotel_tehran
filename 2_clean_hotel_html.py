#!/usr/bin/env python3
"""Strip HTML tags from hotel JSON files while preserving readable text flow."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

DEFAULT_INPUT_DIR = Path(__file__).parent / "Tehran_New"

# Block tags become line breaks so adjacent text does not merge (e.g. </p><p>).
BLOCK_TAGS = (
    "p",
    "div",
    "section",
    "article",
    "header",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "ul",
    "ol",
    "tr",
    "td",
    "th",
    "blockquote",
    "pre",
    "hr",
)
BLOCK_TAG_PATTERN = re.compile(
    rf"<\s*(?:{'|'.join(BLOCK_TAGS)})\b[^>]*>|</\s*(?:{'|'.join(BLOCK_TAGS)})\s*>",
    re.IGNORECASE,
)
BR_TAG_PATTERN = re.compile(r"<\s*br\s*/?\s*>", re.IGNORECASE)
ANY_TAG_PATTERN = re.compile(r"<[^>]+>")
WHITESPACE_PATTERN = re.compile(r"[ \t\u00a0]+")
MULTI_NEWLINE_PATTERN = re.compile(r"\n{3,}")


def strip_html(text: str) -> str:
    """Remove HTML tags and normalize whitespace without breaking word boundaries."""
    if not text:
        return text
    if "<" not in text and "&" not in text:
        return text

    cleaned = html.unescape(text)
    cleaned = BR_TAG_PATTERN.sub("\n", cleaned)
    cleaned = BLOCK_TAG_PATTERN.sub("\n", cleaned)
    cleaned = ANY_TAG_PATTERN.sub("", cleaned)

    lines: list[str] = []
    for raw_line in cleaned.splitlines():
        line = WHITESPACE_PATTERN.sub(" ", raw_line).strip()
        if line:
            lines.append(line)

    cleaned = "\n".join(lines)
    cleaned = MULTI_NEWLINE_PATTERN.sub("\n\n", cleaned)
    return cleaned.strip()


def clean_value(value: object) -> tuple[object, int]:
    """Recursively clean strings inside JSON-like structures."""
    changed = 0

    if isinstance(value, str):
        cleaned = strip_html(value)
        if cleaned != value:
            changed += 1
        return cleaned, changed

    if isinstance(value, list):
        cleaned_list: list[object] = []
        for item in value:
            cleaned_item, item_changed = clean_value(item)
            cleaned_list.append(cleaned_item)
            changed += item_changed
        return cleaned_list, changed

    if isinstance(value, dict):
        cleaned_dict: dict[str, object] = {}
        for key, item in value.items():
            cleaned_item, item_changed = clean_value(item)
            cleaned_dict[key] = cleaned_item
            changed += item_changed
        return cleaned_dict, changed

    return value, changed


def process_file(path: Path, dry_run: bool) -> tuple[bool, int]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERR  {path.name}: {exc}", file=sys.stderr)
        return False, 0

    cleaned_data, changed_fields = clean_value(data)
    if changed_fields == 0:
        print(f"SKIP {path.name}: no HTML found")
        return True, 0

    if not dry_run:
        path.write_text(
            json.dumps(cleaned_data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    action = "DRY  " if dry_run else "OK   "
    print(f"{action}{path.name}: cleaned {changed_fields} string field(s)")
    return True, changed_fields


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remove HTML tags from hotel JSON files in Tehran_New."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Directory containing hotel JSON files (default: {DEFAULT_INPUT_DIR.name}/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report changes without writing files",
    )
    args = parser.parse_args()

    input_dir = args.input_dir.resolve()
    if not input_dir.is_dir():
        raise SystemExit(f"Input folder not found: {input_dir}")

    json_files = sorted(input_dir.glob("*.json"))
    if not json_files:
        raise SystemExit(f"No JSON files found in {input_dir}")

    print(f"Processing {len(json_files)} file(s) in {input_dir.name}/")
    if args.dry_run:
        print("Dry run mode: files will not be modified\n")

    succeeded = 0
    failed = 0
    total_changed_fields = 0

    for path in json_files:
        ok, changed_fields = process_file(path, dry_run=args.dry_run)
        if ok:
            succeeded += 1
            total_changed_fields += changed_fields
        else:
            failed += 1

    print(
        f"\nDone. Files processed: {succeeded}, failed: {failed}, "
        f"fields cleaned: {total_changed_fields}"
    )


if __name__ == "__main__":
    main()
