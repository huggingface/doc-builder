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


@pytest.mark.parametrize("source", ["Read this!\n", "Read **this**!!\n", "Read this\\!!\n", "`code!`\n"])
def test_terminal_exclamations_roundtrip_outside_generation(source):
    plan = segment.extract_pages([source])[0]
    output = segment.render_page(plan, [u["text"].replace("Read", "読む") for u in plan["units"]])
    assert output == source.replace("Read", "読む")
    segment.validate_pages([plan], [output])
    if source.startswith("Read"):
        assert plan["pieces"][-1].startswith("!")
        assert not any(t["raw"] == "!" for t in plan["units"][0]["tokens"])


@pytest.mark.parametrize("prefix", ["", "> ", "  "])
def test_soft_wrapping_is_normalized_before_translation(prefix):
    source = f"{prefix}Read the guide\n{prefix}to learn more.\n"
    plan = segment.extract_pages([source], normalize=True)[0]
    assert not plan["units"][0]["tokens"]
    output = segment.render_page(plan, ["詳細はガイドを参照してください。"])
    assert output == prefix + "詳細はガイドを参照してください。\n"
    segment.validate_pages([plan], [output])


@pytest.mark.parametrize("separator", ["  \n", "\\\n", "<br>"])
def test_explicit_line_breaks_remain_protected(separator):
    plan = segment.extract_pages([f"Read this{separator}and that."], normalize=True)[0]
    u = plan["units"][0]
    assert u["tokens"]
    with pytest.raises(ValueError, match="markers"):
        segment.accept_unit(u, "これとあれを読みます。")
    segment.validate_pages([plan], [segment.render_page(plan, [fake_translation(u)])])


@pytest.mark.parametrize("number", ["5.33488e+08", "1E-5", "-1.2e+3", "256K", "70B", "CPU", "GPU"])
def test_numbers_and_isolated_acronyms_are_not_english_prose(number):
    plan = segment.extract_pages([number])[0]
    assert not segment.required(plan["units"][0])
    assert segment.render_page(plan, [number]) == number
    with pytest.raises(ValueError, match="protected-only"):
        segment.validate_pages([plan], ["123"])


@pytest.mark.parametrize(
    "name",
    [
        "TrainingArguments",
        "CUDA",
        "vLLM",
        "Mamba2LMHeadModel",
        "m48",
        "README.md",
        "modeling_my_multimodal_model.py",
    ],
)
def test_technical_identifiers_stay_unchanged_without_exempting_ordinary_prose(name):
    plan = segment.extract_pages([f"# {name}\n\nRead {name} before using it.\n"], keep=[name], normalize=True)[0]
    assert not segment.required(plan["units"][0])
    assert segment.required(plan["units"][1])
    assert name not in plan["units"][1]["text"]
    with pytest.raises(ValueError, match="echoes"):
        segment.accept_unit(plan["units"][1], plan["units"][1]["text"])
    output = segment.render_page(
        plan, [u["text"] if not segment.required(u) else fake_translation(u) for u in plan["units"]]
    )
    assert output.count(name) >= 2
    segment.validate_pages([plan], [output])


def test_repository_link_labels_are_identifiers_but_slashes_and_adjectives_are_prose():
    source = "Use [google/flan-t5-xxl](https://huggingface.co/google/flan-t5-xxl) for training/inference on FP8-compatible hardware."
    plan = segment.extract_pages([source])[0]
    u = plan["units"][0]
    assert "google/flan-t5-xxl" not in u["text"]
    assert "training/inference" in u["text"] and "-compatible" in u["text"]
    segment.validate_pages([plan], [segment.render_page(plan, [fake_translation(u)])])


@pytest.mark.parametrize("fence", ["```", "~~~~"])
def test_api_link_colon_does_not_expose_fenced_code(fence):
    code = f'{fence}python\ninputs = model.generate(**kwargs)\n\nx = "[`Other.method`]:"\n{fence}'
    source = f"[`Model.method`]:\n\n{code}\n\nRead the guide.\n"
    plan = segment.extract_pages([source], normalize=True)[0]
    assert code in plan["source"]
    assert not any("inputs" in u["text"] or "kwargs" in u["text"] for u in plan["units"])
    assert any("Read the guide" in u["text"] for u in plan["units"])
    rendered = segment.render_page(plan, [fake_translation(u) for u in plan["units"]])
    assert code in rendered
    segment.validate_pages([plan], [rendered])


@pytest.mark.parametrize(
    "label", ["✓ TTFT", "ARC C", "4.11 tok/s", "5.57 GB (7.04%)", "0.6063(6m)", "1.5B-d", "/models"]
)
def test_measurements_and_labels_are_not_prose(label):
    plan = segment.extract_pages([label])[0]
    assert all(not segment.required(u) for u in plan["units"])
    assert segment.render_page(plan, [u["text"] for u in plan["units"]]) == label


@pytest.mark.parametrize("source", ["DO NOT USE THIS MODEL", "READ MORE", "Read at 4.11 tok/s."])
def test_label_exemptions_do_not_skip_prose(source):
    unit = segment.extract_pages([source])[0]["units"][0]
    assert segment.required(unit)
    with pytest.raises(ValueError, match="echoes"):
        segment.accept_unit(unit, unit["text"])


def test_english_abbreviations_are_prose():
    unit = segment.extract_pages(["Use a library, e.g. scipy, i.e. an external dependency."])[0]["units"][0]
    assert "e.g." in unit["text"] and "i.e." in unit["text"]


def test_parenthesized_link_destination_does_not_absorb_adjacent_japanese():
    source = "Read [the guide](https://example.com/#section_(fsdp)) in the book."
    plan = segment.extract_pages([source])[0]
    output = segment.render_page(plan, ["¤0¤ガイド¤1¤を『本』で読みます。"])
    segment.validate_pages([plan], [output])


