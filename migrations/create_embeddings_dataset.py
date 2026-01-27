#!/usr/bin/env python3
"""
Script to create a HuggingFace dataset containing all document IDs from existing Meilisearch index.
This dataset is used to track which documents already have embeddings, enabling incremental updates.

Usage:
    uv run python migrations/create_embeddings_dataset.py --meilisearch_key <key> --hf_token <token>

The dataset will be created at: huggingface/doc-builder-embeddings-tracker
"""

import argparse
import os

import meilisearch
from datasets import Dataset
from huggingface_hub import HfApi

from doc_builder.build_embeddings import MEILI_INDEX

# Dataset repository for tracking embeddings
EMBEDDINGS_TRACKER_REPO = "huggingface/doc-builder-embeddings-tracker"


def fetch_all_document_ids(client: meilisearch.Client, index_name: str) -> list[dict]:
    """
    Fetch all document IDs from a Meilisearch index.

    Returns:
        List of dicts with 'id', 'library', and optionally other metadata
    """
    index = client.index(index_name)

    # Get total number of documents
    stats = index.get_stats()
    total_docs = stats.number_of_documents
    print(f"Total documents in index '{index_name}': {total_docs}")

    if total_docs == 0:
        return []

    # Fetch documents in batches
    documents = []
    offset = 0
    limit = 1000  # Meilisearch max limit per request

    while offset < total_docs:
        print(f"Fetching documents {offset} to {offset + limit}...")
        result = index.get_documents(
            {
                "offset": offset,
                "limit": limit,
                "fields": ["id", "product", "source_page_url"],  # 'product' is the library field
            }
        )

        for doc in result.results:
            documents.append(
                {
                    "id": doc["id"],
                    "library": doc.get("product", ""),
                    "source_page_url": doc.get("source_page_url", ""),
                }
            )

        offset += limit

        if len(result.results) < limit:
            break

    print(f"Fetched {len(documents)} documents")
    return documents


def create_hf_dataset(documents: list[dict], hf_token: str):
    """
    Create and push a HuggingFace dataset with document tracking info.
    """
    if not documents:
        print("No documents to create dataset from")
        return

    # Create dataset
    dataset = Dataset.from_list(documents)

    print(f"Created dataset with {len(dataset)} entries")
    print(f"Columns: {dataset.column_names}")
    print(f"Sample entry: {dataset[0]}")

    # Push to Hub
    print(f"Pushing dataset to {EMBEDDINGS_TRACKER_REPO}...")
    dataset.push_to_hub(
        EMBEDDINGS_TRACKER_REPO,
        token=hf_token,
        private=False,  # Make it public for the workflow to access
    )
    print(f"Successfully pushed dataset to {EMBEDDINGS_TRACKER_REPO}")


def main():
    parser = argparse.ArgumentParser(description="Create HF dataset with document IDs from Meilisearch index")
    parser.add_argument(
        "--meilisearch_key",
        type=str,
        required=False,
        help="Meilisearch API key (or set MEILISEARCH_KEY env var)",
    )
    parser.add_argument(
        "--hf_token",
        type=str,
        required=False,
        help="HuggingFace token with write access (or set HF_TOKEN env var)",
    )
    parser.add_argument(
        "--index",
        type=str,
        default=MEILI_INDEX,
        help=f"Meilisearch index name (default: {MEILI_INDEX})",
    )
    args = parser.parse_args()

    # Get credentials
    meilisearch_key = args.meilisearch_key or os.environ.get("MEILISEARCH_KEY")
    hf_token = args.hf_token or os.environ.get("HF_TOKEN")

    if not meilisearch_key:
        raise ValueError("MEILISEARCH_KEY is required. Set via --meilisearch_key or MEILISEARCH_KEY env var.")
    if not hf_token:
        raise ValueError("HF_TOKEN is required. Set via --hf_token or HF_TOKEN env var.")

    # Connect to Meilisearch
    client = meilisearch.Client("https://edge.meilisearch.com", meilisearch_key)

    # Fetch all document IDs
    documents = fetch_all_document_ids(client, args.index)

    # Create and push HF dataset
    create_hf_dataset(documents, hf_token)

    print("\n" + "=" * 80)
    print("✅ MIGRATION COMPLETE")
    print("=" * 80)
    print(f"Dataset created at: https://huggingface.co/datasets/{EMBEDDINGS_TRACKER_REPO}")


if __name__ == "__main__":
    main()
