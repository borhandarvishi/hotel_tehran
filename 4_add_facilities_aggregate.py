#!/usr/bin/env python3
"""Add aggregated Persian facility titles to each hotel JSON file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_INPUT_DIR = Path(__file__).parent / "data" / "Tehran_New"
FIELD_NAME = "facilitiesAggregate"
LEGACY_FIELD_NAMES = ("تجمیع فسیلیتی‌ها", "تجمیع فسیلیتی\u200cها")
SEPARATOR = "، "


def collect_facility_names(hotel: dict) -> list[str]:
    """Collect unique Persian facility titles, preserving first-seen order."""
    seen: set[str] = set()
    names: list[str] = []

    def add_name(raw_name: object) -> None:
        if not isinstance(raw_name, str):
            return
        name = raw_name.strip()
        if not name or name in seen:
            return
        seen.add(name)
        names.append(name)

    for facility in hotel.get("facilities") or []:
        if isinstance(facility, dict):
            add_name((facility.get("name") or {}).get("fa"))

    for facility in hotel.get("popularFacilities") or []:
        if isinstance(facility, dict):
            add_name((facility.get("name") or {}).get("fa"))

    for group in hotel.get("facilityGroups") or []:
        if not isinstance(group, dict):
            continue
        for facility in group.get("facilities") or []:
            if isinstance(facility, dict):
                add_name((facility.get("name") or {}).get("fa"))

    return names


def remove_legacy_fields(hotel: dict) -> None:
    for key in list(hotel.keys()):
        if key in LEGACY_FIELD_NAMES or (
            "تجمیع" in key and "فسیلیتی" in key
        ):
            del hotel[key]


def process_file(path: Path, dry_run: bool) -> tuple[bool, int]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERR  {path.name}: {exc}", file=sys.stderr)
        return False, 0

    hotel = data.get("result", {}).get("hotel")
    if not isinstance(hotel, dict):
        print(f"ERR  {path.name}: missing result.hotel", file=sys.stderr)
        return False, 0

    names = collect_facility_names(hotel)
    remove_legacy_fields(hotel)
    hotel[FIELD_NAME] = SEPARATOR.join(names)

    if not dry_run:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    hotel_name = hotel.get("name", {}).get("fa", path.stem)
    action = "DRY  " if dry_run else "OK   "
    print(f"{action}{path.name}: {hotel_name} -> {len(names)} facility title(s)")
    return True, len(names)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add comma-separated Persian facility titles to hotel JSON files."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Directory containing hotel JSON files (default: {DEFAULT_INPUT_DIR})",
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
    print(f'Field name: "{FIELD_NAME}"')
    if args.dry_run:
        print("Dry run mode: files will not be modified\n")

    succeeded = 0
    failed = 0
    empty_count = 0
    total_titles = 0

    for path in json_files:
        ok, count = process_file(path, dry_run=args.dry_run)
        if ok:
            succeeded += 1
            total_titles += count
            if count == 0:
                empty_count += 1
        else:
            failed += 1

    avg = total_titles / succeeded if succeeded else 0
    print(
        f"\nDone. Files processed: {succeeded}, failed: {failed}, "
        f"empty: {empty_count}, avg titles/file: {avg:.1f}"
    )


if __name__ == "__main__":
    main()
