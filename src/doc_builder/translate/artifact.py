# Copyright 2026 The HuggingFace Team. Licensed under the Apache License, Version 2.0.
"""One canonical translation tree; metadata contains hashes, never translated text."""

import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from urllib.parse import quote

from huggingface_hub.hf_api import BucketFile

from . import pipeline

STATE = ".translation-state.json"


def bucket_path(uri):
    match = re.fullmatch(r"hf://buckets/([\w.-]+/[\w.-]+)", uri)
    if not match:
        raise ValueError("Pass the Bucket root: hf://buckets/<owner>/<name>")
    return match[1]


def language_prefix(language):
    if not re.fullmatch(r"[a-z]{2,3}", language):
        raise ValueError("Invalid language")
    return f"transformers/{language}"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def download(api, bucket, prefix, names):
    with tempfile.TemporaryDirectory() as directory:
        targets = {name: Path(directory) / str(i) for i, name in enumerate(names)}
        if targets:
            api.download_bucket_files(
                bucket, [(prefix + name, path) for name, path in targets.items()], raise_on_missing_files=True
            )
        return {name: path.read_bytes() for name, path in targets.items()}


def read_state(api, bucket, language):
    path = f"{language_prefix(language)}/{STATE}"
    if not any(e.path == path for e in api.list_bucket_tree(bucket, prefix=path, recursive=False)):
        return {}
    state = json.loads(download(api, bucket, "", [path])[path])
    if not isinstance(state, dict) or state.get("format") != 1 or not isinstance(state.get("files"), dict):
        raise ValueError("Invalid translation state")
    return state


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


def undisclose(name, data):
    # Remove only our generated notice before validating/reusing the translation.
    note = disclose({name: b""})[name]
    return data.replace(note, b"", 1)


def read_cache(api, bucket, files, config, state):
    prefix = language_prefix(config["language"])
    entries = state.get("files", {})
    existing = {e.path for e in api.list_bucket_tree(bucket, prefix=prefix + "/", recursive=True)}
    names = [
        name
        for name in files
        if (Path(name).suffix in {".md", ".mdx"} or name == "_toctree.yml")
        and entries.get(name, {}).get("key") == pipeline.cache_key(name, files[name], config)
        and f"{prefix}/{name}" in existing
    ]
    return {
        entries[name]["key"]: undisclose(name, value).decode("utf-8")
        for name, value in download(api, bucket, prefix + "/", names).items()
        if sha256(value) == entries[name]["sha256"]
    }


def publish(api, bucket, files, accepted, config, state, source_revision, builder_revision, partial=False):
    prefix = language_prefix(config["language"]) + "/"
    for name in files:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name or name.startswith("."):
            raise ValueError(f"Invalid translation source path: {name}")
    entries = dict(state.get("files", {}))
    state = {
        "format": 1,
        "source_revision": source_revision,
        "doc_builder_revision": builder_revision,
        "config": config,
        "complete": False,
        "files": entries,
    }

    def save():
        api.batch_bucket_files(bucket, add=[(json.dumps(state, sort_keys=True).encode(), prefix + STATE)])

    # Invalidate build readiness before changing any document.
    save()
    values = disclose(accepted)
    if partial:
        values = {name: data for name, data in values.items() if Path(name).suffix in {".md", ".mdx"}}
    existing = {
        e.path
        for e in api.list_bucket_tree(bucket, prefix=prefix, recursive=True)
        if isinstance(e, BucketFile) and e.path.startswith(prefix)
    }
    names = [name for name in values if prefix + name in existing]
    previous = download(api, bucket, prefix, names)
    changed = {name: data for name, data in values.items() if previous.get(name) != data}
    if changed:
        api.batch_bucket_files(bucket, add=[(data, prefix + name) for name, data in changed.items()])
    if download(api, bucket, prefix, changed) != changed:
        raise ValueError("Uploaded translations do not match validated pages")
    for name, data in values.items():
        entries[name] = {"key": pipeline.cache_key(name, files[name], config), "sha256": sha256(data)}
    if not partial:
        obsolete = sorted(existing - {prefix + name for name in files} - {prefix + STATE})
        if obsolete:
            api.batch_bucket_files(bucket, delete=obsolete)
        state["files"] = {name: entry for name, entry in entries.items() if name in files}
    state["complete"] = not partial and values.keys() == files.keys()
    save()
    return state


def verify(api, bucket, files, language, source_revision, builder_revision, state_sha256):
    state = read_state(api, bucket, language)
    if pipeline.digest(state) != state_sha256:
        raise ValueError("Translation state changed; rerun translation before building")
    if (
        not state.get("complete")
        or state["source_revision"] != source_revision
        or state["doc_builder_revision"] != builder_revision
    ):
        raise ValueError("Translations are incomplete or belong to another revision")
    config = state["config"]
    if config["language"] != language or set(state["files"]) != set(files):
        raise ValueError("Translation language or source file set differs")
    prefix = language_prefix(language) + "/"
    values = download(api, bucket, prefix, files)
    for name, data in values.items():
        entry = state["files"][name]
        if entry["key"] != pipeline.cache_key(name, files[name], config) or entry["sha256"] != sha256(data):
            raise ValueError(f"Translation does not match current source or output: {name}")
    if read_state(api, bucket, language) != state:
        raise ValueError("Translation state changed while downloading")
    pipeline.check_sidebar(values)
    return values


def result(bucket, language, files, state):
    folder = f"https://huggingface.co/buckets/{bucket}/tree/{language_prefix(language)}"
    first = min(name for name in files if Path(name).suffix in {".md", ".mdx"})
    return {
        "translation_bucket": f"hf://buckets/{bucket}",
        "translation_state_sha256": pipeline.digest(state),
        "folder_url": folder,
        "page_url": f"{folder}/{quote(first)}",
    }


def install(files, target):
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
    import argparse

    from huggingface_hub import HfApi

    parser = argparse.ArgumentParser(description="Install verified translations from a Bucket")
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--state-sha256", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--doc-builder-revision", required=True)
    parser.add_argument("--language", required=True)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--docs-source", required=True, type=Path)
    args = parser.parse_args()
    bucket = bucket_path(args.bucket)
    files, _ = pipeline.inventory(args.repository, args.source_revision)
    translated = verify(
        HfApi(), bucket, files, args.language, args.source_revision, args.doc_builder_revision, args.state_sha256
    )
    install(translated, args.docs_source / args.language)


if __name__ == "__main__":
    main()
