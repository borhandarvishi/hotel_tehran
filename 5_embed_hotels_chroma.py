#!/usr/bin/env python3
"""Embed Tehran hotel JSON files into ChromaDB (single collection, one row per field)."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent
ENV_FILE = PROJECT_ROOT / ".env"
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "Tehran_New"
DEFAULT_CHROMA_DIR = PROJECT_ROOT / "data" / "chroma_db"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "chroma"
CHECKPOINT_FILE = DEFAULT_OUTPUT_DIR / "checkpoint.json"
AUDIT_JSON_FILE = DEFAULT_OUTPUT_DIR / "embedding_audit.json"
AUDIT_CSV_FILE = DEFAULT_OUTPUT_DIR / "embedding_audit.csv"

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-large"
COLLECTION_NAME = "tehran_hotels"
EMBEDDING_MODEL = DEFAULT_EMBEDDING_MODEL

EMBED_FIELDS = {
    "description_fa": ("description", "fa"),
    "facilitiesAggregate": ("facilitiesAggregate",),
    "address": ("address",),
    "title_fa": ("title", "fa"),
}

# Audit CSV column order (matches user field list 1–7).
AUDIT_CSV_COLUMNS = [
    "description_fa",
    "description_fa_embedded",
    "facilitiesAggregate",
    "facilitiesAggregate_embedded",
    "tehran_zone",
    "address",
    "address_embedded",
    "title_fa",
    "title_fa_embedded",
    "star",
    "hotel_id",
]


def load_settings(dry_run: bool) -> str:
    """Load OPENAI_API_KEY and EMBEDDING_MODEL from .env."""
    global EMBEDDING_MODEL

    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
    else:
        load_dotenv()

    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL).strip()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()

    if not dry_run and not api_key:
        raise SystemExit(
            f"OPENAI_API_KEY not found. Set it in {ENV_FILE} or your environment."
        )

    return EMBEDDING_MODEL


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_chroma_id(hotel_id: str, field_name: str) -> str:
    return f"{hotel_id}::{field_name}"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_checkpoint() -> dict[str, Any]:
    if not CHECKPOINT_FILE.exists():
        return {
            "completed_hotel_ids": [],
            "last_processed_hotel_id": None,
            "embedding_model": EMBEDDING_MODEL,
            "collection_name": COLLECTION_NAME,
            "collection_layout": "single",
            "updated_at": None,
        }
    return load_json(CHECKPOINT_FILE)


def save_checkpoint(checkpoint: dict[str, Any]) -> None:
    checkpoint["updated_at"] = utc_now_iso()
    save_json(CHECKPOINT_FILE, checkpoint)


def load_audit_records() -> list[dict[str, Any]]:
    if not AUDIT_JSON_FILE.exists():
        return []
    data = load_json(AUDIT_JSON_FILE)
    if isinstance(data, list):
        return data
    return data.get("hotels", [])


def save_audit_records(records: list[dict[str, Any]]) -> None:
    save_json(
        AUDIT_JSON_FILE,
        {
            "embedding_model": EMBEDDING_MODEL,
            "collection_name": COLLECTION_NAME,
            "collection_layout": "single",
            "row_id_format": "{hotel_id}::{field_name}",
            "embed_fields": list(EMBED_FIELDS.keys()),
            "metadata_fields": ["hotel_id", "star", "tehran_zone", "field"],
            "updated_at": utc_now_iso(),
            "hotel_count": len(records),
            "hotels": records,
        },
    )
    write_audit_csv(records)


def sanitize_csv_cell(text: str) -> str:
    """One physical CSV row per hotel: flatten newlines and extra whitespace."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def write_audit_csv(records: list[dict[str, Any]]) -> None:
    AUDIT_CSV_FILE.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_CSV_FILE.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=AUDIT_CSV_COLUMNS,
            quoting=csv.QUOTE_MINIMAL,
            lineterminator="\n",
        )
        writer.writeheader()
        for record in records:
            embedded = record["embedded"]
            meta = record["metadata_only"]
            row = {
                "description_fa": sanitize_csv_cell(
                    embedded["description_fa"].get("text", "")
                    if embedded["description_fa"].get("embedded")
                    else ""
                ),
                "description_fa_embedded": embedded["description_fa"]["embedded"],
                "facilitiesAggregate": sanitize_csv_cell(
                    embedded["facilitiesAggregate"].get("text", "")
                    if embedded["facilitiesAggregate"].get("embedded")
                    else ""
                ),
                "facilitiesAggregate_embedded": embedded["facilitiesAggregate"]["embedded"],
                "tehran_zone": sanitize_csv_cell(meta["tehran_zone"]),
                "address": sanitize_csv_cell(
                    embedded["address"].get("text", "")
                    if embedded["address"].get("embedded")
                    else ""
                ),
                "address_embedded": embedded["address"]["embedded"],
                "title_fa": sanitize_csv_cell(
                    embedded["title_fa"].get("text", "")
                    if embedded["title_fa"].get("embedded")
                    else ""
                ),
                "title_fa_embedded": embedded["title_fa"]["embedded"],
                "star": meta["star"],
                "hotel_id": meta["hotel_id"],
            }
            writer.writerow(row)


