import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from doc_builder.commands import translate as command
from doc_builder.translate import job, pipeline
from tests.test_translate_adversarial import repo as source_repo  # noqa: F401 - shared fixture
from tests.translate_harness import Hub, generate, job_info


class Jobs(Hub):
    def __init__(self, repo):
        super().__init__()
        self.repo, self.previous, self.canceled, self.submitted = repo, [], [], []
        self.state, self.do_work, self.generator = "COMPLETED", True, generate
        self.old_state, self.refuse_stop = "RUNNING", False

    def model_info(self, *args):
        return SimpleNamespace(sha="a" * 40)

    def list_jobs(self, **kwargs):
        self.labels = kwargs["labels"]
        return self.previous

    def run_job(self, **kwargs):
        self.submitted.append(kwargs)
        if self.do_work:
            args = command.translate_command_parser().parse_args(
                json.loads(kwargs["env"]["TRANSLATE_ARGUMENTS"]) + ["--source", str(self.repo)]
            )
            if kwargs["env"]["TRANSLATION_PAGES"]:
                args.pages_file = str(self.repo / "selected.txt")
                Path(args.pages_file).write_text(kwargs["env"]["TRANSLATION_PAGES"])
            try:
                command.run(args, self, self.generator)
            except ValueError:
                self.state = "ERROR"
        return job_info(state=self.state)

    def inspect_job(self, job_id, **kwargs):
        return job_info(job_id, self.old_state if job_id == "old" else self.state)

    def wait_for_job(self, job_id, **kwargs):
        return self.inspect_job(job_id)

    def cancel_job(self, job_id, **kwargs):
        self.canceled.append(job_id)
        if not self.refuse_stop:
            if job_id == "old":
                self.old_state = "CANCELED"
            else:
                self.state = "CANCELED"


@pytest.fixture
def setup(source_repo, tmp_path, monkeypatch):  # noqa: F811 - pytest fixture injection
    repo = source_repo
    actual_git = pipeline.git

    def git(path, *args):
        if Path(path).resolve() == repo.resolve():
            return actual_git(path, *args)
        if args[:2] == ("rev-parse", "HEAD"):
            return "b" * 40
        if args[0] == "status":
            return ""
        return "https://github.com/test/doc-builder.git"

    monkeypatch.setattr(pipeline, "git", git)
    monkeypatch.setattr(job, "checkout", lambda revision, directory: repo)
    monkeypatch.setattr(job, "get_token", lambda: "test-token")
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "outputs"))
    args = SimpleNamespace(
        bucket="hf://buckets/test/translations",
        namespace="test",
        lang="ja",
        source_revision=actual_git(repo, "rev-parse", "HEAD"),
        full=False,
        pages=None,
        model_revision="a" * 40,
        doc_builder_repository=None,
        flavor="a100-large",
        job_record=str(tmp_path / "job.json"),
    )
    return args, Jobs(repo)


def test_preview_returns_only_verified_run_links_and_never_shared_writes(setup):
    args, api = setup
    result = job.submit(args, api)
    assert "/transformers/ja/.runs/" in result["translation_archive"]
    assert result["folder_url"] == "https://huggingface.co/buckets/test/translations/tree/transformers/ja"
    assert result["page_url"] == result["folder_url"] + "/guide.mdx"
    assert ("test/translations", "transformers/ja/guide.mdx") in api.files
    assert ("test/translations", "transformers/ja/.cache.json") not in api.files
    assert all(name.startswith("transformers/ja/") for batch in api.writes for name in batch)
    assert json.loads(Path(args.job_record).read_text())["id"] == "job1"
    assert api.submitted[0]["secrets"] == {"HF_TOKEN": "test-token"}
    assert "test-token" not in str(api.submitted[0]["command"])
    assert "test-token" not in str(api.files)


