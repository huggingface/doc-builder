import json

import pytest

from doc_builder.commands import translate as command
from doc_builder.translate import pipeline, preflight, segment
from tests.test_translate_adversarial import repo as source_repo  # noqa: F401
from tests.translate_harness import config, files


@pytest.mark.parametrize(
    "label",
    [
        "OCRBench",
        "APr",
        "COCO mAP",
        "Gemma-2 (2.6B)",
        "DeepSeek V3, LLaVA, Qwen2, ModernBERT",
        "GPT NeoX",
        "model_name",
        "TrainingArguments",
    ],
)
def test_identifier_labels_need_no_glossary(label):
    assert not segment.required({"text": label, "tokens": []})


@pytest.mark.parametrize(
    "prose",
    [
        "Overview",
        "READ MORE",
        "DO NOT USE THIS MODEL",
        "Use OCRBench",
        "Train a Gemma-2 model",
        "A100 and H100",
        "Model performance",
    ],
)
def test_identifier_rule_does_not_exempt_prose(prose):
    assert segment.required({"text": prose, "tokens": []})


def test_preflight_preserves_labels_and_moves_links():
    source = {
        **files(),
        "index.md": b"# OCRBench\n\n> [!TIP]\n> Use [demo](https://huggingface.co/spaces/org/demo) tool.\n\n## Overview\n",
    }
    report = preflight.check(source, config())
    assert not report["errors"]
    assert any(x["text"] == "OCRBench" for x in report["preserved_labels"])
    assert any(x["text"] == "Overview" for x in report["review_labels"])
    p = segment.extract_pages([source["index.md"].decode()], normalize=True)[0]
    moved = segment.render_page(p, [preflight.sample(u, True) for u in p["units"]])
    assert "> [demo](https://huggingface.co/spaces/org/demo)" in moved


def test_preflight_reports_failed_page(monkeypatch):
    monkeypatch.setattr(preflight, "sample", lambda *args: "¤999¤")
    report = preflight.check(files(), config())
    assert {x["page"] for x in report["errors"]} == {"index.md", "guide.mdx", "_toctree.yml"}


def test_dry_run_never_initializes_hub_or_model(source_repo, monkeypatch, capsys):  # noqa: F811
    def forbidden(*args, **kwargs):
        pytest.fail("Preflight attempted inference or Hub access")

    monkeypatch.setattr(command, "HfApi", forbidden)
    monkeypatch.setattr(pipeline, "load_model", forbidden)
    args = command.translate_command_parser().parse_args(
        [
            "transformers",
            "--source",
            str(source_repo),
            "--source-revision",
            pipeline.git(source_repo, "rev-parse", "HEAD"),
            "--dry-run",
        ]
    )
    report = command.run(args)
    assert report["pages"] == 2 and not report["errors"]
    assert json.loads(capsys.readouterr().out) == report


def test_preflight_catches_code_changed_during_normalization(monkeypatch):
    source = {**files(), "index.md": b"# Example\n\n```python\nx = 1\n```\n"}
    plans = pipeline.prepare_documents(source, config())
    p = plans["index.md"][0]
    p["source"] = p["source"].replace("x = 1", "x = 2")
    p["pieces"] = [s.replace("x = 1", "x = 2") for s in p["pieces"]]
    monkeypatch.setattr(pipeline, "prepare_documents", lambda *args: plans)
    report = preflight.check(source, config())
    assert report["fenced_blocks"] == 1
    assert any(x["page"] == "index.md" and x["error"] == "Fenced code changed" for x in report["errors"])
