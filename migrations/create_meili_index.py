#!/usr/bin/env python3
"""
Script to create a Meilisearch index for docs semantic search.

Usage:
    uv run python migrations/create_meili_index.py --meilisearch_key <your_key>          # creates main index
    uv run python migrations/create_meili_index.py --meilisearch_key <your_key> --temp   # creates temp index
"""

import argparse

import meilisearch

from doc_builder.build_embeddings import MEILI_INDEX, MEILI_INDEX_TEMP
from doc_builder.meilisearch_helper import create_embedding_db, update_db_settings


def main():
    parser = argparse.ArgumentParser(description="Create a Meilisearch index for docs semantic search")
    parser.add_argument("--meilisearch_key", type=str, required=True, help="Meilisearch API key")
    parser.add_argument("--temp", action="store_true", help="Create the temp index instead of the main index")
    args = parser.parse_args()

    index_name = MEILI_INDEX_TEMP if args.temp else MEILI_INDEX

    client = meilisearch.Client("https://edge.meilisearch.com", args.meilisearch_key)
    create_embedding_db(client, index_name)
    update_db_settings(client, index_name)
    print(f"[meilisearch] successfully created {index_name}")


if __name__ == "__main__":
    main()
