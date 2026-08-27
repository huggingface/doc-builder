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
`doc-builder translate` -- translate a library's English docs into another language.

Built to run as one Hugging Face Job, once a night. It works out what has changed before it
loads the model, so a night where nothing changed finishes in a couple of minutes without
ever downloading 52GB of weights:

    hf jobs uv run --namespace hf-doc-build --flavor a100-large --timeout 6h \
      -v hf://buckets/hf-doc-build/doc-translate:/bucket --secrets HF_TOKEN \
      --with "hf-doc-builder[translate] @ git+https://github.com/huggingface/doc-builder@main" \
      doc-builder translate transformers --lang ja --bucket /bucket

To try it on your own machine, point --bucket at any folder and --source at a docs checkout.
Nothing gets translated without a GPU, but everything up to that point runs:

    doc-builder translate transformers --lang ja \
      --source ~/hf/transformers/docs/source --bucket /tmp/bucket --dry-run
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

from doc_builder.translate import pipeline, publish, validate
from doc_builder.translate.cache import SegmentCache, segment_key
from doc_builder.translate.publish import TOCTREE

DEFAULT_MODEL = "google/gemma-4-26B-A4B-it"
REPO_URL = "https://github.com/huggingface/{package}.git"


def clone_docs(package, into):
    """Grab a copy of the library's repo, latest commit only.

    We fetch the whole repo rather than just the docs folder, which looks wasteful but is not.
    A couple of doc pages are shortcuts pointing outside the docs folder -- in transformers,
    `en/notebooks.md` points at `notebooks/README.md` and `en/contributing.md` at
    `CONTRIBUTING.md`. Fetch only the docs folder and those shortcuts point at nothing, and the
    run dies partway through. The extra few hundred MB is nothing next to a 52GB model.
    """
    url = REPO_URL.format(package=package)
    print(f"[translate] cloning {url}")
    subprocess.run(["git", "clone", "--depth", "1", url, str(into)], check=True)
    return into / "docs" / "source"


