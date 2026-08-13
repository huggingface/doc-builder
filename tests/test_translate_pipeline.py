"""End-to-end page and toctree pipeline, with an identity translator instead of a GPU.

`test_identity_pipeline_reproduces_page` is stronger than the mask/restore round-trip in
test_segment.py: it runs the code the job actually calls -- plan_page, cache keying,
assemble_page, restore -- so a bug in block indexing or reassembly shows up here.
"""

import os
import pathlib

import pytest
import yaml

from doc_builder.translate import pipeline

EN_DOCS = pathlib.Path(os.environ.get("EN_DOCS", "/Users/steven/hf/transformers/docs/source/en"))
ALL_PAGES = sorted(EN_DOCS.rglob("*.md")) if EN_DOCS.is_dir() else []
MODEL = "google/gemma-4-26B-A4B-it"
GLOSSARY = {"pin": {"tokenizer": "トークナイザー", "training": "トレーニング"}, "keep": ["Hub"]}

# Only the tests that read the real corpus skip when it is absent. Applying this at module
# level meant 27 of 32 tests never ran on CI or on any machine but the author's.
needs_corpus = pytest.mark.skipif(not ALL_PAGES, reason=f"English docs not found at {EN_DOCS}")


def plan_for(page, source):
    return pipeline.PagePlan(page, source, "ja", MODEL, "sha")


@needs_corpus
@pytest.mark.parametrize("page", ALL_PAGES, ids=lambda p: str(p.relative_to(EN_DOCS)))
def test_identity_pipeline_reproduces_page(page):
    """Translating each segment to itself must rebuild the page byte-for-byte."""
    source = page.read_text(encoding="utf-8")
    plan = plan_for(str(page.relative_to(EN_DOCS)), source)
    identity = {u.key: u.text for u in plan.units.values()}
    _, rebuilt = pipeline.assemble_page(plan, identity)
    assert rebuilt == source


def test_every_translatable_block_gets_a_unique_key():
    """Distinct blocks must not collide; identical blocks should share a key."""
    source = "# A\n\nOne paragraph.\n\nAnother paragraph.\n\nOne paragraph.\n"
    plan = plan_for("p.md", source)
    assert len(plan.units) == 4  # heading + 3 paragraphs
    assert len(plan.segments) == 3  # the repeat shares a key, so it is sent once


def test_missing_translation_falls_back_to_english():
    source = "# Title\n\nFirst.\n\nSecond.\n"
    plan = plan_for("p.md", source)
    first = plan.units[min(plan.units)]
    partial = {first.key: "# タイトル"}
    _, rebuilt = pipeline.assemble_page(plan, partial)
    assert "# タイトル" in rebuilt
    assert "First." in rebuilt  # untranslated block survives rather than vanishing


def test_pure_placeholder_blocks_are_not_sent_to_the_model():
    source = "# Title\n\n```py\nprint(1)\n```\n\n[[autodoc]] BertModel\n    - forward\n"
    plan = plan_for("p.md", source)
    for unit in plan.units.values():
        assert unit.text
        assert "print(1)" not in unit.text
        assert "[[autodoc]]" not in unit.text


def test_validation_catches_a_model_that_drops_a_placeholder():
    source = "Call `fit` on the `Trainer`.\n"
    plan = plan_for("p.md", source)
    key = next(iter(plan.segments))
    masked_translation, _ = pipeline.assemble_page(plan, {key: "呼び出します。"})
    result = pipeline.validate_plan(plan, masked_translation)
    assert not result.ok
    assert any("dropped" in f for f in result.failures)


