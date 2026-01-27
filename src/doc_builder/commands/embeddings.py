# Copyright 2021 The HuggingFace Team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import argparse
import os
from pathlib import Path

from doc_builder import clean_meilisearch
from doc_builder.build_embeddings import add_gradio_docs, call_embedding_inference
from doc_builder.embeddings_tracker import (
    fetch_existing_doc_ids,
    filter_new_chunks,
    find_stale_ids,
    update_tracker_dataset,
)
from doc_builder.meilisearch_helper import add_embeddings_to_db, delete_documents_by_ids
from doc_builder.process_hf_docs import process_all_libraries
from doc_builder.utils import chunk_list


def get_credential(arg_value, env_var_name):
    """Get credential from argument or environment variable."""
    if arg_value:
        return arg_value
    return os.environ.get(env_var_name)


def process_hf_docs_command(args):
    """
    Process documentation from HF doc-build dataset.
    Downloads pre-built docs and generates embeddings.

    Supports two modes:
    - Full rebuild (default): Process all docs and upload to temp index
    - Incremental (--incremental): Only process new/changed docs, upload to main index
    """
    import meilisearch
    from tqdm import tqdm

    print("Processing documentation from HF doc-build dataset...")

    incremental_mode = getattr(args, "incremental", False)
    if incremental_mode:
        print("Running in INCREMENTAL mode - only processing new/changed documents")

    # Process all or specific libraries
    results = process_all_libraries(
        output_dir=Path(args.output_dir) if args.output_dir else None,
        excerpts_max_length=args.excerpt_length,
        libraries=args.libraries if args.libraries else None,
        skip_download=args.skip_download,
    )

    # If embeddings are requested
    if not args.skip_embeddings:
        # Get credentials from args or environment variables
        hf_ie_url = get_credential(args.hf_ie_url, "HF_IE_URL")
        hf_ie_token = get_credential(args.hf_ie_token, "HF_IE_TOKEN")
        meilisearch_key = get_credential(args.meilisearch_key, "MEILISEARCH_KEY")
        hf_token = get_credential(getattr(args, "hf_token", None), "HF_TOKEN")

        if not hf_ie_url:
            raise ValueError("HF_IE_URL is required. Set via --hf_ie_url or HF_IE_URL env var.")
        if not hf_ie_token:
            raise ValueError("HF_IE_TOKEN is required. Set via --hf_ie_token or HF_IE_TOKEN env var.")
        if not meilisearch_key:
            raise ValueError("MEILISEARCH_KEY is required. Set via --meilisearch_key or MEILISEARCH_KEY env var.")

        # Collect all chunks
        all_chunks = []
        for _library_name, chunks in results.items():
            all_chunks.extend(chunks)

        print(f"\nTotal chunks found: {len(all_chunks)}")

        # In incremental mode, filter to only new chunks and find stale ones
        stale_ids = set()
        if incremental_mode:
            print("\n" + "=" * 80)
            print("CHECKING EXISTING EMBEDDINGS")
            print("=" * 80)

            existing_ids = fetch_existing_doc_ids()
            chunks_to_process, existing_chunks = filter_new_chunks(all_chunks, existing_ids)

            # Find stale IDs (old versions of updated pages)
            stale_ids = find_stale_ids(all_chunks, existing_ids)

            print(f"Chunks already embedded: {len(existing_chunks)}")
            print(f"New chunks to embed: {len(chunks_to_process)}")
            print(f"Stale entries to remove: {len(stale_ids)}")

            if len(chunks_to_process) == 0 and len(stale_ids) == 0:
                print("\nNo new documents to process. All documents are up to date.")
                print("\n" + "=" * 80)
                print("✅ PROCESSING COMPLETE (no updates needed)")
                print("=" * 80)
                return
        else:
            chunks_to_process = all_chunks

        print("\n" + "=" * 80)
        print("GENERATING EMBEDDINGS")
        print("=" * 80)

        print(f"\nChunks to embed: {len(chunks_to_process)}")

        # Generate embeddings
        from doc_builder.build_embeddings import MEILI_INDEX, MEILI_INDEX_TEMP

        embeddings = call_embedding_inference(
            chunks_to_process,
            hf_ie_url,
            hf_ie_token,
            is_python_module=False,  # Pre-built docs are not Python modules
        )

        # Push to Meilisearch
        print("\n" + "=" * 80)
        print("UPLOADING TO MEILISEARCH")
        print("=" * 80)

        client = meilisearch.Client("https://edge.meilisearch.com", meilisearch_key)
        ITEMS_PER_CHUNK = 5000

        # In incremental mode, upload directly to main index (upsert behavior)
        # In full rebuild mode, upload to temp index for later swap
        target_index = MEILI_INDEX if incremental_mode else MEILI_INDEX_TEMP
        print(f"Target index: {target_index}")

        for chunk_embeddings in tqdm(chunk_list(embeddings, ITEMS_PER_CHUNK), desc="Uploading to meilisearch"):
            add_embeddings_to_db(client, target_index, chunk_embeddings)

        print(f"\nSuccessfully uploaded {len(embeddings)} embeddings to Meilisearch")

        # In incremental mode, delete stale entries and update the tracker dataset
        if incremental_mode:
            # Delete stale entries from Meilisearch
            if stale_ids:
                print("\n" + "=" * 80)
                print("REMOVING STALE ENTRIES")
                print("=" * 80)
                print(f"Deleting {len(stale_ids)} stale entries from Meilisearch...")
                delete_documents_by_ids(client, target_index, list(stale_ids))
                print("Stale entries removed successfully")

            # Update the tracker dataset
            if hf_token:
                print("\n" + "=" * 80)
                print("UPDATING TRACKER DATASET")
                print("=" * 80)
                update_tracker_dataset(embeddings, existing_ids, hf_token, stale_ids=stale_ids)

    print("\n" + "=" * 80)
    print("✅ PROCESSING COMPLETE")
    print("=" * 80)


