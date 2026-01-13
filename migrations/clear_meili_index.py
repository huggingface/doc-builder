#!/usr/bin/env python3
"""
Script to delete all documents from a Meilisearch index without deleting the index itself.

Usage:
    uv run python migrations/clear_meili_index.py --meilisearch_key <your_key>          # clears main index
    uv run python migrations/clear_meili_index.py --meilisearch_key <your_key> --temp   # clears temp index
"""

import argparse

import meilisearch

from doc_builder.build_embeddings import MEILI_INDEX, MEILI_INDEX_TEMP
from doc_builder.meilisearch_helper import clear_embedding_db


def main():
    parser = argparse.ArgumentParser(description="Delete all documents from a Meilisearch index")
    parser.add_argument("--meilisearch_key", type=str, required=True, help="Meilisearch API key")
    parser.add_argument("--temp", action="store_true", help="Clear the temp index instead of the main index")
    args = parser.parse_args()

    index_name = MEILI_INDEX_TEMP if args.temp else MEILI_INDEX

    client = meilisearch.Client("https://edge.meilisearch.com", args.meilisearch_key)
    clear_embedding_db(client, index_name)
    print(f"[meilisearch] successfully cleared all documents from {index_name}")


if __name__ == "__main__":
    main()
