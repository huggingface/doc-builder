# Copyright 2026 The HuggingFace Team. Licensed under the Apache License, Version 2.0.
"""Submit a pinned HF worker; only this runner may update the shared page cache."""

import argparse
import json
import os
import re
import tempfile
import uuid
import warnings
from pathlib import Path

from huggingface_hub import HfApi, get_token

from ..commands.translate import checkout
from . import artifact, pipeline

IMAGE = "pytorch/pytorch@sha256:417bd75df6365104c283ea4c1651fb3530d9eb5a4c2fafa51943cff2a94e6385"
TERMINAL = {"COMPLETED", "ERROR", "CANCELED", "DELETED"}
BOOTSTRAP = r"""set -euo pipefail
apt-get update
apt-get install -y --no-install-recommends git curl xz-utils ca-certificates
curl -fsSLO https://nodejs.org/dist/v22.14.0/node-v22.14.0-linux-x64.tar.xz
curl -fsSLO https://nodejs.org/dist/v22.14.0/SHASUMS256.txt
awk '$2 == "node-v22.14.0-linux-x64.tar.xz"' SHASUMS256.txt | sha256sum -c -
tar -xJf node-v22.14.0-linux-x64.tar.xz -C /usr/local --strip-components=1
git clone "$BUILDER_REPOSITORY" doc-builder
cd doc-builder
git checkout --detach "$BUILDER_REVISION"
python -m pip install -e '.[translate]' "transformers @ git+https://github.com/huggingface/transformers.git@$TRANSFORMERS_REVISION" 'torch==2.8.0' 'huggingface_hub==1.27.0'
npm ci --prefix kit
python - <<'WORKER'
import json, os
from doc_builder.commands.translate import translate_command_parser
args = translate_command_parser().parse_args(json.loads(os.environ['TRANSLATE_ARGUMENTS']))
args.func(args)
WORKER
"""


def stage(job):
    value = getattr(getattr(job, "status", None), "stage", None)
    if value not in TERMINAL | {"RUNNING", "SCHEDULING"}:
        raise ValueError(f"Job {job.id} has an unknown status: {value}")
    return value


def stop_job(api, job_id, namespace):
    current = api.inspect_job(job_id=job_id, namespace=namespace)
    if stage(current) not in TERMINAL:
        api.cancel_job(job_id=job_id, namespace=namespace)
        current = api.wait_for_job(job_id, namespace=namespace, timeout=120, poll_interval=5)
        if stage(current) not in TERMINAL:
            raise ValueError(f"Job {job_id} did not stop; inspect it before starting another run")


def cancel_record(path, api):
    if Path(path).exists():
        record = json.loads(Path(path).read_text())
        stop_job(api, record["id"], record["namespace"])


