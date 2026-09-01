"""End-to-end page and toctree pipeline, with an identity translator instead of a GPU.

`test_identity_pipeline_reproduces_page` is stronger than the mask/restore round-trip in
test_segment.py: it runs the code the job actually calls -- plan_page, cache keying,
assemble_page, restore -- so a bug in block indexing or reassembly shows up here.
"""

import os
import pathlib
import re

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
    _, rebuilt, _ = pipeline.assemble_page(plan, identity)
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
    _, rebuilt, _ = pipeline.assemble_page(plan, partial)
    assert "# タイトル" in rebuilt
    assert "First." in rebuilt  # untranslated block survives rather than vanishing


def test_pure_placeholder_blocks_are_not_sent_to_the_model():
    source = "# Title\n\n```py\nprint(1)\n```\n\n[[autodoc]] BertModel\n    - forward\n"
    plan = plan_for("p.md", source)
    for unit in plan.units.values():
        assert unit.text
        assert "print(1)" not in unit.text
        assert "[[autodoc]]" not in unit.text


def test_a_dropped_marker_is_caught_before_it_reaches_the_page():
    """A paragraph that loses its markers is turned down and left in English.

    On a one-paragraph page that means the whole page ends up English, which page validation
    then rejects as "identical to the English source" -- the right answer, reached a step
    earlier than it used to be. On a real page the other paragraphs still get translated.
    """
    source = "Call `fit` on the `Trainer`.\n"
    plan = plan_for("p.md", source)
    key = next(iter(plan.segments))
    masked_translation, rebuilt, outcome = pipeline.assemble_page(plan, {key: "呼び出します。"})

    assert outcome.rejected == [key]
    assert rebuilt == source  # left exactly as it was found
    result = pipeline.validate_plan(plan, masked_translation)
    assert not result.ok
    assert any("identical to the English source" in f for f in result.failures)


def test_token_budget_scales_with_content_not_prompt():
    """Regression: budgeting off the full prompt over-allocated ~6x on short blocks.

    The system prompt dwarfs the median 65-char segment, so the budget must come from the
    segment alone.
    """

    class FakeTok:
        def apply_chat_template(self, msgs, tokenize=True, add_generation_prompt=True, return_dict=True, **kw):
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

        def apply_chat_template(self, msgs, tokenize=True, add_generation_prompt=True, return_dict=True, **kw):
            return {"input_ids": [1, 2, 3], "attention_mask": [1, 1, 1]}

        def encode(self, text, add_special_tokens=False):
            return [1, 2, 3]

    with pytest.raises(TypeError, match="list of token ids"):
        pipeline.build_requests({"k": "some prose"}, DictOnlyTok(), "ja", {})


def test_paragraph_that_loses_a_marker_stays_english():
    """Regression: one bad paragraph used to fail the whole page.

    The model paraphrases a marker away when it stands for short inline code -- writing "from
    the checkpoint" instead of keeping `config.json`. That was 4 paragraphs out of 402 and it
    cost 3 entire pages.
    """
    source = "Set `a` to `b` now.\n\nA second paragraph with `c` in it.\n"
    plan = plan_for("p.md", source)
    units = [plan.units[i] for i in sorted(plan.units)]
    good, bad = units[0], units[1]
    translations = {
        good.key: good.text,  # markers intact
        bad.key: "マーカーを落とした訳文",  # markers gone
    }
    _, rebuilt, outcome = pipeline.assemble_page(plan, translations)
    assert outcome.rejected == [bad.key]
    assert "A second paragraph with `c` in it." in rebuilt  # the bad one stayed English
    assert "Set `a` to `b` now." in rebuilt  # the good one round-tripped


def test_reordered_markers_are_accepted():
    """Japanese word order differs, so moving a marker is fine -- only losing one is not."""
    plan = plan_for("p.md", "Use `a` before `b`.\n")
    unit = next(iter(plan.units.values()))
    swapped = unit.text.replace("¤0¤", "TMP").replace("¤1¤", "¤0¤").replace("TMP", "¤1¤")
    _, _, outcome = pipeline.assemble_page(plan, {unit.key: swapped})
    assert outcome.rejected == []


