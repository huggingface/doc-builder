#!/usr/bin/env python3
"""
Script to swap the main and temp Meilisearch indexes.

Usage:
    uv run python migrations/swap_meili_indexes.py --meilisearch_key <your_key>
"""

import argparse

import meilisearch

from doc_builder.build_embeddings import MEILI_INDEX, MEILI_INDEX_TEMP
from doc_builder.meilisearch_helper import swap_indexes


def main():
    parser = argparse.ArgumentParser(description="Swap main and temp Meilisearch indexes")
    parser.add_argument("--meilisearch_key", type=str, required=True, help="Meilisearch API key")
    args = parser.parse_args()

    client = meilisearch.Client("https://edge.meilisearch.com", args.meilisearch_key)
    swap_indexes(client, MEILI_INDEX, MEILI_INDEX_TEMP)
    print(f"[meilisearch] successfully swapped {MEILI_INDEX} and {MEILI_INDEX_TEMP}")


if __name__ == "__main__":
    main()
