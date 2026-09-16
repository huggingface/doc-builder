# Copyright 2026 The HuggingFace Team. Licensed under the Apache License, Version 2.0.
"""Update canonical translated documents in a Hugging Face Bucket."""

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

from huggingface_hub import HfApi

from ..translate import artifact, pipeline, preflight


def checkout(revision, directory):
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("Source revision must be a full Transformers commit SHA")
    subprocess.run(
        [
            "git",
            "clone",
            "--no-checkout",
            "--filter=blob:none",
            "https://github.com/huggingface/transformers.git",
            str(directory),
        ],
        check=True,
    )
    subprocess.run(["git", "-C", str(directory), "checkout", "--detach", revision], check=True)
    return directory


def run(args, api=None, generate_fn=pipeline.generate):
    with tempfile.TemporaryDirectory() as directory:
        repo = args.source or checkout(args.source_revision, Path(directory) / "transformers")
        selected = Path(args.pages_file).read_text(encoding="utf-8").splitlines() if args.pages_file else None
        if selected is not None:
            selected = [name.strip() for name in selected if name.strip() and not name.startswith("#")]
        files, _ = pipeline.inventory(repo, args.source_revision, selected)
        if args.lang not in pipeline.LANGUAGES:
            raise ValueError(f"Unsupported language: {args.lang}")
        if args.dry_run:
            report = preflight.check(files, {"glossary": pipeline.read_glossary(args.lang)})
            print(json.dumps(report, ensure_ascii=False, indent=2))
            if report["errors"]:
                raise ValueError("Preflight found syntax failures; inspect the errors in the report")
            return report
        api = api or HfApi()
        if not args.bucket:
            raise ValueError("Generation requires --bucket")
        bucket = artifact.bucket_path(args.bucket)
        revision = args.model_revision or api.model_info(pipeline.MODEL).sha
        config = pipeline.configuration(args.lang, revision)
        builder_revision = pipeline.git(Path(__file__).resolve().parents[3], "rev-parse", "HEAD")
        if pipeline.git(Path(__file__).resolve().parents[3], "status", "--porcelain", "--untracked-files=no"):
            raise ValueError("Commit implementation changes before running a translation Job")
        if not re.fullmatch(r"[a-f0-9]{40}", builder_revision):
            raise ValueError("Run from a pinned doc-builder checkout")
        state = artifact.read_state(api, bucket, args.lang)
        cache = artifact.read_cache(api, bucket, files, config, state)
        translated, candidate, failures = pipeline.translate(files, config, cache, generate_fn)
        # Complete pages have cache entries; non-prose assets pass through unchanged.
        accepted = {
            name: translated[name]
            for name in files
            if (name != "_toctree.yml" and Path(name).suffix not in {".md", ".mdx"})
            or pipeline.cache_key(name, files[name], config) in candidate
        }
        state = artifact.publish(
            api,
            bucket,
            files,
            accepted,
            config,
            state,
            args.source_revision,
            builder_revision,
            partial=selected is not None,
        )
        if failures:
            raise ValueError("Translation failed:\n" + "\n".join(failures))
        result = artifact.result(bucket, args.lang, files, state)
        print(json.dumps(result, indent=2))
        return result


def translate_command(args):
    try:
        run(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(str(exc)) from exc


def translate_command_parser(subparsers=None):
    parser = (
        subparsers.add_parser("translate", help="Translate English documentation")
        if subparsers
        else argparse.ArgumentParser()
    )
    parser.add_argument("package", choices=["transformers"])
    parser.add_argument("--source-revision", required=True, help="Translate this full Transformers commit SHA")
    parser.add_argument("--lang", default="ja", help="Choose the target language")
    parser.add_argument("--source", type=Path, help="Read an existing clean repository checkout")
    parser.add_argument("--bucket", help="Store results in hf://buckets/<owner>/<name>")
    parser.add_argument("--model-revision", help="Pin the model and tokenizer commit SHA")
    parser.add_argument("--pages-file", help="Preview the relative page paths listed in this file")
    parser.add_argument(
        "--dry-run", action="store_true", help="Audit labels and syntax locally without generation or Bucket writes"
    )
    parser.set_defaults(func=translate_command)
    return parser
