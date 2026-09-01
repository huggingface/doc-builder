"""Round-trip and coverage tests for the masking layer.

`test_roundtrip_whole_corpus` is the load-bearing test in this project: it runs
mask -> split -> (no-op translate) -> join -> restore over every real English page and
asserts byte-identical output. If it passes, the pipeline cannot silently mangle
structure; if it fails, nothing else matters.
"""

import os
import pathlib
import re

import pytest

from doc_builder.translate import segment, validate

# Twelve real pages live in tests/fixtures/translate_corpus, so the corpus tests run on every
# CI run rather than only where a Transformers checkout happens to sit. They were chosen for
# the shapes that have broken masking before -- see the README next to them.
#
# Point EN_DOCS at a full docs/source/en to run the same tests over all 740 pages, which is
# worth doing before changing a pattern.
FIXTURE_DOCS = pathlib.Path(__file__).parent / "fixtures" / "translate_corpus"
EN_DOCS = pathlib.Path(os.environ.get("EN_DOCS", FIXTURE_DOCS))

ALL_PAGES = sorted(p for p in EN_DOCS.rglob("*.md") if p.name != "README.md") if EN_DOCS.is_dir() else []

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
    """Guard against over-masking on a page that is mostly prose.

    A pattern that over-matches still round-trips perfectly -- masked text is preserved by
    definition -- so the round-trip test cannot catch it. This is the check that can.
    """
    prose = (EN_DOCS / "philosophy.md").read_text(encoding="utf-8")
    masked, _ = segment.mask(prose)
    prose_ratio = len(segment.PLACEHOLDER_RE.sub("", masked)) / len(prose)
    assert prose_ratio > 0.5, f"philosophy.md only {prose_ratio:.0%} translatable"


@needs_corpus
@pytest.mark.parametrize("page", ALL_PAGES, ids=lambda p: str(p.relative_to(EN_DOCS)))
def test_every_page_keeps_some_prose(page):
    """No page may come out with nothing left to translate.

    This is the shape the fence bug took: `model_doc/mms.md` lost a whole paragraph and a
    code block into one placeholder and still round-tripped, because a page that is hidden
    is restored exactly. Nothing in the docs is pure code -- every page has at least a
    heading and a sentence -- so a page with no translatable units means a pattern ate it.
    """
    text = page.read_text(encoding="utf-8")
    masked, _ = segment.mask(text)
    units = [b for i, b in enumerate(segment.split_blocks(masked)) if i % 2 == 0 and segment.has_prose(b)]
    assert units, f"{page.name} has no translatable prose left after masking"


@needs_corpus
@pytest.mark.parametrize("page", ALL_PAGES, ids=lambda p: str(p.relative_to(EN_DOCS)))
def test_link_destinations_are_hidden_whole(page):
    """Every link destination goes into a placeholder in one piece, or not at all.

    Half a destination is worse than none: the balanced-parentheses bug hid
    `](https://e/Fine_(LED)` and left `_guide.ipynb)` in the masked text, where it reads as
    ordinary prose and the model is free to rewrite it. Checking the placeholders rather than
    the masked text is what makes this precise -- a bare URL sitting in a sentence is not a
    link and is meant to stay visible, so looking for `://` in the prose only finds those.
    """
    text = page.read_text(encoding="utf-8")
    _, placeholders = segment.mask(text)
    # Expanded, because a destination can be hidden as placeholders nested inside placeholders:
    # `[a](https://hf.co/<user>)` masks the tag first, so the link holds `(https://hf.co/¤13¤)`.
    # That destination is fully hidden, which is what this test is about.
    markers = "\n".join(f"{segment.PH_OPEN}{i}{segment.PH_CLOSE}" for i in range(len(placeholders)))
    hidden = segment.restore(markers, placeholders)
    for kind, dest in validate.link_targets(text):
        if kind in ("link", "image"):
            assert dest in hidden, f"{page.name}: destination {dest} is not hidden in one piece"


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


def test_link_masking_hides_both_brackets():
    """Both brackets are markers, so a mangled link is just a missing marker.

    Earlier versions left one bracket exposed as raw markdown and the model kept rewriting it:
    adding a `]` when the opening bracket looked unclosed, then dropping the `[` and inventing
    a `\u27e7`. Neither was visible to the marker check, because brackets were not markers.
    """
    masked, placeholders = segment.mask("See [the guide](https://hf.co/docs) now.\n")
    assert masked == "See \u00a40\u00a4the guide\u00a41\u00a4 now.\n"
    assert placeholders == ["[", "](https://hf.co/docs)"]
    assert "[" not in masked and "]" not in masked  # no markdown left to get wrong


