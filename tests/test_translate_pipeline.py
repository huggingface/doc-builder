import re

import pytest

from doc_builder.translate import pipeline
from tests.test_translate_cache import execute
from tests.translate_harness import config, files, generate


@pytest.mark.parametrize("bad", ["", "¤999¤", "echo", "only-body", "missing"])
def test_any_failed_required_unit_fails_the_update(bad):
    def broken(units, cfg, retry=False):
        if bad == "missing":
            return generate(units, cfg)[:-1]
        return [
            u["text"]
            if bad == "echo" or bad == "only-body" and "Read" in u["text"]
            else bad
            if bad not in {"echo", "only-body"}
            else generate([u], cfg)[0]
            for u in units
        ]

    _, cache, failures = execute(files(), fn=broken)
    assert failures
    if bad != "only-body":
        assert not cache


def test_exactly_one_retry_and_complete_pages_survive_failure():
    calls = []

    def broken(units, cfg, retry=False):
        calls.append((retry, [u["text"] for u in units]))
        return ["" if "Read" in u["text"] else generate([u], cfg)[0] for u in units]

    _, candidate, failures = execute(files(), fn=broken)
    assert len(failures) == 1 and failures[0].startswith("index.md:")
    assert len(candidate) == 2
    assert [retry for retry, _ in calls] == [False, True]
    assert len(calls[1][1]) == 1 and "Read" in calls[1][1][0]


def test_retry_can_recover():
    def flaky(units, cfg, retry=False):
        return generate(units, cfg) if retry else [""] * len(units)

    assert not execute(files(), fn=flaky)[2]


def test_batch_result_count_is_checked_before_assignment():
    cfg = {**config(), "group": 2}

    def missing(units, cfg, retry=False):
        return generate(units[1:], cfg)

    _, candidate, failures = execute(files(), cfg=cfg, fn=missing)
    assert not candidate and failures


def test_keep_terms_are_protected_and_glossary_is_guidance():
    cfg = config()
    cfg["glossary"] = {"keep": ["Hub"], "pin": {"training": "トレーニング"}}
    source = {"index.md": b"# Hub\n\nUse Hub for training.\n", "_toctree.yml": b"- local: index\n  title: Hub\n"}

    def translate(units, cfg, retry=False):
        assert all("Hub" not in u["text"] for u in units)
        return [generate([u], cfg)[0].replace("翻訳です。", "トレーニングです。") for u in units]

    output, cache, failures = execute(source, cfg=cfg, fn=translate)
    assert not failures and b"Hub" in output["index.md"]
    assert execute(source, cache, cfg, fn=lambda *a, **k: pytest.fail("warm keep-only title"))[0] == output
    assert not execute(source, cfg=cfg)[2]


def test_safe_splitting_keeps_pairs_and_unicode_intact():
    from doc_builder.translate.segment import extract_pages

    unit = extract_pages(["😀 Read [the complete guide](url). Then take another step."])[0]["units"][0]
    chunks = pipeline.split_unit(unit, lambda u: list(u["text"]), 40)
    assert "".join(c["text"] for c in chunks) == unit["text"]
    assert all(not re.search(r"¤[^¤]*$", c["text"].replace("¤0¤", "").replace("¤1¤", "")) for c in chunks)
    assert any("¤0¤the complete guide¤1¤" in c["text"] for c in chunks)


def test_unsplittable_unit_fails_without_truncation():
    with pytest.raises(ValueError, match="no safe split"):
        pipeline.split_unit({"text": "x" * 100, "tokens": []}, lambda u: list(u["text"]), 10)


def test_unknown_language_fails_before_model_load():
    with pytest.raises(ValueError, match="Unsupported language"):
        pipeline.configuration("xx", "a" * 40)


def test_plain_headings_do_not_receive_marker_instructions():
    plain = pipeline.prompt({"text": "Quickstart", "tokens": []}, config())
    assert "¤" not in plain and "marker" not in plain.lower()
    protected = pipeline.prompt({"text": "Read ¤0¤the guide¤1¤.", "tokens": []}, config())
    assert "Preserve every XML tag" in protected


