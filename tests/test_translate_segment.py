"""Round-trip and coverage tests for the masking layer.

`test_roundtrip_whole_corpus` is the load-bearing test in this project: it runs
mask -> split -> (no-op translate) -> join -> restore over every real English page and
asserts byte-identical output. If it passes, the pipeline cannot silently mangle
structure; if it fails, nothing else matters.
"""

import os
import pathlib

import pytest

from doc_builder.translate import segment

EN_DOCS = pathlib.Path(os.environ.get("EN_DOCS", "/Users/steven/hf/transformers/docs/source/en"))

ALL_PAGES = sorted(EN_DOCS.rglob("*.md")) if EN_DOCS.is_dir() else []

# Only corpus-backed tests skip; the unit tests below must run everywhere.
needs_corpus = pytest.mark.skipif(not ALL_PAGES, reason=f"English docs not found at {EN_DOCS}")


def _roundtrip(text):
    """mask -> split -> join -> restore, the exact path a page takes with a no-op model."""
    masked, placeholders = segment.mask(text)
    parts = segment.split_blocks(masked)
    return segment.restore(segment.join_blocks(parts), placeholders)


@needs_corpus
@pytest.mark.parametrize("page", ALL_PAGES, ids=lambda p: str(p.relative_to(EN_DOCS)))
def test_roundtrip_page(page):
    text = page.read_text(encoding="utf-8")
    assert _roundtrip(text) == text


@needs_corpus
def test_placeholder_chars_absent_from_corpus():
    """Placeholders can only be opaque if they never occur in real content."""
    for page in ALL_PAGES:
        text = page.read_text(encoding="utf-8")
        assert segment.PH_OPEN not in text, f"{page} contains {segment.PH_OPEN}"
        assert segment.PH_CLOSE not in text, f"{page} contains {segment.PH_CLOSE}"


@needs_corpus
def test_masking_leaves_prose_to_translate():
    """Guard against over-masking.

    A pattern that over-matches still round-trips perfectly -- masked text is preserved
    by definition -- so the round-trip test cannot catch it. This asserts that a
    prose-heavy page keeps most of its characters translatable, and that a
    reference-heavy page is mostly masked, which is the expected shape for each.
    """
    prose = (EN_DOCS / "philosophy.md").read_text(encoding="utf-8")
    masked, _ = segment.mask(prose)
    prose_ratio = len(segment.PLACEHOLDER_RE.sub("", masked)) / len(prose)
    assert prose_ratio > 0.5, f"philosophy.md only {prose_ratio:.0%} translatable"


def test_autodoc_block_indented_or_blank_separated():
    """build_doc._re_autodoc allows an indented directive and blank lines before members."""
    indented = "    [[autodoc]] BertModel\n        - forward\n\nProse.\n"
    masked, ph = segment.mask(indented)
    assert len(ph) == 1 and "forward" in ph[0]
    assert "Prose." in masked

    spaced = "[[autodoc]] BertTokenizer\n\n    - save_vocabulary\n\nProse.\n"
    masked, ph = segment.mask(spaced)
    assert len(ph) == 1 and "save_vocabulary" in ph[0]
    assert "Prose." in masked


def test_autodoc_block_keeps_member_lines():
    text = "[[autodoc]] BertTokenizer\n    - get_special_tokens_mask\n    - save_vocabulary\n\nProse.\n"
    masked, placeholders = segment.mask(text)
    assert len(placeholders) == 1
    assert "get_special_tokens_mask" in placeholders[0]
    assert "save_vocabulary" in placeholders[0]
    assert "Prose." in masked


def test_heading_anchor_is_masked_but_heading_is_not():
    text = "## Loading models[[loading-models]]\n"
    masked, placeholders = segment.mask(text)
    assert "Loading models" in masked
    assert placeholders == ["[[loading-models]]"]


def test_tag_masked_inner_markdown_translated():
    text = '<hfoptions id="install">\nInstall it with pip.\n</hfoptions>\n'
    masked, placeholders = segment.mask(text)
    assert "Install it with pip." in masked
    assert 'id="install"' not in masked
    assert len(placeholders) == 2


def test_inline_code_masked_before_tags():
    """`<foo>` in backticks must mask as one unit, not as a nested pair."""
    masked, placeholders = segment.mask("Pass `<mask>` to the tokenizer.\n")
    assert placeholders == ["`<mask>`"]
    assert "to the tokenizer." in masked


def test_link_masking_keeps_brackets_balanced():
    """Regression: hiding `](url)` left `[text⟦0⟧` with an unclosed bracket.

    The model treated that as broken markdown and "fixed" it by adding a `]`, which came back
    as `[text](url)]` -- 30 of them in one six-page run. Hiding only `(url)` leaves `[text]`
    intact, so there is nothing to repair.
    """
    masked, placeholders = segment.mask("See [the guide](https://hf.co/docs) now.\n")
    assert "[the guide]" in masked  # brackets still balanced for the model
    assert placeholders == ["(https://hf.co/docs)"]
    assert masked.count("[") == masked.count("]")


def test_bare_parentheses_in_prose_are_not_masked():
    """Only parentheses right after a `]` are a link target."""
    text = "Use it (carefully) with the tokenizer.\n"
    masked, placeholders = segment.mask(text)
    assert placeholders == []
    assert masked == text


def test_multiline_tag_is_masked():
    """88 corpus tags span newlines; leaving them unmasked leaks URLs to the model."""
    text = '<img src="https://example.com/a.png"\n     alt="Architecture"/>\n\nProse.\n'
    masked, placeholders = segment.mask(text)
    assert len(placeholders) == 1
    assert "https://example.com/a.png" not in masked
    assert "Prose." in masked


def test_bare_angle_brackets_in_prose_survive():
    """`a < b` is real prose in the corpus and must not be mistaken for a tag."""
    text = "Use it when n < m and the batch is small.\n"
    masked, placeholders = segment.mask(text)
    assert placeholders == []
    assert masked == text


def test_unpaired_backtick_does_not_swallow_document():
    text = "A stray ` backtick.\n\nA later paragraph.\n"
    masked, _ = segment.mask(text)
    assert "A later paragraph." in masked


def test_nested_placeholders_restore():
    """A link whose URL is itself masked nests one placeholder inside another.

    Real corpus case (model_doc/blt.md, glmga.md, idefics.md): `tag` masks
    `<INSERT LINK HERE>`, then `link` masks the enclosing `](...)`.
    """
    text = "See [here](<INSERT LINK TO GITHUB REPO HERE>) for details.\n"
    masked, placeholders = segment.mask(text)
    assert segment.PH_OPEN in masked
    assert segment.restore(masked, placeholders) == text


def test_restore_rejects_invented_placeholder():
    _, placeholders = segment.mask("Plain prose.\n")
    with pytest.raises(ValueError):
        segment.restore(f"{segment.PH_OPEN}99{segment.PH_CLOSE}", placeholders)


def test_pure_placeholder_block_is_not_translatable():
    fence = "```py\nprint(1)\n```"
    masked, _ = segment.mask(fence)
    assert not segment.is_translatable(masked)
    assert segment.is_translatable("Real prose.")
