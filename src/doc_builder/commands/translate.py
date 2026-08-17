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

from doc_builder.translate import pipeline, validate
from doc_builder.translate.cache import SegmentCache, segment_key

DEFAULT_MODEL = "google/gemma-4-26B-A4B-it"
REPO_URL = "https://github.com/huggingface/{package}.git"
TOCTREE = "_toctree.yml"


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
        if line.strip() and not line.startswith("#")
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


def write_toctree(out_dir, tree, titles):
    """Write out the sidebar with translated titles, but only if it still reads back correctly.

    We check by writing the file out, reading it straight back, and making sure every page is
    still listed. Checking the version in memory would prove nothing, since swapping titles
    cannot change the shape of anything. What could actually go wrong is the writing and
    re-reading itself, and a broken sidebar takes down the entire language -- unlike one bad
    page, which only affects itself.
    """
    source_locals = pipeline.toctree_values(tree, "local")
    pipeline.apply_toctree_titles(tree, titles)
    dumped = yaml.safe_dump(tree, sort_keys=False, allow_unicode=True)
    if pipeline.toctree_values(yaml.safe_load(dumped), "local") != source_locals:
        print("[translate] ERROR toctree did not survive a re-parse; keeping the existing one")
        return False
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / TOCTREE).write_text(dumped, encoding="utf-8")
    return True


def write_page(out_dir, page, text):
    dest = out_dir / page
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")


def keep_published(path, source):
    """Is the page already in the bucket still good enough to leave alone?

    Only the checks that read a finished page apply here -- we have the published text, not the
    marked-up version it was built from, so the marker checks cannot run. In practice that is
    the check that matters, since it is the one that has caught pages published under older,
    weaker rules.
    """
    if not path.is_file():
        return False
    try:
        published = path.read_text(encoding="utf-8")
    except OSError:
        return False
    problems = validate.check_links(source, published)
    if problems:
        print(f"[translate]   replacing published {path.name}: {problems[0]}")
        return False
    return True


def run(args, source_dir):
    bucket = Path(args.bucket)
    out_dir = bucket / "translations" / args.package / args.lang
    cache = SegmentCache(bucket)

    glossary = pipeline.load_glossary(args.glossary or pipeline.glossary_path(args.lang))
    gloss_sha = pipeline.glossary_sha(glossary)
    print(f"[translate] {args.package}/{args.lang} model={args.model} glossary={gloss_sha[:12]}")

    pages = select_pages(source_dir, args.pages_file)
    plans = plan_all(source_dir, pages, args.lang, args.model, gloss_sha)
    # If we are only translating some pages, the sidebar has to be trimmed to match, or the
    # result cannot be built.
    subset = pages if args.pages_file else None
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

    # This is the moment the whole design is built around: decide whether there is anything to
    # do before going anywhere near the model.
    #
    # --rebuild carries on anyway, using the cache. Nothing here needs a GPU when there is
    # nothing to translate, so it is a cheap way to republish every page after a change to how
    # pages are assembled or checked. Without it those changes never reach the bucket, because
    # a warm run stops before it ever rebuilds a page.
    if not missing and not args.rebuild:
        print("[translate] cache is warm, nothing to translate -- exiting before model load")
        return 0
    if args.dry_run:
        print(f"[translate] dry run, would translate {len(missing)} segment(s)")
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
    for key, why in failures[:10]:
        print(f"[translate]   FAILED {key[:12]} {why}")

    cache.put_many(fresh)
    cache.save_index()

    # Pull together what we had already and what we just translated.
    available = cache.get_many([k for k in wanted if k in known and k not in fresh])
    available.update(fresh)

    results, written, skipped = [], 0, 0
    for page, plan in plans.items():
        masked_translation, page_text, rejected = pipeline.assemble_page(plan, available)
        result = pipeline.validate_plan(plan, masked_translation, glossary, page_text)
        if rejected:
            result.warnings.append(f"{len(rejected)} paragraph(s) kept in English: markers not preserved")
        results.append(result)
        if result.ok:
            disclosed = pipeline.add_disclosure(page_text, page, args.lang, args.package)
            write_page(out_dir, page, disclosed)
            written += 1
        else:
            # This page failed its checks, so keep whatever is already published -- but only if
            # that still passes today's checks. "The last good translation" meant good under the
            # rules at the time, and the rules get stricter: continuous_batching.md sat in the
            # bucket with 8 broken links for two runs, kept each time because the fresh attempt
            # failed for an unrelated reason. Anything that no longer passes drops to English.
            if not keep_published(out_dir / page, plan.source):
                write_page(out_dir, page, plan.source)
            skipped += 1

    toctree_ok = True
    if toc_tree is not None:
        toctree_ok = write_toctree(
            out_dir,
            toc_tree,
            # Sidebar titles never go through assemble_page, so they need the same clean-up.
            {title: pipeline.strip_echoed_markers(available.get(key, title)) for key, title in toc_keys.items()},
        )

    print(validate.summarize(results))
    print(f"[translate] wrote {written} page(s), kept/fell back on {skipped}")
    # If the sidebar was rejected, fail the run. The pages have already gone out, so reporting
    # success here would leave new pages sitting behind an old sidebar that does not list them.
    return 0 if toctree_ok else 1


def translate_command(args):
    """Where the command starts.

    It exits with an error code rather than returning one. The CLI throws away whatever a
    command returns, so a returned code would vanish -- and this runs unattended every night,
    where the exit code is the only way anyone finds out something went wrong. `check_links` and
    `light_install` do the same.
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
        help="Newline-separated subset of page paths to translate, for smoke runs.",
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
        "--rebuild",
        action="store_true",
        help=(
            "Rebuild and republish every page from the cache even when nothing needs "
            "translating. Use after changing how pages are assembled or checked. Needs no GPU "
            "if the cache is warm."
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