def get_nested_value(data: dict[str, Any], keys: tuple[str, ...]) -> str:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    if not isinstance(current, str):
        return ""
    return current.strip()


def extract_hotel_record(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    hotel = payload.get("result", {}).get("hotel", {})
    hotel_id = path.stem

    title_fa = get_nested_value(hotel, ("title", "fa"))
    address = get_nested_value(hotel, ("address",))
    description_fa = get_nested_value(hotel, ("description", "fa"))
    facilities_aggregate = get_nested_value(hotel, ("facilitiesAggregate",))
    tehran_zone = get_nested_value(hotel, ("tehranZone", "fa"))
    star = hotel.get("star")
    hotel_name = get_nested_value(hotel, ("name", "fa")) or title_fa

    texts = {
        "description_fa": description_fa,
        "facilitiesAggregate": facilities_aggregate,
        "address": address,
        "title_fa": title_fa,
    }

    metadata = {
        "hotel_id": hotel_id,
        "star": int(star) if star is not None else -1,
        "tehran_zone": tehran_zone,
    }

    return {
        "hotel_id": hotel_id,
        "hotel_name": hotel_name,
        "file_name": path.name,
        "texts": texts,
        "metadata": metadata,
        "metadata_only": {
            "hotel_id": hotel_id,
            "star": metadata["star"],
            "tehran_zone": tehran_zone,
        },
    }


def build_audit_entry(
    hotel_data: dict[str, Any],
    embedded_results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "hotel_id": hotel_data["hotel_id"],
        "hotel_name": hotel_data["hotel_name"],
        "file_name": hotel_data["file_name"],
        "metadata_only": hotel_data["metadata_only"],
        "embedded": embedded_results,
        "processed_at": utc_now_iso(),
    }


def get_collection(
    client: chromadb.PersistentClient,
    embedding_fn: OpenAIEmbeddingFunction,
) -> Any:
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine", "embedding_model": EMBEDDING_MODEL},
    )


