"""
Golden test of docstring rendering, Python half: builds `data/docstring_snapshots/docs/page.md`, which autodocs the
objects of `docstring_samples.py`, into `page.mdx`. The kit half (`kit/scripts/docstring-snapshots.test.js`) renders
that `page.mdx` into the final HTML of the docstrings, `page.html`.

A change to the docstring pipeline may change `page.mdx`, the format passed from Python to the kit; `page.html` must
only change when the rendered documentation is meant to change. Regenerate both snapshots with:

    UPDATE_SNAPSHOTS=1 python -m pytest tests/test_docstring_snapshots.py
    cd kit && UPDATE_SNAPSHOTS=1 npm test
"""

import importlib.util
import os
import sys
from pathlib import Path

from doc_builder.build_doc import build_mdx_files, resolve_links

SNAPSHOT_DIR = Path(__file__).parent / "data" / "docstring_snapshots"


def load_docstring_samples():
    spec = importlib.util.spec_from_file_location("docstring_samples", SNAPSHOT_DIR / "docstring_samples.py")
    package = importlib.util.module_from_spec(spec)
    # `inspect` finds the source of classes through `sys.modules`
    sys.modules["docstring_samples"] = package
    spec.loader.exec_module(package)
    return package


def test_docstring_mdx_snapshot(tmp_path):
    package = load_docstring_samples()
    # same page_info as `build_doc`
    page_info = {
        "version": "main",
        "version_tag": "main",
        "language": "en",
        "package_name": "docstring_samples",
        "repo_owner": "huggingface",
        "repo_name": "docstring_samples",
        "emit_warning": False,
    }
    anchors_mapping, _ = build_mdx_files(
        package, SNAPSHOT_DIR / "docs", tmp_path, page_info, version_tag_suffix="src/"
    )
    resolve_links(tmp_path, package, anchors_mapping, page_info)
    mdx = (tmp_path / "page.mdx").read_text(encoding="utf-8")

    snapshot = SNAPSHOT_DIR / "page.mdx"
    if os.environ.get("UPDATE_SNAPSHOTS"):
        snapshot.write_text(mdx, encoding="utf-8")
    assert mdx == snapshot.read_text(encoding="utf-8"), (
        "The MDX of the docstring snapshots changed. If intended, regenerate the snapshots (see the docstring of "
        "tests/test_docstring_snapshots.py) and check that page.html, the rendered HTML, only changed as intended."
    )