def test_full_runner_is_the_only_shared_cache_writer(setup, monkeypatch):
    args, api = setup
    args.full = True
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    result = job.submit(args, api)
    canonical = "transformers/ja/.cache.json"
    assert api.writes.count([canonical]) == 1
    assert "/.runs/" in result["translation_archive"]
    cache = json.loads(api.files["test/translations", canonical])
    assert len(cache) == 3
    api.generator = lambda *a, **k: pytest.fail("Warm worker loaded the model")
    assert job.submit(args, api)["translation_archive"] != result["translation_archive"]


def test_failed_full_job_recovers_only_complete_pages_without_build_output(setup, monkeypatch, tmp_path):
    args, api = setup
    args.full = True
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    def broken(units, config, retry=False):
        return ["" if "Read" in u["text"] else generate([u], config)[0] for u in units]

    api.generator = broken
    api.files["test/translations", "transformers/ja/index.md"] = b"previous accepted page"
    with pytest.raises(ValueError, match="ERROR"):
        job.submit(args, api)
    assert len(json.loads(api.files["test/translations", "transformers/ja/.cache.json"])) == 2
    assert not any(name.endswith("/README.md") or name.endswith(".tar.gz") for _, name in api.files)
    assert not (tmp_path / "outputs").exists()
    assert api.files["test/translations", "transformers/ja/index.md"] == b"previous accepted page"


def test_runner_validates_cache_without_reentering_translation(setup, monkeypatch):
    args, api = setup
    args.full = True
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    wait = api.wait_for_job

    def completed(*args, **kwargs):
        # The simulated worker has finished; the runner must only validate its output.
        monkeypatch.setattr(pipeline, "translate", lambda *a, **k: pytest.fail("Runner entered translation"))
        return wait(*args, **kwargs)

    monkeypatch.setattr(api, "wait_for_job", completed)
    assert "/.runs/" in job.submit(args, api)["translation_archive"]


@pytest.mark.parametrize("state", ["CANCELED", "DELETED", "RUNNING", "UNKNOWN"])
def test_non_successful_job_has_no_outputs_or_cache_update(setup, state, tmp_path):
    args, api = setup
    api.do_work, api.state = False, state
    with pytest.raises(ValueError):
        job.submit(args, api)
    assert not api.writes and not (tmp_path / "outputs").exists()
    if state == "RUNNING":
        assert api.canceled == ["job1"]


def test_orphan_is_stopped_before_submission(setup):
    args, api = setup
    api.previous = [job_info("old", "RUNNING")]
    job.submit(args, api)
    assert api.canceled == ["old"]
    assert api.labels["purpose"] == "preview"


def test_unstoppable_orphan_prevents_submission(setup):
    args, api = setup
    api.previous, api.refuse_stop = [job_info("old", "RUNNING")], True
    with pytest.raises(ValueError, match="did not stop"):
        job.submit(args, api)
    assert not api.submitted


def test_recording_failure_still_stops_submitted_job(setup, monkeypatch):
    args, api = setup
    api.do_work, api.state = False, "RUNNING"
    actual = Path.write_text

    def fail(path, *args_, **kwargs):
        if str(path) == args.job_record:
            raise OSError("record interrupted")
        return actual(path, *args_, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail)
    with pytest.raises(OSError):
        job.submit(args, api)
    assert api.canceled == ["job1"]


def test_always_cleanup_uses_record_and_missing_record_is_harmless(setup):
    args, api = setup
    job.cancel_record(args.job_record, api)
    Path(args.job_record).write_text(json.dumps({"id": "job1", "namespace": "test"}))
    api.state = "RUNNING"
    job.cancel_record(args.job_record, api)
    assert api.canceled == ["job1"]


def test_wrong_archive_never_reaches_workflow_outputs(setup, monkeypatch, tmp_path):
    args, api = setup
    original = job.artifact.verify_archive

    def reject(data, expected, **kwargs):
        if "expected_files" in kwargs and expected["preview"]:
            raise ValueError("wrong source")
        return original(data, expected, **kwargs)

    monkeypatch.setattr(job.artifact, "verify_archive", reject)
    with pytest.raises(ValueError):
        job.submit(args, api)
    assert not (tmp_path / "outputs").exists()