def test_token_budget_scales_with_content_not_prompt():
    """Regression: budgeting off the full prompt over-allocated ~6x on short blocks.

    The system prompt dwarfs the median 65-char segment, so the budget must come from the
    segment alone.
    """

    class FakeTok:
        def apply_chat_template(self, msgs, tokenize=True, add_generation_prompt=True, return_dict=True):
            # Mirrors transformers v5: a BatchEncoding unless return_dict=False is asked for.
            ids = list(range(sum(len(m["content"]) for m in msgs) // 4))
            return {"input_ids": ids, "attention_mask": [1] * len(ids)} if return_dict else ids

        def encode(self, text, add_special_tokens=False):
            return list(range(len(text) // 4))

    short, long = "## Notes", "x" * 4000
    reqs = {
        key: (len(prompt), budget)
        for key, prompt, budget in pipeline.build_requests({"short": short, "long": long}, FakeTok(), "ja", {})
    }
    short_prompt, short_budget = reqs["short"]
    long_prompt, long_budget = reqs["long"]

    assert short_budget < short_prompt  # budget is not driven by prompt size
    assert short_budget >= 48  # but never below the floor
    assert long_budget > long_prompt  # long content gets room to expand into Japanese


def test_build_requests_asks_for_token_ids_not_a_batchencoding():
    """Regression: v5 defaults return_dict=True, so we got a dict and the batcher saw its keys.

    The real failure was "too many dimensions 'str'" thrown deep inside the batcher, because it
    iterated the dict and tried to tensorise the strings "input_ids" and "attention_mask".
    """

    class DictOnlyTok:
        """A tokenizer that ignores return_dict -- stands in for a future default change."""

        def apply_chat_template(self, msgs, tokenize=True, add_generation_prompt=True, return_dict=True):
            return {"input_ids": [1, 2, 3], "attention_mask": [1, 1, 1]}

        def encode(self, text, add_special_tokens=False):
            return [1, 2, 3]

    with pytest.raises(TypeError, match="list of token ids"):
        pipeline.build_requests({"k": "some prose"}, DictOnlyTok(), "ja", {})


# -- glossary -------------------------------------------------------------------


def test_only_matching_glossary_terms_reach_the_prompt():
    prompt = pipeline.build_prompt("The tokenizer is fast.", "ja", GLOSSARY)
    system = prompt[0]["content"]
    assert "トークナイザー" in system
    assert "トレーニング" not in system  # 'training' absent from the segment


def test_prompt_omits_glossary_block_when_nothing_matches():
    system = pipeline.build_prompt("Nothing relevant here.", "ja", GLOSSARY)[0]["content"]
    assert pipeline.GLOSSARY_HEADER not in system


def test_glossary_sha_is_stable_and_sensitive():
    a = pipeline.glossary_sha(GLOSSARY)
    assert a != pipeline.glossary_sha({"pin": {"tokenizer": "別の訳"}})


def test_shipped_glossary_loads_and_pins_are_reachable():
    gloss = pipeline.load_glossary(pipeline.glossary_path("ja"))
    assert gloss["pin"]["fine-tun"] == "微調整"
    assert "Hub" in gloss["keep"]
    matched = pipeline.glossary_for_segment("How to fine-tune a model", gloss)
    assert matched == {"fine-tun": "微調整"}


# -- disclosure -----------------------------------------------------------------


@needs_corpus
def test_disclosure_lands_after_the_license_header():
    source = (EN_DOCS / "philosophy.md").read_text(encoding="utf-8")
    out = pipeline.add_disclosure(source, "philosophy.md", "ja", "transformers")
    assert out.startswith("<!--")
    header_end = out.index("-->") + 3
    assert "> [!TIP]" in out[header_end : header_end + 400]
    assert "機械翻訳" in out


def test_disclosure_without_license_header_goes_first():
    out = pipeline.add_disclosure("# Title\n", "p.md", "ja", "transformers")
    assert out.startswith("> [!TIP]")


def test_disclosure_links_to_the_english_page():
    out = pipeline.add_disclosure("# T\n", "tasks/summarization.md", "ja", "transformers")
    assert "docs/transformers/en/tasks/summarization" in out


def test_disclosure_urls_follow_the_package():
    """Regression: both URLs were hardcoded to transformers in a package-generic command."""
    out = pipeline.add_disclosure("# T\n", "quicktour.md", "ja", "diffusers")
    assert "docs/diffusers/en/quicktour" in out
    assert "huggingface/diffusers/issues" in out
    assert "transformers" not in out


# -- toctree --------------------------------------------------------------------


@needs_corpus
def test_real_toctree_survives_translate_and_reparse():
    """The invariant that matters: every `local:` target survives a dump/re-parse."""
    tree = yaml.safe_load((EN_DOCS / "_toctree.yml").read_text(encoding="utf-8"))
    titles = pipeline.toctree_titles(tree)
    locals_ = pipeline.toctree_values(tree, "local")
    assert len(titles) > 700 and len(locals_) > 700

    pipeline.apply_toctree_titles(tree, {t: f"[ja] {t}" for t in titles})
    dumped = yaml.safe_dump(tree, sort_keys=False, allow_unicode=True)
    reparsed = yaml.safe_load(dumped)
    assert pipeline.toctree_values(reparsed, "local") == locals_
    assert pipeline.toctree_titles(reparsed) == [f"[ja] {t}" for t in titles]


def test_toctree_translates_titles_and_preserves_locals():
    tree = yaml.safe_load("- sections:\n  - local: quicktour\n    title: Quickstart\n  title: Get started\n")
    pipeline.apply_toctree_titles(tree, {"Quickstart": "クイックツアー", "Get started": "はじめに"})
    assert tree[0]["sections"][0]["local"] == "quicktour"
    assert tree[0]["sections"][0]["title"] == "クイックツアー"
    assert tree[0]["title"] == "はじめに"


def test_prune_toctree_keeps_only_selected_pages():
    """Regression: a --pages-file run wrote the full toctree, which doc-builder refuses to build.

    Verified before the fix: 3 translated pages beside a 734-entry toctree failed with
    "Remove them from _toctree.yml", so smoke-run output could be neither built nor previewed.
    """
    tree = yaml.safe_load(
        "- sections:\n"
        "  - local: keep_me\n    title: Keep\n"
        "  - local: drop_me\n    title: Drop\n"
        "  title: Group A\n"
        "- sections:\n"
        "  - local: also_dropped\n    title: Gone\n"
        "  title: Group B\n"
    )
    pruned = pipeline.prune_toctree(tree, {"keep_me"})
    assert pipeline.toctree_values(pruned, "local") == ["keep_me"]
    # Group B lost every child, so the group goes too rather than rendering empty.
    # Parent before children, matching how the nav renders.
    assert pipeline.toctree_titles(pruned) == ["Group A", "Keep"]


def test_prune_toctree_drops_nested_groups_that_empty_out():
    tree = yaml.safe_load(
        "- isExpanded: true\n  sections:\n  - isExpanded: false\n    sections:\n"
        "    - local: a\n      title: A\n    title: Inner\n  title: Outer\n"
    )
    assert pipeline.prune_toctree(tree, {"a"}) is not None
    assert pipeline.prune_toctree(tree, {"nothing"}) is None


@needs_corpus
def test_prune_toctree_on_the_real_corpus():
    tree = yaml.safe_load((EN_DOCS / "_toctree.yml").read_text(encoding="utf-8"))
    keep = {"index", "quicktour", "model_doc/bert"}
    pruned = pipeline.prune_toctree(tree, keep)
    assert set(pipeline.toctree_values(pruned, "local")) == keep
    # And far fewer titles to translate than the ~756 of the full tree.
    assert len(pipeline.toctree_titles(pruned)) < 20


def test_toctree_values_collects_locals_and_titles_separately():
    tree = yaml.safe_load("- sections:\n  - local: a\n    title: A\n  - local: b\n    title: B\n")
    assert pipeline.toctree_values(tree, "local") == ["a", "b"]
    assert pipeline.toctree_values(tree, "title") == ["A", "B"]