def select_pages(source_dir, pages_file):
    pages = sorted(p.relative_to(source_dir).as_posix() for p in source_dir.rglob("*.md"))
    if not pages_file:
        return pages
    wanted = {
        line.strip()
        for line in Path(pages_file).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    missing = wanted - set(pages)
    if missing:
        print(f"[translate] WARNING {len(missing)} requested page(s) not found: {sorted(missing)[:5]}")
    return [p for p in pages if p in wanted]


def plan_all(source_dir, pages, lang, model, gloss_sha):
    """Break every page into paragraphs, ready to translate.

    A page we cannot read is skipped with a warning rather than stopping everything. A couple of
    pages are shortcuts to files outside the docs folder, so if one of those ever points
    somewhere we did not fetch, it should cost us that page and not the whole night.
    """
    plans, unreadable = {}, []
    for page in pages:
        try:
            text = (source_dir / page).read_text(encoding="utf-8")
        except OSError as exc:
            unreadable.append(f"{page} ({exc.__class__.__name__})")
            continue
        plans[page] = pipeline.PagePlan(page, text, lang, model, gloss_sha)
    if unreadable:
        print(f"[translate] WARNING skipped {len(unreadable)} unreadable page(s): {unreadable[:5]}")
    return plans


def load_toctree(source_dir, lang, model, gloss_sha, pages=None):
    """Read the sidebar file and work out an ID for each of its titles.

    Pass `pages` to cut the sidebar down to just those pages -- that is for test runs on a
    handful of pages. Leave it out and the whole sidebar is kept, which is the normal case.
    """
    path = source_dir / TOCTREE
    if not path.is_file():
        return None, {}
    tree = yaml.safe_load(path.read_text(encoding="utf-8"))

    if pages is not None:
        # the sidebar refers to pages without the .md on the end
        keep = {p[:-3] if p.endswith(".md") else p for p in pages}
        tree = pipeline.prune_toctree(tree, keep)
        if tree is None:
            print("[translate] WARNING no toctree entries match the selected pages; skipping it")
            return None, {}

    keys = {
        segment_key(title, model, pipeline.PROMPT_VERSION, gloss_sha, lang): title
        for title in pipeline.toctree_titles(tree)
    }
    return tree, keys


def translated_titles(toc_keys, available):
    """The sidebar titles, translated where we have one and left in English where we do not.

    Same clean-up the page paragraphs get, plus the same emptiness guard: an empty translation
    here would blank out a sidebar entry, which reads as a missing page rather than an
    untranslated one. Titles never go through `assemble_page`, so they need it spelled out.
    """
    titles = {}
    for key, title in toc_keys.items():
        translated = pipeline.strip_echoed_markers(available.get(key, ""))
        titles[title] = translated if pipeline.has_prose(translated) else title
    return titles


def render_toctree(tree, titles):
    """Turn the sidebar into the text we will publish, or None if it did not survive.

    We check by dumping it and reading it straight back, making sure every page is still
    listed. Checking the version in memory would prove nothing, since swapping titles cannot
    change the shape of anything. What could actually go wrong is the writing and re-reading
    itself, and a broken sidebar takes down the entire language -- unlike one bad page, which
    only affects itself.
    """
    source_locals = pipeline.toctree_values(tree, "local")
    pipeline.apply_toctree_titles(tree, titles)
    dumped = yaml.safe_dump(tree, sort_keys=False, allow_unicode=True)
    if pipeline.toctree_values(yaml.safe_load(dumped), "local") != source_locals:
        print("[translate] ERROR toctree did not survive a re-parse; keeping the existing one")
        return None
    return dumped


def keep_published(path, source):
    """Is the page already in the bucket still good enough to leave alone?

    Only the checks that read a finished page apply here -- we have the published text, not the
    marked-up version it was built from, so the marker checks cannot run. In practice that is
    the check that matters, since it is the one that has caught pages published under older,
    weaker rules.
    """
    if not path.is_file():
        return None
    try:
        published = path.read_text(encoding="utf-8")
    except OSError:
        return None
    problems = validate.check_links(source, published)
    if problems:
        print(f"[translate]   replacing published {path.name}: {problems[0]}")
        return None
    return published


def assemble_tree(plans, available, glossary, args, out_dir):
    """Build every page, in memory, and say which ones failed their checks.

    Nothing is written here. The whole tree has to exist and be checked before any of it is
    published, so that an interrupted or failing run cannot leave a half-translated folder
    behind for the build to pick up.
    """
    tree, results, failed = {}, [], []
    for page, plan in plans.items():
        masked_translation, page_text, rejected = pipeline.assemble_page(plan, available)
        result = pipeline.validate_plan(plan, masked_translation, glossary, page_text)
        if rejected:
            result.warnings.append(f"{len(rejected)} paragraph(s) kept in English: markers not preserved")
        results.append(result)
        if result.ok:
            tree[page] = pipeline.add_disclosure(page_text, page, args.lang, args.package)
        else:
            # This page failed its checks, so keep whatever is already published -- but only if
            # that still passes today's checks. "The last good translation" meant good under the
            # rules at the time, and the rules get stricter: continuous_batching.md sat in the
            # bucket with 8 broken links for two runs, kept each time because the fresh attempt
            # failed for an unrelated reason. Anything that no longer passes drops to English.
            kept = keep_published(out_dir / page, plan.source)
            tree[page] = kept if kept is not None else plan.source
            failed.append(page)
    return tree, results, failed


def run(args, source_dir):
    bucket = Path(args.bucket)
    # A run on a handful of pages publishes somewhere of its own. It has to: publishing now
    # removes anything not in the tree it was given, so pointing a three-page smoke run at the
    # live folder would delete the other 737 pages and replace the sidebar with three entries.
    # Nothing here touches the live tree or its manifest.
    preview = bool(args.pages_file)
    out_dir = bucket / "translations" / args.package / (f"{args.lang}.preview" if preview else args.lang)
    if preview:
        print(f"[translate] --pages-file given: publishing to {out_dir}, leaving the live tree alone")
    cache = SegmentCache(bucket)

    glossary = pipeline.load_glossary(args.glossary or pipeline.glossary_path(args.lang))
    gloss_sha = pipeline.glossary_sha(glossary)
    print(f"[translate] {args.package}/{args.lang} model={args.model} glossary={gloss_sha[:12]}")

    pages = select_pages(source_dir, args.pages_file)
    plans = plan_all(source_dir, pages, args.lang, args.model, gloss_sha)
    # If we are only translating some pages, the sidebar has to be trimmed to match, or the
    # result cannot be built.
    subset = pages if preview else None
    toc_tree, toc_keys = load_toctree(source_dir, args.lang, args.model, gloss_sha, subset)

    wanted = {}
    for plan in plans.values():
        wanted.update(plan.segments)
    wanted.update(toc_keys)

    known = cache.load_index()
    missing = {k: v for k, v in wanted.items() if k not in known}
    print(
        f"[translate] {len(plans)} pages, {len(wanted)} unique segments, "
        f"{len(missing)} missing ({len(wanted) - len(missing)} cached)"
    )

    # Two separate questions, and they used to be answered by the same `if`.
    #
    # The cache answers the first: is there new prose, i.e. do we need a GPU tonight? The
    # manifest answers the second: does what is published still match the English docs? A code
    # or link edit changes a page without adding a single new paragraph, and a deleted
    # paragraph adds none either, so a warm cache tells us nothing about the second question.
    # Answering both with the cache left those edits unpublished, and meant a tree that a
    # previous run left incomplete could never repair itself.
    manifest = publish.load_manifest(publish.manifest_path(bucket, args.package, args.lang))
    sources = {page: plan.source for page, plan in plans.items()}
    # The sidebar is tracked like any other page. It has to be: it is a file in the published
    # tree, so leaving it out means it never gets rebuilt when a title changes, and it looks
    # like an orphan to be deleted every single run.
    if toc_tree is not None:
        sources[TOCTREE] = (source_dir / TOCTREE).read_text(encoding="utf-8")
    if preview:
        stale, orphans, why = set(sources), set(), "preview run"
    else:
        why = publish.stale_reason(manifest, args.lang, args.model, gloss_sha, pipeline.PROMPT_VERSION)
        if why:
            stale, orphans = set(sources), publish.live_files(out_dir) - set(sources)
        else:
            stale, orphans = publish.reconcile(out_dir, manifest, sources)
            why = f"{len(stale)} file(s) out of date, {len(orphans)} to remove" if stale or orphans else None
    if why:
        print(f"[translate] republishing: {why}")

    if not missing and not why and not args.rebuild:
        print("[translate] cache is warm and the published tree is current -- exiting before model load")
        return 0
    if args.dry_run:
        print(f"[translate] dry run, would translate {len(missing)} segment(s) and rebuild {len(stale)} file(s)")
        return 0

    fresh, failures = ({}, [])
    if missing:
        fresh, failures = pipeline.translate_segments(
            missing,
            args.lang,
            glossary,
            args.model,
            attn_implementation=args.attn_implementation,
            use_cuda_graph=args.cuda_graphs,
        )
    print(f"[translate] translated {len(fresh)}, {len(failures)} request failure(s)")
    for key, why_failed in failures[:10]:
        print(f"[translate]   FAILED {key[:12]} {why_failed}")

    cache.put_many(fresh)
    cache.save_index()

    # Pull together what we had already and what we just translated.
    available = cache.get_many([k for k in wanted if k in known and k not in fresh])
    available.update(fresh)

    tree, results, failed = assemble_tree(plans, available, glossary, args, out_dir)

    toctree_text = None
    if toc_tree is not None:
        toctree_text = render_toctree(toc_tree, translated_titles(toc_keys, available))
        if toctree_text is None:
            # The sidebar is the one thing a page cannot fail on its own. Publish nothing:
            # new pages behind an old sidebar are not listed, and a missing sidebar takes the
            # whole language down.
            print("[translate] ERROR sidebar could not be rebuilt; publishing nothing")
            print(validate.summarize(results))
            return 1
        tree[TOCTREE] = toctree_text

    print(validate.summarize(results))

    # Refuse to publish a run that went badly wrong. Every failed page falls back to English or
    # to whatever it had before, so a night where the model returns rubbish for everything used
    # to look like a success: 732 English pages written into the Japanese docs, exit code 0.
    # Leaving the previous translation in place is better than that, and it means one bad
    # night cannot undo a good one.
    rate = len(failed) / len(results) if results else 0.0
    if rate > args.max_failure_rate:
        print(
            f"[translate] ERROR {rate:.1%} of pages failed, above the {args.max_failure_rate:.0%} limit "
            f"-- publishing nothing and leaving the existing translation alone"
        )
        return 2

    if preview:
        publish.clear_preview(out_dir)
    written, removed = publish.publish_tree(out_dir, tree)
    print(f"[translate] published {written} changed file(s), removed {len(removed)}, {len(failed)} page(s) failed")
    for name in removed[:10]:
        print(f"[translate]   removed {name}")

    if preview:
        return 0

    # The manifest goes last, once the tree it describes is really in place. If the run dies
    # before this, the manifest still describes the previous tree, disagrees with what is on
    # disk, and the next run finishes the job.
    publish.save_manifest(
        publish.manifest_path(bucket, args.package, args.lang),
        publish.build_manifest(args.lang, args.model, gloss_sha, pipeline.PROMPT_VERSION, sources, tree),
    )

    # Go red on a rate that is bad but not catastrophic. The pages are published -- a mostly
    # translated page beats no page -- but nobody watches a job that never fails, and this is
    # the only signal there is.
    if rate > args.warn_failure_rate:
        print(f"[translate] {rate:.1%} of pages failed, above the {args.warn_failure_rate:.0%} warning level")
        return 1
    return 0


def translate_command(args):
    """Where the command starts.

    It exits with an error code rather than returning one. The CLI throws away whatever a
    command returns, so a returned code would vanish -- and this runs unattended every night,
    where the exit code is the only way anyone finds out something went wrong. `check_links` and
    `light_install` do the same.

    What the codes mean:

        0  published, or there was nothing to do
        1  published, but enough pages failed to be worth a look -- or the sidebar was
           rejected, in which case nothing was published
        2  too many pages failed; nothing was published and the previous translation stands

    A run that goes wrong quietly is the thing to avoid here. Everything that fails falls back
    to English, so a bad night looks exactly like a good one from the outside unless the job
    goes red.
    """
    if args.source:
        code = run(args, Path(args.source) / "en")
    else:
        with tempfile.TemporaryDirectory() as tmp:
            code = run(args, clone_docs(args.package, Path(tmp)) / "en")
    if code:
        sys.exit(code)


def translate_command_parser(subparsers=None):
    if subparsers is not None:
        parser = subparsers.add_parser("translate")
    else:
        parser = argparse.ArgumentParser("Doc Builder translate command")

    parser.add_argument("package", type=str, help="Name of the GitHub repo whose docs to translate.")
    parser.add_argument("--lang", type=str, default="ja", help="Target language code.")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help="Translation model id.")
    parser.add_argument(
        "--bucket",
        type=str,
        default="/bucket",
        help="Mounted HF storage bucket (or a local directory) holding `cache/` and `translations/`.",
    )
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Existing docs/source checkout to translate from. Clones the package repo if omitted.",
    )
    parser.add_argument(
        "--glossary",
        type=str,
        default=None,
        help="Glossary YAML. Defaults to the packaged `doc_builder/glossaries/<lang>.yml`.",
    )
    parser.add_argument(
        "--pages-file",
        type=str,
        default=None,
        help=(
            "Newline-separated subset of page paths to translate, for smoke runs. Publishes to "
            "`<lang>.preview/` and never touches the live tree."
        ),
    )
    parser.add_argument(
        "--attn-implementation",
        type=str,
        default=pipeline.DEFAULT_ATTENTION,
        help=(
            "How attention is computed, e.g. 'paged|sdpa' (the default, always available) or "
            "'paged|flash_attention_2' (faster, but needs flash-attn or a matching Hub kernel)."
        ),
    )
    parser.add_argument(
        "--cuda-graphs",
        action="store_true",
        default=pipeline.DEFAULT_CUDA_GRAPHS,
        help=(
            "Record and replay the GPU work for speed. Off by default because it is incompatible "
            "with mixture-of-experts models, which copy between CPU and GPU to route experts."
        ),
    )
    parser.add_argument(
        "--max-failure-rate",
        type=float,
        default=0.25,
        help=(
            "Publish nothing if more than this fraction of pages fail their checks. A night "
            "where everything fails would otherwise write English over the whole language."
        ),
    )
    parser.add_argument(
        "--warn-failure-rate",
        type=float,
        default=0.02,
        help="Exit non-zero (but still publish) above this fraction of failed pages.",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help=(
            "Rebuild and republish every page from the cache even when nothing needs "
            "translating and the manifest says the tree is current. Needs no GPU if the cache "
            "is warm. Bumping publish.OUTPUT_VERSION does this on its own, so this is for "
            "one-off checks rather than for shipping a change."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report how many segments are missing and exit without loading the model.",
    )
    if subparsers is not None:
        parser.set_defaults(func=translate_command)
    return parser