def test_link_label_is_still_translatable():
    """The label stays outside the markers -- 80% of link labels are real phrases."""
    masked, _ = segment.mask("Read [continuous batching](../cb) first.\n")
    assert "continuous batching" in masked


def test_cross_reference_is_hidden_whole():
    """`[`Foo`]` goes as one piece, brackets included.

    Masking only the backticked name left `[¤0¤]` -- both brackets raw, the exact shape that
    caused the link damage. 2,307 of these across 463 pages. Nothing is lost by hiding the
    whole thing: what is between the brackets is in backticks, so it is an API name, not prose.
    """
    masked, placeholders = segment.mask("Use [`Pipeline`] to run it.\n")
    assert masked == "Use ¤0¤ to run it.\n"
    assert placeholders == ["[`Pipeline`]"]
    assert "[" not in masked and "]" not in masked


def test_cross_reference_loss_is_an_ordinary_missing_marker():
    """The point of hiding it whole: no new check needed, the marker check already sees it.

    A dropped `[Pipeline]` is not malformed markdown -- it just quietly stops resolving to a
    link -- so nothing looking at the finished page would catch it.
    """
    masked, _ = segment.mask("Use [`Pipeline`] to run it.\n")
    assert segment.placeholder_indices(masked) == [0]
    assert segment.placeholder_indices("実行します。\n") == []  # dropped -> plain missing marker


def test_linked_cross_reference_still_masks_as_a_link():
    """`[`Foo`](url)` is a link, not a cross-reference -- the lookahead keeps them apart."""
    masked, placeholders = segment.mask("See [`Trainer`](../trainer) now.\n")
    # numbered in the order the patterns run, not the order they appear: `code` masks the name
    # before `link_open` reaches the bracket
    assert masked == "See ¤1¤¤0¤¤2¤ now.\n"
    assert placeholders == ["`Trainer`", "[", "](../trainer)"]
    assert segment.restore(masked, placeholders) == "See [`Trainer`](../trainer) now.\n"


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
    assert not segment.has_prose(masked)
    assert segment.has_prose("Real prose.")


def test_fence_closes_on_a_longer_delimiter():
    """A ``` block may be closed by ````, and CommonMark says that is a closer.

    Regression: with a plain backreference the closer had to be the opener's exact length, so
    this block never ended. Masking ran on to the next bare ``` and swallowed the paragraph
    and the Python block in between -- prose that was then never translated and that no check
    could see, because masked text round-trips perfectly by definition.

    Real shape, from `model_doc/mms.md` (a ```bash block closed with four backticks) and
    `model_doc/mistral3.md`.
    """
    text = "```bash\npip install x\n````\n\nProse to translate.\n\n```python\nprint(1)\n```\n\nMore prose.\n"
    masked, placeholders = segment.mask(text)
    assert len(placeholders) == 2  # the bash block and the python block, separately
    assert "Prose to translate." in masked
    assert "More prose." in masked
    assert segment.restore(masked, placeholders) == text


def test_fence_closes_on_an_equal_length_delimiter():
    """Six backticks open and six close, which the old backreference already handled.

    Kept so the "at least as long" fix cannot regress into "any length": a ``` line inside a
    `````` block is content, not a closer. Real shape, from `model_doc/deepseek_v3.md`.
    """
    text = "``````text\nsome ``` output\n``````\n\nProse.\n"
    masked, placeholders = segment.mask(text)
    assert len(placeholders) == 1
    assert "some ``` output" in placeholders[0]
    assert "Prose." in masked


def test_fence_delimiter_character_must_match():
    """A ~~~ line does not close a ``` block."""
    text = "```\ncode\n~~~\nstill code\n```\n\nProse.\n"
    masked, placeholders = segment.mask(text)
    assert len(placeholders) == 1
    assert "still code" in placeholders[0]


def test_link_destination_with_balanced_parentheses():
    """`(LED)` inside a URL must not end the destination early.

    Regression: stopping at the first `)` left `_guide.ipynb)` sitting in the masked text as
    if it were prose, so the model was free to rewrite part of a URL. Nine links in the docs
    have this shape, in community.md, mixtral.md, sam.md and layoutlmv3.md.
    """
    text = "See [LED](https://e/Fine_(LED)_guide.ipynb) for more.\n"
    masked, placeholders = segment.mask(text)
    assert masked == "See ¤0¤LED¤1¤ for more.\n"
    assert placeholders == ["[", "](https://e/Fine_(LED)_guide.ipynb)"]
    assert ".ipynb" not in masked  # no part of the URL is left in front of the model
    assert segment.restore(masked, placeholders) == text


