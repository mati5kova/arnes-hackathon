from __future__ import annotations

from pathlib import Path

import chromadb

try:
    from AI.embedding_pipeline import build_embedding_records, load_canonical_embedding_payload
except ModuleNotFoundError:
    from embedding_pipeline import build_embedding_records, load_canonical_embedding_payload

BASE_DIR = Path(__file__).resolve().parent
CHROMA_PATH = BASE_DIR / "Data" / "chroma_db"
COLLECTION_NAME = "kulturna_dediscina"
BATCH_SIZE = 500


def sync_chroma_metadata() -> None:
    if not CHROMA_PATH.exists():
        print(f"Skipping Chroma sync because {CHROMA_PATH} does not exist.")
        return

    payload = load_canonical_embedding_payload()
    records = build_embedding_records(payload)

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = client.get_or_create_collection(COLLECTION_NAME)
    existing_count = collection.count()
    if existing_count == 0:
        raise RuntimeError(
            "The Chroma collection is empty. Rebuild embeddings with makeEmbedding.py instead."
        )

    for start in range(0, len(records), BATCH_SIZE):
        batch = records[start : start + BATCH_SIZE]
        ids = [record["eid"] for record in batch]
        existing = collection.get(ids=ids)
        found_ids = {str(identifier) for identifier in existing.get("ids", [])}
        missing_ids = [identifier for identifier in ids if identifier not in found_ids]
        if missing_ids:
            raise RuntimeError(
                f"Chroma collection is missing {len(missing_ids)} ids from batch starting at {start}: "
                f"{', '.join(missing_ids[:5])}"
            )

        collection.update(
            ids=ids,
            metadatas=[record["meta_data"] for record in batch],
        )

    print(f"Synchronized metadata for {len(records)} Chroma records in {CHROMA_PATH}")


def main() -> None:
    sync_chroma_metadata()


if __name__ == "__main__":
    main()