def submit(args, api=None):
    api = api or HfApi()
    bucket, suffix = artifact.bucket_path(args.bucket)
    if suffix:
        raise ValueError("Pass a Bucket root")
    root = Path(__file__).resolve().parents[3]
    builder_revision = pipeline.git(root, "rev-parse", "HEAD")
    if pipeline.git(root, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("Commit the doc-builder implementation before submitting a Job")
    repository = args.doc_builder_repository or pipeline.git(root, "remote", "get-url", "origin")
    if not re.fullmatch(r"https://github.com/[\w.-]+/doc-builder(?:\.git)?", repository):
        raise ValueError("Doc-builder repository must be an HTTPS GitHub URL")
    model_revision = args.model_revision or api.model_info(pipeline.MODEL).sha
    config = pipeline.configuration(args.lang, model_revision)
    preview = not args.full
    if args.pages and not preview:
        raise ValueError("Selected pages require a preview run")
    if args.full and os.environ.get("GITHUB_ACTIONS") != "true":
        raise ValueError("Full runs require a serialized GitHub Actions caller; use a preview locally")
    run_id = f"{os.environ.get('GITHUB_RUN_ID', 'local')}-{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}-{uuid.uuid4().hex[:12]}"
    prefix = artifact.run_prefix(args.lang, run_id, preview)
    labels = {
        "doc-builder-translation": "v2",
        "language": args.lang,
        "bucket": pipeline.digest(bucket)[:16],
        "purpose": "preview" if preview else "full",
    }
    with tempfile.TemporaryDirectory() as directory:
        repo = checkout(args.source_revision, Path(directory) / "transformers")
        files, _ = pipeline.inventory(repo, args.source_revision, args.pages)
        for previous in api.list_jobs(namespace=args.namespace, labels=labels):
            if stage(previous) not in TERMINAL:
                stop_job(api, previous.id, args.namespace)
        worker_args = [
            "transformers",
            "--source-revision",
            args.source_revision,
            "--lang",
            args.lang,
            "--bucket",
            args.bucket,
            "--run-id",
            run_id,
            "--model-revision",
            model_revision,
        ]
        if preview:
            worker_args.append("--preview")
        bootstrap = BOOTSTRAP
        if args.pages:
            worker_args.extend(["--pages-file", "/tmp/translation-pages.txt"])
            bootstrap = "printf '%s' \"$TRANSLATION_PAGES\" > /tmp/translation-pages.txt\n" + bootstrap
        token = get_token()
        if not token:
            raise ValueError("Log in with hf auth login before submitting a Job")
        job = api.run_job(
            image=IMAGE,
            command=["bash", "-c", bootstrap],
            namespace=args.namespace,
            flavor=args.flavor,
            timeout="5h",
            name=f"translate-{args.lang}-{run_id}",
            labels={**labels, "run": run_id},
            secrets={"HF_TOKEN": token},
            env={
                "BUILDER_REPOSITORY": repository,
                "BUILDER_REVISION": builder_revision,
                "TRANSFORMERS_REVISION": pipeline.TRANSFORMERS_REVISION,
                "TRANSLATE_ARGUMENTS": json.dumps(worker_args),
                "TRANSLATION_PAGES": "\n".join(args.pages or []),
            },
        )
        try:
            Path(args.job_record).write_text(json.dumps({"id": job.id, "namespace": args.namespace}))
            print(f"Job: {job.url}", flush=True)
            completed = api.wait_for_job(job.id, namespace=args.namespace, timeout=5 * 3600 + 300, poll_interval=15)
            state = stage(completed)
            if state in {"COMPLETED", "ERROR"} and not preview:
                candidate = artifact.read_cache(api, bucket, f"{prefix}/cache.json")

                _, valid = pipeline.load_valid_cache(files, config, candidate)
                if valid:
                    try:
                        api.batch_bucket_files(
                            bucket,
                            add=[
                                (
                                    json.dumps(valid, ensure_ascii=False).encode(),
                                    f"cache/transformers/{args.lang}.json",
                                )
                            ],
                        )
                    except Exception as exc:
                        warnings.warn(f"Shared cache update failed; next run may recompute pages: {exc}", stacklevel=2)
            if state != "COMPLETED":
                raise ValueError(f"Translation Job {job.id} ended in {state}; no build artifact selected")
            data = artifact.download(api, bucket, [f"{prefix}/source.tar.gz"])[0]
            expected = artifact.run_metadata(args.source_revision, builder_revision, config, run_id, preview)
            accepted, _ = artifact.verify_archive(data, expected, expected_files=files)
            remote = [f"{prefix}/source/{name}" for name in accepted]
            if artifact.download(api, bucket, remote) != list(accepted.values()):
                raise ValueError("Browsable source differs from the archive")
            if not artifact.download(api, bucket, [f"{prefix}/README.md"])[0]:
                raise ValueError("Completed run README is missing")
            result = {
                **artifact.run_result(bucket, prefix, accepted, data),
                "translation_language": args.lang,
                "doc_builder_revision": builder_revision,
            }
            if os.environ.get("GITHUB_OUTPUT"):
                with open(os.environ["GITHUB_OUTPUT"], "a") as stream:
                    for key, value in result.items():
                        stream.write(f"{key}={value}\n")
            print(json.dumps(result, indent=2))
            return result
        finally:
            stop_job(api, job.id, args.namespace)


def main():
    parser = argparse.ArgumentParser(description="Submit a documentation translation Job")
    parser.add_argument("--cancel-record", help="Stop the Job recorded in this local file")
    parser.add_argument("--source-revision", help="Translate this full Transformers commit SHA")
    parser.add_argument("--bucket", help="Store translations in hf://buckets/<owner>/<name>")
    parser.add_argument("--namespace", help="Run the Job in this Hub namespace")
    parser.add_argument("--lang", default="ja", choices=pipeline.LANGUAGES)
    parser.add_argument("--pages", nargs="+", help="Preview these relative .md or .mdx paths")
    parser.add_argument("--model-revision", help="Use this model and tokenizer commit SHA")
    parser.add_argument("--doc-builder-repository", help="Fetch the implementation from this GitHub HTTPS repository")
    parser.add_argument("--flavor", default="a100-large", help="Choose the HF Job hardware")
    parser.add_argument("--job-record", default="translation-job.json", help="Record the Job ID for cancellation")
    parser.add_argument("--full", action="store_true", help="Produce a full build artifact in a serialized workflow")
    args = parser.parse_args()
    if args.cancel_record:
        cancel_record(args.cancel_record, HfApi())
    else:
        if not all([args.source_revision, args.bucket, args.namespace]):
            parser.error("--source-revision, --bucket, and --namespace are required")
        submit(args)


if __name__ == "__main__":
    main()
