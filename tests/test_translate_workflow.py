from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def workflow(name):
    # BaseLoader preserves GitHub's "on" key instead of treating it as YAML 1.1 true.
    return yaml.load((ROOT / ".github/workflows" / name).read_text(), Loader=yaml.BaseLoader)


def test_manual_updates_are_serialized_and_cleanup_is_unconditional():
    value = workflow("preview_translation.yml")
    assert set(value["on"]) == {"workflow_dispatch"}
    assert value["jobs"]["preview"]["concurrency"]["cancel-in-progress"] == "false"
    assert "inputs.language" in value["jobs"]["preview"]["concurrency"]["group"]
    steps = value["jobs"]["preview"]["steps"]
    checkout = steps[0]["with"]
    assert checkout["ref"] == "${{ github.sha }}"
    submit = next(s for s in steps if s.get("id") == "translation")
    assert submit["env"]["SOURCE_REVISION"] == "${{ inputs.source_revision }}"
    assert "--full" not in submit["run"]
    cleanup = next(s for s in steps if s.get("name") == "Stop an unfinished Job")
    assert cleanup["if"] == "always()" and "--cancel-record" in cleanup["run"]
    assert not any("hf-doc-build/doc-build" in s.get("run", "") for s in steps)


def test_bucket_consumer_pins_both_checkouts_and_preserves_html_cache():
    value = workflow("build_main_documentation.yml")
    inputs = value["on"]["workflow_call"]["inputs"]
    assert "translated_languages" not in inputs
    assert {
        "translation_bucket",
        "translation_state_sha256",
        "translation_language",
        "doc_builder_revision",
    } <= inputs.keys()
    steps = value["jobs"]["build_main_documentation"]["steps"]
    assert "inputs.doc_builder_revision || ''" in steps[0]["with"]["ref"]
    assert "inputs.commit_sha || ''" in steps[1]["with"]["ref"]
    setup = next(s for s in steps if s.get("name") == "Setup environment")
    assert 'if [ -z "$TRANSLATION_BUCKET" ]; then\n  git pull origin main' in setup["run"]
    install = next(s for s in steps if s.get("name") == "Install verified translation source")
    assert install["if"] == "inputs.translation_bucket != ''"
    assert 'test "$LANGUAGE" = "$LANGUAGES"' in install["run"]
    assert '--state-sha256 "$STATE_SHA256"' in install["run"]
    text = (ROOT / ".github/workflows/build_main_documentation.yml").read_text()
    assert "--html_page_cache hf://buckets/hf-doc-build/doc-build-cache" in text
    assert "--html_page_cache_write" in text
    assert "CURRENT" not in text


def test_translation_parser_runs_in_linux_and_windows_ci():
    value = workflow("test.yml")
    assert set(value["jobs"]["test"]["strategy"]["matrix"]["os"]) == {"ubuntu-latest", "windows-latest"}
    assert any(s.get("run") == "npm ci --prefix kit" for s in value["jobs"]["test"]["steps"])


def test_build_and_translation_share_concurrency_group():
    build = workflow("build_main_documentation.yml")["jobs"]["build_main_documentation"]["concurrency"]
    preview = workflow("preview_translation.yml")["jobs"]["preview"]["concurrency"]
    assert "translation-transformers-" in build["group"] and "translation-transformers-" in preview["group"]
    assert "inputs.translation_bucket" in build["group"] and "inputs.bucket" in preview["group"]
    assert build["cancel-in-progress"] == preview["cancel-in-progress"] == "false"
