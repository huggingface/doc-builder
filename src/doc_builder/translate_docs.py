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
huggingface.co and writes translated pages next to them, to `<library>/<version>/<language>/`, so
moon-landing serves them like any other language. A language folder with its own `_app/` comes from the
library's own docs build (a human translation, the workflows' former `languages` input). Those of `main` are deleted
before its first machine translation; any other is never touched.

Like `populate-search-engine --incremental`, every run diffs against a tracker:

- `main` is checked on every run; only English pages whose content changed are translated
  again, and pages deleted from the English build are deleted from the translation.
- A release version is translated once, then frozen. Releases that already existed when a
  language was first translated are never backfilled.
- Translations are cached per block, so a page whose HTML changed (e.g. after a doc-builder
  update that changes every page's asset hashes) only sends its edited paragraphs to the model.
- A page with blocks kept in English (answers that failed validation) is retried on the next
  runs, up to `MAX_TRIES` translations of the same English; after that only an English change retries it.

State lives in the doc bucket under `.translation/<library>/<language>/`.
"""

import gzip
import hashlib
import json
import os
import re
import shutil
import tempfile
import warnings
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from urllib.parse import quote

import yaml

from . import translate_html as th
from .translate_md import translate_md
from .translate_model import BILL_TO, TranslationFailed, Translator

# Served by huggingface.co: English builds are read from it, translations are written to it.
DOC_BUCKET = "hf://buckets/hf-doc-build/doc"
# Libraries and languages translated by the scheduled job.
TRANSLATED_DOCS = {
    "hub": ["zh", "ja", "ko", "pt", "es", "fr", "vi", "id", "tr", "ru", "ar"],
    "lerobot": ["zh", "ja", "ko", "pt", "es", "fr", "vi", "id", "tr", "ru", "ar"],
}
# Copied unchanged from the English build. Pages (`.html`) and their Markdown (`.md`, served for
# "Copy page" and `Accept: text/plain`) are translated; llms.txt and llms-full.txt are rebuilt from
# the translated Markdown.
COPIED_SUFFIXES = set()
COPIED_NAMES = {"_redirects.yml"}
LLMS_FEEDS = ("llms.txt", "llms-full.txt")
STATE_DIR = ".translation"
FLUSH_EVERY = 20  # pages; bounds the work lost if a run is interrupted
# Translations of the same English page while some of its blocks fail: past that, the model keeps getting them wrong.
MAX_TRIES = 3
# Bump when `translate_html.find_blocks` finds prose it used to skip (2: raw HTML outside paragraphs and lists),
# so translated pages are processed again; their other blocks come from the cache.
BLOCKS_VERSION = 2
# Above this share of blocks kept in English, a run fails: something is systematically wrong (model, prompt, provider).
MAX_ENGLISH_BLOCKS = 0.1


@dataclass
class RunStats:
    """What a run translated, and what it could not: a successful run can still leave English in pages."""

    pages: int = 0
    blocks: int = 0
    english_blocks: int = 0
    incomplete: list[tuple[str, int, int]] = field(default_factory=list)  # (page, english blocks, blocks)
    waiting: list[str] = field(default_factory=list)  # pages built before #851, waiting for a rebuild

    def failed(self):
        return self.blocks > 0 and self.english_blocks / self.blocks > MAX_ENGLISH_BLOCKS

    def report(self):
        """Print the summary; on GitHub Actions also annotate the run and write the job summary."""
        lines = [
            f"Translated {self.pages} pages: {self.blocks - self.english_blocks}/{self.blocks} blocks,"
            f" {self.english_blocks} kept in English; {len(self.waiting)} pages waiting for a rebuild."
        ]
        lines += [f"- {page}: {english}/{blocks} blocks kept in English" for page, english, blocks in self.incomplete]
        lines += [f"- {page}: built before huggingface/doc-builder#851, not translated" for page in self.waiting]
        print("\n".join(lines))
        if os.environ.get("GITHUB_ACTIONS") != "true":
            return
        if self.incomplete or self.waiting:
            print(
                f"::warning title=Incomplete translations::{len(self.incomplete)} pages keep English blocks and"
                f" {len(self.waiting)} pages are waiting for a rebuild; they are retried on the next run."
                " See the job summary."
            )
        if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(summary, "a", encoding="utf-8") as f:
                f.write("### Translation\n\n" + "\n".join(lines) + "\n")


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

    def folders(self, directory):
        """Names of the folders directly in `directory`."""
        if not self.is_bucket:
            root = self.root / directory
            return sorted(p.name for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
        from huggingface_hub import BucketFolder

        base = self._remote(directory).rstrip("/") + "/"
        return sorted(
            PurePosixPath(entry.path).name
            for entry in self.api.list_bucket_tree(self.bucket_id, prefix=base, recursive=False)
            if isinstance(entry, BucketFolder)
        )

    def has_folder(self, directory, name):
        return name in self.folders(directory)

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
        from huggingface_hub import BucketFolder

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
                with warnings.catch_warnings():  # missing files are expected: read returns what exists
                    warnings.simplefilter("ignore")
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

    def delete_folder(self, directory):
        """Delete `directory` and everything in it, `_app` included. Returns the number of files deleted."""
        if not self.is_bucket:
            root = self.root / directory
            count = sum(p.is_file() for p in root.rglob("*"))
            shutil.rmtree(root, ignore_errors=True)
            return count
        from huggingface_hub import BucketFolder

        base = self._remote(directory).rstrip("/") + "/"
        paths = [
            f"{directory}/{entry.path[len(base) :]}"
            for entry in self.api.list_bucket_tree(self.bucket_id, prefix=base, recursive=True)
            if not isinstance(entry, BucketFolder)
        ]
        self.delete(paths)
        return len(paths)


class LanguageState:
    """Tracker and block cache of one library/language, stored in the doc bucket."""

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
    Translate a built page. Returns `(html, (blocks, blocks_kept_in_english), (english_title, translated_title))`.
    A block that cannot be translated stays in English.
    """
    metadata, body = th.split_page(page)
    blocks = th.find_blocks(body)

    def work(block):
        try:
            if th.is_static(body, block):
                region, frozen = (block.start, block.end), False
            else:
                # docstring parameters and headings: their {@html} content may still be reordered
                region, frozen = th.html_region(body, block), True
            if region:
                markup, elements = th.to_markup(body[region[0] : region[1]], freeze_leading_strong=frozen)
                return [(*region, th.from_markup(translator.translate_markup(markup), elements))]
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
    return metadata + "\n" + body, (len(blocks), failed), (english_title, th.page_title(metadata))


def translate_toctree(source, page_titles, translator, untranslated=()):
    """
    Same structure as the English toctree; titles of page entries reuse the page's translated title.
    Entries of `untranslated` pages (not translated yet) keep their English title, like the page.
    """
    tree = yaml.safe_load(source)

    def visit(items):
        for item in items or []:
            title = item.get("title")
            if isinstance(title, str) and title.strip():
                pair = page_titles.get(item.get("local"))
                if pair and pair[0] == title and pair[1]:
                    item["title"] = pair[1]
                elif item.get("local") not in untranslated:
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


def llms_pages(llms, pages):
    """The `pages` (Markdown paths) an English llms.txt links to, in its order, and the base URL of its links."""
    order, base = [], None
    # a feed written on Windows has CRLF line endings
    for url in re.findall(r"^- \[.*\]\((\S+)\)$", llms.replace("\r\n", "\n"), re.M):
        # the longest match: ".../xet/index.md" also ends with "/index.md"
        page = max((p for p in pages if url.endswith("/" + quote(p, safe="/"))), key=len, default=None)
        if page and page not in order:
            order.append(page)
            base = base or url[: -len(quote(page, safe="/")) - 1]
    return order, base


def latest_build(source, src_dir, english):
    """
    `english` without the pages of earlier builds: the bucket keeps pages that were removed from the
    docs (nothing deletes them, and they are never rebuilt). The English llms.txt lists the latest build's pages.
    """
    if "llms.txt" not in english:
        return english
    llms = source.read([f"{src_dir}/llms.txt"])[f"{src_dir}/llms.txt"].decode("utf-8")
    listed, _ = llms_pages(llms, [p for p in english if p.endswith(".md")])
    if not listed:
        return english
    built = {str(PurePosixPath(p).with_suffix("")) for p in listed}
    return {
        p: v
        for p, v in english.items()
        if PurePosixPath(p).suffix not in (".html", ".md") or str(PurePosixPath(p).with_suffix("")) in built
    }


def translate_llms_feeds(source, target, src_dir, dst_dir, library, english):
    """
    Rebuild llms.txt and llms-full.txt of a translated folder from its translated Markdown, with
    doc-builder's own generator: the English pages in the English order, translated titles and
    content, and URLs pointing to the translated Markdown (`<english base>/<language>/<page>.md`).
    """
    from .utils import write_llms_feeds

    language = PurePosixPath(dst_dir).name
    llms = source.read([f"{src_dir}/llms.txt"])[f"{src_dir}/llms.txt"].decode("utf-8")
    pages = [p for p in english if p.endswith(".md")]
    order, base = llms_pages(llms, pages)
    order = order or sorted(pages)
    translated = target.read(f"{dst_dir}/{p}" for p in order)
    # a page whose Markdown isn't translated yet (e.g. a partial run) keeps its English text
    fallback = source.read(f"{src_dir}/{p}" for p in order if f"{dst_dir}/{p}" not in translated)
    items = [
        (p, (translated.get(f"{dst_dir}/{p}") or fallback.get(f"{src_dir}/{p}") or b"").decode("utf-8")) for p in order
    ]
    with tempfile.TemporaryDirectory() as directory:
        write_llms_feeds(
            Path(directory),
            items,
            base_url=f"{base}/{language}" if base else None,
            package_name=library,
            language=language,
            is_python_module=False,
        )
        return {
            name: (Path(directory) / name).read_bytes() for name in LLMS_FEEDS if (Path(directory) / name).exists()
        }


def clear_docs_build_translations(target, library, language):
    """
    Before the first machine translation of `<library>/main` into `language`, delete the translations of `main` built
    by the library's docs build: `main` builds no longer update them (huggingface/doc-builder#870), and they would
    clash with the machine translation, in its folder or next to it (e.g. `cn` or `zh-CN` next to `zh`).
    """
    main = f"{library}/main"
    # the other configured languages run in parallel jobs, each clearing its own folder
    others = {"en", *TRANSLATED_DOCS.get(library, ())} - {language}
    for name in target.folders(main):
        # nothing in this language's folder is ours yet; elsewhere, only folders of a docs build (never a translation)
        if name == language or (name not in others and target.has_folder(f"{main}/{name}", "_app")):
            count = target.delete_folder(f"{main}/{name}")
            print(f"{main}/{name}: deleted the translation built by the docs build ({count} files)")


def translate_version(source, target, state, translator, library, version, language, stats, max_pages=None, workers=8):
    """Bring `<library>/<version>/<language>` in the target up to date with the English build."""
    src_dir, dst_dir = f"{library}/{version}/en", f"{library}/{version}/{language}"
    english = source.walk(src_dir)
    if not english:
        print(f"{src_dir}: no English build, skipping")
        return
    # pages left over from earlier builds are treated as removed: not translated, and their translation is deleted
    english = latest_build(source, src_dir, english)
    if version == "main" and version not in state.tracker["versions"]:
        clear_docs_build_translations(target, library, language)
    record = state.version(version)
    tracked = record["files"]
    # docs builds ship their own JS in `_app/`; translations reuse the English one
    if target.has_folder(dst_dir, "_app"):
        print(f"{dst_dir}: built by the library's docs build, skipping")
        return

    def outdated(path):
        entry = tracked.get(path)
        if entry is None or entry["source"] != english[path]:
            return True
        if path.endswith(".html") and entry.get("blocks", 1) < BLOCKS_VERSION:
            return True
        return not entry.get("complete", True) and entry.get("tries", 0) < MAX_TRIES

    def tries(path):
        """Translations of the current English of `path` with blocks kept in English, this one included."""
        previous = tracked.get(path)
        return (previous.get("tries", 0) if previous and previous["source"] == english[path] else 0) + 1

    pages = sorted(p for p in english if p.endswith(".html") and outdated(p))
    markdown = sorted(p for p in english if p.endswith(".md") and outdated(p))
    copies = sorted(
        p for p in english if (PurePosixPath(p).suffix in COPIED_SUFFIXES or p in COPIED_NAMES) and outdated(p)
    )
    if max_pages is not None:
        pages = pages[:max_pages]
        markdown = [p for p in markdown if p[: -len(".md")] + ".html" in pages]
    given_up = sum(not outdated(p) and not tracked[p].get("complete", True) for p in english if p in tracked)
    print(
        f"{dst_dir}: {len(pages)} pages and {len(markdown)} Markdown files to translate, {len(copies)} files to copy"
        + (f"; {given_up} keep English blocks after {MAX_TRIES} tries" if given_up else "")
    )

    copied = {path[len(src_dir) + 1 :]: data for path, data in source.read(f"{src_dir}/{p}" for p in copies).items()}
    target.write({f"{dst_dir}/{rel}": data for rel, data in copied.items()})
    for rel in copied:
        tracked[rel] = {"source": english[rel], "complete": True}

    pending = {}  # path -> (translated page, tracker entry)
    toctree = (
        source.read([f"{src_dir}/_toctree.yml"])[f"{src_dir}/_toctree.yml"] if "_toctree.yml" in english else None
    )

    def write_toctree():
        page_titles = {
            str(PurePosixPath(p).with_suffix("")): tuple(e["title"]) for p, e in tracked.items() if e.get("title")
        }
        html_pages = {str(PurePosixPath(p).with_suffix("")) for p in english if p.endswith(".html")}
        translated = translate_toctree(toctree, page_titles, translator, untranslated=html_pages - set(page_titles))
        digest = hashlib.sha256(translated).hexdigest()
        if record.get("toctree") != digest:
            target.write({f"{dst_dir}/_toctree.yml": translated})
            record["toctree"] = digest

    def flush():
        # A page is only recorded once its upload succeeded: an interrupted upload is retried next run.
        target.write({f"{dst_dir}/{p}": html for p, (html, _) in pending.items()})
        tracked.update({p: entry for p, (_, entry) in pending.items()})
        pending.clear()
        if toctree is not None:
            # updated with every batch of pages, so a partly translated folder already has its sidebar
            write_toctree()
        state.save()

    try:
        for i, path in enumerate(pages, 1):
            page = source.read([f"{src_dir}/{path}"]).get(f"{src_dir}/{path}")
            if page is None:
                continue
            text = page.decode("utf-8")
            if not th.is_hydration_safe(th.split_page(text)[1]):
                # built before huggingface/doc-builder#851: the translation would be replaced by English on load
                print(f"  [{i}/{len(pages)}] {path}: built by an older doc-builder, waiting for a rebuild")
                tracked[path] = {"source": english[path], "complete": False, "reason": "not hydration-safe"}
                stats.waiting.append(f"{dst_dir}/{path}")
                continue
            html, (blocks, failed), title = translate_page(text, translator, library, version, language, workers)
            entry = {"source": english[path], "complete": failed == 0, "title": list(title), "blocks": BLOCKS_VERSION}
            if failed:
                entry.update(english_blocks=failed, tries=tries(path))
                stats.incomplete.append((f"{dst_dir}/{path}", failed, blocks))
            pending[path] = (html.encode(), entry)
            stats.pages += 1
            stats.blocks += blocks
            stats.english_blocks += failed
            print(
                f"  [{i}/{len(pages)}] {path}: {'ok' if not failed else f'{failed}/{blocks} blocks kept in English'}"
            )
            if len(pending) >= FLUSH_EVERY:
                flush()

        for i, path in enumerate(markdown, 1):
            data = source.read([f"{src_dir}/{path}"]).get(f"{src_dir}/{path}")
            if data is None:
                continue
            md, blocks, failed = translate_md(
                data.decode("utf-8"), translator.translate_markup, library, version, language, workers
            )
            entry = {"source": english[path], "complete": failed == 0}
            if failed:
                entry.update(english_blocks=failed, tries=tries(path))
                stats.incomplete.append((f"{dst_dir}/{path}", failed, blocks))
            pending[path] = (md.encode(), entry)
            stats.pages += 1
            stats.blocks += blocks
            stats.english_blocks += failed
            print(
                f"  [{i}/{len(markdown)}] {path}: {'ok' if not failed else f'{failed}/{blocks} blocks kept in English'}"
            )
            if len(pending) >= FLUSH_EVERY:
                flush()
    finally:
        # pages finished before an error (e.g. rate limiting that outlasts the retries) are kept
        flush()

    if "llms.txt" in english and (markdown or record.get("llms_source") != english["llms.txt"]):
        feeds = translate_llms_feeds(source, target, src_dir, dst_dir, library, english)
        digest = hashlib.sha256(b"".join(feeds.values())).hexdigest()
        if record.get("llms") != digest:
            target.write({f"{dst_dir}/{name}": data for name, data in feeds.items()})
            record["llms"] = digest
        record["llms_source"] = english["llms.txt"]

    # Pages removed from the English build disappear from the translation too (only files this job wrote).
    existing = target.walk(dst_dir)
    stale = sorted(p for p in existing if p not in english and p in tracked)
    if stale:
        print(f"{dst_dir}: deleting {len(stale)} pages removed from the English build")
        target.delete(f"{dst_dir}/{p}" for p in stale)
    record["files"] = {p: e for p, e in tracked.items() if p in english}

    settled = all(e.get("complete", True) or e.get("tries", 0) >= MAX_TRIES for e in record["files"].values())
    done = settled and set(record["files"]) >= {p for p in english if p.endswith(".html")}
    if version != "main" and done:
        record["frozen"] = True
        print(f"{dst_dir}: complete, frozen")
    state.save()


def release_versions(source, library):
    data = source.read([f"{library}/_versions.yml"]).get(f"{library}/_versions.yml")
    versions = [v["version"] for v in yaml.safe_load(data) or []] if data else []
    return [v for v in versions if v not in ("main", "master")]


def translate_library(
    source,
    target,
    library,
    language,
    token=None,
    versions=None,
    max_pages=None,
    workers=8,
    complete=None,
    bill_to=BILL_TO,
    stats=None,
):
    """Returns the `RunStats` of this library/language (accumulated into `stats` if given)."""
    stats = stats if stats is not None else RunStats()
    state = LanguageState(target, library, language)
    releases = release_versions(source, library)
    if "baseline_versions" not in state.tracker:
        # No backfill: releases published before this language was enabled stay untranslated.
        state.tracker["baseline_versions"] = releases
    baseline = set(state.tracker["baseline_versions"])
    if versions is None:
        versions = ["main"] + [v for v in releases if v not in baseline and not state.version(v).get("frozen")]
    translator = Translator(language, state.cache, complete=complete, token=token, bill_to=bill_to)
    try:
        for version in versions:
            translate_version(source, target, state, translator, library, version, language, stats, max_pages, workers)
    finally:
        state.save()
        print(f"{library}/{language}: {translator.model_calls} model calls")
    return stats


def translate_docs(target_url, inference_token, source_url=DOC_BUCKET, translations=None, token=None, **kwargs):
    """
    Translate every configured library/language; returns the `RunStats` of the whole run.
    `token` reads and writes the buckets; `inference_token` calls the model on HF Inference Providers.
    """
    source, target = Store(source_url, token), Store(target_url, token)
    stats = RunStats()
    for library, languages in (translations or TRANSLATED_DOCS).items():
        for language in languages:
            translate_library(source, target, library, language, token=inference_token, stats=stats, **kwargs)
    stats.report()
    return stats
