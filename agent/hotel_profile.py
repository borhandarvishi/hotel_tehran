from functools import lru_cache
from pathlib import Path
from typing import Any

from agent.config import DATA_DIR

HOTEL_JSON_DIR = DATA_DIR / "Tehran_New"


def _get_nested(data: dict, keys: tuple[str, ...], default: str = "") -> str:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    if isinstance(current, str):
        return current.strip()
    return default if current is None else str(current)


def _primary_image_url(hotel: dict) -> str | None:
    images = hotel.get("images") or []
    for img in images:
        if isinstance(img, dict) and img.get("isPrimary") and img.get("url"):
            return img["url"]
    for img in images:
        if isinstance(img, dict) and img.get("url"):
            return img["url"]
    image = hotel.get("image") or {}
    if isinstance(image, dict) and image.get("sourceUrl"):
        return image["sourceUrl"]
    return None


@lru_cache(maxsize=256)
def load_hotel_raw(hotel_id: str) -> dict | None:
    path = HOTEL_JSON_DIR / f"{hotel_id}.json"
    if not path.exists():
        return None
    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    hotel = payload.get("result", {}).get("hotel")
    return hotel if isinstance(hotel, dict) else None


def get_hotel_profile(hotel_id: str) -> dict[str, Any] | None:
    hotel = load_hotel_raw(hotel_id)
    if not hotel:
        return None

    score = hotel.get("score") or {}
    popular = hotel.get("popularFacilities") or []
    facility_names = [
        (f.get("name") or {}).get("fa", "")
        for f in popular
        if isinstance(f, dict)
    ]
    facility_names = [n for n in facility_names if n][:8]

    description = _get_nested(hotel, ("description", "fa"))
    if len(description) > 1200:
        description = description[:1200] + "…"

    return {
        "hotel_id": hotel_id,
        "name": _get_nested(hotel, ("title", "fa")) or _get_nested(hotel, ("name", "fa")),
        "star": hotel.get("star"),
        "tehran_zone": _get_nested(hotel, ("tehranZone", "fa")),
        "address": hotel.get("address", ""),
        "description": description,
        "facilities_aggregate": hotel.get("facilitiesAggregate", ""),
        "popular_facilities": facility_names,
        "checkin": hotel.get("checkinTime", ""),
        "checkout": hotel.get("checkoutTime", ""),
        "score": score.get("score"),
        "review_count": score.get("count"),
        "link": hotel.get("link", ""),
        "image_url": _primary_image_url(hotel),
        "gallery_urls": [
            img.get("url")
            for img in (hotel.get("images") or [])
            if isinstance(img, dict) and img.get("url")
        ][:6],
    }
