# coding=utf-8
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
import importlib

from doc_builder import build_embeddings, clean_meilisearch
from doc_builder.build_embeddings import add_gradio_docs
from doc_builder.utils import get_default_branch_name, get_doc_config, read_doc_config


def embeddings_command(args):
    read_doc_config(args.path_to_docs)

    default_version = get_default_branch_name(args.path_to_docs)
    if args.not_python_module and args.version is None:
        version = default_version
    elif args.version is None:
        module = importlib.import_module(args.library_name)
        version = module.__version__

        if "dev" in version:
            version = default_version
        else:
            version = f"v{version}"
    else:
        version = args.version

    # `version` will always start with prefix `v`
    # `version_tag` does not have to start with prefix `v` (see: https://github.com/huggingface/datasets/tags)
    version_tag = version
    if version != default_version:
        doc_config = get_doc_config()
        version_prefix = getattr(doc_config, "version_prefix", "v")
        version_ = version[1:]  # v2.1.0 -> 2.1.0
        version_tag = f"{version_prefix}{version_}"

    # Disable notebook building for non-master version
    if version != default_version:
        args.notebook_dir = None

    print("Building embeddings for", args.library_name, args.path_to_docs)
    build_embeddings(
        args.library_name,
        args.path_to_docs,
        args.hf_ie_name,
        args.hf_ie_namespace,
        args.hf_ie_token,
        args.meilisearch_key,
        version=version,
        version_tag=version_tag,
        language=args.language,
        is_python_module=not args.not_python_module,
        version_tag_suffix=args.version_tag_suffix,
        repo_owner=args.repo_owner,
        repo_name=args.repo_name,
    )


def embeddings_command_parser(subparsers=None):
    if subparsers is not None:
        parser = subparsers.add_parser("embeddings")
    else:
        parser = argparse.ArgumentParser("Doc Builder embeddings command")

    parser.add_argument("library_name", type=str, help="Library name")
    parser.add_argument(
        "path_to_docs",
        type=str,
        help="Local path to library documentation. The library should be cloned, and the folder containing the "
        "documentation files should be indicated here.",
    )
    parser.add_argument("--hf_ie_name", type=str, help="Inference Endpoints name.", required=True)
    parser.add_argument("--hf_ie_namespace", type=str, help="Inference Endpoints namespace.", required=True)
    parser.add_argument("--hf_ie_token", type=str, help="Hugging Face token.", required=True)
    parser.add_argument("--meilisearch_key", type=str, help="Meilisearch key.", required=True)
    parser.add_argument("--language", type=str, help="Language of the documentation to generate", default="en")
    parser.add_argument(
        "--version",
        type=str,
        help="Version of the documentation to generate. Will default to the version of the package module (using "
        "`main` for a version containing dev).",
    )
    parser.add_argument(
        "--not_python_module",
        action="store_true",
        help="Whether docs files do NOT have corresponding python module (like HF course & hub docs).",
    )
    parser.add_argument(
        "--version_tag_suffix",
        type=str,
        default="src/",
        help="Suffix to add after the version tag (e.g. 1.3.0 or main) in the documentation links. For example, the default `src/` suffix will result in a base link as `https://github.com/huggingface/{package_name}/blob/{version_tag}/src/`.",
    )
    parser.add_argument(
        "--repo_owner",
        type=str,
        default="huggingface",
        help="Owner of the repo (e.g. huggingface, rwightman, etc.).",
    )
    parser.add_argument(
        "--repo_name",
        type=str,
        default=None,
        help="Name of the repo (e.g. transformers, pytorch-image-models, etc.). By default, this is the same as the library_name.",
    )
    if subparsers is not None:
        parser.set_defaults(func=embeddings_command)

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

    return parser
