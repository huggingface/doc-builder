import pytest

from doc_builder.translate import pipeline, preflight, segment
from tests.translate_harness import fake_translation, files

GLOSSARY = pipeline.read_glossary("ja")


@pytest.mark.parametrize(
    "decision,label", [(decision, label) for decision, labels in GLOSSARY["labels"].items() for label in labels]
)
def test_reviewed_label_decision_applies_to_heading_not_sentence(decision, label):
    source = {**files(), "index.md": f"# {label}\n\nUse {label} in this sentence.\n".encode()}
    plan = pipeline.prepare_documents(source, {"glossary": GLOSSARY})["index.md"][0]
    assert segment.required(plan["units"][0]) == (decision == "translate")
    assert segment.required(plan["units"][1])
    responses = [fake_translation(u) if segment.required(u) else u["text"] for u in plan["units"]]
    segment.validate_pages([plan], [segment.render_page(plan, responses)])


def test_cached_translation_cannot_change_a_kept_label():
    source = {**files(), "index.md": b"# scale\n"}
    plan = pipeline.prepare_documents(source, {"glossary": GLOSSARY})["index.md"][0]
    with pytest.raises(ValueError, match="protected-only"):
        segment.validate_pages([plan], [plan["source"].replace("# scale", "# 翻訳")])


@pytest.mark.parametrize("label", ["True", "TRUE", "False", "FALSE"])
def test_spreadsheet_boolean_casing_does_not_change_source(label):
    source = {**files(), "index.md": f"# {label}\n".encode()}
    plan = pipeline.prepare_documents(source, {"glossary": GLOSSARY})["index.md"][0]
    assert not segment.required(plan["units"][0])
    assert segment.render_page(plan, [plan["units"][0]["text"]]).startswith(f"# {label}")


def test_preflight_does_not_ask_to_review_approved_translations_again():
    source = {**files(), "index.md": b"# scale\n\n## Overview\n\n## Foobar\n"}
    report = preflight.check(source, {"glossary": GLOSSARY})
    assert not report["errors"]
    assert "scale" in {x["text"] for x in report["preserved_labels"]}
    candidates = {x["text"] for x in report["review_labels"]}
    assert "Foobar" in candidates
    assert not {"scale", "Overview"} & candidates


def test_translate_decision_cannot_override_protected_api_heading():
    source = {**files(), "index.md": b"# Attention\n\n[[autodoc]] Attention\n"}
    plan = pipeline.prepare_documents(source, {"glossary": GLOSSARY})["index.md"][0]
    assert "Attention" in GLOSSARY["labels"]["translate"]
    assert not any(segment.required(u) for u in plan["units"])
