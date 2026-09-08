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
    assert all("Guide" not in text for text in calls[1][1])


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


def test_keep_terms_and_glossary_pin_are_enforced():
    cfg = config()
    cfg["glossary"] = {"keep": ["Hub"], "pin": {"training": "トレーニング"}}
    source = {"index.md": b"# Hub\n\nUse Hub for training.\n", "_toctree.yml": b"- local: index\n  title: Hub\n"}

    def translate(units, cfg, retry=False):
        assert all("Hub" not in u["text"] for u in units)
        return [generate([u], cfg)[0].replace("翻訳です。", "トレーニングです。") for u in units]

    output, cache, failures = execute(source, cfg=cfg, fn=translate)
    assert not failures and b"Hub" in output["index.md"]
    assert execute(source, cache, cfg, fn=lambda *a, **k: pytest.fail("warm keep-only title"))[0] == output
    assert execute(source, cfg=cfg)[2]


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
    plain = pipeline.prompt({"text": "Quickstart"}, config())
    assert "¤" not in plain and "marker" not in plain.lower()
    protected = pipeline.prompt({"text": "Read ¤0¤the guide¤1¤."}, config())
    assert "Preserve every XML tag" in protected


def test_model_xml_tags_express_nested_pairs_and_opaque_content():
    from doc_builder.translate.segment import extract_pages

    unit = extract_pages(["[![Notebook](badge.svg)](book.ipynb) and `code`."])[0]["units"][0]
    assert pipeline.xml_tags(unit) == ["<g0>", "<g1>", "</g1>", "</g0>", "<ph4/>"]


@pytest.mark.parametrize("fault", [None, "missing", "error", "unfinished", "truncated", "misordered"])
def test_public_generate_batch_requires_complete_correctly_associated_results(monkeypatch, fault):
    import sys
    from types import ModuleType, SimpleNamespace

    from doc_builder.translate.segment import extract_pages

    class Tokenizer:
        eos_token_id = 0

        def apply_chat_template(self, messages, **kwargs):
            assert kwargs["return_dict"] is False and kwargs["enable_thinking"] is False
            assert [m["role"] for m in messages] == ["system", "user"]
            assert "¤" not in messages[1]["content"]
            return [ord(c) for c in "".join(m["content"] for m in messages)]

        def decode(self, tokens, **kwargs):
            return "".join(chr(t) for t in tokens if t)

    class Model:
        generation_config = SimpleNamespace(eos_token_id=0)

        def generate_batch(self, inputs, **kwargs):
            assert len(inputs) == 2
            results = [
                SimpleNamespace(
                    prompt_ids=ids,
                    generated_tokens=[ord(c) for c in ("<g0>訳</g0>" if i == 0 else "訳")] + [0],
                    error=None,
                    is_finished=lambda: True,
                )
                for i, ids in enumerate(inputs)
            ]
            if fault == "missing":
                results.pop(0)
            elif fault == "error":
                results[0].error = "GPU failure"
            elif fault == "unfinished":
                results[0].is_finished = lambda: False
            elif fault == "truncated":
                results[0].generated_tokens = [ord("訳")]
            elif fault == "misordered":
                results.reverse()
            return dict(enumerate(results))

    library, generation = ModuleType("transformers"), ModuleType("transformers.generation")
    library.GenerationConfig = SimpleNamespace
    generation.ContinuousBatchingConfig = SimpleNamespace
    monkeypatch.setitem(sys.modules, "transformers", library)
    monkeypatch.setitem(sys.modules, "transformers.generation", generation)
    monkeypatch.setattr(pipeline, "load_model", lambda *args: (Tokenizer(), Model()))
    units = extract_pages(["[First paragraph](url).\n\nSecond paragraph."])[0]["units"]
    if fault:
        with pytest.raises(ValueError, match="results"):
            pipeline.generate(units, config())
    else:
        assert pipeline.generate(units, config()) == ["¤0¤訳¤1¤", "訳"]
