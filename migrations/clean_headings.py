#!/usr/bin/env python3
"""
One-time migration: remove Markdown syntax and doc-builder `[[anchor]]` suffixes from the `heading1`-`heading5`
fields of the documents already in the Meilisearch index, e.g. "BatchEncoding[[transformers.BatchEncoding]]"
becomes "BatchEncoding".

Documents are updated in place (partial updates), so their vectors are kept and nothing is re-embedded.
Document IDs only hash `text`, which is unchanged, so the incremental-update tracker stays valid.
The migration is idempotent: documents whose headings are already clean are skipped.

Usage:
    uv run python migrations/clean_headings.py --meilisearch_key <key> --meilisearch_url <url> [--dry_run]
"""

import argparse

import meilisearch

from doc_builder.build_embeddings import MEILI_INDEX, clean_heading
from doc_builder.meilisearch_helper import update_all_documents

HEADING_FIELDS = ["heading1", "heading2", "heading3", "heading4", "heading5"]


def main():
    parser = argparse.ArgumentParser(description="Clean headings of existing Meilisearch documents.")
    parser.add_argument("--meilisearch_key", type=str, required=True, help="Meilisearch API key")
    parser.add_argument("--meilisearch_url", type=str, required=True, help="Meilisearch URL")
    parser.add_argument("--index", type=str, default=MEILI_INDEX, help=f"Index to migrate (default: {MEILI_INDEX})")
    parser.add_argument("--dry_run", action="store_true", help="Print sample changes without writing")
    args = parser.parse_args()

    samples = []

    def transform(doc):
        changes = {
            field: clean_heading(doc[field])
            for field in HEADING_FIELDS
            if doc[field] is not None and clean_heading(doc[field]) != doc[field]
        }
        if changes and len(samples) < 5:
            samples.append({field: (doc[field], heading) for field, heading in changes.items()})
        return changes or None

    client = meilisearch.Client(args.meilisearch_url, args.meilisearch_key)
    updated = update_all_documents(client, args.index, HEADING_FIELDS, transform, dry_run=args.dry_run)

    for sample in samples:
        print(sample)
    print(f"{'Would update' if args.dry_run else 'Updated'} {updated} documents in '{args.index}'")


if __name__ == "__main__":
    main()