def process_hotel(
    hotel_data: dict[str, Any],
    collection: Any,
    dry_run: bool,
) -> dict[str, dict[str, Any]]:
    embedded_results: dict[str, dict[str, Any]] = {}
    base_metadata = hotel_data["metadata"]
    hotel_id = hotel_data["hotel_id"]

    upsert_ids: list[str] = []
    upsert_documents: list[str] = []
    upsert_metadatas: list[dict[str, Any]] = []

    for field_name in EMBED_FIELDS:
        text = hotel_data["texts"][field_name]
        chroma_id = make_chroma_id(hotel_id, field_name)
        result: dict[str, Any] = {
            "collection": COLLECTION_NAME,
            "chroma_id": chroma_id,
            "embedded": False,
            "char_count": len(text),
        }

        if not text:
            result["reason"] = "empty"
            embedded_results[field_name] = result
            continue

        upsert_ids.append(chroma_id)
        upsert_documents.append(text)
        upsert_metadatas.append({**base_metadata, "field": field_name})

        result["embedded"] = True
        result["text"] = text
        embedded_results[field_name] = result

    if not dry_run and upsert_ids:
        collection.upsert(
            ids=upsert_ids,
            documents=upsert_documents,
            metadatas=upsert_metadatas,
        )

    return embedded_results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Embed hotel JSON files into one Chroma collection (one row per field)."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Hotel JSON directory (default: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--chroma-dir",
        type=Path,
        default=DEFAULT_CHROMA_DIR,
        help=f"Chroma persistence directory (default: {DEFAULT_CHROMA_DIR})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build audit preview without OpenAI/Chroma writes",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear checkpoint, audit files, and Chroma database before run",
    )
    args = parser.parse_args()

    embedding_model = load_settings(dry_run=args.dry_run)

    input_dir = args.input_dir.resolve()
    chroma_dir = args.chroma_dir.resolve()

    if not input_dir.is_dir():
        raise SystemExit(f"Input folder not found: {input_dir}")

    json_files = sorted(input_dir.glob("*.json"))
    if not json_files:
        raise SystemExit(f"No JSON files found in {input_dir}")

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.reset:
        if CHECKPOINT_FILE.exists():
            CHECKPOINT_FILE.unlink()
        if AUDIT_JSON_FILE.exists():
            AUDIT_JSON_FILE.unlink()
        if AUDIT_CSV_FILE.exists():
            AUDIT_CSV_FILE.unlink()
        if chroma_dir.exists() and not args.dry_run:
            import shutil
            shutil.rmtree(chroma_dir)
        print("Reset checkpoint, audit files, and Chroma directory.")

    checkpoint = load_checkpoint()
    if checkpoint.get("collection_layout") != "single" and checkpoint.get("completed_hotel_ids"):
        raise SystemExit(
            "Checkpoint uses the old multi-collection layout. Run with --reset to re-embed."
        )
    if (
        checkpoint.get("embedding_model")
        and checkpoint["embedding_model"] != embedding_model
        and checkpoint.get("completed_hotel_ids")
    ):
        raise SystemExit(
            f"Checkpoint uses model '{checkpoint['embedding_model']}' but .env has "
            f"'{embedding_model}'. Run with --reset to re-embed from scratch."
        )

    completed_ids = set(checkpoint.get("completed_hotel_ids", []))
    audit_records = load_audit_records()
    audit_by_id = {r["hotel_id"]: r for r in audit_records}

    collection: Any = None
    client: chromadb.PersistentClient | None = None

    if not args.dry_run:
        embedding_fn = OpenAIEmbeddingFunction(model_name=embedding_model)
        chroma_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(chroma_dir))
        collection = get_collection(client, embedding_fn)

    pending_files = [p for p in json_files if p.stem not in completed_ids]
    print(f"Total hotels: {len(json_files)}")
    print(f"Already completed: {len(completed_ids)}")
    print(f"Pending: {len(pending_files)}")
    print(f"Collection: {COLLECTION_NAME} (one row per embeddable field)")
    print(f"Embedding model: {embedding_model}")
    print(f"Env file: {ENV_FILE if ENV_FILE.exists() else 'not found (using environment)'}")
    print(f"Chroma dir: {chroma_dir}")
    print(f"Audit JSON: {AUDIT_JSON_FILE}")
    print(f"Audit CSV: {AUDIT_CSV_FILE}")
    if args.dry_run:
        print("Dry run: no API calls, no Chroma writes\n")

    succeeded = 0
    failed = 0
    dry_run_records: list[dict[str, Any]] = []

    for index, path in enumerate(pending_files, start=1):
        hotel_id = path.stem
        try:
            hotel_data = extract_hotel_record(path)
            embedded_results = process_hotel(hotel_data, collection, dry_run=args.dry_run)
            audit_entry = build_audit_entry(hotel_data, embedded_results)

            if not args.dry_run:
                audit_by_id[hotel_id] = audit_entry
                audit_records = list(audit_by_id.values())
                save_audit_records(audit_records)

                completed_ids.add(hotel_id)
                checkpoint["embedding_model"] = embedding_model
                checkpoint["collection_name"] = COLLECTION_NAME
                checkpoint["collection_layout"] = "single"
                checkpoint["completed_hotel_ids"] = sorted(completed_ids)
                checkpoint["last_processed_hotel_id"] = hotel_id
                save_checkpoint(checkpoint)

            embedded_count = sum(1 for v in embedded_results.values() if v["embedded"])
            print(
                f"[{index}/{len(pending_files)}] OK  {hotel_id} "
                f"({hotel_data['hotel_name']}) rows={embedded_count}/4"
            )
            if args.dry_run:
                dry_run_records.append(audit_entry)
            succeeded += 1
        except Exception as exc:
            failed += 1
            print(f"[{index}/{len(pending_files)}] ERR {hotel_id}: {exc}", file=sys.stderr)

    if args.dry_run and dry_run_records:
        save_audit_records(dry_run_records)
        print(f"\nDry-run audit saved for {len(dry_run_records)} hotel(s).")

    print(
        f"\nDone. Succeeded: {succeeded}, failed: {failed}, "
        f"total completed: {len(completed_ids)}"
    )


if __name__ == "__main__":
    main()
