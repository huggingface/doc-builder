from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def workflow(name):
    # BaseLoader preserves GitHub's "on" key instead of treating it as YAML 1.1 true.
    return yaml.load((ROOT / ".github/workflows" / name).read_text(), Loader=yaml.BaseLoader)


def test_manual_preview_is_isolated_and_cleanup_is_unconditional():
    value = workflow("preview_translation.yml")
    assert set(value["on"]) == {"workflow_dispatch"}
    assert value["concurrency"]["cancel-in-progress"] == "false"
    assert "inputs.language" in value["concurrency"]["group"]
    steps = value["jobs"]["preview"]["steps"]
    checkout = steps[0]["with"]
    assert checkout["ref"] == "${{ github.sha }}"
    submit = next(s for s in steps if s.get("id") == "translation")
    assert submit["env"]["SOURCE_REVISION"] == "${{ inputs.source_revision }}"
    assert "--full" not in submit["run"]
    cleanup = next(s for s in steps if s.get("name") == "Stop an unfinished Job")
    assert cleanup["if"] == "always()" and "--cancel-record" in cleanup["run"]
    assert not any("hf-doc-build/doc-build" in s.get("run", "") for s in steps)


def test_archive_consumer_pins_both_checkouts_and_preserves_html_cache():
    value = workflow("build_main_documentation.yml")
    inputs = value["on"]["workflow_call"]["inputs"]
    assert "translated_languages" not in inputs
    assert {
        "translation_archive",
        "translation_archive_sha256",
        "translation_language",
        "doc_builder_revision",
    } <= inputs.keys()
    steps = value["jobs"]["build_main_documentation"]["steps"]
    assert "inputs.doc_builder_revision || ''" in steps[0]["with"]["ref"]
    assert "inputs.commit_sha || ''" in steps[1]["with"]["ref"]
    setup = next(s for s in steps if s.get("name") == "Setup environment")
    assert 'if [ -z "$TRANSLATION_ARCHIVE" ]; then\n  git pull origin main' in setup["run"]
    install = next(s for s in steps if s.get("name") == "Install verified translation source")
    assert install["if"] == "inputs.translation_archive != ''"
    assert 'test "$LANGUAGE" = "$LANGUAGES"' in install["run"]
    assert '--sha256 "$ARCHIVE_SHA256"' in install["run"]
    text = (ROOT / ".github/workflows/build_main_documentation.yml").read_text()
    assert "--html_page_cache hf://buckets/hf-doc-build/doc-build-cache" in text
    assert "--html_page_cache_write" in text
    assert "CURRENT" not in text


def test_translation_parser_runs_in_linux_and_windows_ci():
    value = workflow("test.yml")
    assert set(value["jobs"]["test"]["strategy"]["matrix"]["os"]) == {"ubuntu-latest", "windows-latest"}
    assert any(s.get("run") == "npm ci --prefix kit" for s in value["jobs"]["test"]["steps"])
