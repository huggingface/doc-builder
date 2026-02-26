#!/usr/bin/env python3
"""
One-time migration script: export all existing Meilisearch document IDs to the
HF Hub tracker dataset (hf-doc-build/doc-builder-embeddings-tracker).

This bootstraps the tracker so that subsequent `populate-search-engine
--incremental` runs can diff against it instead of re-indexing everything.

Usage:
    uv run python migrations/export_meili_ids_to_hf.py \
        --meilisearch_key <key> \
        --meilisearch_url <url> \
        [--hf_token <token>]   # falls back to HF_TOKEN env var
"""

import argparse

import meilisearch

from doc_builder.build_embeddings import MEILI_INDEX
from doc_builder.meilisearch_helper import get_all_document_ids
from doc_builder.embeddings_tracker import save_tracker


def main():
    parser = argparse.ArgumentParser(description="Export all Meilisearch document IDs to the HF Hub tracker dataset.")
    parser.add_argument("--meilisearch_key", type=str, required=True, help="Meilisearch API key")
    parser.add_argument("--meilisearch_url", type=str, required=True, help="Meilisearch URL")
    parser.add_argument(
        "--hf_token",
        type=str,
        required=False,
        default=None,
        help="HuggingFace token with write access (falls back to HF_TOKEN env var)",
    )
    args = parser.parse_args()

    client = meilisearch.Client(args.meilisearch_url, args.meilisearch_key)

    print(f"Fetching all document IDs from Meilisearch index '{MEILI_INDEX}'...")
    ids = get_all_document_ids(client, MEILI_INDEX)
    print(f"Found {len(ids)} documents in '{MEILI_INDEX}'")

    print("Pushing ID list to HF Hub tracker...")
    save_tracker(ids, hf_token=args.hf_token)
    print("Done. The tracker is now ready for incremental updates.")


if __name__ == "__main__":
    main()
