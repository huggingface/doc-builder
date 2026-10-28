# Copyright 2026 The HuggingFace Team. All rights reserved.
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

from doc_builder.translate_docs import (
    DOC_BUCKET,
    MAX_ENGLISH_BLOCKS,
    TRANSLATED_DOCS,
    translate_docs,
)
from doc_builder.translate_model import BILL_TO


def translate_docs_command(args):
    inference_token = args.inference_token or os.environ.get("TRANSLATION_INFERENCE_TOKEN")
    if not inference_token:
        raise ValueError(
            "Pass --inference_token or set TRANSLATION_INFERENCE_TOKEN (a token for HF Inference Providers)."
        )
    libraries = args.libraries or list(TRANSLATED_DOCS)
    translations = {}
    for library in libraries:
        languages = args.languages or TRANSLATED_DOCS.get(library)
        if not languages:
            raise ValueError(f"No languages configured for {library!r}; pass --languages.")
        translations[library] = languages
    stats = translate_docs(
        args.bucket,
        inference_token,
        source_url=args.source,
        translations=translations,
        token=args.hf_token or os.environ.get("HF_TOKEN"),
        versions=args.versions,
        max_pages=args.max_pages,
        workers=args.workers,
        bill_to=args.bill_to,
    )
    if stats.failed():
        raise SystemExit(
            f"{stats.english_blocks}/{stats.blocks} blocks were kept in English (more than {MAX_ENGLISH_BLOCKS:.0%}):"
            " the model or provider is likely failing. Pages were published with the English blocks."
        )


def translate_docs_command_parser(subparsers=None):
    if subparsers is not None:
        parser = subparsers.add_parser(
            "translate-docs",
            help="Machine-translate built English docs into other languages, incrementally.",
        )
    else:
        parser = argparse.ArgumentParser("Doc Builder translate-docs command")

    parser.add_argument(
        "--bucket",
        type=str,
        default=DOC_BUCKET,
        help=f"Where translations are written: hf://buckets/<owner>/<name> or a local directory. Default: {DOC_BUCKET}.",
    )
    parser.add_argument(
        "--source",
        type=str,
        default=DOC_BUCKET,
        help=f"Bucket (or local directory) with the built English docs. Default: {DOC_BUCKET}.",
    )
    parser.add_argument("--libraries", type=str, nargs="+", help=f"Default: {', '.join(TRANSLATED_DOCS)}.")
    parser.add_argument("--languages", type=str, nargs="+", help="Default: the languages configured per library.")
    parser.add_argument(
        "--versions",
        type=str,
        nargs="+",
        help="Only these versions. Default: main and every release published since translation started.",
    )
    parser.add_argument("--max_pages", type=int, help="Translate at most this many pages per version (for testing).")
    parser.add_argument("--workers", type=int, default=8, help="Concurrent model requests per page.")
    parser.add_argument("--hf_token", type=str, help="Token for the buckets (default: $HF_TOKEN).")
    parser.add_argument(
        "--bill_to",
        type=str,
        default=BILL_TO,
        help=f"Organization billed for inference (X-HF-Bill-To). Default: {BILL_TO}; pass '' to bill the token's owner.",
    )
    parser.add_argument(
        "--inference_token",
        type=str,
        help="Token for HF Inference Providers (default: $TRANSLATION_INFERENCE_TOKEN). Required.",
    )

    if subparsers is not None:
        parser.set_defaults(func=translate_docs_command)
    return parser