def meilisearch_clean_command(args):
    """Wrapper for clean_meilisearch that supports environment variables."""
    meilisearch_key = get_credential(args.meilisearch_key, "MEILISEARCH_KEY")
    if not meilisearch_key:
        raise ValueError("MEILISEARCH_KEY is required. Set via --meilisearch_key or MEILISEARCH_KEY env var.")
    clean_meilisearch(meilisearch_key, args.swap)


def add_gradio_docs_command(args):
    """Wrapper for add_gradio_docs that supports environment variables."""
    hf_ie_token = get_credential(args.hf_ie_token, "HF_IE_TOKEN")
    hf_ie_url = get_credential(args.hf_ie_url, "HF_IE_URL")
    meilisearch_key = get_credential(args.meilisearch_key, "MEILISEARCH_KEY")
    hf_token = get_credential(getattr(args, "hf_token", None), "HF_TOKEN")
    incremental = getattr(args, "incremental", False)

    if not hf_ie_token:
        raise ValueError("HF_IE_TOKEN is required. Set via --hf_ie_token or HF_IE_TOKEN env var.")
    if not hf_ie_url:
        raise ValueError("HF_IE_URL is required. Set via --hf_ie_url or HF_IE_URL env var.")
    if not meilisearch_key:
        raise ValueError("MEILISEARCH_KEY is required. Set via --meilisearch_key or MEILISEARCH_KEY env var.")

    add_gradio_docs(
        hf_ie_url,
        hf_ie_token,
        meilisearch_key,
        incremental=incremental,
        hf_token=hf_token,
    )


