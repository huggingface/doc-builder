#!/usr/bin/env python3
"""
One-time migration: add the `text_plain` field (plain-text version of `text`, used for search result snippets)
to the documents already in the Meilisearch index.

Documents are updated in place (partial updates), so their vectors are kept and nothing is re-embedded.
Document IDs only hash `text`, which is unchanged, so the incremental-update tracker stays valid.
The migration is idempotent: documents whose `text_plain` is already up to date are skipped.

Usage:
    uv run python migrations/add_text_plain.py --meilisearch_key <key> --meilisearch_url <url> [--dry_run]
"""

import argparse

import meilisearch

from doc_builder.build_embeddings import MEILI_INDEX, markdown_to_plain_text
from doc_builder.meilisearch_helper import update_all_documents


def main():
    parser = argparse.ArgumentParser(description="Add `text_plain` to existing Meilisearch documents.")
    parser.add_argument("--meilisearch_key", type=str, required=True, help="Meilisearch API key")
    parser.add_argument("--meilisearch_url", type=str, required=True, help="Meilisearch URL")
    parser.add_argument("--index", type=str, default=MEILI_INDEX, help=f"Index to migrate (default: {MEILI_INDEX})")
    parser.add_argument("--dry_run", action="store_true", help="Print sample changes without writing")
    args = parser.parse_args()

    samples = []

    def transform(doc):
        text_plain = markdown_to_plain_text(doc["text"] or "")
        if text_plain == doc["text_plain"]:
            return None
        if len(samples) < 3:
            samples.append((doc["id"], text_plain[:200]))
        return {"text_plain": text_plain}

    client = meilisearch.Client(args.meilisearch_url, args.meilisearch_key)
    updated = update_all_documents(client, args.index, ["text", "text_plain"], transform, dry_run=args.dry_run)

    for doc_id, text_plain in samples:
        print(f"{doc_id}: {text_plain!r}")
    print(f"{'Would update' if args.dry_run else 'Updated'} {updated} documents in '{args.index}'")


if __name__ == "__main__":
    main()
