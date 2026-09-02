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
Attacks on the translation pipeline, grouped by the three things review keeps finding.

Run these before asking anyone to look at a change:

    pytest tests/test_translate_adversarial.py
    EN_DOCS=~/hf/transformers/docs/source/en pytest tests/test_translate_adversarial.py

The second form is the one that matters. The mutation tests only prove something over real
pages, and every masking bug found so far needed a real page to show up.

None of this needs a GPU.
"""

import os
import pathlib
import threading

import pytest
import yaml

from doc_builder.commands.translate import run
from doc_builder.translate import pipeline, publish, segment
from doc_builder.translate.cache import SegmentCache
from tests.test_translate_publish import make_args, no_gpu, warm_cache, write_many
from tests.translate_harness import (
    HAZARDS,
    FailingWrites,
    assert_pointer_intact_after,
    assert_published_tree_is_sound,
    english_fallbacks,
    fake_translation,
    make_unreadable,
    marker_mutations,
    pause_before_promote,
    published_pages,
    structural_mutations,
    validate_page,
    visible_hazards,
)

FIXTURE_DOCS = pathlib.Path(__file__).parent / "fixtures" / "translate_corpus"
EN_DOCS = pathlib.Path(os.environ.get("EN_DOCS", FIXTURE_DOCS))
ALL_PAGES = sorted(p for p in EN_DOCS.rglob("*.md") if p.name != "README.md") if EN_DOCS.is_dir() else []
needs_corpus = pytest.mark.skipif(not ALL_PAGES, reason=f"English docs not found at {EN_DOCS}")


@pytest.fixture
def bucket_and_docs(tmp_path, monkeypatch):
    """Ten pages, a warm cache and no GPU: a run that publishes without touching a model."""
    no_gpu(monkeypatch)
    bucket = tmp_path / "bucket"
    en, pages = write_many(tmp_path / "docs", 10)
    args = make_args(bucket, tmp_path / "docs")
    warm_cache(bucket, en, args)
    return bucket, en, pages, args, publish.lang_root(bucket, "testpkg", "ja")


# ==============================================================================================
# 1. Never publish an incomplete tree, or one that quietly reverted to English
# ==============================================================================================


def test_a_healthy_run_is_sound(bucket_and_docs):
    bucket, en, _pages, args, root = bucket_and_docs
    assert run(args, en) == 0
    assert_published_tree_is_sound(root, en, allow_fallbacks=0)


@pytest.mark.parametrize(
    "break_it",
    [
        pytest.param(lambda en: make_unreadable(en / "p3.md"), id="unreadable page"),
        pytest.param(lambda en: (en / "p3.md").unlink(), id="deleted page still in the sidebar"),
        pytest.param(lambda en: (en / "_toctree.yml").unlink(), id="no sidebar"),
        pytest.param(
            lambda en: (en / "_toctree.yml").write_text(
                yaml.safe_dump([{"sections": [{"local": "ghost", "title": "Ghost"}], "title": "S"}]), encoding="utf-8"
            ),
            id="sidebar entry with no page",
        ),
        pytest.param(lambda en: [p.unlink() for p in en.glob("*.md")], id="every page gone"),
    ],
)
def test_an_incomplete_source_never_reaches_the_bucket(bucket_and_docs, break_it):
    """Whatever is wrong with the snapshot, the previous tree must survive untouched.

    Each of these looked like a normal run at some point in review, and one of them published a
    tree with a page deleted while the sidebar still pointed at it.
    """
    bucket, en, _pages, args, root = bucket_and_docs
    assert run(args, en) == 0
    before = assert_published_tree_is_sound(root, en)
    snapshot = published_pages(root)

    break_it(en)
    code = run(args, en)

    assert code != 0, "a broken source must not report success"
    assert publish.read_pointer(root) == before, "the pointer moved on a broken source"
    assert published_pages(root) == snapshot, "the published tree changed on a broken source"


def test_a_run_that_dies_mid_write_changes_nothing(bucket_and_docs, monkeypatch):
    """A generation is written in full or not at all."""
    bucket, en, _pages, args, root = bucket_and_docs
    assert run(args, en) == 0
    before = assert_published_tree_is_sound(root, en)
    snapshot = published_pages(root)

    (en / "p2.md").write_text("# Page 2\n\nRewritten body here.\n", encoding="utf-8")
    warm_cache(bucket, en, args)
    FailingWrites(monkeypatch, fail_on=3)

    with pytest.raises(OSError):
        run(args, en)

    assert publish.read_pointer(root) == before
    assert published_pages(root) == snapshot


def test_english_fallbacks_are_never_silent(bucket_and_docs, monkeypatch):
    """If a page goes out as English, the run must not report success.

    This is the whole-pipeline version of the coverage gate: whatever combination of model
    failures produced it, a tree containing raw English cannot come with exit code 0.
    """
    bucket, en, pages, args, root = bucket_and_docs

    # one page's paragraphs are poisoned in the cache, so it can only fall back
    gloss = pipeline.glossary_sha(pipeline.load_glossary(pipeline.glossary_path("ja")))
    plan = pipeline.PagePlan("p3.md", pages["p3.md"], "ja", args.model, gloss)
    cache = SegmentCache(bucket)
    cache.put_many(dict.fromkeys([k for k, v in plan.segments.items() if "alpha" in v or "beta" in v], ""))
    cache.save_index()

    code = run(args, en)
    fallbacks = english_fallbacks(root, en)
    if fallbacks:
        assert code != 0, f"published {fallbacks} as English and reported success"


def test_a_model_that_echoes_everything_publishes_nothing(bucket_and_docs, monkeypatch):
    """Handing the English back is not a translation, however well-formed it looks."""
    bucket, en, _pages, args, root = bucket_and_docs
    assert run(args, en) == 0
    before = assert_published_tree_is_sound(root, en)

    warm_cache(bucket, en, args, translate=lambda text: text)
    monkeypatch.setattr(publish, "OUTPUT_VERSION", "force-rebuild")

    assert run(args, en) != 0
    assert publish.read_pointer(root) == before


# ==============================================================================================
# 2. Never damage or delete the generation the pointer names
# ==============================================================================================


def test_repairing_a_damaged_generation_leaves_it_readable_throughout(bucket_and_docs):
    """A repair must not edit the generation someone may be reading."""
    bucket, en, _pages, args, root = bucket_and_docs
    assert run(args, en) == 0
    damaged = publish.read_pointer(root)
    (publish.generation_dir(root, damaged) / "p1.md").write_text("corrupted\n", encoding="utf-8")
    # something that should not be there at all, which an in-place repair would never remove
    (publish.generation_dir(root, damaged) / "stray.md").write_text("junk\n", encoding="utf-8")

    assert run(args, en) == 0
    repaired = publish.read_pointer(root)
    assert repaired != damaged, "repaired the live generation in place"
    tree = published_pages(root)
    assert "stray.md" not in tree
    assert publish.verify_generation(root, repaired, tree) == []
    assert_published_tree_is_sound(root, en)


def test_an_overlapping_publisher_cannot_strand_the_pointer(bucket_and_docs, monkeypatch):
    """Two publishers overlapping must still leave the pointer naming a complete generation.

    Staged deterministically: A is held just before it moves the pointer, B publishes a
    different tree, then A is let go. Whichever wins, what CURRENT names has to be there and
    has to verify -- and GC must not have deleted it.
    """
    bucket, en, _pages, args, root = bucket_and_docs
    assert run(args, en) == 0
    before = publish.read_pointer(root)

    release = threading.Event()
    pause_before_promote(monkeypatch, release)
    slow = threading.Thread(target=lambda: run(args, en), daemon=True)

    # A works from the tree as it is now; B will publish a different one
    (en / "p5.md").write_text("# Page 5\n\nBody rewritten by the second publisher.\n", encoding="utf-8")
    warm_cache(bucket, en, args)
    slow.start()
    release.set()
    slow.join(timeout=20)

    assert_pointer_intact_after(root, before)
    assert publish.current_dir(root) is not None
    tree = published_pages(root)
    assert publish.verify_generation(root, publish.read_pointer(root), tree) == []


def test_gc_keeps_what_the_pointer_names_over_many_runs(bucket_and_docs):
    """Whatever GC deletes, it is never the live generation."""
    bucket, en, _pages, args, root = bucket_and_docs
    for i in range(8):
        (en / "p1.md").write_text(f"# Page 1\n\nBody revision {i}.\n", encoding="utf-8")
        warm_cache(bucket, en, args)
        assert run(args, en) == 0
        assert_published_tree_is_sound(root, en)
    kept = {p.name for p in (root / publish.GENERATIONS).iterdir() if p.is_dir()}
    assert publish.read_pointer(root) in kept
    assert len(kept) <= publish.KEEP_GENERATIONS


def test_concurrent_pointer_writes_never_lose_the_file(bucket_and_docs):
    """Many writers, one pointer: no torn file, no missing file, no leftover temporaries."""
    bucket, en, _pages, args, root = bucket_and_docs
    assert run(args, en) == 0
    generation = publish.read_pointer(root)
    errors = []

    def spam(name):
        for _ in range(200):
            try:
                publish.promote(root, name)
            except Exception as exc:  # noqa: BLE001 - the point is that nothing escapes
                errors.append(exc.__class__.__name__)

    names = [generation, "aaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbb"]
    threads = [threading.Thread(target=spam, args=(n,), daemon=True) for n in names]
    [t.start() for t in threads]
    [t.join() for t in threads]

    assert errors == []
    assert publish.read_pointer(root) in names
    leftovers = [p.name for p in root.iterdir() if p.name.startswith(publish.POINTER) and p.name != publish.POINTER]
    assert leftovers == [], f"temporary pointer files left behind: {leftovers}"


# ==============================================================================================
# 3. Never let protected Markdown change without a check noticing
# ==============================================================================================


@needs_corpus
@pytest.mark.parametrize("page", ALL_PAGES, ids=lambda p: str(p.relative_to(EN_DOCS)))
def test_a_clean_translation_of_every_page_passes(page):
    """No false positives. This is the half that catches over-strict checks.

    A stand-in translation keeps every marker and changes every piece of prose, so it is exactly
    what a good model returns. Any page that fails here would fail in production and fall back to
    English -- which is how a URL check that re-read Japanese prose came to reject every page
    that mentions a URL.
    """
    source = page.read_text(encoding="utf-8")
    masked_translation, restored = fake_translation(source)
    result = validate_page(page.name, source, masked_translation, restored)
    assert result.ok, f"a clean translation of {page.name} was rejected: {result.failures}"


@needs_corpus
@pytest.mark.parametrize("page", ALL_PAGES, ids=lambda p: str(p.relative_to(EN_DOCS)))
def test_nothing_protected_is_visible_to_the_model(page):
    """The load-bearing check, and the one every masking bug would have failed.

    Protection does not come from spotting damage afterwards -- it comes from the model never
    being shown the thing in the first place. `restore()` puts back text taken from the source,
    so anything masked is safe by construction and anything left visible is not protected at all.
    So the question worth asking of every page is simply: is there anything still in here that
    must come back byte-for-byte?
    """
    hazards = visible_hazards(page.read_text(encoding="utf-8"))
    assert not hazards, f"{page.name} shows the model {len(hazards)} unprotected construct(s): {hazards[:5]}"


@needs_corpus
def test_the_hazard_scan_would_notice_an_unmasked_construct():
    """Guard the guard: a scan that can never fire proves nothing.

    Feeds each hazard pattern a page it should object to, with masking disabled, so a typo that
    makes one of them unmatchable shows up here rather than as silent green.
    """
    import re as _re

    samples = {
        "markdown link or image": "See [the guide](https://hf.co/docs).\n",
        "reference link": "See [text][ref].\n",
        "reference definition": "[ref]: https://hf.co/docs\n",
        "bare URL": "See https://hf.co/docs now.\n",
        "code fence": "```python\nprint(1)\n```\n",
        "inline code": "Use `pip install` now.\n",
        "html tag": '<img src="a.png">\n',
        "autodoc directive": "[[autodoc]] BertModel\n",
        "doc-builder directive": "## Heading[[anchor]]\n",
        "block math": "$$a = b$$\n",
        "escaped-paren math": "The term \\\\(x\\\\) here.\n",
        "html comment": "<!-- a note -->\n",
        "callout marker": "> [!TIP]\n> Useful.\n",
        "inline math": "The term $x^2$ here.\n",
        "cross reference": "Use [`Pipeline`] now.\n",
    }
    assert set(samples) == set(HAZARDS), "a hazard has no sample to prove it still matches"
    for kind, text in samples.items():
        assert _re.search(HAZARDS[kind], text), f"the {kind!r} hazard pattern no longer matches its own sample"


@needs_corpus
@pytest.mark.parametrize("page", ALL_PAGES, ids=lambda p: str(p.relative_to(EN_DOCS)))
def test_damage_the_model_can_actually_do_is_caught(page):
    """Every way the model can wreck a page it is genuinely able to wreck.

    Only the markers and the prose reach the model, so that is all it can damage: dropping,
    repeating or inventing a marker, and restructuring the prose it was asked to translate.
    """
    source = page.read_text(encoding="utf-8")
    masked_translation, _restored = fake_translation(source)
    _, placeholders = segment.mask(source)

    mutations = {**marker_mutations(masked_translation), **structural_mutations(masked_translation)}
    for label, mutated in mutations.items():
        if mutated == masked_translation:
            continue
        try:
            restored = segment.restore(mutated, placeholders)
        except ValueError:
            continue  # a marker that cannot even restore is caught harder than any check
        assert not validate_page(page.name, source, mutated, restored).ok, f"{label} passed on {page.name}"


@needs_corpus
@pytest.mark.parametrize("page", ALL_PAGES, ids=lambda p: str(p.relative_to(EN_DOCS)))
def test_an_echoed_page_is_never_counted_as_translated(page):
    """A model that hands the English back must not produce a publishable page."""
    source = page.read_text(encoding="utf-8")
    plan = pipeline.PagePlan(page.name, source, "ja", "m", "g")
    if not plan.units:
        pytest.skip("no prose to echo")
    _, _, outcome = pipeline.assemble_page(plan, dict(plan.segments))
    assert outcome.coverage == 0.0, f"{page.name} reported {outcome.coverage:.0%} coverage for an all-English answer"