def embeddings_command_parser(subparsers=None):
    # meilsiearch clean: swap & delete the temp index
    if subparsers is not None:
        parser_meilisearch_clean = subparsers.add_parser("meilisearch-clean")
    else:
        parser_meilisearch_clean = argparse.ArgumentParser(
            "Doc Builder meilisearch clean command. Swap & delete the temp index."
        )
    parser_meilisearch_clean.add_argument(
        "--meilisearch_key", type=str, help="Meilisearch key (or set MEILISEARCH_KEY env var).", required=False
    )
    parser_meilisearch_clean.add_argument(
        "--swap", action="store_true", help="Whether to swap temp index with prod index."
    )
    if subparsers is not None:
        parser_meilisearch_clean.set_defaults(func=meilisearch_clean_command)

    # add-gradio-docs: add Gradio documentation
    if subparsers is not None:
        parser_add_gradio_docs = subparsers.add_parser("add-gradio-docs")
    else:
        parser_add_gradio_docs = argparse.ArgumentParser(
            "Doc Builder add-gradio-docs command. Add Gradio documentation to embeddings."
        )

    parser_add_gradio_docs.add_argument(
        "--hf_ie_url", type=str, help="Inference Endpoints URL (or set HF_IE_URL env var).", required=False
    )
    parser_add_gradio_docs.add_argument(
        "--hf_ie_token", type=str, help="Hugging Face token (or set HF_IE_TOKEN env var).", required=False
    )
    parser_add_gradio_docs.add_argument(
        "--meilisearch_key", type=str, help="Meilisearch key (or set MEILISEARCH_KEY env var).", required=False
    )
    parser_add_gradio_docs.add_argument(
        "--incremental",
        action="store_true",
        help="Enable incremental mode: only process new/changed Gradio documents. "
        "Uploads directly to main index instead of temp index.",
    )
    parser_add_gradio_docs.add_argument(
        "--hf_token",
        type=str,
        help="HuggingFace token for updating tracker dataset in incremental mode (or set HF_TOKEN env var)",
        required=False,
    )
    if subparsers is not None:
        parser_add_gradio_docs.set_defaults(func=add_gradio_docs_command)

    # populate-search-engine: process documentation from HF doc-build dataset and populate search engine
    if subparsers is not None:
        parser_process_hf_docs = subparsers.add_parser("populate-search-engine")
    else:
        parser_process_hf_docs = argparse.ArgumentParser(
            "Doc Builder populate-search-engine command. Process pre-built documentation from HF doc-build dataset and populate search engine."
        )

    parser_process_hf_docs.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory for downloaded/extracted files (uses temp dir if not specified)",
    )
    parser_process_hf_docs.add_argument(
        "--libraries",
        type=str,
        nargs="+",
        default=None,
        help="Specific libraries to process (e.g., accelerate diffusers). If not specified, processes all libraries.",
    )
    parser_process_hf_docs.add_argument(
        "--excerpt-length", type=int, default=2000, help="Maximum length of each excerpt in characters (default: 2000)"
    )
    parser_process_hf_docs.add_argument(
        "--skip-download", action="store_true", help="Skip download if files already exist in output-dir"
    )
    parser_process_hf_docs.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Skip embedding generation and meilisearch upload (useful for testing)",
    )
    parser_process_hf_docs.add_argument(
        "--hf_ie_url",
        type=str,
        help="Inference Endpoints URL (or set HF_IE_URL env var, required unless --skip-embeddings is set)",
        required=False,
    )
    parser_process_hf_docs.add_argument(
        "--hf_ie_token", type=str, help="Hugging Face token (required unless --skip-embeddings is set)", required=False
    )
    parser_process_hf_docs.add_argument(
        "--meilisearch_key",
        type=str,
        help="Meilisearch key (required unless --skip-embeddings is set)",
        required=False,
    )
    parser_process_hf_docs.add_argument(
        "--incremental",
        action="store_true",
        help="Enable incremental mode: only process new/changed documents. "
        "Checks existing document IDs from HuggingFace dataset and skips already embedded docs. "
        "Uploads directly to main index instead of temp index.",
    )
    parser_process_hf_docs.add_argument(
        "--hf_token",
        type=str,
        help="HuggingFace token for updating tracker dataset in incremental mode (or set HF_TOKEN env var)",
        required=False,
    )

    if subparsers is not None:
        parser_process_hf_docs.set_defaults(func=process_hf_docs_command)
