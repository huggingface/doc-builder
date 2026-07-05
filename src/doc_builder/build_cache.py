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
Page-level HTML build cache for `doc-builder build --html`.

Building the HTML docs of a large library (e.g. transformers) prerenders hundreds of
pages even when a commit only changed one of them. This module caches each built page
keyed by the content that produced it, so subsequent builds only run the SvelteKit
build for pages whose content actually changed.

Design:

- A page's cache key is `sha256` of its **generated mdx content** (i.e. after autodoc
  and internal-link resolution, so docstring changes from library code invalidate
  exactly the affected pages), the **kit tree hash** (any component/dependency change
  invalidates everything), the doc-builder version and the language.
- The mdx content is *version-normalized* before hashing: resolved internal links and
  base paths embed `/docs/{package}/{version}/{language}/`, which would make otherwise
  identical pages differ between e.g. `main` and `pr_123` builds. The version segment
  is replaced with a placeholder so those pages share a key.
- The cache stores a manifest per `(package, language)` mapping each page to
  `{key, blob, source_version}`, plus content-addressed HTML blobs.
- On a same-version hit, the cached HTML is reused byte-identical. On a cross-version
  hit, page-URL occurrences of the source base path are rewritten to the current
  version, while asset URLs (`.../_app/...`) stay pinned to the source version: the
  serving bucket is additive, so the source version's content-hashed assets remain
  hosted, and chunk-to-chunk imports resolve relative to the chunk's own URL.