def test_reasoning_block_is_stripped():
    """Regression: Qwen3 returned pages of <think> and never reached the translation.

    Every page failed validation with "0 headings" and duplicated markers, because what got
    cached was the model talking to itself about the markers.
    """
    thought = "<think>\nOkay, the user wants me to translate. Keep \u00a40\u00a4 in place.\n</think>\n"
    assert pipeline.strip_reasoning(thought + "# \u898b\u51fa\u3057\n") == "# \u898b\u51fa\u3057\n"
    # other tag spellings, and case
    assert pipeline.strip_reasoning("<Thinking>x</Thinking>\n\u8a33") == "\u8a33"
    # a page that legitimately mentions the tag mid-text is left alone
    body = "\u8a33\u6587 <think>not at the start</think>"
    assert pipeline.strip_reasoning(body) == body
    # no reasoning at all is a no-op
    assert pipeline.strip_reasoning("# \u898b\u51fa\u3057\n") == "# \u898b\u51fa\u3057\n"


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
    assert gloss["pin"]["fine-tune"] == "微調整"
    assert "Hub" in gloss["keep"]
    matched = pipeline.glossary_for_segment("How to fine-tune a model", gloss)
    assert matched == {"fine-tune": "微調整"}


@needs_corpus
def test_glossary_keys_are_whole_words():
    """Regression: a stem key like `fine-tun` was shown to the model, which then wrote
    "微調整（fine-tun）" into the page.

    The key is both the thing we match on and the English term the model is shown, so it has to
    be a real word. Checked against the corpus: every key must appear followed by a word
    boundary somewhere in the English docs.
    """
    gloss = pipeline.load_glossary(pipeline.glossary_path("ja"))
    corpus = "\n".join(p.read_text(encoding="utf-8") for p in ALL_PAGES[:400]).lower()
    stems = [term for term in gloss["pin"] if not re.search(rf"{re.escape(term.lower())}\b", corpus)]
    assert not stems, f"glossary keys that are not whole words: {stems}"


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


def test_empty_translation_keeps_the_english():
    """A paragraph translated to nothing must not be deleted from the page.

    Regression: for a paragraph with no markers in it, `""` matched the source's empty marker
    list and passed the invented-bracket check, so the paragraph was replaced with nothing.
    The page still passed validation, because whole-page checks only ask whether *something*
    was translated -- one silently deleted paragraph does not show up there.
    """
    source = "# Title\n\nFirst paragraph.\n\nSecond paragraph.\n"
    plan = pipeline.PagePlan("p.md", source, "ja", "m", "g")
    keys = list(plan.segments)
    translations = dict.fromkeys(keys, "翻訳")
    empty_key = next(k for k, v in plan.segments.items() if v == "First paragraph.")
    translations[empty_key] = ""

    _, page_text, outcome = pipeline.assemble_page(plan, translations)
    assert empty_key in outcome.rejected
    assert "First paragraph." in page_text  # kept, not dropped


def test_marker_only_translation_keeps_the_english():
    """Markers alone are not a translation either -- the prose is still gone."""
    source = "Run `pip install` to begin.\n"
    plan = pipeline.PagePlan("p.md", source, "ja", "m", "g")
    key = next(iter(plan.segments))
    _, page_text, outcome = pipeline.assemble_page(plan, {key: "  ¤0¤  "})
    assert outcome.rejected == [key]
    assert "to begin." in page_text


def test_has_prose():
    assert pipeline.has_prose("こんにちは")
    assert pipeline.has_prose("¤0¤ を使う")
    assert not pipeline.has_prose("")
    assert not pipeline.has_prose("   \n ")
    assert not pipeline.has_prose("¤0¤¤1¤")


def test_empty_toctree_title_falls_back_to_english():
    """An empty sidebar title reads as a missing page, not an untranslated one."""
    toc_keys = {"k1": "Quickstart", "k2": "Installation"}
    from doc_builder.commands.translate import translated_titles

    titles = translated_titles(toc_keys, {"k1": "クイックスタート", "k2": "  "})
    assert titles == {"Quickstart": "クイックスタート", "Installation": "Installation"}