def test_restored_names_keep_boundaries_and_prose_can_change_case():
    plan = segment.extract_pages(
        ["Read Hugging Face Transformers with Pytorch at 16 kHz."], keep=["Hugging Face", "Transformers", "kHz"]
    )[0]
    rendered = segment.render_page(plan, ["¤0¤¤1¤をPyTorchで16¤2¤で使用します。"])
    assert "Hugging Face Transformers" in rendered and "16 kHz" in rendered
    segment.validate_pages([plan], [rendered])


def test_html_table_cells_translate_without_exposing_table_tags():
    source = '<table>\n<tr><th>Backend</th><th>Description</th></tr>\n<tr><td><code>sdpa</code></td><td>Read <a href="url">the guide</a>.</td></tr>\n</table>'
    plan = segment.extract_pages([source], normalize=True)[0]
    assert [u["text"] for u in plan["units"]] == ["Backend", "Description", "Read ¤0¤the guide¤1¤."]
    output = segment.render_page(plan, [fake_translation(u) for u in plan["units"]])
    assert "<code>sdpa</code>" in output
    segment.validate_pages([plan], [output])
    with pytest.raises(ValueError, match="structure"):
        segment.validate_pages([plan], [output.replace("<th>", "<td>")])


@pytest.mark.parametrize("name", ["DeepGEMM", "MambaLMHeadModel", "PVT-V2-B5", "2x8", "VideoLlava", "fp8"])
def test_isolated_identifiers_are_preserved_without_masking_prose(name):
    plans = segment.extract_pages([name, f"Read {name} before using it."])
    assert not segment.required(plans[0]["units"][0])
    assert segment.required(plans[1]["units"][0])


def test_plural_names_are_preserved_on_roundtrip():
    plan = segment.extract_pages(["Read about CPUs and EfficientNets."], keep=["CPU", "EfficientNet"])[0]
    assert [t["raw"] for t in plan["units"][0]["tokens"]] == ["CPUs", "EfficientNets"]
    segment.validate_pages([plan], [segment.render_page(plan, ["¤0¤と¤1¤について読んでください。"])])


@pytest.mark.parametrize("name", ["CPU", "BEiT"])
def test_repeated_prose_name_is_not_added_syntax(name):
    plan = segment.extract_pages([f"Use {name} for inference."], keep=[name])[0]
    rendered = segment.render_page(plan, [f"{name}を使い、¤0¤で推論します。"])
    segment.validate_pages([plan], [rendered])
    with pytest.raises(ValueError):
        segment.validate_pages([plan], ["推論します。"])


def test_parenthesized_names_remain_separate():
    plan = segment.extract_pages(
        ["Use Vision Transformer (ViT) and Dinov2."], keep=["Vision Transformer (ViT)", "Dinov2"]
    )[0]
    rendered = segment.render_page(plan, ["¤0¤¤1¤を使います。"])
    assert "(ViT) Dinov2" in rendered
    segment.validate_pages([plan], [rendered])


@pytest.mark.parametrize(
    "source,translated",
    [
        ("Use `CPU` for inference.", "`CPU`と`CPU`を使います。"),
        ("Use [CPU](url) for inference.", "[推論](url)でCPUを使います。"),
    ],
)
def test_name_tolerance_preserves_code_and_link_containment(source, translated):
    plan = segment.extract_pages([source], keep=["CPU"])[0]
    with pytest.raises(ValueError):
        segment.validate_pages([plan], [translated])


@pytest.mark.parametrize(
    "label",
    [
        "Kubernetes",
        "GGUF / GGML",
        "AMD (ROCm)",
        "BT (MB)",
        "Python",
        "torchvision",
        "DeepSeek V3, LLaVA, Qwen2, ModernBERT",
        "Gemma-2 (2.6B)",
        "DFN5B (ViT-H-14-378px)",
        "SigLIP (ViT-SO400M-384px)",
        "COCO mAP",
        "Olmo2, Cohere",
        "Serve CLI",
        "GPT NeoX",
        "OCRBench",
    ],
)
def test_technical_labels_do_not_require_translation(label):
    from doc_builder.translate.pipeline import configuration

    keep = configuration("ja", "a" * 40)["glossary"]["keep"]
    plan = segment.extract_pages([label], keep=keep)[0]
    assert not any(segment.required(u) for u in plan["units"])
    segment.validate_pages([plan], [label])


@pytest.mark.parametrize("admonition", ["NOTE", "TIP", "IMPORTANT", "WARNING", "CAUTION"])
def test_hub_link_can_move_to_start_of_admonition(admonition):
    source = f"> [!{admonition}]\n> Use [demo](https://huggingface.co/spaces/org/demo) tool.\n"
    plan = segment.extract_pages([source])[0]
    translated = segment.render_page(plan, ["¤0¤¤1¤¤2¤を使います。"])
    segment.validate_pages([plan], [translated])
    assert translated.startswith(f"> [!{admonition}]\n> [demo](https://huggingface.co/spaces/org/demo)")


@pytest.mark.parametrize("name,target", [("Swin Transformer", "swin"), ("Swin Transformer v2", "swinv2")])
def test_swin_link_label_is_preserved_without_model_page(name, target):
    from doc_builder.translate import pipeline

    source = {
        "backbones.md": f"* [{name}](../model_doc/{target})\n".encode(),
        "_toctree.yml": b"- local: backbones\n  title: Backbones\n",
    }
    plan = pipeline.prepare_documents(source, {"glossary": pipeline.read_glossary("ja")})["backbones.md"][0]
    assert not any(segment.required(u) for u in plan["units"])
    segment.validate_pages([plan], [source["backbones.md"].decode()])
