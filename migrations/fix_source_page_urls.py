#!/usr/bin/env python3
"""
One-time migration: fix the `source_page_url` anchors of the documents already in the Meilisearch index.

Anchors used to be slugified from the raw heading, e.g. `#tokentowordtransformersbatchencodingtokentoword` for
`token_to_word[[transformers.BatchEncoding.token_to_word]]`, which doesn't exist on the page. The docs are
processed the same way as `populate-search-engine` does, and each document gets the URL of the chunk with the
same ID (IDs only hash `text`, so they match and the incremental-update tracker stays valid).

Documents are updated in place (partial updates), so their vectors are kept and nothing is re-embedded.
The migration is idempotent: documents whose URL is already correct are skipped.

Usage:
    uv run python migrations/fix_source_page_urls.py --meilisearch_key <key> --meilisearch_url <url> \
        [--output-dir <dir> [--skip-download]] [--dry_run]
"""

import argparse
from pathlib import Path

import meilisearch

from doc_builder.build_embeddings import MEILI_INDEX, chunks_to_documents
from doc_builder.meilisearch_helper import generate_doc_id, update_all_documents
from doc_builder.process_hf_docs import process_all_libraries


def main():
    parser = argparse.ArgumentParser(description="Fix `source_page_url` anchors of existing Meilisearch documents.")
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
    urls = {
        generate_doc_id(document.library, document.page, document.text): document.source_page_url
        for document in chunks_to_documents(chunks)
    }
    print(f"Computed URLs for {len(urls)} documents")

    samples = []

    def transform(doc):
        url = urls.get(doc["id"])
        if url is None or url == doc["source_page_url"]:
            return None
        if len(samples) < 5:
            samples.append((doc["source_page_url"], url))
        return {"source_page_url": url}

    client = meilisearch.Client(args.meilisearch_url, args.meilisearch_key)
    updated = update_all_documents(client, args.index, ["source_page_url"], transform, dry_run=args.dry_run)

    for old, new in samples:
        print(f"{old}\n  -> {new}")
    print(f"{'Would update' if args.dry_run else 'Updated'} {updated} documents in '{args.index}'")


if __name__ == "__main__":
    main()
