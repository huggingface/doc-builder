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

"""
Machine-translate built English docs into other languages, incrementally.

Reads the built English pages (`<library>/<version>/en/`) from the doc bucket served by
huggingface.co and writes translated pages to `<library>/<version>/<language>/` in a translation
bucket, in the same layout, so moon-landing serves them like any other language.

Like `populate-search-engine --incremental`, every run diffs against a tracker:

- `main` is checked on every run; only English pages whose content changed are translated
  again, and pages deleted from the English build are deleted from the translation.
- A release version is translated once, then frozen. Releases that already existed when a
  language was first translated are never backfilled.
- Translations are cached per block, so a page whose HTML changed (e.g. after a doc-builder
  update that changes every page's asset hashes) only sends its edited paragraphs to the model.

State lives in the translation bucket under `.translation/<library>/<language>/`.
"""

import gzip
import hashlib
import json
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

import yaml

from . import translate_html as th
from .translate_model import TranslationFailed, Translator

SOURCE_BUCKET = "hf://buckets/hf-doc-build/doc"
# Libraries and languages translated by the scheduled job.
TRANSLATED_DOCS = {"transformers": ["ja"]}
# Copied unchanged from the English build: Markdown (served for `Accept: text/plain`), llms.txt files and redirects.
COPIED_SUFFIXES = {".md", ".txt"}
COPIED_NAMES = {"_redirects.yml"}
STATE_DIR = ".translation"
FLUSH_EVERY = 20  # pages; bounds the work lost if a run is interrupted


