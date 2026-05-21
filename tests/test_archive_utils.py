import importlib.util
import zipfile
from pathlib import Path

import pytest


def load_archive_utils_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "src" / "doc_builder" / "archive_utils.py"
    spec = importlib.util.spec_from_file_location("archive_utils", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("member_name", ["../escape.md", "/tmp/escape.md", "..\\escape.md", "C:\\tmp\\escape.md"])
def test_safe_extract_zip_rejects_path_traversal(tmp_path, member_name):
    archive_utils = load_archive_utils_module()
    zip_path = tmp_path / "docs.zip"
    with zipfile.ZipFile(zip_path, "w") as zip_ref:
        zip_ref.writestr(member_name, "bad")

    with zipfile.ZipFile(zip_path) as zip_ref:
        with pytest.raises(ValueError, match="Unsafe ZIP member path"):
            archive_utils.safe_extract_zip(zip_ref, tmp_path / "extract")

    assert not (tmp_path / "escape.md").exists()


def test_safe_extract_zip_allows_nested_docs(tmp_path):
    archive_utils = load_archive_utils_module()
    zip_path = tmp_path / "docs.zip"
    with zipfile.ZipFile(zip_path, "w") as zip_ref:
        zip_ref.writestr("transformers/main/en/index.md", "# Docs")

    extract_path = tmp_path / "extract"
    with zipfile.ZipFile(zip_path) as zip_ref:
        archive_utils.safe_extract_zip(zip_ref, extract_path)

    assert (extract_path / "transformers" / "main" / "en" / "index.md").read_text() == "# Docs"
