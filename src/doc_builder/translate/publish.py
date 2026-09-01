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

**A run publishes a whole generation or nothing.** Each run writes its tree to a folder of its
own under `generations/`, never touching what is already published. When every file is written
and read back correctly, one small file -- `CURRENT` -- is rewritten to name the new generation.
That single write is the publish, and it is the only thing the build looks at.

Nothing weaker than this works. Writing pages into the live folder one at a time leaves it
mixed for the length of the run, and the file that sorts first is `_toctree.yml`, so the usual
mixture is a new sidebar over old or missing pages. Assembling in memory first narrows that
window but does not close it. Writing the manifest last only lets the *next* run notice; the
build does not read the manifest, so a sync that lands in between publishes the mixture anyway.

Deleting comes free from this. A generation contains exactly the pages that exist now, so a page
removed from the English docs is simply not in it -- there is no pruning step to get half done.

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

Each generation carries its own manifest, named after it and stored beside the generations
rather than inside any of them. The pointer therefore selects the tree and the record of how it
was built in one move, and a run that finishes late cannot overwrite the record of the run that
beat it.
"""

import json
import shutil
import time
import traceback
from pathlib import Path

from .cache import atomic_write, sha256_text

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

# How many generations to leave on the bucket, the published one included. More than two, so a
# build that resolved the pointer just before a new run promoted still finds the generation it
# asked for while it downloads it. Older ones are only taking up room.
KEEP_GENERATIONS = 4

GENERATIONS = "generations"
MANIFESTS = "manifests"
POINTER = "CURRENT"


def manifest_path(root, generation):
    """Where the manifest describing one generation lives.

    One file per generation, named after it, rather than one file per language that every run
    rewrites. Two publishers finishing at once used to take turns clobbering that single file,
    so the surviving manifest could describe a tree that `CURRENT` no longer named. Now each run
    writes only its own, and the pointer decides which one is authoritative -- the manifest is
    selected by the same atomic switch as the tree it belongs to.

    It sits under the language root but outside `generations/`, which is the only thing the
    build syncs, so it never reaches the docs.
    """
    return Path(root) / MANIFESTS / f"{generation}.json"


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
    if manifest.get("generation") != Path(path).stem:
        # Filed under one generation, claiming another. Nothing should produce this, so treat it
        # as unusable rather than guess which half is right.
        print(f"[publish] manifest at {path} describes {manifest.get('generation')!r}; ignoring it")
        return {}
    return manifest


def save_manifest(path, manifest):
    """Write the manifest, last of all, once the tree it describes is really in place.

    Last on purpose. If the run dies partway through publishing, the manifest still describes
    the previous tree, so it disagrees with what is on disk -- and the next run notices the
    disagreement and finishes the job. A manifest written first would instead claim the
    interrupted tree was complete.
    """
    try:
        atomic_write(path, json.dumps(manifest, indent=1, sort_keys=True))
        return True
    except Exception:
        traceback.print_exc()
        print("[publish] could not write the manifest; the next run will rebuild everything")
        return False


def build_manifest(language, model, gloss_sha, prompt_version, sources, published, generation, failed=()):
    """Describe what we just published: what it was built from, and what it came out as.

    `failed` is the pages that fell back to English or to an older translation. They are
    recorded by name because their `output` hash is a fallback rather than a real translation,
    and a manifest that did not say so made them invisible: the next run compared the published
    English against the recorded hash, found them equal, called the tree current and exited 0.
    The page stayed English for good and the job went green the morning after it broke.
    """
    return {
        "manifest_version": MANIFEST_VERSION,
        "output_version": OUTPUT_VERSION,
        "generation": generation,
        "prompt_version": prompt_version,
        "language": language,
        "model": model,
        "glossary": gloss_sha,
        "failed": sorted(failed),
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
    """Every file currently published, as paths relative to the tree.

    `None` means nothing is published yet, which is the same answer as an empty tree.
    """
    if out_dir is None:
        return set()
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
    if out_dir is None:
        return set(sources), set()
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


def lang_root(bucket, package, language):
    """The folder holding every generation for one language, plus the pointer."""
    return Path(bucket) / "translations" / package / language


def pointer_path(root):
    return Path(root) / POINTER


def read_pointer(root):
    """Which generation is published right now, or None if none is."""
    try:
        name = pointer_path(root).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    # Only ever a folder name we wrote. Anything with a path separator in it is not ours.
    return name if name and "/" not in name and name != ".." else None


def generation_dir(root, generation):
    return Path(root) / GENERATIONS / generation


def current_dir(root):
    """The published generation as a folder, or None if there is nothing published."""
    generation = read_pointer(root)
    if generation is None:
        return None
    path = generation_dir(root, generation)
    return path if path.is_dir() else None


def generation_id(tree):
    """Name a generation after what is in it.

    Content-addressed, so a run that produces exactly what is already published gets the same
    name and can stop without writing anything. It also means a generation folder never needs
    to be modified once written -- a different tree is a different folder.
    """
    digest = sha256_text("\0".join(f"{page}\0{text}" for page, text in sorted(tree.items())))
    return digest[:16]


def repair_suffix():
    """A short suffix so a rebuilt generation gets a directory of its own.

    A generation's name is its content hash, and the published one is never written into, so a
    tree that has to be rebuilt under the same content needs a distinct name. Time-based, which
    is enough: it only has to differ from the damaged one.
    """
    return f"{int(time.time())}"


def verify_generation(root, generation, tree):
    """Read a generation back off disk and say which files are not what they should be.

    Reading back is the point. A generation is only published once we know it is complete and
    correct on the far side of a network filesystem, and the only way to know that is to look.
    Also used to check whether an existing generation is still intact, since being named after
    its contents is a claim about what should be there rather than proof that it is.
    """
    target = generation_dir(root, generation)
    bad = []
    for page, text in sorted(tree.items()):
        try:
            if (target / page).read_text(encoding="utf-8") != text:
                bad.append(page)
        except OSError as exc:
            bad.append(f"{page} ({exc.__class__.__name__})")
    extra = live_files(target) - set(tree)
    bad.extend(sorted(extra))
    return bad


def _write_files(target, tree):
    """Write a whole tree of pages under `target`."""
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    for page, text in sorted(tree.items()):
        dest = target / page
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")


def write_generation(root, generation, tree):
    """Write every file of a generation, then read them all back.

    Gives back the list of files that did not survive, empty if all is well.
    """
    _write_files(generation_dir(root, generation), tree)
    return verify_generation(root, generation, tree)


def promote(root, generation):
    """Publish a generation by pointing at it. This is the moment it goes live.

    One small write, and the only step that changes what anyone else can see. Written to a
    temporary name first and moved into place, so a reader never catches it half-written.
    """
    try:
        atomic_write(pointer_path(root), f"{generation}\n")
        return True
    except Exception:
        traceback.print_exc()
        print("[publish] could not update the pointer; nothing was published")
        return False


def gc_generations(root, keep=KEEP_GENERATIONS):
    """Delete old generations, keeping the newest few and never the published one.

    Newest by modification time. The pointer is re-read here rather than taken from the caller:
    a caller's idea of the published generation can be stale by the time we delete, and deleting
    the generation `CURRENT` actually names is the one mistake this function must not make.

    Failures are only wasted space, so they are reported and otherwise ignored.
    """
    base = Path(root) / GENERATIONS
    if not base.is_dir():
        return []
    live = read_pointer(root)
    candidates = [p for p in base.iterdir() if p.is_dir() and p.name != live]
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    removed = []
    # `keep` counts the published generation, which is never a candidate, so this many others
    # survive alongside it. Kept generous enough that a build which already resolved an older
    # generation can finish syncing it before the folder goes away.
    for path in candidates[max(keep - 1, 0) :]:
        try:
            shutil.rmtree(path)
            removed.append(path.name)
        except OSError:
            traceback.print_exc()
            print(f"[publish] could not remove old generation {path.name}")
            continue
        # the manifest describes a tree that is gone, so it goes too
        manifest_path(root, path.name).unlink(missing_ok=True)
    return removed


def write_tree(out_dir, tree):
    """Write a plain tree, replacing whatever was there.

    Only used for `--pages-file` preview runs, which nothing builds from. The live path goes
    through generations instead.
    """
    shutil.rmtree(out_dir, ignore_errors=True)
    _write_files(out_dir, tree)
