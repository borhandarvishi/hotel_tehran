#!/usr/bin/env python3
"""Add tehranZone (north/south/east/west/center) to hotel JSON files from coordinates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_INPUT_DIR = Path(__file__).parent / "data" / "Tehran_New"

# Reference point: roughly Enghelab / Valiasr axis (downtown Tehran).
CENTER_LNG = 51.411
CENTER_LAT = 35.701

# ~±2 km box around downtown → "center".
CENTER_LNG_RADIUS = 0.020
CENTER_LAT_RADIUS = 0.020

ZONES = {
    "center": {"fa": "مرکز", "en": "center"},
    "north": {"fa": "شمال", "en": "north"},
    "south": {"fa": "جنوب", "en": "south"},
    "east": {"fa": "شرق", "en": "east"},
    "west": {"fa": "غرب", "en": "west"},
}


def classify_tehran_zone(lng: float, lat: float) -> str:
    """Return one of: center, north, south, east, west."""
    in_center = (
        abs(lng - CENTER_LNG) <= CENTER_LNG_RADIUS
        and abs(lat - CENTER_LAT) <= CENTER_LAT_RADIUS
    )
    if in_center:
        return "center"

    delta_lng = lng - CENTER_LNG
    delta_lat = lat - CENTER_LAT

    if abs(delta_lat) >= abs(delta_lng):
        return "north" if delta_lat > 0 else "south"
    return "east" if delta_lng > 0 else "west"


def build_zone_payload(zone_code: str) -> dict[str, str]:
    labels = ZONES[zone_code]
    return {
        "code": zone_code,
        "fa": labels["fa"],
        "en": labels["en"],
    }


def process_file(path: Path, dry_run: bool) -> tuple[bool, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERR  {path.name}: {exc}", file=sys.stderr)
        return False, None

    hotel = data.get("result", {}).get("hotel")
    if not isinstance(hotel, dict):
        print(f"ERR  {path.name}: missing result.hotel", file=sys.stderr)
        return False, None

    location = hotel.get("location") or {}
    coordinates = location.get("coordinates")
    if not coordinates or len(coordinates) != 2:
        print(f"ERR  {path.name}: missing location.coordinates", file=sys.stderr)
        return False, None

    lng, lat = float(coordinates[0]), float(coordinates[1])
    zone_code = classify_tehran_zone(lng, lat)
    hotel["tehranZone"] = build_zone_payload(zone_code)

    if not dry_run:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    name = hotel.get("name", {}).get("fa", path.stem)
    action = "DRY  " if dry_run else "OK   "
    print(f"{action}{path.name}: {name} -> {hotel['tehranZone']['fa']} ({zone_code})")
    return True, zone_code


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add tehranZone field to hotel JSON files based on coordinates."
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
        help="Report zones without writing files",
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
    zone_counts: dict[str, int] = {code: 0 for code in ZONES}

    for path in json_files:
        ok, zone_code = process_file(path, dry_run=args.dry_run)
        if ok and zone_code:
            succeeded += 1
            zone_counts[zone_code] += 1
        else:
            failed += 1

    print(
        f"\nDone. Files processed: {succeeded}, failed: {failed}\n"
        "Zone distribution:"
    )
    for code, count in zone_counts.items():
        print(f"  {ZONES[code]['fa']} ({code}): {count}")


if __name__ == "__main__":
    main()
