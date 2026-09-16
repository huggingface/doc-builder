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
            self.state = "COMPLETED"
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
        pages=None,
        model_revision="a" * 40,
        doc_builder_repository=None,
        flavor="a100-large",
        job_record=str(tmp_path / "job.json"),
    )
    return args, Jobs(repo)


def test_job_writes_only_canonical_files_and_warm_run_skips_generation(setup):
    args, api = setup
    result = job.submit(args, api)
    assert result["translation_bucket"] == args.bucket
    assert result["page_url"] == result["folder_url"] + "/guide.mdx"
    assert len(api.files) == 5  # Four source files plus hashes-only state.
    assert not any(".runs" in name or ".cache.json" in name for _, name in api.files)
    assert json.loads(Path(args.job_record).read_text())["id"] == "job1"
    assert api.submitted[0]["secrets"] == {"HF_TOKEN": "test-token"}
    assert "test-token" not in str(api.files)
    api.generator = lambda *a, **k: pytest.fail("Warm worker loaded the model")
    api.writes.clear()
    assert job.submit(args, api) == result
    assert all(batch == ["transformers/ja/.translation-state.json"] for batch in api.writes)


def test_failed_job_keeps_old_page_and_caches_successes_without_build_output(setup, tmp_path):
    args, api = setup

    def broken(units, config, retry=False):
        return ["" if "Read" in u["text"] else generate([u], config)[0] for u in units]

    api.generator = broken
    api.files["test/translations", "transformers/ja/index.md"] = b"previous accepted page"
    with pytest.raises(ValueError, match="ERROR"):
        job.submit(args, api)
    state = job.artifact.read_state(api, "test/translations", "ja")
    assert not state["complete"] and "index.md" not in state["files"]
    assert "guide.mdx" in state["files"]
    assert not (tmp_path / "outputs").exists()
    assert api.files["test/translations", "transformers/ja/index.md"] == b"previous accepted page"


def test_selected_pages_preserve_other_docs_and_sidebar(setup):
    args, api = setup
    job.submit(args, api)
    before = dict(api.files)
    args.pages = ["index.md"]
    job.submit(args, api)
    for name in ["guide.mdx", "_toctree.yml", "image.svg"]:
        assert (
            api.files["test/translations", "transformers/ja/" + name]
            == before["test/translations", "transformers/ja/" + name]
        )
    assert not job.artifact.read_state(api, "test/translations", "ja")["complete"]


@pytest.mark.parametrize("state", ["CANCELED", "DELETED", "RUNNING", "UNKNOWN"])
def test_non_successful_job_has_no_outputs_or_cache_update(setup, state, tmp_path):
    args, api = setup
    api.do_work, api.state = False, state
    with pytest.raises(ValueError):
        job.submit(args, api)
    assert not api.writes and not (tmp_path / "outputs").exists()
    if state == "RUNNING":
        assert api.canceled == ["job1"]


def test_active_translation_prevents_submission_even_for_other_scope(setup):
    args, api = setup
    api.previous = [job_info("old", "RUNNING")]
    with pytest.raises(ValueError, match="still active"):
        job.submit(args, api)
    assert not api.submitted and not api.canceled
    assert "purpose" not in api.labels


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


def test_changed_state_never_reaches_workflow_outputs(setup, monkeypatch, tmp_path):
    args, api = setup

    def reject(*args, **kwargs):
        raise ValueError("Translation state changed")

    monkeypatch.setattr(job.artifact, "verify", reject)
    with pytest.raises(ValueError, match="state changed"):
        job.submit(args, api)
    assert not (tmp_path / "outputs").exists()


def test_failed_update_retains_old_hash_and_retry_only_generates_failed_page(setup, tmp_path):
    from tests.test_translate_adversarial import commit

    args, api = setup
    job.submit(args, api)
    old = dict(api.files)
    root = api.repo / "docs/source/en"
    (root / "index.md").write_bytes(b"# Introduction\n\nRead updated instructions.\n")
    args.source_revision = commit(api.repo)
    api.generator = lambda units, *a, **k: ["" for _ in units]
    with pytest.raises(ValueError, match="ERROR"):
        job.submit(args, api)
    state = job.artifact.read_state(api, "test/translations", "ja")
    assert not state["complete"]
    assert (
        api.files["test/translations", "transformers/ja/index.md"]
        == old["test/translations", "transformers/ja/index.md"]
    )
    calls = []

    def retry(units, cfg, retry=False):
        calls.extend(u["text"] for u in units)
        return generate(units, cfg, retry)

    api.generator = retry
    job.submit(args, api)
    assert calls == ["Introduction", "Read updated instructions."]
    assert job.artifact.read_state(api, "test/translations", "ja")["complete"]
