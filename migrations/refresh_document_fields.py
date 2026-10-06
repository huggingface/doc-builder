#!/usr/bin/env python3
"""
Migration: recompute the fields derived from the docs (URL, page title, headings, `text_plain`) of the documents
already in the Meilisearch index, after a change to how they are computed.

Incremental updates only re-index chunks whose text changed, since document IDs hash the text: a chunk with the
same text keeps its fields even when the code computing them changed. The docs are processed the same way as
`populate-search-engine` does, and each document gets the fields of the chunk with the same ID.

Run it after `populate-search-engine` has indexed the chunks whose text changed. Documents are updated in place
(partial updates), so their vectors are kept and nothing is re-embedded. The migration is idempotent: documents
whose fields are already up to date are skipped.

Usage:
    uv run python migrations/refresh_document_fields.py --meilisearch_key <key> --meilisearch_url <url> \
        [--output-dir <dir> [--skip-download]] [--dry_run]
"""

import argparse
from collections import Counter
from pathlib import Path

import meilisearch

from doc_builder.build_embeddings import MEILI_INDEX, chunks_to_documents
from doc_builder.meilisearch_helper import generate_doc_id, update_all_documents
from doc_builder.process_hf_docs import process_all_libraries

FIELDS = [
    "source_page_url",
    "source_page_title",
    "heading1",
    "heading2",
    "heading3",
    "heading4",
    "heading5",
    "text_plain",
]


def main():
    parser = argparse.ArgumentParser(
        description="Recompute the docs-derived fields of existing Meilisearch documents."
    )
    parser.add_argument("--meilisearch_key", type=str, required=True, help="Meilisearch API key")
    parser.add_argument("--meilisearch_url", type=str, required=True, help="Meilisearch URL")
    parser.add_argument("--index", type=str, default=MEILI_INDEX, help=f"Index to migrate (default: {MEILI_INDEX})")
    parser.add_argument("--output-dir", type=str, default=None, help="Directory for the downloaded docs")
    parser.add_argument("--skip-download", action="store_true", help="Reuse docs already in --output-dir")
    parser.add_argument(
        "--excerpt-length", type=int, default=1000, help="Must match populate-search-engine (default: 1000)"
    )
    parser.add_argument("--dry_run", action="store_true", help="Print sample changes without writing")
    args = parser.parse_args()

    results = process_all_libraries(
        output_dir=Path(args.output_dir) if args.output_dir else None,
        excerpts_max_length=args.excerpt_length,
        skip_download=args.skip_download,
    )
    chunks = [chunk for library_chunks in results.values() for chunk in library_chunks]
    recomputed = {
        generate_doc_id(document.library, document.page, document.text): {
            field: getattr(document, field) for field in FIELDS
        }
        for document in chunks_to_documents(chunks)
    }
    print(f"Recomputed fields for {len(recomputed)} documents")

    changed_fields = Counter()
    samples = []

    def transform(doc):
        fields = recomputed.get(doc["id"])
        if fields is None:
            return None
        changes = {field: value for field, value in fields.items() if value != doc[field]}
        changed_fields.update(changes)
        if changes and len(samples) < 5:
            samples.append({field: (doc[field], value) for field, value in changes.items() if field != "text_plain"})
        return changes or None

    client = meilisearch.Client(args.meilisearch_url, args.meilisearch_key)
    updated = update_all_documents(client, args.index, FIELDS, transform, dry_run=args.dry_run)

    for sample in samples:
        print(sample)
    print(f"Changed fields: {dict(changed_fields)}")
    print(f"{'Would update' if args.dry_run else 'Updated'} {updated} documents in '{args.index}'")


if __name__ == "__main__":
    main()
