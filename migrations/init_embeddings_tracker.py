#!/usr/bin/env python3
"""
Script to initialize the embeddings tracker dataset by processing docs from hf-doc-build/doc-build.
This reconstructs document IDs deterministically without needing Meilisearch.

Usage:
    uv run python migrations/init_embeddings_tracker.py --hf_token <token>

The dataset will be created at: hf-doc-build/doc-builder-embeddings-tracker
"""

import argparse
import os
from pathlib import Path

from datasets import Dataset
from tqdm import tqdm

from doc_builder.meilisearch_helper import generate_doc_id
from doc_builder.process_hf_docs import process_all_libraries

# Dataset repository for tracking embeddings
EMBEDDINGS_TRACKER_REPO = "hf-doc-build/doc-builder-embeddings-tracker"


def main():
    parser = argparse.ArgumentParser(description="Initialize embeddings tracker dataset from hf-doc-build/doc-build")
    parser.add_argument(
        "--hf_token",
        type=str,
        required=False,
        help="HuggingFace token with write access (or set HF_TOKEN env var)",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default=EMBEDDINGS_TRACKER_REPO,
        help=f"Dataset repository ID (default: {EMBEDDINGS_TRACKER_REPO})",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory for downloaded/extracted files (uses temp dir if not specified)",
    )
    args = parser.parse_args()

    hf_token = args.hf_token or os.environ.get("HF_TOKEN")

    if not hf_token:
        raise ValueError("HF_TOKEN is required. Set via --hf_token or HF_TOKEN env var.")

    # Process all libraries from hf-doc-build/doc-build (same as populate-search-engine)
    print("=" * 80)
    print("DOWNLOADING AND PROCESSING DOCS FROM hf-doc-build/doc-build")
    print("=" * 80)

    results = process_all_libraries(
        output_dir=Path(args.output_dir) if args.output_dir else None,
        excerpts_max_length=2000,  # Same as default in populate-search-engine
    )

    # Generate document IDs for all chunks
    print("\n" + "=" * 80)
    print("GENERATING DOCUMENT IDS")
    print("=" * 80)

    entries = []
    for library_name, chunks in tqdm(results.items(), desc="Processing libraries"):
        for chunk in chunks:
            doc_id = generate_doc_id(chunk.package_name, chunk.page, chunk.text)
            entries.append(
                {
                    "id": doc_id,
                    "library": chunk.package_name,
                    "source_page_url": chunk.source_page_url,
                }
            )

    print(f"\nTotal document IDs generated: {len(entries)}")

    # Deduplicate by ID (in case of any duplicates)
    seen_ids = set()
    unique_entries = []
    for entry in entries:
        if entry["id"] not in seen_ids:
            seen_ids.add(entry["id"])
            unique_entries.append(entry)

    print(f"Unique document IDs: {len(unique_entries)}")

    # Create and push dataset
    print("\n" + "=" * 80)
    print("PUSHING TO HUGGINGFACE")
    print("=" * 80)

    dataset = Dataset.from_list(unique_entries)
    print(f"Created dataset with {len(dataset)} entries")
    print(f"Columns: {dataset.column_names}")

    print(f"Pushing to {args.repo}...")
    dataset.push_to_hub(args.repo, token=hf_token, private=False)

    print("\n" + "=" * 80)
    print("✅ MIGRATION COMPLETE")
    print("=" * 80)
    print(f"Dataset created at: https://huggingface.co/datasets/{args.repo}")
    print(f"Total documents tracked: {len(unique_entries)}")


if __name__ == "__main__":
    main()
