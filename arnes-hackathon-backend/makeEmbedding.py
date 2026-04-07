from __future__ import annotations

import os
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from openai import AzureOpenAI

try:
    from AI.embedding_pipeline import build_embedding_records, load_canonical_embedding_payload
except ModuleNotFoundError:
    from embedding_pipeline import build_embedding_records, load_canonical_embedding_payload

BASE_DIR = Path(__file__).resolve().parent
CHROMA_PATH = BASE_DIR / "AI" / "Data" / "chroma_db"
COLLECTION_NAME = "kulturna_dediscina"
BATCH_SIZE = 100


def build_embedding_client() -> tuple[AzureOpenAI, str]:
    load_dotenv()

    deployment_name = os.getenv("MDML-TextEmbedding-003_DEPLOYMENT")
    api_key = os.getenv("MDML-TextEmbedding-003_API_KEY")
    base_url = os.getenv("MDML-TextEmbedding-003_BASE_URL")
    if not deployment_name or not api_key or not base_url:
        raise RuntimeError("Missing Azure embedding configuration for MDML-TextEmbedding-003.")

    client = AzureOpenAI(
        api_key=api_key,
        azure_endpoint=base_url,
        api_version="2024-02-01",
    )
    return client, deployment_name


def main() -> None:
    payload = load_canonical_embedding_payload()
    records = build_embedding_records(payload)
    client, deployment_name = build_embedding_client()
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = chroma_client.get_or_create_collection(COLLECTION_NAME)

    total_embedding_tokens = 0
    for start in range(0, len(records), BATCH_SIZE):
        batch = records[start : start + BATCH_SIZE]
        texts = [record["text"] for record in batch]
        response = client.embeddings.create(model=deployment_name, input=texts)

        collection.upsert(
            ids=[record["eid"] for record in batch],
            documents=texts,
            metadatas=[record["meta_data"] for record in batch],
            embeddings=[item.embedding for item in response.data],
        )

        total_embedding_tokens += response.usage.total_tokens
        print(f"batch {start // BATCH_SIZE + 1}: {response.usage.total_tokens} tokens")

    print(f"all embedding tokens: {total_embedding_tokens}")


if __name__ == "__main__":
    main()
