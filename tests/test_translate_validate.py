import pytest

from doc_builder.translate import segment
from tests.translate_harness import fake_translation


def unit(text):
    return segment.extract_pages([text])[0]["units"][0]


@pytest.mark.parametrize(
    "text", ["Ordinary prose.", "# Heading", "Short", "[A label](url)", "![Diagram][fig]\n\n[fig]: image.png"]
)
@pytest.mark.parametrize("failure", ["empty", "echo", "drop", "duplicate", "invent", "markup"])
def test_rejects_unusable_prose(text, failure):
    u = unit(text)
    good = fake_translation(u)
    bad = {
        "empty": "",
        "echo": u["text"],
        "drop": good.replace("¤0¤", ""),
        "duplicate": good + "¤0¤",
        "invent": good + "¤999¤",
        "markup": good + "\n## More",
    }[failure]
    if bad == good:
        return
    with pytest.raises(ValueError):
        segment.accept_unit(u, bad)


def test_complete_links_can_move_but_pairs_cannot_cross():
    u = unit("Read [first](one) and [second](two).")
    assert segment.accept_unit(u, "¤2¤第二¤3¤と¤0¤第一¤1¤を読みます。")
    for bad in ["¤0¤第一¤2¤第二¤1¤¤3¤です。", "¤1¤第一¤0¤と¤2¤第二¤3¤です。"]:
        with pytest.raises(ValueError, match="nesting"):
            segment.accept_unit(u, bad)


def test_cached_empty_body_does_not_hide_behind_translated_heading():
    plan = segment.extract_pages(["# Heading\n\nRead the body.\n"], normalize=True)[0]
    with pytest.raises(ValueError):
        segment.validate_pages([plan], ["# 見出し[[heading]]\n\nRead the body.\n"])


def test_image_kind_destinations_and_nested_brackets_are_preserved():
    source = "[![Open notebook](badge.svg)](book.ipynb) and [huggingface_hub[cli]](url)."
    plan = segment.extract_pages([source])[0]
    output = segment.render_page(plan, [fake_translation(u) for u in plan["units"]])
    for old, new in [("![", "["), ("badge.svg", "other.svg"), ("book.ipynb", "other.ipynb"), ("[cli]", "")]:
        bad = output.replace(old, new)
        if bad != output:
            with pytest.raises(ValueError):
                segment.validate_pages([plan], [bad])


def test_anchors_follow_unicode_renderer_and_preserve_custom_ids():
    source = "# Héllo **world**\n\n## Existing[[my-id]]\n\nSetext heading\n--------------\n"
    result = segment.extract_pages([source], normalize=True)[0]["source"]
    assert "# Héllo **world**[[héllo-world]]" in result
    assert "Existing[[my-id]]" in result
    assert "Setext heading[[setext-heading]]\n---" in result


def test_autodoc_supplies_its_heading_anchor():
    source = "## BertModel\n\n[[autodoc]] BertModel\n    - forward\n"
    result = segment.extract_pages([source], normalize=True)[0]["source"]
    assert result == source


def test_bare_url_is_delimited_before_japanese_prose():
    plan = segment.extract_pages(["Read https://hf.co/docs now."], normalize=True)[0]
    output = segment.render_page(plan, ["¤0¤を参照してください。"])
    assert "<https://hf.co/docs>を" in output
    segment.validate_pages([plan], [output])


def test_inline_html_and_nested_badge_cannot_be_reparented():
    for source in ['Read <a href="url">the guide</a>.', "[![Notebook](badge.svg)](book.ipynb)"]:
        u = unit(source)
        assert segment.accept_unit(u, fake_translation(u))
        with pytest.raises(ValueError):
            segment.accept_unit(u, "¤1¤翻訳¤0¤¤2¤¤3¤")
    u = unit("[![Notebook](badge.svg)](book.ipynb)")
    with pytest.raises(ValueError, match="containment"):
        segment.accept_unit(u, "¤0¤翻訳¤3¤¤1¤画像¤2¤")


@pytest.mark.parametrize(
    "source",
    ["Read [guide].\n\n[guide]: url\n", "Read [guide][].\n\n[guide]: url\n", "![diagram]\n\n[diagram]: image.png\n"],
)
def test_reference_shortcuts_keep_the_original_identifier(source):
    plan = segment.extract_pages([source], normalize=True)[0]
    result = segment.render_page(plan, [fake_translation(u) for u in plan["units"]])
    assert "][guide]" in result or "][diagram]" in result
    segment.validate_pages([plan], [result])


def test_cached_translation_uses_the_fresh_acceptance_checks():
    plan = segment.extract_pages(["Read the guide."])[0]
    with pytest.raises(ValueError, match="invented a marker"):
        segment.validate_pages([plan], ["ガイドを読みます。⟦0⟧"])


def test_exact_autodoc_class_headings_are_protected_without_guessing_capitalization():
    plan = segment.extract_pages(["## BertModel\n\n[[autodoc]] BertModel\n    - forward\n\n## Short\n"])[0]
    visible = [u["text"] for u in plan["units"] if segment.required(u)]
    assert visible == ["Short"]


@pytest.mark.parametrize(
    "source",
    [
        'Read {format({label: "English"})} next.',
        "Read {format(/}/g)} next.",
        '{#if matches({language: "English"})}\nRead this.\n{/if}',
    ],
)
def test_nested_svelte_expressions_are_opaque(source):
    plan = segment.extract_pages([source])[0]
    visible = "\n".join(u["text"] for u in plan["units"])
    assert "Read" in visible
    assert "format" not in visible and "English" not in visible and "matches" not in visible
    translated = segment.render_page(plan, [fake_translation(u) for u in plan["units"]])
    if "format(/}/g)" in source:
        assert "{format(/}/g)}" in translated
    segment.validate_pages([plan], [translated])


@pytest.mark.parametrize(
    "source", [r"![Outer [inner] final words](image.svg)", r"![Escaped \] final words](image.svg)"]
)
def test_image_alt_text_after_inner_bracket_stays_visible(source):
    plan = segment.extract_pages([source])[0]
    assert "final words" in plan["units"][0]["text"]
    output = segment.render_page(plan, [fake_translation(u) for u in plan["units"]])
    segment.validate_pages([plan], [output])


@pytest.mark.parametrize(
    "source, visible",
    [(r"Read {\em Transient Global} next.", "Transient Global"), ("Read {Pop, Piano Cover} pairs.", "Piano Cover")],
)
def test_literal_brace_groups_retain_translatable_prose(source, visible):
    plan = segment.extract_pages([source])[0]
    assert visible in plan["units"][0]["text"]
    output = segment.render_page(plan, [fake_translation(u) for u in plan["units"]])
    segment.validate_pages([plan], [output])


def test_blockquote_callout_marker_stays_outside_generation():
    source = "> [!TIP]\n> An *architecture* is a skeleton.\n"
    plan = segment.extract_pages([source])[0]
    assert plan["pieces"][0] == "> [!TIP]\n> "
    assert plan["units"][0]["text"] == "An ¤0¤architecture¤1¤ is a skeleton."


def test_parameter_names_in_link_labels_are_immutable():
    plan = segment.extract_pages(["Set [device_map](url) to auto."], normalize=True)[0]
    assert any(t["raw"] == "device_map" for t in plan["units"][0]["tokens"])
    assert "device" not in plan["units"][0]["text"]