def test_link_destination_with_a_title():
    text = 'A [title link](https://hf.co "the title") here.\n'
    masked, placeholders = segment.mask(text)
    assert masked == "A ¤0¤title link¤1¤ here.\n"
    assert segment.restore(masked, placeholders) == text


def test_reference_style_link_is_masked():
    """`[text][ref]` masks like an ordinary link, and its definition goes whole.

    Four of these exist, all in `model_doc/gemma3n.md`, and none were masked at all before --
    so `altup` went to the model as prose, where translating it would break the link with
    nothing to notice.
    """
    text = "See [Alternating Updates][altup] here.\n\n[altup]: https://a.example/paper\n"
    masked, placeholders = segment.mask(text)
    assert "Alternating Updates" in masked  # the visible words stay translatable
    assert "altup" not in masked
    assert "a.example" not in masked
    assert segment.restore(masked, placeholders) == text


def test_undefined_reference_is_left_alone():
    """`[a][b]` only counts when the page defines `b`.

    Python indexing looks exactly like a reference link -- `outputs["train"][0]` -- and there
    are 116 of those in the docs against four real references. CommonMark agrees: an
    undefined reference renders as plain text, so masking it would be wrong as well as risky.
    """
    text = 'Then outputs["train"][0] is used.\n'
    masked, placeholders = segment.mask(text)
    assert placeholders == []
    assert masked == text


def test_image_opener_is_masked_with_its_bracket():
    """The `!` goes with the bracket, not into the text.

    Left bare between two markers it is one character of ordinary prose, and the model dropped
    it -- which silently turns an image into a link while every marker stays intact.
    """
    masked, placeholders = segment.mask("![Diagram](https://hf.co/a.png)\n")
    assert masked == "¤0¤Diagram¤1¤\n"
    assert placeholders == ["![", "](https://hf.co/a.png)"]
    assert "!" not in masked


def test_image_inside_a_link_is_fully_masked():
    """`[![alt](badge)](target)` -- an image used as a link's label. 142 of these in the docs.

    Both destinations and both openers have to be hidden. A label grammar that stopped at the
    first `]` left the outer link unrecognised, so only the inner destination was ever checked.
    """
    text = "[![Open In Colab](https://colab.example/badge.svg)](https://colab.example/nb.ipynb)\n"
    masked, placeholders = segment.mask(text)
    # numbered in document order: the outer `[`, then the inner `![`, then the two destinations
    assert masked == "¤0¤¤1¤Open In Colab¤2¤¤3¤\n"
    assert "[" not in masked and "]" not in masked and "!" not in masked
    assert segment.restore(masked, placeholders) == text


def test_bare_url_is_masked():
    """A URL written straight into a sentence. 53 of these were handed to the model as prose."""
    masked, placeholders = segment.mask("See https://github.com/deepseek-ai/DeepSeek-V3 for details.\n")
    assert masked == "See ¤0¤ for details.\n"
    assert placeholders == ["https://github.com/deepseek-ai/DeepSeek-V3"]


def test_bare_url_keeps_trailing_punctuation_out():
    """Prose puts a full stop after a URL, and it is not part of the address."""
    for text, expected in [
        ("See https://hf.co/docs.\n", "https://hf.co/docs"),
        ("Try https://hf.co/docs, then stop.\n", "https://hf.co/docs"),
        ("Wrap it (https://hf.co/docs) here.\n", "https://hf.co/docs"),
    ]:
        masked, placeholders = segment.mask(text)
        assert placeholders == [expected], text
        assert segment.restore(masked, placeholders) == text


def test_bare_url_rule_leaves_link_destinations_alone():
    """A URL already inside a link is hidden by the link rules, in one piece with its brackets."""
    masked, placeholders = segment.mask("Read [the guide](https://hf.co/docs) now.\n")
    assert placeholders == ["[", "](https://hf.co/docs)"]


def test_inline_dollar_math_is_masked():
    """`$x$` formulas, tight and padded. 170 of these across 9 pages went to the model as prose."""
    masked, placeholders = segment.mask("The term $K_{\\text{past}}$ is reused.\n")
    assert placeholders == ["$K_{\\text{past}}$"]
    assert masked == "The term ¤0¤ is reused.\n"

    # cache_explanation.md writes them with a space just inside each delimiter
    masked, placeholders = segment.mask("Both $ K_{\\text{past}} $ and $ V_{\\text{past}} $ are cached.\n")
    assert placeholders == ["$ K_{\\text{past}} $", "$ V_{\\text{past}} $"]


