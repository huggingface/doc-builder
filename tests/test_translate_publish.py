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
        min_page_coverage=0.75,
        min_segment_success=0.5,
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


def write_many(root, count=10):
    """A corpus big enough that one failing page stays under the page-failure limit.

    Each page's prose is unique, so poisoning one page's cache entry cannot affect another --
    identical masked paragraphs share a translation, which is the point of the cache.
    """
    en = root / "en"
    en.mkdir(parents=True, exist_ok=True)
    pages = {}
    for i in range(count):
        pages[f"p{i}.md"] = (
            f"# Page {i}\n\nUnique body alpha {i}.\n\nUnique body beta {i}.\n\nUnique body gamma {i}.\n"
        )
        (en / f"p{i}.md").write_text(pages[f"p{i}.md"], encoding="utf-8")
    (en / "_toctree.yml").write_text(
        yaml.safe_dump(
            [{"sections": [{"local": f"p{i}", "title": f"Page {i}"} for i in range(count)], "title": "Start"}],
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return en, pages


def live(root):
    """The generation the pointer names -- what the build would actually read."""
    return publish.current_dir(root)


@pytest.fixture
def env(tmp_path, monkeypatch):
    no_gpu(monkeypatch)
    bucket = tmp_path / "bucket"
    en = write_docs(tmp_path / "docs")
    args = make_args(bucket, tmp_path / "docs")
    warm_cache(bucket, en, args)
    root = publish.lang_root(bucket, "testpkg", "ja")
    return argparse.Namespace(bucket=bucket, en=en, args=args, root=root, tmp=tmp_path)


def test_first_run_publishes_a_generation(env):
    assert run(env.args, env.en) == 0
    out = live(env.root)
    assert out is not None
    assert sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()) == [
        "_toctree.yml",
        "guide.md",
        "index.md",
    ]
    assert publish.manifest_path(env.bucket, "testpkg", "ja").is_file()


def test_publishing_is_one_pointer_write(env):
    """Nothing visible changes until the pointer moves, and it names a complete generation.

    Writing into the live folder page by page left it mixed for the length of the run, and
    `_toctree.yml` sorts first, so the usual mixture was a new sidebar over old pages.
    """
    assert run(env.args, env.en) == 0
    first = publish.read_pointer(env.root)

    (env.en / "index.md").write_text("# Home\n\nRewritten body.\n", encoding="utf-8")
    warm_cache(env.bucket, env.en, env.args)
    assert run(env.args, env.en) == 0
    second = publish.read_pointer(env.root)

    assert second != first
    # the old generation is untouched, so what the previous pointer named is still intact
    assert "Welcome to the docs" in (publish.generation_dir(env.root, first) / "index.md").read_text(encoding="utf-8")
    assert "Rewritten body." in (live(env.root) / "index.md").read_text(encoding="utf-8")


def test_a_failed_write_publishes_nothing(env, monkeypatch):
    """If any file of a generation does not survive, the pointer must not move."""
    assert run(env.args, env.en) == 0
    before = publish.read_pointer(env.root)

    monkeypatch.setattr(publish, "write_generation", lambda root, gen, tree: ["guide.md"])
    (env.en / "index.md").write_text("# Home\n\nChanged.\n", encoding="utf-8")
    warm_cache(env.bucket, env.en, env.args)

    assert run(env.args, env.en) == 2
    assert publish.read_pointer(env.root) == before
    assert "Welcome to the docs" in (live(env.root) / "index.md").read_text(encoding="utf-8")


def test_old_generations_are_cleaned_up(env):
    for i in range(4):
        (env.en / "index.md").write_text(f"# Home\n\nBody number {i}.\n", encoding="utf-8")
        warm_cache(env.bucket, env.en, env.args)
        assert run(env.args, env.en) == 0
    kept = sorted(p.name for p in (env.root / publish.GENERATIONS).iterdir() if p.is_dir())
    assert len(kept) <= publish.KEEP_GENERATIONS
    assert publish.read_pointer(env.root) in kept  # never the one in use


def test_second_run_with_nothing_changed_does_nothing(env, capsys):
    assert run(env.args, env.en) == 0
    before = publish.read_pointer(env.root)
    assert run(env.args, env.en) == 0
    assert "exiting before model load" in capsys.readouterr().out
    assert publish.read_pointer(env.root) == before


def test_code_only_edit_is_republished(env):
    """A change inside a code block keeps every paragraph ID, so the cache stays warm.

    Regression: the run exited on the warm cache and the old code sample stayed published.
    Nothing about the segment cache can see this edit -- the code was masked before the ID was
    worked out, which is exactly what makes the cache reusable.
    """
    assert run(env.args, env.en) == 0
    (env.en / "index.md").write_text(PAGES["index.md"].replace("print(1)", "print(2)"), encoding="utf-8")

    assert run(env.args, env.en) == 0
    assert "print(2)" in (live(env.root) / "index.md").read_text(encoding="utf-8")


def test_deleted_paragraph_is_republished(env):
    """Removing a paragraph adds no new segments, so the cache stays warm here too."""
    assert run(env.args, env.en) == 0
    assert "Welcome to the docs" in (live(env.root) / "index.md").read_text(encoding="utf-8")

    (env.en / "index.md").write_text("# Home\n\n```python\nprint(1)\n```\n", encoding="utf-8")
    assert run(env.args, env.en) == 0
    assert "Welcome to the docs" not in (live(env.root) / "index.md").read_text(encoding="utf-8")


def test_deleted_page_is_not_in_the_new_generation(env):
    """An English page that goes away must not stay published.

    Nothing pruned the bucket before, so an orphan was copied into `docs/source/ja` by the
    workflow and served unlisted -- not in the sidebar, so nobody would find it to notice.
    A generation holds exactly the pages that exist now, so this comes for free.
    """
    assert run(env.args, env.en) == 0
    assert (live(env.root) / "guide.md").is_file()

    (env.en / "guide.md").unlink()
    (env.en / "_toctree.yml").write_text(
        "- sections:\n  - local: index\n    title: Home\n  title: Get started\n", encoding="utf-8"
    )
    assert run(env.args, env.en) == 0
    out = live(env.root)
    assert not (out / "guide.md").exists()
    assert (out / "index.md").is_file()


def test_tree_that_disagrees_with_the_manifest_is_rebuilt(env):
    """A published generation that is not what we recorded gets rebuilt, even on a warm cache."""
    assert run(env.args, env.en) == 0
    good = (live(env.root) / "index.md").read_text(encoding="utf-8")
    (live(env.root) / "index.md").write_text("tampered\n", encoding="utf-8")

    assert run(env.args, env.en) == 0
    assert (live(env.root) / "index.md").read_text(encoding="utf-8") == good


def test_missing_pointer_is_repaired(env):
    """No pointer means nothing is published, so the run must republish rather than skip."""
    assert run(env.args, env.en) == 0
    publish.pointer_path(env.root).unlink()

    assert run(env.args, env.en) == 0
    assert live(env.root) is not None
    assert (live(env.root) / "index.md").is_file()


def test_output_version_bump_republishes_everything(env, monkeypatch):
    """Changing how pages are assembled reaches the bucket without anyone passing --rebuild."""
    assert run(env.args, env.en) == 0
    monkeypatch.setattr(publish, "OUTPUT_VERSION", "v-next")
    (live(env.root) / "index.md").write_text("stale\n", encoding="utf-8")

    assert run(env.args, env.en) == 0
    assert "stale" not in (live(env.root) / "index.md").read_text(encoding="utf-8")


def test_unreadable_page_does_not_delete_it(env):
    """A transient read failure must not be mistaken for a deletion.

    Regression: the page was skipped with a warning, so it was absent from the expected set and
    the publish pruned it. One `OSError` unpublished a good translation, the run returned 0, and
    `_toctree.yml` was left pointing at nothing.
    """
    assert run(env.args, env.en) == 0
    before = publish.read_pointer(env.root)

    (env.en / "guide.md").chmod(0o000)
    try:
        assert run(env.args, env.en) == 2
    finally:
        (env.en / "guide.md").chmod(0o644)

    assert publish.read_pointer(env.root) == before
    assert (live(env.root) / "guide.md").is_file()


def test_empty_source_publishes_nothing(env, tmp_path):
    """An empty source directory is a mistake, not an instruction to delete the language."""
    assert run(env.args, env.en) == 0
    before = publish.read_pointer(env.root)

    empty = tmp_path / "empty" / "en"
    empty.mkdir(parents=True)
    assert run(make_args(env.bucket, tmp_path / "empty"), empty) == 2
    assert publish.read_pointer(env.root) == before


def test_missing_toctree_publishes_nothing(env, tmp_path):
    """A full publish needs a sidebar; without one the build has nothing to lay pages out with."""
    assert run(env.args, env.en) == 0
    before = publish.read_pointer(env.root)

    (env.en / "_toctree.yml").unlink()
    assert run(env.args, env.en) == 2
    assert publish.read_pointer(env.root) == before


def test_total_failure_publishes_nothing(env, capsys):
    """A night where every page fails must not overwrite the language with English.

    Falling back page by page is right when one page fails; doing it for all of them is a
    silent revert of the whole translation, and it used to exit 0.
    """
    assert run(env.args, env.en) == 0
    before = publish.read_pointer(env.root)

    # Re-warm with translations that are just the English back again: every page then fails
    # check_translated, so the whole run is a wash.
    warm_cache(env.bucket, env.en, env.args, translate=lambda text: text)
    (live(env.root) / "index.md").write_text("force a rebuild\n", encoding="utf-8")

    assert run(env.args, env.en) == 2
    assert "publishing nothing" in capsys.readouterr().out
    assert publish.read_pointer(env.root) == before


def test_page_with_english_body_is_failed(env, monkeypatch, capsys):
    """A page whose heading translated and whose body did not is not a translated page.

    Regression: it passed every structural check -- markers intact, headings intact, no longer
    identical to the source -- so validation reported 1/1 pages passed at a 0.0% rejection rate
    and the run published it with a machine-translation banner over English prose.
    """
    (env.en / "index.md").write_text(
        "# Home\n\nFirst body paragraph.\n\nSecond body paragraph.\n\nThird body paragraph.\n",
        encoding="utf-8",
    )
    (env.en / "guide.md").unlink()
    (env.en / "_toctree.yml").write_text(
        "- sections:\n  - local: index\n    title: Home\n  title: Get started\n", encoding="utf-8"
    )

    def only_heading(segments, *_args, **_kwargs):
        ok, fails = {}, []
        for key, text in sorted(segments.items()):
            if text.startswith("# ") or text == "Home" or text == "Get started":
                ok[key] = text + "(ja)"
            else:
                fails.append((key, "request failed"))
        return ok, fails

    monkeypatch.setattr(pipeline, "translate_segments", only_heading)
    code = run(env.args, env.en)
    out = capsys.readouterr().out
    assert code != 0
    assert "paragraph(s) translated" in out
    assert live(env.root) is None  # nothing was ever published


def _mostly_fail(segments, *_args, **_kwargs):
    """Translate one segment and fail the rest."""
    items = sorted(segments.items())
    return {k: v + "(ja)" for k, v in items[:1]}, [(k, "request failed") for k, _ in items[1:]]


def test_low_segment_success_publishes_nothing(env, monkeypatch, capsys):
    """Ask the same question of the model, not just of the pages."""
    assert run(env.args, env.en) == 0
    before = publish.read_pointer(env.root)

    # enough new paragraphs for a success rate to mean something
    body = "\n\n".join(f"New paragraph number {i}." for i in range(30))
    (env.en / "index.md").write_text(f"# Home\n\n{body}\n", encoding="utf-8")

    monkeypatch.setattr(pipeline, "translate_segments", _mostly_fail)
    assert run(env.args, env.en) == 2
    assert "came back" in capsys.readouterr().out
    assert publish.read_pointer(env.root) == before


def test_a_couple_of_failed_requests_do_not_block_the_publish(tmp_path, monkeypatch):
    """A rate over one or two requests says nothing, and used to block everything.

    Regression: a settled night asks the model for a handful of new paragraphs. One transient
    failure out of one request read as 0% success, so the run published nothing at all -- every
    other page included, all of them unchanged and fine -- and went red.
    """
    no_gpu(monkeypatch)
    bucket = tmp_path / "bucket"
    en, pages = write_many(tmp_path / "docs")
    args = make_args(bucket, tmp_path / "docs")
    warm_cache(bucket, en, args)
    root = publish.lang_root(bucket, "testpkg", "ja")
    assert run(args, en) == 0
    before = publish.read_pointer(root)

    # one page gains one short paragraph, and the model fails that single request
    (en / "p4.md").write_text(pages["p4.md"] + "\nA newly added sentence.\n", encoding="utf-8")
    monkeypatch.setattr(pipeline, "translate_segments", lambda segs, *a, **k: ({}, [(k, "failed") for k in segs]))

    code = run(args, en)
    assert code != 2, "one failed request out of one must not block the publish"
    assert publish.read_pointer(root) != before  # the other nine pages were republished


def test_a_fallback_page_keeps_being_reported(tmp_path, monkeypatch, capsys):
    """A page published as English must not go quiet the morning after it broke.

    Regression: the manifest recorded the English fallback as that page's correct output, so the
    next run found the tree current, exited 0 and said nothing. Reproduced over three runs: the
    page stayed English for good behind a green job.
    """
    no_gpu(monkeypatch)
    bucket = tmp_path / "bucket"
    en, pages = write_many(tmp_path / "docs")
    args = make_args(bucket, tmp_path / "docs")
    warm_cache(bucket, en, args)

    # poison two of p3's paragraphs so it lands below the coverage bar on every run
    gloss = pipeline.glossary_sha(pipeline.load_glossary(pipeline.glossary_path("ja")))
    plan = pipeline.PagePlan("p3.md", pages["p3.md"], "ja", args.model, gloss)
    bad = [k for k, v in plan.segments.items() if "alpha" in v or "beta" in v]
    cache = SegmentCache(bucket)
    cache.put_many(dict.fromkeys(bad, ""))  # empty -> rejected, and it stays cached
    cache.save_index()

    assert run(args, en) != 0  # the night it breaks
    capsys.readouterr()

    assert run(args, en) != 0, "a page still published as a fallback must keep the job red"
    out = capsys.readouterr().out
    assert "still published as a fallback" in out
    assert "p3.md" in out


def test_pages_file_writes_to_a_preview_tree(env, tmp_path):
    """A smoke run must not touch the live tree."""
    assert run(env.args, env.en) == 0
    before = publish.read_pointer(env.root)

    pages_file = tmp_path / "pages.txt"
    pages_file.write_text("# just the one\n  # indented comment\nguide.md\n", encoding="utf-8")
    preview_args = make_args(env.bucket, env.tmp / "docs", pages_file=str(pages_file))
    assert run(preview_args, env.en) == 0

    preview = publish.lang_root(env.bucket, "testpkg", "ja.preview")
    assert (preview / "guide.md").is_file()
    assert not (preview / "index.md").exists()
    assert publish.read_pointer(env.root) == before


def test_sidebar_entry_without_a_page_publishes_nothing(tmp_path, monkeypatch):
    """The sidebar is the other half of the snapshot, and it was never checked against the pages.

    Regression: an entry with no page behind it published a generation the sidebar points past --
    which doc-builder refuses to build -- and the run exited 0.
    """
    no_gpu(monkeypatch)
    bucket = tmp_path / "bucket"
    en, _pages = write_many(tmp_path / "docs", 6)
    args = make_args(bucket, tmp_path / "docs")
    warm_cache(bucket, en, args)
    root = publish.lang_root(bucket, "testpkg", "ja")
    assert run(args, en) == 0
    before = publish.read_pointer(root)

    # the sidebar gains an entry with no file behind it
    (en / "_toctree.yml").write_text(
        yaml.safe_dump(
            [{"sections": [{"local": f"p{i}", "title": f"Page {i}"} for i in range(7)], "title": "Start"}],
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    assert run(args, en) == 2
    assert publish.read_pointer(root) == before


def test_unreadable_cache_blob_is_dropped_from_the_index(env, monkeypatch):
    """Being listed in the index is not the same as being readable.

    Regression: a missing blob left its paragraph in English while the key stayed indexed, so the
    model was never asked for it again and every later run reported success. Noticed on a run
    that actually assembles, which is the run where the paragraph would go out in English.
    """
    assert run(env.args, env.en) == 0
    cache = SegmentCache(env.bucket)
    victim = sorted(cache.load_index())[0]
    cache._blob_path(victim).unlink()

    rebuild = make_args(env.bucket, env.tmp / "docs", rebuild=True)
    run(rebuild, env.en)
    assert victim not in SegmentCache(env.bucket).load_index()


def test_preview_with_no_matching_page_fails(env, tmp_path):
    """A pages file that matches nothing wrote an empty tree and exited 0."""
    pages_file = tmp_path / "pages.txt"
    pages_file.write_text("does_not_exist.md\n", encoding="utf-8")
    args = make_args(env.bucket, env.tmp / "docs", pages_file=str(pages_file))
    assert run(args, env.en) == 2


def test_damaged_live_generation_is_rebuilt_under_a_new_name(env):
    """A published generation is never written into.

    Repairing in place replaces its files one at a time under whoever is reading it, and leaves
    any unexpected extra file exactly where it was -- so it could never verify again.
    """
    assert run(env.args, env.en) == 0
    first = publish.read_pointer(env.root)
    (publish.generation_dir(env.root, first) / "index.md").write_text("damaged\n", encoding="utf-8")

    assert run(env.args, env.en) == 0
    second = publish.read_pointer(env.root)
    assert second != first
    assert "damaged" not in (live(env.root) / "index.md").read_text(encoding="utf-8")


def test_gc_never_removes_the_published_generation(env):
    """GC re-reads the pointer rather than trusting what a caller captured earlier."""
    for i in range(6):
        (env.en / "index.md").write_text(f"# Home\n\nBody {i}.\n", encoding="utf-8")
        warm_cache(env.bucket, env.en, env.args)
        assert run(env.args, env.en) == 0
    live_name = publish.read_pointer(env.root)
    kept = {p.name for p in (env.root / publish.GENERATIONS).iterdir() if p.is_dir()}
    assert live_name in kept
    assert len(kept) <= publish.KEEP_GENERATIONS
    assert (live(env.root) / "index.md").is_file()