def test_source_model_names_and_autodoc_identifiers_are_kept_on_cold_and_warm_runs():
    source = {
        "model_doc/bert.md": b"# BERT\n\nRead the guide.\n\n## TrainingArguments\n\n[[autodoc]] TrainingArguments\n",
        "index.md": b"# Overview\n\nUse BERT with TrainingArguments.\n\n## AttentionMaskInterface\n\nUse [`AttentionMaskInterface`].\n",
        "_toctree.yml": b"- local: model_doc/bert\n  title: BERT\n- local: index\n  title: Overview\n",
    }

    def translate(units, cfg, retry=False):
        assert all("BERT" not in u["text"] and "TrainingArguments" not in u["text"] for u in units)
        assert all("AttentionMaskInterface" not in u["text"] for u in units)
        return generate(units, cfg)

    output, cache, failures = execute(source, fn=translate)
    assert not failures
    assert b"BERT" in output["index.md"] and b"TrainingArguments" in output["index.md"]
    assert b"title: BERT" in output["_toctree.yml"]
    assert execute(source, cache, fn=lambda *a, **k: pytest.fail("warm names cache"))[0] == output


def test_api_method_references_do_not_protect_common_verbs():
    plans = pipeline.prepare_documents(
        {**files(), "index.md": b"Register with [`AttentionInterface.register`]."}, config()
    )
    assert "Register" in plans["index.md"][0]["units"][0]["text"]


@pytest.mark.parametrize(
    "source, translation",
    [
        ("The three-command sequence covers every check.", "3つのコマンドで、すべてのチェックをカバーできます。"),
        ("Go from protein sequence to a protein model.", "タンパク質配列からタンパク質モデルへと進みます。"),
    ],
)
def test_glossary_does_not_reject_contextual_translations(source, translation):
    cfg = config()
    cfg["glossary"]["pin"] = {"sequence": "シーケンス"}
    docs = {"index.md": source.encode(), "_toctree.yml": b"- local: index\n  title: Guide\n"}

    def translate(units, cfg, retry=False):
        return [translation if "sequence" in u["text"] else "ガイド" for u in units]

    output, cache, failures = execute(docs, cfg=cfg, fn=translate)
    assert not failures and output["index.md"].decode() == translation
    assert execute(docs, cache, cfg, fn=lambda *a, **k: pytest.fail("warm contextual glossary"))[0] == output


@pytest.mark.parametrize("duplicate_code", [False, True])
def test_hub_can_repeat_in_prose_but_api_references_cannot(duplicate_code):
    cfg = pipeline.configuration("ja", "a" * 40)
    source = {
        "index.md": (
            b"Make sure you have the latest bitsandbytes version so you can serialize 4-bit models "
            b"and push them to the Hub with [`~PreTrainedModel.push_to_hub`]. "
            b"Use [`~PreTrainedModel.save_pretrained`] to save the 4-bit model locally."
        ),
        "_toctree.yml": b"- local: index\n  title: Guide\n",
    }

    def translate(units, cfg, retry=False):
        return [
            "最新の ¤0¤ バージョンを確保して、4ビットモデルをシリアライズし、Hub にプッシュできるようにしてください。"
            "¤1¤ を使用して、4ビットモデルを Hub にプッシュします。"
            "4ビットモデルをローカルに保存するには、¤2¤ を使用してください。" + ("¤1¤" if duplicate_code else "")
            if "Hub" in u["text"]
            else "ガイド"
            for u in units
        ]

    assert pipeline.pins("Hub API", cfg) == {"Hub": "Hub", "API": "API"}
    output, cache, failures = execute(source, cfg=cfg, fn=translate)
    assert bool(failures) == duplicate_code
    if not duplicate_code:
        assert output["index.md"].count(b"Hub") == 2
        assert execute(source, cache, cfg, fn=lambda *a, **k: pytest.fail("warm Hub cache"))[0] == output


def test_plural_acronyms_are_prose_but_code_and_identifiers_stay_protected():
    from doc_builder.translate.segment import extract_pages, render_page, validate_pages

    cfg = pipeline.configuration("ja", "a" * 40)
    plan = extract_pages(["Use LLMs and GPUs through APIs with CUDA and `LLMs`."], keep=cfg["glossary"]["keep"])[0]
    unit = plan["units"][0]
    assert "LLMs" in unit["text"] and "GPUs" in unit["text"]
    assert [t["raw"] for t in unit["tokens"]] == ["CUDA", "`LLMs`"]
    translated = render_page(plan, ["LLM と GPU を API、¤0¤ と ¤1¤ で使用します。"])
    validate_pages([plan], [translated])