- Storage backends: a local directory (used in tests / local builds) or a Hugging Face
  storage bucket (`hf://buckets/...`, see https://huggingface.co/docs/hub/storage-buckets).
- Cache failures are never fatal: any error degrades to building the affected pages.

Security note: cache writes should only be enabled on trusted builds (e.g. main-branch
builds). PR builds should be read-only so that a malicious PR cannot poison pages that
a later trusted build would reuse.
"""

import hashlib
import json
import re
import shutil
import tempfile
import traceback
from dataclasses import dataclass
from pathlib import Path

from . import __version__

VERSION_PLACEHOLDER = "__DOC_BUILDER_VERSION__"

# node_modules etc. are not part of the staged kit (see commands/build.py) and local
# build artifacts must not influence the cache key
KIT_HASH_IGNORE_DIRS = {"node_modules", ".svelte-kit", "build"}


def hash_kit_tree(kit_folder):
    """
    Deterministic hash of the kit folder contents (everything that is staged for the
    SvelteKit build: sources, preprocessors, configs, lockfile).
    """
    kit_folder = Path(kit_folder)
    sha = hashlib.sha256()
    files = [
        f
        for f in sorted(kit_folder.rglob("*"))
        if f.is_file() and not any(part in KIT_HASH_IGNORE_DIRS for part in f.relative_to(kit_folder).parts)
    ]
    for f in files:
        sha.update(f.relative_to(kit_folder).as_posix().encode("utf-8"))
        sha.update(b"\0")
        sha.update(f.read_bytes())
        sha.update(b"\0")
    return sha.hexdigest()


def normalize_version(text, package, version, language):
    """
    Replaces the versioned doc base path (embedded by internal-link resolution and the
    SvelteKit base path) with a placeholder, so content that only differs by the built
    version compares equal.
    """
    return text.replace(f"/docs/{package}/{version}/{language}/", f"/docs/{package}/{VERSION_PLACEHOLDER}/{language}/")


def page_cache_key(mdx_content, kit_hash, package, version, language):
    """
    Cache key for one page. `mdx_content` is the final generated mdx (post autodoc and
    link resolution).
    """
    normalized = normalize_version(mdx_content, package, version, language)
    sha = hashlib.sha256()
    for part in (normalized, kit_hash, package, language, __version__):
        sha.update(part.encode("utf-8"))
        sha.update(b"\0")
    return sha.hexdigest()


def rewrite_cached_html(html, package, source_version, target_version, language):
    """
    Rewrites a cached page built for `source_version` so it can be served under
    `target_version`: page URLs (resolved internal links, SvelteKit base config,
    metadata) move to the target version, while asset URLs (`.../_app/...`) keep
    pointing at the source version, whose content-hashed assets remain hosted.
    """
    if source_version == target_version:
        return html
    source_base = f"/docs/{package}/{source_version}/{language}/"
    target_base = f"/docs/{package}/{target_version}/{language}/"
    # negative lookahead: leave asset URLs on the source version
    return re.sub(re.escape(source_base) + r"(?!_app/)", target_base.replace("\\", r"\\\\"), html)


@dataclass
class FetchedPage:
    page: str  # rel mdx posix path, e.g. "quicktour.mdx"
    html_path: Path  # local path of the fetched (and possibly rewritten) html
    source_version: str


class PageCache:
    """
    Page-level HTML cache over a local directory or an HF storage bucket.

    Layout under the cache root:
        <package>/<language>/manifest.json
        blobs/<key[:2]>/<key>.html
    """

    def __init__(self, cache_url, package, version, language, write=False):
        self.package = package
        self.version = version
        self.language = language
        self.write = write
        self.is_bucket = cache_url.startswith("hf://")
        self.cache_url = cache_url.rstrip("/")
        if not self.is_bucket:
            Path(self.cache_url).mkdir(parents=True, exist_ok=True)
        self._workdir = Path(tempfile.mkdtemp(prefix="doc_builder_page_cache_"))

    # ------------------------------------------------------------------ paths
    @property
    def _manifest_rel(self):
        return f"{self.package}/{self.language}/manifest.json"

    def _blob_rel(self, key):
        return f"blobs/{key[:2]}/{key}.html"

    # ---------------------------------------------------------------- backend
    def _bucket_id_and_prefix(self):
        # hf://buckets/<owner>/<bucket>[/<prefix>]
        parts = self.cache_url.removeprefix("hf://buckets/").split("/")
        bucket_id = "/".join(parts[:2])
        prefix = "/".join(parts[2:])
        return bucket_id, prefix

    def _remote_path(self, rel):
        _, prefix = self._bucket_id_and_prefix()
        return f"{prefix}/{rel}" if prefix else rel

    def _download(self, rel_paths, dest_paths):
        """Downloads `rel_paths` to `dest_paths`. Returns the successfully fetched indices."""
        if not rel_paths:
            return []
        if not self.is_bucket:
            fetched = []
            for i, (rel, dest) in enumerate(zip(rel_paths, dest_paths, strict=True)):
                src = Path(self.cache_url) / rel
                if src.is_file():
                    Path(dest).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src, dest)
                    fetched.append(i)
            return fetched
        from huggingface_hub import download_bucket_files

        bucket_id, _ = self._bucket_id_and_prefix()
        for dest in dest_paths:
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
        try:
            download_bucket_files(
                bucket_id,
                files=[(self._remote_path(rel), str(dest)) for rel, dest in zip(rel_paths, dest_paths, strict=True)],
            )
        except Exception:
            # transient error: fall back to per-file downloads
            for rel, dest in zip(rel_paths, dest_paths, strict=True):
                try:
                    download_bucket_files(bucket_id, files=[(self._remote_path(rel), str(dest))])
                except Exception:
                    pass
        # `download_bucket_files` skips files missing on the remote instead of raising,
        # so report success based on what actually landed on disk
        return [i for i, dest in enumerate(dest_paths) if Path(dest).is_file()]

    def _upload(self, items):
        """Uploads `(local_path, rel_path)` pairs."""
        if not items:
            return
        if not self.is_bucket:
            for local, rel in items:
                dest = Path(self.cache_url) / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(local, dest)
            return
        from huggingface_hub import batch_bucket_files

        bucket_id, _ = self._bucket_id_and_prefix()
        batch_bucket_files(bucket_id, add=[(str(local), self._remote_path(rel)) for local, rel in items])

    # ----------------------------------------------------------------- public
    def load_manifest(self):
        """
        Returns the manifest for this package/language: `{page: {key, blob, source_version}}`.
        Empty on any failure (treated as a cold cache).
        """
        try:
            dest = self._workdir / "manifest.json"
            fetched = self._download([self._manifest_rel], [dest])
            if not fetched:
                return {}
            return json.loads(dest.read_text(encoding="utf-8"))
        except Exception:
            print("[page-cache] could not load the cache manifest, treating the cache as cold")
            traceback.print_exc()
            return {}

    def fetch_pages(self, wanted, manifest):
        """
        `wanted` is `{page: key}` for the current build. Fetches every page whose key
        matches the manifest and returns `{page: FetchedPage}` for the successful ones.
        Cross-version entries are rewritten for the current version.
        """
        hits = {
            page: manifest[page]
            for page, key in wanted.items()
            if page in manifest and manifest[page].get("key") == key
        }
        if not hits:
            return {}
        try:
            pages = list(hits.keys())
            rel_paths = [self._blob_rel(hits[page]["blob"]) for page in pages]
            dest_paths = [self._workdir / "fetched" / page for page in pages]
            fetched_indices = self._download(rel_paths, dest_paths)
            fetched = {}
            for i in fetched_indices:
                page = pages[i]
                entry = hits[page]
                source_version = entry.get("source_version", self.version)
                if source_version != self.version:
                    html = dest_paths[i].read_text(encoding="utf-8")
                    html = rewrite_cached_html(html, self.package, source_version, self.version, self.language)
                    dest_paths[i].write_text(html, encoding="utf-8")
                fetched[page] = FetchedPage(page=page, html_path=dest_paths[i], source_version=source_version)
            return fetched
        except Exception:
            print("[page-cache] fetching cached pages failed, building all pages")
            traceback.print_exc()
            return {}

    def store_pages(self, built, manifest, reused):
        """
        Uploads freshly built pages and the updated manifest (only when `write=True`).

        - `built` is `{page: (key, html_path)}` for pages built in this run.
        - `manifest` is the previously loaded manifest.
        - `reused` is `{page: FetchedPage}` for cache hits merged into this build.
        """
        if not self.write:
            return
        try:
            uploads = []
            new_manifest = {}
            for page in reused:
                new_manifest[page] = dict(manifest[page])
            for page, (key, html_path) in built.items():
                blob = key
                uploads.append((html_path, self._blob_rel(blob)))
                new_manifest[page] = {"key": key, "blob": blob, "source_version": self.version}
            manifest_path = self._workdir / "manifest_out.json"
            manifest_path.write_text(json.dumps(new_manifest, indent=1, sort_keys=True), encoding="utf-8")
            uploads.append((manifest_path, self._manifest_rel))
            self._upload(uploads)
            print(f"[page-cache] stored {len(built)} built page(s) and the updated manifest")
        except Exception:
            print("[page-cache] storing built pages failed (the build itself is unaffected)")
            traceback.print_exc()
