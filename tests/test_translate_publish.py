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

"""End-to-end runs of `doc-builder translate` with the cache pre-warmed, so no GPU is needed.

These cover the cases where the published tree and the English docs can drift apart. They are
whole-command tests on purpose: every one of them passed the unit tests before it was fixed,
because the bug was in how the pieces were wired together rather than in any one of them.
"""

import argparse

import pytest
import yaml

from doc_builder.commands.translate import run
from doc_builder.translate import pipeline, publish
from doc_builder.translate.cache import SegmentCache

TOCTREE = "- sections:\n  - local: index\n    title: Home\n  - local: guide\n    title: Guide\n  title: Get started\n"

PAGES = {
    "index.md": "# Home\n\nWelcome to the docs.\n\n```python\nprint(1)\n```\n",
    "guide.md": "# Guide\n\nRead [the guide](https://hf.co/docs) first.\n",
}


def make_args(bucket, source, **overrides):
    args = argparse.Namespace(
        package="testpkg",
        lang="ja",
        model="fake-model",
        bucket=str(bucket),
        source=str(source),
        glossary=None,
        pages_file=None,
        attn_implementation="paged|sdpa",
        cuda_graphs=False,
        rebuild=False,
        dry_run=False,
        max_failure_rate=0.25,
        warn_failure_rate=0.02,
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def write_docs(root, pages=None, toctree=TOCTREE):
    """Lay out a docs/source/en tree the command can read."""
    en = root / "en"
    en.mkdir(parents=True, exist_ok=True)
    for name, text in (PAGES if pages is None else pages).items():
        (en / name).write_text(text, encoding="utf-8")
    (en / "_toctree.yml").write_text(toctree, encoding="utf-8")
    return en


def warm_cache(bucket, en_dir, args, translate=lambda text: text + "。"):
    """Fill the segment cache so the run never reaches the model.

    The stand-in translation appends a character. That is enough to satisfy the checks -- the
    markers and heading levels are untouched and the prose differs from the English -- without
    needing a model or a language.
    """
    # The same glossary the run will load, or the IDs come out different and nothing matches.
    gloss_sha = pipeline.glossary_sha(pipeline.load_glossary(pipeline.glossary_path(args.lang)))
    segments = {}
    for name in sorted(p.name for p in en_dir.glob("*.md")):
        plan = pipeline.PagePlan(name, (en_dir / name).read_text(encoding="utf-8"), args.lang, args.model, gloss_sha)
        segments.update(plan.segments)
    tree = yaml.safe_load((en_dir / "_toctree.yml").read_text(encoding="utf-8"))
    for title in pipeline.toctree_titles(tree):
        segments[pipeline.segment_key(title, args.model, pipeline.PROMPT_VERSION, gloss_sha, args.lang)] = title

    cache = SegmentCache(bucket)
    cache.put_many({key: translate(text) for key, text in segments.items()})
    cache.save_index()
    return segments


def no_gpu(monkeypatch):
    """Fail loudly if a run tries to load the model -- these tests must never need one."""

    def boom(*_args, **_kwargs):
        raise AssertionError("translate_segments was called; the cache should have been warm")

    monkeypatch.setattr(pipeline, "translate_segments", boom)


@pytest.fixture
def env(tmp_path, monkeypatch):
    no_gpu(monkeypatch)
    bucket = tmp_path / "bucket"
    en = write_docs(tmp_path / "docs")
    args = make_args(bucket, tmp_path / "docs")
    warm_cache(bucket, en, args)
    out = bucket / "translations" / "testpkg" / "ja"
    return argparse.Namespace(bucket=bucket, en=en, args=args, out=out, tmp=tmp_path)


def test_first_run_publishes_the_tree(env):
    assert run(env.args, env.en) == 0
    assert (env.out / "index.md").is_file()
    assert (env.out / "guide.md").is_file()
    assert (env.out / "_toctree.yml").is_file()
    assert publish.manifest_path(env.bucket, "testpkg", "ja").is_file()


def test_second_run_with_nothing_changed_does_nothing(env, capsys):
    assert run(env.args, env.en) == 0
    before = (env.out / "index.md").read_text(encoding="utf-8")
    assert run(env.args, env.en) == 0
    assert "exiting before model load" in capsys.readouterr().out
    assert (env.out / "index.md").read_text(encoding="utf-8") == before


def test_code_only_edit_is_republished(env):
    """A change inside a code block keeps every paragraph ID, so the cache stays warm.

    Regression: the run exited on the warm cache and the old code sample stayed published.
    Nothing about the segment cache can see this edit -- the code was masked before the ID was
    worked out, which is exactly what makes the cache reusable.
    """
    assert run(env.args, env.en) == 0
    edited = PAGES["index.md"].replace("print(1)", "print(2)")
    (env.en / "index.md").write_text(edited, encoding="utf-8")

    assert run(env.args, env.en) == 0
    assert "print(2)" in (env.out / "index.md").read_text(encoding="utf-8")


def test_deleted_paragraph_is_republished(env):
    """Removing a paragraph adds no new segments, so the cache stays warm here too."""
    assert run(env.args, env.en) == 0
    assert "Welcome to the docs" in (env.out / "index.md").read_text(encoding="utf-8")

    (env.en / "index.md").write_text("# Home\n\n```python\nprint(1)\n```\n", encoding="utf-8")
    assert run(env.args, env.en) == 0
    assert "Welcome to the docs" not in (env.out / "index.md").read_text(encoding="utf-8")


def test_deleted_page_is_removed_from_the_bucket(env):
    """An English page that goes away must not stay published forever.

    Nothing pruned the bucket before, so an orphan was copied into `docs/source/ja` by the
    workflow and served unlisted -- not in the sidebar, so nobody would find it to notice.
    """
    assert run(env.args, env.en) == 0
    assert (env.out / "guide.md").is_file()

    (env.en / "guide.md").unlink()
    (env.en / "_toctree.yml").write_text(
        "- sections:\n  - local: index\n    title: Home\n  title: Get started\n", encoding="utf-8"
    )
    assert run(env.args, env.en) == 0
    assert not (env.out / "guide.md").exists()
    assert (env.out / "index.md").is_file()


def test_interrupted_run_is_repaired(env):
    """A tree that does not match its manifest gets rebuilt, even on a warm cache.

    This is what an interrupted publish leaves behind. The manifest is written last precisely
    so that it disagrees with the tree in this case, and the disagreement is the signal.
    """
    assert run(env.args, env.en) == 0
    good = (env.out / "index.md").read_text(encoding="utf-8")
    (env.out / "guide.md").unlink()
    (env.out / "index.md").write_text("half written\n", encoding="utf-8")

    assert run(env.args, env.en) == 0
    assert (env.out / "guide.md").is_file()
    assert (env.out / "index.md").read_text(encoding="utf-8") == good


def test_output_version_bump_republishes_everything(env, monkeypatch):
    """Changing how pages are assembled reaches the bucket without anyone passing --rebuild."""
    assert run(env.args, env.en) == 0
    monkeypatch.setattr(publish, "OUTPUT_VERSION", "v-next")

    (env.out / "index.md").write_text("stale\n", encoding="utf-8")
    assert run(env.args, env.en) == 0
    assert "stale" not in (env.out / "index.md").read_text(encoding="utf-8")


def test_total_failure_publishes_nothing(tmp_path, monkeypatch, capsys):
    """A night where every page fails must not overwrite the language with English.

    Falling back page by page is right when one page fails; doing it for all of them is a
    silent revert of the whole translation, and it used to exit 0.
    """
    no_gpu(monkeypatch)
    bucket = tmp_path / "bucket"
    en = write_docs(tmp_path / "docs")
    args = make_args(bucket, tmp_path / "docs")
    warm_cache(bucket, en, args)
    assert run(args, en) == 0
    published = (bucket / "translations" / "testpkg" / "ja" / "index.md").read_text(encoding="utf-8")

    # Re-warm with translations that are just the English back again: every page then fails
    # check_translated, so the whole run is a wash.
    warm_cache(bucket, en, args, translate=lambda text: text)
    (bucket / "translations" / "testpkg" / "ja" / "index.md").write_text("force a rebuild\n", encoding="utf-8")

    assert run(args, en) == 2
    assert "publishing nothing" in capsys.readouterr().out
    # the good translation from the first run is still there for guide.md
    assert (bucket / "translations" / "testpkg" / "ja" / "guide.md").read_text(encoding="utf-8") != PAGES["guide.md"]
    assert published  # sanity: the first run really did publish something


def test_pages_file_writes_to_a_preview_tree(env, tmp_path):
    """A smoke run must not touch the live tree.

    It would do real damage now that publishing prunes: three pages in, 737 deleted, and a
    three-entry sidebar replacing the real one.
    """
    assert run(env.args, env.en) == 0
    live_before = sorted(p.name for p in env.out.rglob("*") if p.is_file())

    pages_file = tmp_path / "pages.txt"
    pages_file.write_text("# just the one\n  # indented comment\nguide.md\n", encoding="utf-8")
    preview_args = make_args(env.bucket, env.tmp / "docs", pages_file=str(pages_file))
    assert run(preview_args, env.en) == 0

    preview = env.bucket / "translations" / "testpkg" / "ja.preview"
    assert (preview / "guide.md").is_file()
    assert not (preview / "index.md").exists()
    assert sorted(p.name for p in env.out.rglob("*") if p.is_file()) == live_before
