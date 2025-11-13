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
from pathlib import Path

from doc_builder import clean_meilisearch
from doc_builder.build_embeddings import add_gradio_docs, call_embedding_inference
from doc_builder.meilisearch_helper import add_embeddings_to_db
from doc_builder.process_hf_docs import process_all_libraries
from doc_builder.utils import chunk_list


def process_hf_docs_command(args):
    """
    Process documentation from HF doc-build dataset.
    Downloads pre-built docs and generates embeddings.
    """
    import meilisearch
    from tqdm import tqdm

    print("Processing documentation from HF doc-build dataset...")

    # Process all or specific libraries
    results = process_all_libraries(
        output_dir=Path(args.output_dir) if args.output_dir else None,
        excerpts_max_length=args.excerpt_length,
        libraries=args.libraries if args.libraries else None,
        skip_download=args.skip_download,
    )

    # If embeddings are requested
    if not args.skip_embeddings:
        print("\n" + "=" * 80)
        print("🔢 GENERATING EMBEDDINGS")
        print("=" * 80)

        # Collect all chunks
        all_chunks = []
        for _library_name, chunks in results.items():
            all_chunks.extend(chunks)

        print(f"\nTotal chunks to embed: {len(all_chunks)}")

        # Generate embeddings
        from doc_builder.build_embeddings import MEILI_INDEX_TEMP

        embeddings = call_embedding_inference(
            all_chunks,
            args.hf_ie_name,
            args.hf_ie_namespace,
            args.hf_ie_token,
            is_python_module=False,  # Pre-built docs are not Python modules
        )

        # Push to Meilisearch
        print("\n" + "=" * 80)
        print("📤 UPLOADING TO MEILISEARCH")
        print("=" * 80)

        client = meilisearch.Client("https://edge.meilisearch.com", args.meilisearch_key)
        ITEMS_PER_CHUNK = 5000

        for chunk_embeddings in tqdm(chunk_list(embeddings, ITEMS_PER_CHUNK), desc="Uploading to meilisearch"):
            add_embeddings_to_db(client, MEILI_INDEX_TEMP, chunk_embeddings)

        print(f"\n✅ Successfully uploaded {len(embeddings)} embeddings to Meilisearch")

    print("\n" + "=" * 80)
    print("✅ PROCESSING COMPLETE")
    print("=" * 80)


def embeddings_command_parser(subparsers=None):
    # meilsiearch clean: swap & delete the temp index
    if subparsers is not None:
        parser_meilisearch_clean = subparsers.add_parser("meilisearch-clean")
    else:
        parser_meilisearch_clean = argparse.ArgumentParser(
            "Doc Builder meilisearch clean command. Swap & delete the temp index."
        )
    parser_meilisearch_clean.add_argument("--meilisearch_key", type=str, help="Meilisearch key.", required=True)
    parser_meilisearch_clean.add_argument(
        "--swap", action="store_true", help="Whether to swap temp index with prod index."
    )
    if subparsers is not None:
        parser_meilisearch_clean.set_defaults(func=lambda args: clean_meilisearch(args.meilisearch_key, args.swap))

    # add-gradio-docs: add Gradio documentation
    if subparsers is not None:
        parser_add_gradio_docs = subparsers.add_parser("add-gradio-docs")
    else:
        parser_add_gradio_docs = argparse.ArgumentParser(
            "Doc Builder add-gradio-docs command. Add Gradio documentation to embeddings."
        )

    parser_add_gradio_docs.add_argument("--hf_ie_name", type=str, help="Inference Endpoints name.", required=True)
    parser_add_gradio_docs.add_argument(
        "--hf_ie_namespace", type=str, help="Inference Endpoints namespace.", required=True
    )
    parser_add_gradio_docs.add_argument("--hf_ie_token", type=str, help="Hugging Face token.", required=True)
    parser_add_gradio_docs.add_argument("--meilisearch_key", type=str, help="Meilisearch key.", required=True)
    if subparsers is not None:
        parser_add_gradio_docs.set_defaults(
            func=lambda args: add_gradio_docs(
                args.hf_ie_name, args.hf_ie_namespace, args.hf_ie_token, args.meilisearch_key
            )
        )

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
        "--excerpt-length", type=int, default=1000, help="Maximum length of each excerpt in characters (default: 1000)"
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
        "--hf_ie_name",
        type=str,
        help="Inference Endpoints name (required unless --skip-embeddings is set)",
        required=False,
    )
    parser_process_hf_docs.add_argument(
        "--hf_ie_namespace",
        type=str,
        help="Inference Endpoints namespace (required unless --skip-embeddings is set)",
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

    if subparsers is not None:
        parser_process_hf_docs.set_defaults(func=process_hf_docs_command)
