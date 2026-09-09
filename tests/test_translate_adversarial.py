import subprocess

import pytest

from doc_builder.translate import pipeline, segment
from tests.translate_harness import files


@pytest.fixture
def repo(tmp_path):
    directory = tmp_path / "transformers"
    directory.mkdir()
    subprocess.run(["git", "init", str(directory)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(directory), "config", "core.autocrlf", "false"], check=True)
    for name, value in files().items():
        path = directory / "docs/source/en" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    commit(directory)
    return directory


def commit(repo):
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Translation Test",
            "-c",
            "user.email=translation-test@example.com",
            "commit",
            "-m",
            "fixture",
        ],
        check=True,
        capture_output=True,
    )
    return pipeline.git(repo, "rev-parse", "HEAD")


def test_exact_source_inventory_and_preview(repo):
    sha = pipeline.git(repo, "rev-parse", "HEAD")
    source, _ = pipeline.inventory(repo, sha)
    assert source == files()
    preview, tree = pipeline.inventory(repo, sha, ["guide.mdx"])
    assert set(preview) == {"guide.mdx", "_toctree.yml", "image.svg"}
    assert "index" not in str(tree)


@pytest.mark.parametrize("damage", ["unlisted-missing", "unreadable", "sidebar-missing", "dangling", "empty"])
def test_incomplete_source_fails_before_inference(repo, damage):
    root = repo / "docs/source/en"
    if damage == "unlisted-missing":
        (root / "unlisted.md").write_text("# Unlisted\n")
        commit(repo)
    sha = pipeline.git(repo, "rev-parse", "HEAD")
    if damage == "unlisted-missing":
        (root / "unlisted.md").unlink()
    elif damage == "unreadable":
        (root / "index.md").unlink()
        (root / "index.md").mkdir()
    elif damage == "sidebar-missing":
        (root / "_toctree.yml").unlink()
    elif damage == "dangling":
        (root / "_toctree.yml").write_text("- local: ghost\n  title: Missing\n")
        sha = commit(repo)
    else:
        for page in root.glob("*.md*"):
            page.unlink()
        sha = commit(repo)
    with pytest.raises((ValueError, OSError)):
        pipeline.inventory(repo, sha)


@pytest.mark.parametrize("selection", [[], ["missing.md"], ["image.svg"], ["../index.md"]])
def test_invalid_preview_fails(repo, selection):
    with pytest.raises(ValueError):
        pipeline.inventory(repo, pipeline.git(repo, "rev-parse", "HEAD"), selection)


def test_wrong_revision_fails(repo):
    with pytest.raises(ValueError, match="revision"):
        pipeline.inventory(repo, "a" * 40)


def test_source_symlinks_must_resolve_inside_repo(repo, tmp_path):
    target = repo / "docs/source/en/linked.md"
    try:
        target.symlink_to("../../../README.md")
    except OSError:
        pytest.skip("This OS does not permit creating test symlinks")
    (repo / "README.md").write_text("# Shared source\n")
    sha = commit(repo)
    assert pipeline.inventory(repo, sha)[0]["linked.md"] == b"# Shared source\n"
    target.unlink()
    target.symlink_to(tmp_path / "outside.md")
    (tmp_path / "outside.md").write_text("# External\n")
    sha = commit(repo)
    with pytest.raises(ValueError, match="escapes"):
        pipeline.inventory(repo, sha)


@pytest.mark.parametrize(
    "source,visible,hidden",
    [
        ("    [[autodoc]] BertModel\n        - forward\n\nRead this.\n", "Read this", "forward"),
        ("Set `$HOME` and `$PATH` before running.", "and", "$HOME"),
        ("Pay $5-$10 or $5/$10 for $x$ units.", "or", "$x$"),
        ('Read [technical\nreport](https://example/Fine_(LED) "Title").', "report", "https://"),
        ("[![Notebook](badge.svg)](book.ipynb)", "Notebook", "badge.svg"),
        ('<hfoption id="pt">\nRead the instructions.\n</hfoption>', "instructions", 'id="pt"'),
    ],
)
def test_review_syntax_remains_visible_or_protected(source, visible, hidden):
    plan = segment.extract_pages([source])[0]
    prose = "\n".join(u["text"] for u in plan["units"])
    assert visible in prose and hidden not in prose
