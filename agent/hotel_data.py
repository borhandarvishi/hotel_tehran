from functools import lru_cache
from pathlib import Path

import pandas as pd

from agent.config import AUDIT_CSV_PATH


@lru_cache(maxsize=1)
def load_hotels_df() -> pd.DataFrame:
    if not AUDIT_CSV_PATH.exists():
        raise FileNotFoundError(f"Audit CSV not found: {AUDIT_CSV_PATH}")
    return pd.read_csv(AUDIT_CSV_PATH, encoding="utf-8-sig", dtype=str).fillna("")


def get_hotels_by_ids(hotel_ids: list[str]) -> list[dict]:
    df = load_hotels_df()
    rows: list[dict] = []
    for hid in hotel_ids:
        match = df[df["hotel_id"] == hid]
        if not match.empty:
            rows.append(match.iloc[0].to_dict())
    return rows


def get_candidate_rows(hotel_ids: list[str]) -> list[dict]:
    """Slim candidate payload for ranker LLM."""
    candidates = []
    for row in get_hotels_by_ids(hotel_ids):
        candidates.append(
            {
                "hotel_id": row["hotel_id"],
                "title_fa": row.get("title_fa", ""),
                "star": row.get("star", ""),
                "tehran_zone": row.get("tehran_zone", ""),
                "address": row.get("address", ""),
                "facilitiesAggregate": row.get("facilitiesAggregate", ""),
                "description_preview": (row.get("description_fa") or "")[:400],
            }
        )
    return candidates
