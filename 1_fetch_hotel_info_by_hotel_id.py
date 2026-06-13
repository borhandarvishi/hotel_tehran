#!/usr/bin/env python3
"""Fetch hotel info from Alibaba API for each ID in the Tehran folder."""

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://ws.alibaba.ir/api/v1/hotel/general/info"
INPUT_DIR = Path(__file__).parent / "Tehran"
OUTPUT_DIR = Path(__file__).parent / "Tehran_New"
REQUEST_DELAY_SECONDS = 0.5


def get_hotel_ids(source_dir: Path) -> list[str]:
    ids = []
    for path in sorted(source_dir.glob("*.json")):
        hotel_id = path.stem.strip()
        if hotel_id:
            ids.append(hotel_id)
    return ids


def fetch_hotel_info(hotel_id: str) -> dict:
    payload = json.dumps({"hotelId": hotel_id}).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    if not INPUT_DIR.is_dir():
        raise SystemExit(f"Input folder not found: {INPUT_DIR}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    hotel_ids = get_hotel_ids(INPUT_DIR)

    if not hotel_ids:
        raise SystemExit(f"No JSON files found in {INPUT_DIR}")

    print(f"Found {len(hotel_ids)} hotel IDs in {INPUT_DIR.name}/")
    print(f"Saving responses to {OUTPUT_DIR.name}/\n")

    succeeded = 0
    failed = 0

    for index, hotel_id in enumerate(hotel_ids, start=1):
        output_path = OUTPUT_DIR / f"{hotel_id}.json"

        try:
            data = fetch_hotel_info(hotel_id)
            output_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            succeeded += 1
            print(f"[{index}/{len(hotel_ids)}] OK  {hotel_id}")
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
            failed += 1
            print(f"[{index}/{len(hotel_ids)}] ERR {hotel_id}: {exc}")

        if index < len(hotel_ids):
            time.sleep(REQUEST_DELAY_SECONDS)

    print(f"\nDone. Success: {succeeded}, Failed: {failed}")


if __name__ == "__main__":
    main()
