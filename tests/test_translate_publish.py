import json

import pytest

from doc_builder.translate import artifact, pipeline
from tests.translate_harness import Hub, config, files, generate

BUCKET = "owner/bucket"
PREFIX = "transformers/ja/"


@pytest.fixture
def translated():
    source = {**files(), "image.svg": b"\xff\x00binary"}
    output, _, failures = pipeline.translate(source, config(), {}, generate)
    assert not failures
    return source, output


def publish(hub, translated, state=None, **kwargs):
    source, output = translated
    return artifact.publish(hub, BUCKET, source, output, config(), state or {}, "a" * 40, "b" * 40, **kwargs)


def verify(hub, source, state):
    return artifact.verify(hub, BUCKET, source, "ja", "a" * 40, "b" * 40, pipeline.digest(state))


def test_single_copy_is_cache_and_build_source(translated, tmp_path):
    hub = Hub()
    source, output = translated
    state = publish(hub, translated)
    assert len(hub.files) == len(source) + 1
    assert set(state["files"]) == set(source)
    assert all(set(entry) == {"key", "sha256"} for entry in state["files"].values())
    assert "翻訳" not in json.dumps(state, ensure_ascii=False)
    restored = verify(hub, source, state)
    assert restored == artifact.disclose(output)
    cache = artifact.read_cache(hub, BUCKET, source, config(), state)
    again, _, errors = pipeline.translate(source, config(), cache, lambda *a, **k: pytest.fail("Loaded model"))
    assert not errors and again == output
    target = tmp_path / "ja"
    target.mkdir()
    (target / "obsolete.md").write_bytes(b"old")
    artifact.install(restored, target)
    assert not (target / "obsolete.md").exists()
    assert (target / "index.md").read_bytes() == restored["index.md"]


@pytest.mark.parametrize("at", [2, 3])
def test_interrupted_upload_blocks_build_and_can_resume(translated, at):
    hub = Hub()
    hub.fail_at = at
    with pytest.raises(OSError):
        publish(hub, translated)
    state = artifact.read_state(hub, BUCKET, "ja")
    assert not state["complete"]
    with pytest.raises(ValueError, match="incomplete"):
        verify(hub, translated[0], state)
    hub.fail_at = None
    state = publish(hub, translated, state)
    assert verify(hub, translated[0], state)


@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_damaged_document_is_a_cache_miss_and_is_repaired(translated, damage):
    hub = Hub()
    source, _ = translated
    state = publish(hub, translated)
    if damage == "missing":
        del hub.files[BUCKET, PREFIX + "index.md"]
    else:
        hub.files[BUCKET, PREFIX + "index.md"] = b"corrupt"
    cache = artifact.read_cache(hub, BUCKET, source, config(), state)
    assert pipeline.cache_key("index.md", source["index.md"], config()) not in cache
    with pytest.raises((ValueError, KeyError)):
        verify(hub, source, state)
    state = publish(hub, translated, state)
    assert verify(hub, source, state)


def test_old_state_cannot_build_new_or_mixed_files(translated):
    hub = Hub()
    source, output = translated
    old = publish(hub, translated)
    updated = {**output, "index.md": output["index.md"].replace("翻訳".encode(), "日本語".encode())}
    publish(hub, (source, updated), old)
    with pytest.raises(ValueError, match="state changed"):
        verify(hub, source, old)


def test_state_change_during_download_is_rejected(translated, monkeypatch):
    hub = Hub()
    state = publish(hub, translated)
    read = artifact.read_state
    count = 0

    def changing(*args):
        nonlocal count
        count += 1
        result = read(*args)
        return result if count == 1 else {**result, "complete": False}

    monkeypatch.setattr(artifact, "read_state", changing)
    with pytest.raises(ValueError, match="changed while downloading"):
        verify(hub, translated[0], state)


@pytest.mark.parametrize("change", ["source", "config", "missing", "revision", "partial"])
def test_incompatible_state_cannot_build(translated, change):
    hub = Hub()
    source, _ = translated
    state = publish(hub, translated, partial=change == "partial")
    if change == "source":
        source = {**source, "index.md": b"new English"}
    if change == "config":
        state["config"]["model_revision"] = "c" * 40
    if change == "missing":
        del state["files"]["index.md"]
    if change == "revision":
        state["source_revision"] = "d" * 40
    hub.files[BUCKET, PREFIX + artifact.STATE] = json.dumps(state).encode()
    with pytest.raises(ValueError):
        verify(hub, source, state)


def test_full_update_removes_obsolete_files_and_old_duplicates_only_in_language(translated):
    hub = Hub()
    for name in ["obsolete.md", ".cache.json", ".runs/old/source/index.md", ".runs/old/source.tar.gz"]:
        hub.files[BUCKET, PREFIX + name] = b"old"
    hub.files[BUCKET, "transformers/fr/index.md"] = b"French"
    publish(hub, translated)
    assert {name for bucket, name in hub.files if name.startswith(PREFIX)} == {
        PREFIX + name for name in [*translated[0], artifact.STATE]
    }
    assert hub.files[BUCKET, "transformers/fr/index.md"] == b"French"


@pytest.mark.parametrize("name", ["../escape", "/tmp/escape", "folder\\escape", artifact.STATE, ".runs/a"])
def test_reserved_or_unsafe_source_paths_never_write(translated, name):
    hub = Hub()
    source, output = translated
    with pytest.raises(ValueError, match="source path"):
        publish(hub, ({**source, name: b"bad"}, output))
    assert not hub.writes


def test_disclosure_roundtrip_preserves_license():
    source = {"index.md": b"<!-- license -->\n\n# Heading\n"}
    data = artifact.disclose(source)["index.md"]
    assert data.startswith(b"<!-- license -->\n\n> ")
    assert artifact.undisclose("index.md", data) == source["index.md"]


def test_build_cli_installs_verified_canonical_files(translated, monkeypatch, tmp_path):
    import sys

    import huggingface_hub

    hub = Hub()
    state = publish(hub, translated)
    source, output = translated
    monkeypatch.setattr(huggingface_hub, "HfApi", lambda: hub)
    monkeypatch.setattr(pipeline, "inventory", lambda *args: (source, []))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "artifact",
            "--bucket",
            f"hf://buckets/{BUCKET}",
            "--state-sha256",
            pipeline.digest(state),
            "--source-revision",
            "a" * 40,
            "--doc-builder-revision",
            "b" * 40,
            "--language",
            "ja",
            "--repository",
            str(tmp_path),
            "--docs-source",
            str(tmp_path),
        ],
    )
    artifact.main()
    assert (tmp_path / "ja/index.md").read_bytes() == artifact.disclose(output)["index.md"]


def test_missing_accepted_page_cannot_mark_state_complete(translated):
    hub = Hub()
    source, output = translated
    state = publish(hub, (source, {name: data for name, data in output.items() if name != "index.md"}))
    assert not state["complete"]
    with pytest.raises(ValueError, match="incomplete"):
        verify(hub, source, state)
