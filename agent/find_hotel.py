import json
import os
from typing import Any

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from agent.chroma_client import get_chroma_collection
from agent.config import (
    ENV_FILE,
    FIELD_SEARCH_MAP,
    MAX_RECOMMENDATIONS,
    TOP_K_PER_FIELD,
    ZONE_OPTIONS,
)
from agent.hotel_data import get_candidate_rows, get_hotels_by_ids
from agent.ranker_prompt import RANKER_SYSTEM_PROMPT
from agent.schemas import FindHotelInput, RankHotelsOutput


def _build_metadata_filter(
    location: str | None,
    star: int | None,
) -> dict[str, Any] | None:
    clauses: list[dict[str, Any]] = []
    if location and location in ZONE_OPTIONS:
        clauses.append({"tehran_zone": location})
    if star is not None:
        clauses.append({"star": star})

    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def _merge_where(field: str, base_filter: dict[str, Any] | None) -> dict[str, Any]:
    field_clause = {"field": field}
    if base_filter is None:
        return field_clause
    return {"$and": [base_filter, field_clause]}


def _vector_search(
    query_text: str,
    chroma_field: str,
    base_filter: dict[str, Any] | None,
    n_results: int,
) -> list[str]:
    collection = get_chroma_collection()
    where = _merge_where(chroma_field, base_filter)
    try:
        result = collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where,
            include=["metadatas"],
        )
    except Exception:
        return []

    ids: list[str] = []
    metas = result.get("metadatas") or [[]]
    for meta in metas[0]:
        hid = meta.get("hotel_id")
        if hid:
            ids.append(hid)
    return ids


def _rank_candidates(
    user_summary: str,
    candidates: list[dict],
) -> RankHotelsOutput:
    load_dotenv(ENV_FILE)
    model = os.getenv("GENERATION_MODEL", "gpt-4o")
    llm = ChatOpenAI(model=model, temperature=0).with_structured_output(RankHotelsOutput)

    payload = {
        "user_request": user_summary,
        "candidates": candidates,
    }
    return llm.invoke(
        [
            {"role": "system", "content": RANKER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False),
            },
        ]
    )


def find_hotel(params: FindHotelInput) -> dict[str, Any]:
    """
    Hybrid hotel search: metadata filter + per-field vector search + LLM rerank.
    Returns selected hotels as JSON-friendly dict for the agent.
    """
    base_filter = _build_metadata_filter(params.location, params.star)

    search_pairs: list[tuple[str, str]] = []
    if params.hotel_name and params.hotel_name.strip():
        search_pairs.append(("hotel_name", params.hotel_name.strip()))
    if params.facilities_preferences and params.facilities_preferences.strip():
        search_pairs.append(("facilities_preferences", params.facilities_preferences.strip()))
    if params.address and params.address.strip():
        search_pairs.append(("address", params.address.strip()))
    if params.general_preferences and params.general_preferences.strip():
        search_pairs.append(("general_preferences", params.general_preferences.strip()))

    if not search_pairs and base_filter is None:
        return {
            "success": False,
            "message": "حداقل یک ترجیح (منطقه، ستاره، امکانات، آدرس یا توضیح کلی) لازم است.",
            "hotels": [],
        }

    retrieved_ids: list[str] = []
    for param_key, query_text in search_pairs:
        chroma_field = FIELD_SEARCH_MAP[param_key]
        retrieved_ids.extend(
            _vector_search(query_text, chroma_field, base_filter, TOP_K_PER_FIELD)
        )

    # If only metadata filters and no text queries, fetch by filter
    if not search_pairs and base_filter is not None:
        collection = get_chroma_collection()
        try:
            batch = collection.get(where=base_filter, include=["metadatas"], limit=20)
            for meta in batch.get("metadatas") or []:
                hid = meta.get("hotel_id")
                if hid:
                    retrieved_ids.append(hid)
        except Exception:
            pass

    unique_ids = list(dict.fromkeys(retrieved_ids))
    if not unique_ids:
        return {
            "success": False,
            "message": "هتلی با این شرایط در دیتابیس پیدا نشد. لطفاً فیلترها را باز کنید.",
            "hotels": [],
        }

    candidates = get_candidate_rows(unique_ids)
    if not candidates:
        return {
            "success": False,
            "message": "هتل‌های پیدا شده در فایل audit موجود نیستند.",
            "hotels": [],
        }

    user_summary = json.dumps(params.model_dump(exclude_none=True), ensure_ascii=False)
    ranked = _rank_candidates(user_summary, candidates)
    selected_ids = ranked.hotel_ids[:MAX_RECOMMENDATIONS]

    hotels = get_hotels_by_ids(selected_ids)
    return {
        "success": True,
        "message": ranked.reasoning,
        "selected_hotel_ids": selected_ids,
        "candidate_count": len(unique_ids),
        "hotels": hotels,
    }


def find_hotel_tool(**kwargs: Any) -> str:
    """LangChain tool wrapper returning JSON string."""
    params = FindHotelInput(**kwargs)
    return json.dumps(find_hotel(params), ensure_ascii=False)
