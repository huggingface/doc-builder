#!/usr/bin/env python3
"""
Migration: apply the current search settings (searchable attributes, ranking rules, synonyms...) to an existing
Meilisearch index, after a change to `SEARCH_SETTINGS`.

Meilisearch re-indexes the documents when the searchable attributes change. Documents are only matched on the
searchable attributes, so run it once every document has them: after `populate-search-engine` and
`migrations/refresh_document_fields.py`.

Usage:
    uv run python migrations/update_meili_settings.py --meilisearch_key <key> --meilisearch_url <url>
"""

import argparse

import meilisearch

from doc_builder.build_embeddings import MEILI_INDEX
from doc_builder.meilisearch_helper import update_db_settings


def main():
    parser = argparse.ArgumentParser(description="Apply the current search settings to a Meilisearch index.")
    parser.add_argument("--meilisearch_key", type=str, required=True, help="Meilisearch API key")
    parser.add_argument("--meilisearch_url", type=str, required=True, help="Meilisearch URL")
    parser.add_argument("--index", type=str, default=MEILI_INDEX, help=f"Index to update (default: {MEILI_INDEX})")
    args = parser.parse_args()

    client = meilisearch.Client(args.meilisearch_url, args.meilisearch_key)
    update_db_settings(client, args.index)
    print(f"[meilisearch] updated the settings of {args.index}")


if __name__ == "__main__":
    main()
