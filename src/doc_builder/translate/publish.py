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
Getting a finished translation into the bucket without breaking what is already there.

The bucket is what the build reads, so anything written here is published. Two things follow
from that, and they are what this file exists for.

**Nothing is written until the whole tree is ready.** Pages used to be written one at a time
as they were assembled, which left the folder in a mixed state for the length of the run --
new pages sitting behind the previous run's sidebar, and a half-written tree if the job died.
The workflow's existence check is happy with a mixed tree, so it would build and publish one.
Now the tree is assembled in memory (about 3MB for transformers), checked as a whole, and
only then does anything touch the bucket.

**A warm cache does not mean the output is current.** Knowing there is no new prose to
translate says nothing about whether what is published matches the English docs. An edit that
only touches a code sample keeps every paragraph ID it had, and deleting a paragraph adds no
new ones either -- both leave the cache warm and the bucket stale. So the decision to load the
model and the decision to republish are worked out separately: the first from the segment
cache, the second from the manifest here.

The manifest records, per page, the hash of the English source it was built from and the hash
of what we published. A page is rebuilt when its source changed, when its published file is
missing or is not what we recorded, or when any of the versions below moved. That last case is
what lets a change to how pages are assembled reach the bucket on its own, instead of waiting
for someone to remember to pass --rebuild.

The manifest lives outside the published tree, because the workflow copies that tree wholesale
into `docs/source/<lang>` and it has no business in the docs.
"""

import json
import shutil
import traceback
from pathlib import Path

from .cache import sha256_text

# Bump when the shape of the manifest itself changes. An unreadable or older manifest is not an
# error -- it just means we rebuild everything, which is correct and costs no GPU.
MANIFEST_VERSION = 1

# Bump when anything about how a finished page is put together changes: assembly, the
# disclosure banner, the checks that decide whether a page is publishable. It is recorded in
# the manifest, so bumping it republishes every page from the cache on the next run with no
# GPU and nothing retranslated. PROMPT_VERSION is the equivalent for the model side, and the
# two are deliberately separate -- changing how pages are assembled should not throw away
# 14,000 paid-for translations.
OUTPUT_VERSION = "v1"

TOCTREE = "_toctree.yml"


def manifest_path(bucket, package, language):
    return Path(bucket) / "state" / package / f"{language}.json"


def load_manifest(path):
    """The last run's manifest, or an empty one if there isn't a usable one.

    Anything wrong with it means "we know nothing", which makes the run rebuild everything.
    That is the safe direction to fail in: it costs some assembly time and no GPU.
    """
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception:
        traceback.print_exc()
        print("[publish] could not read the manifest; rebuilding everything")
        return {}
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        return {}
    return manifest


def save_manifest(path, manifest):
    """Write the manifest, last of all, once the tree it describes is really in place.

    Last on purpose. If the run dies partway through publishing, the manifest still describes
    the previous tree, so it disagrees with what is on disk -- and the next run notices the
    disagreement and finishes the job. A manifest written first would instead claim the
    interrupted tree was complete.
    """
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(path)
        return True
    except Exception:
        traceback.print_exc()
        print("[publish] could not write the manifest; the next run will rebuild everything")
        return False


def build_manifest(language, model, gloss_sha, prompt_version, sources, published):
    """Describe what we just published: what it was built from, and what it came out as."""
    return {
        "manifest_version": MANIFEST_VERSION,
        "output_version": OUTPUT_VERSION,
        "prompt_version": prompt_version,
        "language": language,
        "model": model,
        "glossary": gloss_sha,
        "pages": {
            page: {"source": sha256_text(sources[page]), "output": sha256_text(text)}
            for page, text in sorted(published.items())
            if page in sources
        },
    }


def stale_reason(manifest, language, model, gloss_sha, prompt_version):
    """Is the whole published tree out of date, and if so why?

    These are the settings that affect every page at once, so there is no point comparing them
    page by page.
    """
    if not manifest:
        return "no usable manifest"
    checks = {
        "output version": (manifest.get("output_version"), OUTPUT_VERSION),
        "prompt version": (manifest.get("prompt_version"), prompt_version),
        "language": (manifest.get("language"), language),
        "model": (manifest.get("model"), model),
        "glossary": (manifest.get("glossary"), gloss_sha),
    }
    for name, (was, now) in checks.items():
        if was != now:
            return f"{name} changed: {was} -> {now}"
    return None


def live_files(out_dir):
    """Every file currently published, as paths relative to the tree."""
    out_dir = Path(out_dir)
    if not out_dir.is_dir():
        return set()
    return {p.relative_to(out_dir).as_posix() for p in out_dir.rglob("*") if p.is_file()}


def reconcile(out_dir, manifest, sources):
    """Work out what the published tree is missing, and what should not be in it.

    The published files are read rather than taken on trust. The manifest can be right about
    what we meant to publish and wrong about what is there -- an interrupted run, or anything
    else that touched the bucket -- and reading is what turns "we think this is fine" into
    "this is fine". It is one read per page against 20,000 for the segment cache, which is the
    whole reason the cache has an index and this does not need one.

    Gives back the pages to rebuild and the files to remove.
    """
    out_dir = Path(out_dir)
    recorded = manifest.get("pages", {})
    stale = set()
    for page, source in sources.items():
        entry = recorded.get(page)
        if entry is None or entry.get("source") != sha256_text(source):
            stale.add(page)
            continue
        try:
            current = (out_dir / page).read_text(encoding="utf-8")
        except OSError:
            stale.add(page)
            continue
        if sha256_text(current) != entry.get("output"):
            stale.add(page)
    orphans = live_files(out_dir) - set(sources)
    return stale, orphans


def publish_tree(out_dir, tree):
    """Write the finished tree into the bucket and take out anything that is no longer in it.

    Removing is as much a part of publishing as writing. Without it, a page deleted from the
    English docs stays in the bucket forever, gets copied into `docs/source/<lang>` by the
    workflow, and goes on being served -- unlisted in the sidebar, so nobody finds it to
    notice. The workflow's wholesale folder copy only clears orphans that are in the repo; the
    ones in the bucket are ours to clear.

    Only called once the tree has been checked, so "not in the tree" really does mean gone
    rather than failed.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for page, text in sorted(tree.items()):
        dest = out_dir / page
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            if dest.is_file() and dest.read_text(encoding="utf-8") == text:
                continue
        except OSError:
            pass
        dest.write_text(text, encoding="utf-8")
        written += 1

    removed = []
    for name in sorted(live_files(out_dir) - set(tree)):
        try:
            (out_dir / name).unlink()
            removed.append(name)
        except OSError:
            traceback.print_exc()
            print(f"[publish] could not remove {name}")
    _prune_empty_dirs(out_dir)
    return written, removed


def _prune_empty_dirs(out_dir):
    """Clear out folders left behind when every page inside them was removed."""
    for path in sorted(Path(out_dir).rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            try:
                path.rmdir()
            except OSError:
                pass


def clear_preview(out_dir):
    """Empty a preview tree before writing a new one, so runs do not pile up in it."""
    shutil.rmtree(out_dir, ignore_errors=True)