def test_retry_receives_the_validation_failure_and_preserves_accepted_units():
    def translate(units, cfg, retry=False):
        if retry:
            assert len(units) == 1
            assert "echoes the source" in units[0]["error"]
            assert units[0]["previous"] == units[0]["text"]
            assert units[0]["error"] in pipeline.prompt(units[0], cfg, retry=True)
        return [u["text"] if "Read" in u["text"] and not retry else generate([u], cfg)[0] for u in units]

    assert not execute(files(), fn=translate)[2]


def test_model_xml_tags_express_nested_pairs_and_opaque_content():
    from doc_builder.translate.segment import extract_pages

    unit = extract_pages(["[![Notebook](badge.svg)](book.ipynb) and `code`."])[0]["units"][0]
    assert pipeline.xml_tags(unit) == ["<link0>", "<image1>", "</image1>", "</link0>", "<keep4>`code`</keep4>"]


def test_heading_anchor_payload_is_not_translation_context():
    from doc_builder.translate.segment import extract_pages

    unit = extract_pages(["## Fixing the CI\n"], keep=["CI"], normalize=True)[0]["units"][0]
    assert pipeline.xml_tags(unit) == ["<keep0>CI</keep0>"]
    assert "heading" in pipeline.prompt(unit, config())
    assert "exactly once" in pipeline.prompt(unit, config())


def test_structural_retry_keeps_other_valid_units():
    source = {
        "index.md": b"# Example with `GPT`\n\nRead the body.\n",
        "_toctree.yml": b"- local: index\n  title: Guide\n",
    }
    cfg = config()
    cfg["glossary"]["keep"] = ["GPT"]
    calls = []

    def translate(units, cfg, retry=False):
        calls.append((retry, [u["text"] for u in units]))
        return [
            generate([u], cfg)[0] + " `GPT`" if "Example" in u["text"] and not retry else generate([u], cfg)[0]
            for u in units
        ]

    output, cache, failures = execute(source, cfg=cfg, fn=translate)
    assert not failures
    assert len(cache) == 2
    assert calls[1][0] and len(calls[1][1]) == 1 and "Example" in calls[1][1][0]
    assert output["index.md"].count(b"GPT") == 1


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "repair",
        "spaced",
        "unwrapped",
        "math_payload",
        "closing_bracket",
        "missing",
        "error",
        "unfinished",
        "truncated",
        "misordered",
        "duplicate",
        "nested",
    ],
)
def test_public_generate_batch_requires_complete_correctly_associated_results(monkeypatch, fault):
    import sys
    from types import ModuleType, SimpleNamespace

    from doc_builder.translate.segment import accept_unit, extract_pages, render_page

    class Tokenizer:
        eos_token_id = 0

        def apply_chat_template(self, messages, **kwargs):
            assert kwargs["return_dict"] is False and kwargs["enable_thinking"] is False
            assert [m["role"] for m in messages] == ["system", "user"]
            if fault == "repair" and "<link0>" in messages[1]["content"]:
                assert "duplicate" in messages[0]["content"]
            assert "¤" not in messages[1]["content"]
            return [ord(c) for c in "".join(m["content"] for m in messages)]

        def decode(self, tokens, **kwargs):
            return "".join(chr(t) for t in tokens if t)

    class Model:
        generation_config = SimpleNamespace(eos_token_id=0)

        def generate_batch(self, inputs, **kwargs):
            assert kwargs["generation_config"].do_sample is False
            assert len(inputs) == 2
            results = [
                SimpleNamespace(
                    prompt_ids=ids,
                    generated_tokens=[ord(c) for c in ("<link0>訳</link0><keep2>コード</keep2>" if i == 0 else "訳")]
                    + [0],
                    error=None,
                    is_finished=lambda: True,
                )
                for i, ids in enumerate(inputs)
            ]
            if fault == "spaced":
                results[0].generated_tokens = [ord(c) for c in "< link0 >訳< / link0 >< keep2 >コード< / keep2 >"] + [
                    0
                ]
            elif fault == "math_payload":
                results[0].generated_tokens = [ord(c) for c in "<link0>訳</link0><keep2>$x_{<i}$</keep2>"] + [0]
            elif fault == "closing_bracket":
                results[0].generated_tokens = [ord(c) for c in "<link0>訳</link0><keep2>CI</keep2"] + [0]
            elif fault == "unwrapped":
                results[0].generated_tokens = [ord(c) for c in "<link0>訳</link0>CI"] + [0]
            elif fault == "missing":
                results.pop(0)
            elif fault == "error":
                results[0].error = "GPU failure"
            elif fault == "unfinished":
                results[0].is_finished = lambda: False
            elif fault == "truncated":
                results[0].generated_tokens = [ord("訳")]
            elif fault == "misordered":
                results.reverse()
            elif fault in {"duplicate", "nested"}:
                bad = "<keep2>コード</keep2>" if fault == "duplicate" else "<keep2><keep2>コード</keep2></keep2>"
                results[0].generated_tokens = [ord(c) for c in "<link0>訳</link0><keep2>コード</keep2>" + bad] + [0]
            return dict(enumerate(results))

    library, generation = ModuleType("transformers"), ModuleType("transformers.generation")
    library.GenerationConfig = SimpleNamespace
    generation.ContinuousBatchingConfig = SimpleNamespace
    monkeypatch.setitem(sys.modules, "transformers", library)
    monkeypatch.setitem(sys.modules, "transformers.generation", generation)
    monkeypatch.setattr(pipeline, "load_model", lambda *args: (Tokenizer(), Model()))
    plan = extract_pages(["[First paragraph](url) with CI.\n\nSecond paragraph."], keep=["CI"])[0]
    units = plan["units"]
    if fault == "repair":
        units[0].update(previous="¤0¤訳¤1¤¤2¤¤2¤", error="duplicate marker")
        monkeypatch.setattr(pipeline, "split_unit", lambda unit, *a, **kw: [unit])
    if fault in {"duplicate", "nested", "unwrapped"}:
        with pytest.raises(ValueError):
            accept_unit(units[0], pipeline.generate(units, config())[0])
    elif fault in {"error", "unfinished", "truncated"}:
        assert pipeline.generate(units, config()) == [None, "訳"]
    elif fault not in {None, "spaced", "repair", "unwrapped", "math_payload", "closing_bracket"}:
        with pytest.raises(ValueError, match="results"):
            pipeline.generate(units, config())
    else:
        translated = pipeline.generate(units, config(), retry=fault == "repair")
        assert translated == ["¤0¤訳¤1¤¤2¤", "訳"]
        assert "CI" in render_page(plan, translated)


