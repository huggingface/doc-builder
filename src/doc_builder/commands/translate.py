# Copyright 2026 The HuggingFace Team. Licensed under the Apache License, Version 2.0.
"""Generate one translation run; HF workers never update the shared cache."""

import argparse
import json
import re
import subprocess
import tempfile
import warnings
from pathlib import Path

from huggingface_hub import HfApi

from ..translate import artifact, pipeline


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
    api = api or HfApi()
    with tempfile.TemporaryDirectory() as directory:
        repo = args.source or checkout(args.source_revision, Path(directory) / "transformers")
        selected = Path(args.pages_file).read_text().splitlines() if args.pages_file else None
        if selected is not None:
            selected = [name.strip() for name in selected if name.strip() and not name.startswith("#")]
        files, _ = pipeline.inventory(repo, args.source_revision, selected)
        if args.lang not in pipeline.LANGUAGES:
            raise ValueError(f"Unsupported language: {args.lang}")
        if args.dry_run:
            plans = pipeline.extract_pages(
                [value.decode() for name, value in files.items() if Path(name).suffix in {".md", ".mdx"}],
                normalize=True,
            )
            print(f"Validated {len(plans)} source pages at {args.source_revision}")
            return
        if not args.bucket or not args.run_id:
            raise ValueError("Generation requires --bucket and --run-id")
        bucket, path = artifact.bucket_path(args.bucket)
        if path:
            raise ValueError("Pass the Bucket root; each run gets its own output folder")
        prefix = artifact.run_prefix(args.lang, args.run_id)
        revision = args.model_revision or api.model_info(pipeline.MODEL).sha
        config = pipeline.configuration(args.lang, revision)
        builder_revision = pipeline.git(Path(__file__).resolve().parents[3], "rev-parse", "HEAD")
        if pipeline.git(Path(__file__).resolve().parents[3], "status", "--porcelain", "--untracked-files=no"):
            raise ValueError("Commit implementation changes before running a translation Job")
        if not re.fullmatch(r"[a-f0-9]{40}", builder_revision):
            raise ValueError("Run from a pinned doc-builder checkout")
        cache = artifact.read_cache(api, bucket, f"{artifact.language_prefix(args.lang)}/.cache.json")
        translated, candidate, failures = pipeline.translate(files, config, cache, generate_fn)
        try:
            api.batch_bucket_files(
                bucket, add=[(json.dumps(candidate, ensure_ascii=False).encode(), f"{prefix}/cache.json")]
            )
        except Exception as exc:
            warnings.warn(f"Cache upload failed; this run's completed pages cannot be reused: {exc}", stacklevel=2)
        if failures:
            raise ValueError("Translation failed:\n" + "\n".join(failures))
        metadata = artifact.run_metadata(
            args.source_revision, builder_revision, config, args.run_id, args.preview or selected is not None
        )
        result = artifact.upload_run(api, bucket, prefix, artifact.disclose(translated), metadata)
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
    parser.add_argument("--run-id", help="Write to a unique run folder")
    parser.add_argument("--model-revision", help="Pin the model and tokenizer commit SHA")
    parser.add_argument("--pages-file", help="Preview the relative page paths listed in this file")
    parser.add_argument("--preview", action="store_true", help="Keep this run isolated from full build artifacts")
    parser.add_argument("--dry-run", action="store_true", help="Validate sources without generation or Bucket writes")
    parser.set_defaults(func=translate_command)
    return parser
