import io
import tarfile

import pytest

from doc_builder.translate import artifact
from tests.translate_harness import Hub, files

META = {
    "format": 1,
    "package": "transformers",
    "language": "ja",
    "source_revision": "a" * 40,
    "doc_builder_revision": "b" * 40,
    "config_digest": "c" * 64,
    "run_id": "unique",
    "preview": False,
}


def test_archive_and_browsable_files_match_and_readme_is_last():
    hub = Hub()
    prefix = artifact.run_prefix("ja", "unique", False)
    source = artifact.disclose(files())
    result = artifact.upload_run(hub, "owner/bucket", prefix, source, META)
    assert hub.writes[-1] == [prefix + "/README.md"]
    assert all(name.startswith(prefix + "/") for batch in hub.writes for name in batch)
    data = hub.files["owner/bucket", prefix + "/source.tar.gz"]
    restored, _ = artifact.verify_archive(data, META, result["translation_archive_sha256"], source)
    assert restored == source
    for name, value in source.items():
        assert hub.files["owner/bucket", prefix + "/source/" + name] == value
    readme = hub.files["owner/bucket", prefix + "/README.md"].decode()
    assert result["page_url"] in readme
    assert "/tree/runs/" in result["folder_url"] and "/blob/" not in result["page_url"]


@pytest.mark.parametrize("at", [1, 2])
def test_interrupted_upload_never_changes_another_run(at):
    hub = Hub()
    hub.files["owner/bucket", "runs/old/source/index.md"] = b"previous"
    hub.fail_at = at
    with pytest.raises(OSError):
        artifact.upload_run(hub, "owner/bucket", "runs/new", files(), META)
    assert hub.files["owner/bucket", "runs/old/source/index.md"] == b"previous"
    assert ("owner/bucket", "runs/new/README.md") not in hub.files


def test_corrupt_download_prevents_completion_readme():
    class Corrupt(Hub):
        def download_bucket_files(self, bucket_id, files, **kwargs):
            super().download_bucket_files(bucket_id, files, **kwargs)
            files[0][1].write_bytes(b"corrupt")

    hub = Corrupt()
    with pytest.raises(ValueError, match="accepted tree"):
        artifact.upload_run(hub, "owner/bucket", "runs/new", files(), META)
    assert len(hub.writes) == 1


@pytest.mark.parametrize(
    "key,value",
    [
        ("source_revision", "d" * 40),
        ("language", "fr"),
        ("run_id", "wrong"),
        ("doc_builder_revision", "d" * 40),
        ("config_digest", "d" * 64),
        ("preview", True),
    ],
)
def test_wrong_identity_is_rejected(key, value):
    data = artifact.archive_bytes(files(), {**META, key: value})
    with pytest.raises(ValueError, match="provenance"):
        artifact.verify_archive(data, META)


@pytest.mark.parametrize(
    "name,kind",
    [
        ("source/../../escape", "file"),
        ("/tmp/escape", "file"),
        ("source/link", "symlink"),
        ("source/hard", "hardlink"),
        ("other/file", "file"),
        ("source/index.md", "duplicate"),
    ],
)
def test_malicious_members_are_rejected(name, kind):
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as tar:
        info = tarfile.TarInfo(name)
        if kind in {"symlink", "hardlink"}:
            info.type = tarfile.SYMTYPE if kind == "symlink" else tarfile.LNKTYPE
            info.linkname = "/tmp/outside"
            tar.addfile(info)
        else:
            info.size = 1
            tar.addfile(info, io.BytesIO(b"x"))
            if kind == "duplicate":
                tar.addfile(info, io.BytesIO(b"y"))
    with pytest.raises(ValueError):
        artifact.verify_archive(out.getvalue(), META)


def test_bad_hash_missing_page_and_preview_leave_target_untouched(tmp_path):
    target = tmp_path / "ja"
    target.mkdir()
    (target / "previous.md").write_text("old")
    data = artifact.archive_bytes(files(), META)
    with pytest.raises(ValueError, match="checksum"):
        artifact.install(data, target, META, "0" * 64, files())
    with pytest.raises(ValueError, match="missing or unexpected"):
        artifact.verify_archive(data, META, expected_files={**files(), "missing.md": b""})
    preview = {**META, "preview": True}
    with pytest.raises(ValueError, match="Preview"):
        artifact.install(artifact.archive_bytes(files(), preview), target, preview, None, files())
    assert (target / "previous.md").read_text() == "old"
    artifact.install(data, target, META, None, files())
    assert not (target / "previous.md").exists()
    assert (target / "guide.mdx").read_bytes() == files()["guide.mdx"]


def test_disclosure_is_not_cached_and_follows_license():
    source = {"index.md": b"<!-- license -->\n\n# Heading\n"}
    result = artifact.disclose(source)["index.md"].decode()
    assert result.startswith("<!-- license -->\n\n> ")
    assert "/main/en/index" in result


def test_bad_or_missing_cache_is_a_cold_miss():
    hub = Hub()
    with pytest.warns(UserWarning):
        assert artifact.read_cache(hub, "o/b", "missing") == {}
    hub.files["o/b", "cache"] = b"[]"
    with pytest.warns(UserWarning):
        assert artifact.read_cache(hub, "o/b", "cache") == {}