@pytest.mark.parametrize("response", ["訳", "¤999¤", "<bad>"])
def test_retry_restores_markers_without_sending_them_to_model(monkeypatch, response):
    import sys
    from types import ModuleType, SimpleNamespace

    from doc_builder.translate import segment

    class Tokenizer:
        eos_token_id = 0

        def apply_chat_template(self, messages, **kwargs):
            text = messages[-1]["content"]
            assert "fragment" in messages[0]["content"]
            assert "do not complete it" in messages[0]["content"]
            assert not re.search(r"[¤<>`*]", text)
            return [ord(c) for c in text]

        def decode(self, tokens, **kwargs):
            return "".join(chr(t) for t in tokens if t)

    class Model:
        generation_config = SimpleNamespace(eos_token_id=0)

        def generate_batch(self, inputs, **kwargs):
            assert kwargs["generation_config"].do_sample is False
            return {
                i: SimpleNamespace(
                    prompt_ids=ids,
                    generated_tokens=[ord(c) for c in response] + [0],
                    error=None,
                    is_finished=lambda: True,
                )
                for i, ids in enumerate(inputs)
            }

    library, generation = ModuleType("transformers"), ModuleType("transformers.generation")
    library.GenerationConfig = SimpleNamespace
    generation.ContinuousBatchingConfig = SimpleNamespace
    monkeypatch.setitem(sys.modules, "transformers", library)
    monkeypatch.setitem(sys.modules, "transformers.generation", generation)
    monkeypatch.setattr(pipeline, "load_model", lambda *args: (Tokenizer(), Model()))
    plan = segment.extract_pages(["*Read [the guide](url) with `code`.*"])[0]
    translated = pipeline.generate(plan["units"], config(), retry=True)
    if response != "訳":
        with pytest.raises(ValueError):
            segment.render_page(plan, translated)
    else:
        rendered = segment.render_page(plan, translated)
        assert rendered.startswith("*訳") and not rendered.startswith("* ")
        assert "[訳](url)" in rendered and "`code`" in rendered
        segment.validate_pages([plan], [rendered])


def test_inferred_api_names_do_not_mask_english_verbs():
    source = {
        **files(),
        "index.md": b"It requires a cache to generate output. [`requires`] [`Cache.generate`] [`Cache`] [`Pipeline`] [`Accelerator`]\n\n[[autodoc]] helper.requires\n",
    }
    plan = pipeline.prepare_documents(source, config())["index.md"][0]
    assert "It requires a cache to generate output." in plan["units"][0]["text"]
