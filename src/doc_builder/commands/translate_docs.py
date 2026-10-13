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

from doc_builder.translate_docs import SOURCE_BUCKET, TRANSLATED_DOCS, translate_docs


def translate_docs_command(args):
    bucket = args.bucket or os.environ.get("TRANSLATION_BUCKET")
    if not bucket:
        raise ValueError(
            "Pass --bucket or set TRANSLATION_BUCKET (hf://buckets/<owner>/<name>, or a local directory)."
        )
    libraries = args.libraries or list(TRANSLATED_DOCS)
    translations = {}
    for library in libraries:
        languages = args.languages or TRANSLATED_DOCS.get(library)
        if not languages:
            raise ValueError(f"No languages configured for {library!r}; pass --languages.")
        translations[library] = languages
    translate_docs(
        bucket,
        source_url=args.source,
        translations=translations,
        token=args.hf_token or os.environ.get("HF_TOKEN"),
        versions=args.versions,
        max_pages=args.max_pages,
        workers=args.workers,
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
        help="Where translations are written: hf://buckets/<owner>/<name> or a local directory (default: $TRANSLATION_BUCKET).",
    )
    parser.add_argument(
        "--source",
        type=str,
        default=SOURCE_BUCKET,
        help=f"Bucket (or local directory) with the built English docs. Default: {SOURCE_BUCKET}.",
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
    parser.add_argument("--hf_token", type=str, help="Token for HF Inference and the buckets (default: $HF_TOKEN).")

    if subparsers is not None:
        parser.set_defaults(func=translate_docs_command)
    return parser