def test_inline_dollar_math_spans_lines_within_a_paragraph():
    """model_doc/reformer.md wraps formulas across source lines mid-paragraph."""
    text = "Factorized into $(n_{\\text{buckets}}^1,\nn_{\\text{buckets}}^2)$. This is crucial.\n"
    masked, placeholders = segment.mask(text)
    assert len(placeholders) == 1 and "\n" in placeholders[0]
    assert segment.restore(masked, placeholders) == text


def test_dollar_signs_in_prose_are_not_math():
    """A lone `$` is a dollar sign, and two of them are two prices rather than a formula.

    The space rule is what separates them: a formula has no space just inside its delimiters,
    or has one on both sides. `$5 and $10` has a space before the closing `$` and none after
    the opening one, so it fails both ways.
    """
    for text in [
        "It costs $5 and $10 today.\n",
        "Total is $100.\n",
        "costs $5\nor $10 today.\n",
    ]:
        masked, placeholders = segment.mask(text)
        assert placeholders == [], text
        assert masked == text


@needs_corpus
@pytest.mark.parametrize("page", ALL_PAGES, ids=lambda p: str(p.relative_to(EN_DOCS)))
def test_no_urls_or_formulas_left_for_the_model(page):
    """Nothing that has to come back byte-for-byte may be visible to the model.

    URLs and formulas both round-trip perfectly while masked, so the round-trip test cannot see
    either of these. Both were exposed until they were measured.
    """
    masked, _ = segment.mask(page.read_text(encoding="utf-8"))
    prose = segment.PLACEHOLDER_RE.sub("", masked)
    assert "://" not in prose, f"{page.name} leaves a URL in the prose"
    assert not re.search(r"(?<![$\\])\$[^$\n]{1,120}\$(?!\$)", prose), f"{page.name} leaves a formula in the prose"


def test_link_label_may_wrap_across_a_line():
    """25 links across 20 corpus pages wrap their label onto the next source line.

    Forbidding the newline masked only the closing half, leaving the opening `[` in front of the
    model -- and the model removes an opener it thinks is unmatched.
    """
    text = "See the [technical\nreport](https://hf.co/paper) for details.\n"
    masked, placeholders = segment.mask(text)
    assert placeholders == ["[", "](https://hf.co/paper)"]
    assert "[" not in masked and "]" not in masked
    assert segment.restore(masked, placeholders) == text


def test_link_label_still_stops_at_a_blank_line():
    """A soft break is allowed; a paragraph boundary is not, so a stray `[` cannot run away."""
    text = "An unclosed [bracket here.\n\nA later paragraph](url).\n"
    masked, placeholders = segment.mask(text)
    assert "An unclosed [bracket here." in masked  # the stray bracket stays where it is
    assert segment.restore(masked, placeholders) == text


def test_price_ranges_are_not_math():
    """A closing `$` followed by a digit or a range separator is a price, not a formula.

    Regression: `US$5 to US$10` masked as `$5 to US$`, which hid ordinary prose from translation
    while round-tripping perfectly, so nothing could see it.
    """
    for text in [
        "Costs US$5 to US$10 per hour.\n",
        "A $5-$10 range.\n",
        "Either $5/$10 works.\n",
        "It costs $5 and $10 today.\n",
    ]:
        masked, placeholders = segment.mask(text)
        assert placeholders == [], text
        assert masked == text


def test_real_formulas_still_mask_after_the_price_fix():
    """Only a digit may not follow the closing `$`.

    `$\\sigma$-VAE` in `model_doc/vibevoice.md` is a real formula followed by a hyphenated word,
    so forbidding `-` and `/` after the closing delimiter un-masked it. A digit is enough to tell
    a price range apart.
    """
    for text, expected in [
        ("The term $K_{a}$ here.\n", "$K_{a}$"),
        ("Value $x^2$ ok.\n", "$x^2$"),
        ("Both $ K_a $ and rest.\n", "$ K_a $"),
        ("the $\\sigma$-VAE model\n", "$\\sigma$"),
    ]:
        assert segment.mask(text)[1] == [expected], text


def test_reference_image_opener_is_masked():
    """The `!` goes with the bracket here too, or dropping it turns a picture into a link."""
    text = "![Diagram][fig]\n\n[fig]: https://hf.co/a.png\n"
    masked, placeholders = segment.mask(text)
    assert placeholders[0] == "!["
    assert "!" not in masked.splitlines()[0]
    assert segment.restore(masked, placeholders) == text
