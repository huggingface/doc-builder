# Copyright 2026 The HuggingFace Team. Licensed under the Apache License, Version 2.0.
"""Run-scoped Bucket transfers and verified source archives."""

import hashlib
import io
import json
import re
import shutil
import tarfile
import tempfile
import warnings
from pathlib import Path, PurePosixPath
from urllib.parse import quote

from huggingface_hub.hf_api import BucketFile

from .pipeline import check_sidebar, digest


def bucket_path(uri):
    match = re.fullmatch(r"hf://buckets/([\w.-]+/[\w.-]+)(?:/(.+))?", uri)
    if not match or (match[2] and any(p in {"", ".", ".."} for p in match[2].split("/"))):
        raise ValueError("Bucket must use hf://buckets/<owner>/<name>[/path]")
    return match[1], match[2] or ""


def language_prefix(language):
    if not re.fullmatch(r"[a-z]{2,3}", language):
        raise ValueError("Invalid language")
    return f"transformers/{language}"


def run_prefix(language, run_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
        raise ValueError("Invalid run ID")
    return f"{language_prefix(language)}/.runs/{run_id}"


def run_metadata(source_revision, builder_revision, config, run_id, preview):
    return {
        "format": 1,
        "package": "transformers",
        "language": config["language"],
        "source_revision": source_revision,
        "doc_builder_revision": builder_revision,
        "config_digest": digest(config),
        "run_id": run_id,
        "preview": preview,
    }


def run_result(bucket, prefix, files, data, docs_prefix=None):
    folder = f"https://huggingface.co/buckets/{bucket}/tree/{docs_prefix or prefix}"
    source = folder if docs_prefix else f"{folder}/source"
    first_page = min(name for name in files if Path(name).suffix in {".md", ".mdx"})
    return {
        "translation_archive": f"hf://buckets/{bucket}/{prefix}/source.tar.gz",
        "translation_archive_sha256": hashlib.sha256(data).hexdigest(),
        "folder_url": folder,
        "page_url": f"{source}/{quote(first_page)}",
    }


def download(api, bucket, paths):
    with tempfile.TemporaryDirectory() as directory:
        targets = [Path(directory) / str(i) for i in range(len(paths))]
        api.download_bucket_files(bucket, list(zip(paths, targets, strict=True)), raise_on_missing_files=True)
        return [path.read_bytes() for path in targets]


def read_cache(api, bucket, path):
    try:
        value = json.loads(download(api, bucket, [path])[0])
        if not isinstance(value, dict):
            raise ValueError("Cache must be a JSON object")
        return value
    except Exception as exc:
        warnings.warn(f"Cache read failed; pages will be translated again: {exc}", stacklevel=2)
        return {}


def archive_bytes(files, metadata):
    check_sidebar(files)
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        for name, value in {
            "metadata.json": json.dumps(metadata, sort_keys=True).encode(),
            **{f"source/{name}": value for name, value in files.items()},
        }.items():
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(value), 0o644
            archive.addfile(info, io.BytesIO(value))
    return stream.getvalue()


def verify_archive(data, expected, sha256=None, expected_files=None):
    if sha256 and hashlib.sha256(data).hexdigest() != sha256:
        raise ValueError("Translation archive checksum mismatch")
    files, metadata, seen = {}, None, set()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if (
                member.name in seen
                or member.name != str(path)
                or path.is_absolute()
                or any(p in {".", ".."} for p in path.parts)
                or "\\" in member.name
                or not member.isfile()
            ):
                raise ValueError(f"Invalid archive member: {member.name}")
            seen.add(member.name)
            value = archive.extractfile(member).read()
            if member.name == "metadata.json":
                metadata = json.loads(value)
            elif len(path.parts) > 1 and path.parts[0] == "source":
                files[str(PurePosixPath(*path.parts[1:]))] = value
            else:
                raise ValueError(f"Unexpected archive member: {member.name}")
    if not isinstance(metadata, dict) or any(metadata.get(k) != v for k, v in expected.items()):
        raise ValueError("Translation archive provenance mismatch")
    if metadata.get("format") != 1:
        raise ValueError("Unsupported translation archive format")
    if expected_files is not None and set(files) != set(expected_files):
        raise ValueError("Translation archive has missing or unexpected source files")
    check_sidebar(files)
    return files, metadata


def disclose(files):
    result = dict(files)
    for name, value in files.items():
        if Path(name).suffix not in {".md", ".mdx"}:
            continue
        text = value.decode("utf-8")
        page = str(PurePosixPath(name).with_suffix(""))
        note = f"> このページは機械翻訳です。[英語の原文](https://huggingface.co/docs/transformers/main/en/{quote(page)})を参照してください。\n\n"
        match = re.match(r"\s*<!--.*?-->\s*", text, re.S)
        index = match.end() if match else 0
        result[name] = (text[:index] + note + text[index:]).encode()
    return result


def upload_run(api, bucket, prefix, files, metadata):
    """Upload and reread the same tree in both forms; completion README goes last."""
    data = archive_bytes(files, metadata)
    remote = {f"{prefix}/source/{name}": value for name, value in files.items()}
    remote[f"{prefix}/source.tar.gz"] = data
    api.batch_bucket_files(bucket, add=[(value, name) for name, value in remote.items()])
    downloaded = download(api, bucket, list(remote))
    if downloaded != list(remote.values()):
        raise ValueError("Uploaded translation files do not match the accepted tree")
    verify_archive(data, metadata, expected_files=files)
    result = run_result(bucket, prefix, files, data)
    pages = sorted(name for name in files if Path(name).suffix in {".md", ".mdx"})
    folder = result["folder_url"]
    readme = (
        f"# {metadata['language']} translations\n\nCompleted {'preview' if metadata['preview'] else 'full run'}. "
        f"Source: `{metadata['source_revision']}`.\n\nRead the translated Markdown below. "
        "Doc-builder components may appear as source in the Hub viewer.\n\n"
        + "\n".join(f"- [{name}]({folder}/source/{quote(name)})" for name in pages)
        + "\n"
    )
    readme_path = f"{prefix}/README.md"
    api.batch_bucket_files(bucket, add=[(readme.encode(), readme_path)])
    if download(api, bucket, [readme_path])[0] != readme.encode():
        raise ValueError("Completion README verification failed")
    return result


def publish_docs(api, bucket, language, files):
    """Replace the readable language folder after the runner verifies a complete run."""
    prefix = language_prefix(language) + "/"
    if any(name == ".cache.json" or name == ".runs" or name.startswith(".runs/") for name in files):
        raise ValueError("Source collides with translation cache or run artifacts")
    remote = {prefix + name: value for name, value in files.items()}
    obsolete = [
        entry.path
        for entry in api.list_bucket_tree(bucket, prefix=prefix, recursive=True)
        if isinstance(entry, BucketFile)
        and entry.path.startswith(prefix)
        and entry.path not in remote
        and entry.path != prefix + ".cache.json"
        and not entry.path.startswith(prefix + ".runs/")
    ]
    if obsolete:
        api.batch_bucket_files(bucket, delete=obsolete)
    api.batch_bucket_files(bucket, add=[(value, name) for name, value in remote.items()])
    if download(api, bucket, list(remote)) != list(remote.values()):
        raise ValueError("Published documentation differs from the verified archive")


def install(data, target, expected, sha256, expected_files):
    files, metadata = verify_archive(data, expected, sha256, expected_files)
    if metadata["preview"]:
        raise ValueError("Preview archives cannot replace a build language")
    target = Path(target)
    if target.is_symlink():
        raise ValueError("Build language target must not be a symlink")
    with tempfile.TemporaryDirectory(dir=target.parent) as directory:
        staged = Path(directory) / "source"
        staged.mkdir()
        for name, value in files.items():
            path = staged / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
        if target.exists():
            shutil.rmtree(target)
        staged.rename(target)


def main():
    """Install the exact archive selected by the producer workflow."""
    import argparse

    from huggingface_hub import HfApi

    from .pipeline import inventory

    parser = argparse.ArgumentParser(description="Install a verified translation archive")
    parser.add_argument("--archive", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--doc-builder-revision", required=True)
    parser.add_argument("--language", required=True)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--docs-source", required=True, type=Path)
    args = parser.parse_args()
    bucket, path = bucket_path(args.archive)
    match = re.fullmatch(r"transformers/([a-z]{2,3})/\.runs/([A-Za-z0-9_-]+)/source\.tar\.gz", path)
    if not match or match[1] != args.language:
        raise ValueError("Build input must identify a full translation run for the requested language")
    if not re.fullmatch(r"[a-f0-9]{64}", args.sha256):
        raise ValueError("Build input needs an archive SHA-256")
    files, _ = inventory(args.repository, args.source_revision)
    data = download(HfApi(), bucket, [path])[0]
    install(
        data,
        args.docs_source / args.language,
        {
            "format": 1,
            "package": "transformers",
            "language": args.language,
            "source_revision": args.source_revision,
            "doc_builder_revision": args.doc_builder_revision,
            "run_id": match[2],
            "preview": False,
        },
        args.sha256,
        files,
    )


if __name__ == "__main__":
    main()