class Store:
    """Files under a local directory or an HF storage bucket (`hf://buckets/<owner>/<name>[/<prefix>]`)."""

    def __init__(self, url, token=None):
        self.is_bucket = url.startswith("hf://buckets/")
        if self.is_bucket:
            from huggingface_hub import HfApi

            parts = url.removeprefix("hf://buckets/").strip("/").split("/")
            self.bucket_id = "/".join(parts[:2])
            self.prefix = "/".join(parts[2:])
            self.api = HfApi(token=token)
        else:
            self.root = Path(url)
            self.root.mkdir(parents=True, exist_ok=True)

    def _remote(self, rel):
        return f"{self.prefix}/{rel}" if self.prefix else rel

    def walk(self, directory):
        """`{path relative to directory: content hash}`, skipping `_app` (SvelteKit assets)."""
        files = {}
        if not self.is_bucket:
            root = self.root / directory
            if root.is_dir():
                for path in root.rglob("*"):
                    rel = path.relative_to(root).as_posix()
                    if path.is_file() and "_app" not in PurePosixPath(rel).parts:
                        files[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
            return files
        from huggingface_hub.hf_api import BucketFolder

        base = self._remote(directory).rstrip("/") + "/"
        pending = [base]
        while pending:
            prefix = pending.pop()
            for entry in self.api.list_bucket_tree(self.bucket_id, prefix=prefix, recursive=False):
                if isinstance(entry, BucketFolder):
                    if PurePosixPath(entry.path).name != "_app":
                        pending.append(entry.path.rstrip("/") + "/")
                else:
                    files[entry.path[len(base) :]] = entry.xet_hash
        return files

    def read(self, paths):
        """`{path: bytes}` for the paths that exist."""
        paths = list(paths)
        if not self.is_bucket:
            return {p: (self.root / p).read_bytes() for p in paths if (self.root / p).is_file()}
        result = {}
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(0, len(paths), 200):
                batch = paths[i : i + 200]
                targets = {p: Path(tmp) / str(i + j) for j, p in enumerate(batch)}
                self.api.download_bucket_files(
                    self.bucket_id,
                    [(self._remote(p), str(t)) for p, t in targets.items()],
                    raise_on_missing_files=False,
                )
                result.update({p: t.read_bytes() for p, t in targets.items() if t.is_file()})
        return result

    def write(self, files):
        if not files:
            return
        if not self.is_bucket:
            for path, data in files.items():
                (self.root / path).parent.mkdir(parents=True, exist_ok=True)
                (self.root / path).write_bytes(data)
            return
        items = list(files.items())
        for i in range(0, len(items), 100):
            self.api.batch_bucket_files(
                self.bucket_id, add=[(data, self._remote(p)) for p, data in items[i : i + 100]]
            )

    def delete(self, paths):
        paths = list(paths)
        if not paths:
            return
        if not self.is_bucket:
            for p in paths:
                (self.root / p).unlink(missing_ok=True)
            return
        for i in range(0, len(paths), 500):
            self.api.batch_bucket_files(self.bucket_id, delete=[self._remote(p) for p in paths[i : i + 500]])


class LanguageState:
    """Tracker and block cache of one library/language, stored in the translation bucket."""

    def __init__(self, store, library, language):
        self.store = store
        self.dir = f"{STATE_DIR}/{library}/{language}"
        files = store.read([f"{self.dir}/tracker.json", f"{self.dir}/cache.json.gz"])
        self.tracker = json.loads(files.get(f"{self.dir}/tracker.json", b'{"format": 1, "versions": {}}'))
        self.cache = (
            json.loads(gzip.decompress(files[f"{self.dir}/cache.json.gz"]))
            if f"{self.dir}/cache.json.gz" in files
            else {}
        )
        self._cache_size = len(self.cache)

    def version(self, version):
        return self.tracker["versions"].setdefault(version, {"files": {}, "frozen": False})

    def save(self):
        files = {f"{self.dir}/tracker.json": json.dumps(self.tracker, ensure_ascii=False, indent=1).encode()}
        if len(self.cache) != self._cache_size:
            files[f"{self.dir}/cache.json.gz"] = gzip.compress(json.dumps(self.cache, ensure_ascii=False).encode())
            self._cache_size = len(self.cache)
        self.store.write(files)


def translate_page(page, translator, library, version, language, workers=8):
    """
    Translate a built page. Returns `(html, failed_blocks, (english_title, translated_title))`.
    A block that cannot be translated stays in English.
    """
    metadata, body = th.split_page(page)
    blocks = th.find_blocks(body)

    def work(block):
        try:
            if th.is_static(body, block):
                markup, elements = th.to_markup(body[block.start : block.end])
                return [(block.start, block.end, th.from_markup(translator.translate_markup(markup), elements))]
            return th.replace_text_nodes(block, translator.translate_segments(th.segments(body, block)))
        except TranslationFailed as exc:
            print(f"  kept in English ({exc}): {th.visible_text(body[block.start : block.end])[:80]!r}")
            return None

    with ThreadPoolExecutor(workers) as pool:
        results = list(pool.map(work, blocks))

    edits, titles, failed = [], {}, 0
    for block, block_edits in zip(blocks, results, strict=True):
        if block_edits is None:
            failed += 1
            continue
        edits.extend(block_edits)
        if block.anchor:
            inner = th.apply_edits(body[: block.end], [e for e in block_edits if block.start <= e[0] < block.end])[
                block.start :
            ]
            titles[block.anchor] = th.visible_text(inner)

    english_title = th.page_title(metadata)
    body = th.rewrite_links(th.apply_edits(body, edits), library, version, language)
    metadata = th.translate_metadata(metadata, titles)
    return metadata + "\n" + body, failed, (english_title, th.page_title(metadata))


def translate_toctree(source, page_titles, translator):
    """Same structure as the English toctree; titles of page entries reuse the page's translated title."""
    tree = yaml.safe_load(source)

    def visit(items):
        for item in items or []:
            title = item.get("title")
            if isinstance(title, str) and title.strip():
                pair = page_titles.get(item.get("local"))
                if pair and pair[0] == title and pair[1]:
                    item["title"] = pair[1]
                else:
                    try:
                        item["title"] = translator.translate_segments([{"id": 0, "text": title}])["0"].strip() or title
                    except TranslationFailed:
                        pass
            visit(item.get("sections"))

    visit(tree)
    translated = yaml.safe_dump(tree, allow_unicode=True, sort_keys=False)
    # never publish a sidebar that moon-landing can't render
    check = yaml.safe_load(translated)
    if json.dumps(_strip_titles(check)) != json.dumps(_strip_titles(yaml.safe_load(source))):
        raise ValueError("Translated toctree changed structure")
    return translated.encode()


def _strip_titles(node):
    if isinstance(node, list):
        return [_strip_titles(n) for n in node]
    if isinstance(node, dict):
        return {k: _strip_titles(v) for k, v in node.items() if k != "title"}
    return node


def translate_version(source, target, state, translator, library, version, language, max_pages=None, workers=8):
    """Bring `<library>/<version>/<language>` in the target up to date with the English build."""
    src_dir, dst_dir = f"{library}/{version}/en", f"{library}/{version}/{language}"
    record = state.version(version)
    tracked = record["files"]
    english = source.walk(src_dir)
    if not english:
        print(f"{src_dir}: no English build, skipping")
        return

    def outdated(path):
        entry = tracked.get(path)
        return entry is None or entry["source"] != english[path] or not entry.get("complete", True)

    pages = sorted(p for p in english if p.endswith(".html") and outdated(p))
    copies = sorted(
        p for p in english if (PurePosixPath(p).suffix in COPIED_SUFFIXES or p in COPIED_NAMES) and outdated(p)
    )
    if max_pages is not None:
        pages = pages[:max_pages]
    print(f"{dst_dir}: {len(pages)} pages to translate, {len(copies)} files to copy")

    copied = {path[len(src_dir) + 1 :]: data for path, data in source.read(f"{src_dir}/{p}" for p in copies).items()}
    target.write({f"{dst_dir}/{rel}": data for rel, data in copied.items()})
    for rel in copied:
        tracked[rel] = {"source": english[rel], "complete": True}

    pending = {}
    for i, path in enumerate(pages, 1):
        page = source.read([f"{src_dir}/{path}"]).get(f"{src_dir}/{path}")
        if page is None:
            continue
        text = page.decode("utf-8")
        if not th.is_hydration_safe(th.split_page(text)[1]):
            # built before huggingface/doc-builder#851: the translation would be replaced by English on load
            print(f"  [{i}/{len(pages)}] {path}: built by an older doc-builder, waiting for a rebuild")
            tracked[path] = {"source": english[path], "complete": False, "reason": "not hydration-safe"}
            continue
        html, failed, title = translate_page(text, translator, library, version, language, workers)
        pending[f"{dst_dir}/{path}"] = html.encode()
        tracked[path] = {"source": english[path], "complete": failed == 0, "title": list(title)}
        print(f"  [{i}/{len(pages)}] {path}: {'ok' if not failed else f'{failed} blocks kept in English'}")
        if len(pending) >= FLUSH_EVERY:
            target.write(pending)
            pending = {}
            state.save()
    target.write(pending)

    if "_toctree.yml" in english:
        page_titles = {
            str(PurePosixPath(p).with_suffix("")): tuple(e["title"]) for p, e in tracked.items() if e.get("title")
        }
        toctree = source.read([f"{src_dir}/_toctree.yml"])[f"{src_dir}/_toctree.yml"]
        translated = translate_toctree(toctree, page_titles, translator)
        digest = hashlib.sha256(translated).hexdigest()
        if record.get("toctree") != digest:
            target.write({f"{dst_dir}/_toctree.yml": translated})
            record["toctree"] = digest

    # Pages removed from the English build disappear from the translation too.
    existing = target.walk(dst_dir)
    stale = sorted(p for p in existing if p not in english and p != "_toctree.yml")
    if stale:
        print(f"{dst_dir}: deleting {len(stale)} pages removed from the English build")
        target.delete(f"{dst_dir}/{p}" for p in stale)
    record["files"] = {p: e for p, e in tracked.items() if p in english}

    done = all(e.get("complete", True) for e in record["files"].values()) and set(record["files"]) >= {
        p for p in english if p.endswith(".html")
    }
    if version != "main" and done:
        record["frozen"] = True
        print(f"{dst_dir}: complete, frozen")
    state.save()


def release_versions(source, library):
    data = source.read([f"{library}/_versions.yml"]).get(f"{library}/_versions.yml")
    versions = [v["version"] for v in yaml.safe_load(data) or []] if data else []
    return [v for v in versions if v not in ("main", "master")]


def translate_library(
    source, target, library, language, token=None, versions=None, max_pages=None, workers=8, complete=None
):
    state = LanguageState(target, library, language)
    releases = release_versions(source, library)
    if "baseline_versions" not in state.tracker:
        # No backfill: releases published before this language was enabled stay untranslated.
        state.tracker["baseline_versions"] = releases
    baseline = set(state.tracker["baseline_versions"])
    if versions is None:
        versions = ["main"] + [v for v in releases if v not in baseline and not state.version(v).get("frozen")]
    translator = Translator(language, state.cache, complete=complete, token=token)
    try:
        for version in versions:
            translate_version(source, target, state, translator, library, version, language, max_pages, workers)
    finally:
        state.save()
        print(f"{library}/{language}: {translator.model_calls} model calls")


def translate_docs(target_url, source_url=SOURCE_BUCKET, translations=None, token=None, **kwargs):
    source, target = Store(source_url, token), Store(target_url, token)
    for library, languages in (translations or TRANSLATED_DOCS).items():
        for language in languages:
            translate_library(source, target, library, language, token=token, **kwargs)
