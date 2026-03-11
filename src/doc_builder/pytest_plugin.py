# Copyright 2026 The HuggingFace Team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Pytest plugin that collects runnable code blocks from markdown files."""

import tempfile
from pathlib import Path

import pytest

from doc_builder.testing import DocIntegrationTest


def pytest_collect_file(parent, file_path):
    if file_path.suffix == ".md":
        return MarkdownFile.from_parent(parent, path=file_path)


class MarkdownFile(pytest.File):
    def collect(self):
        text = self.path.read_text(encoding="utf-8")
        blocks = list(DocIntegrationTest._iter_runnable_code_blocks(text))
        for idx, (code, name) in enumerate(blocks):
            block_name = name or f"doc_block_{idx}"
            yield MarkdownCodeItem.from_parent(self, name=block_name, code=code)


class MarkdownCodeItem(pytest.Item):
    def __init__(self, name, parent, code):
        super().__init__(name, parent)
        self._code = code

    def runtest(self):
        namespace = {"__name__": f"{self.path.stem}_{self.name}"}
        # Write code to a temp .py file so pdb can display the correct source lines.
        self._tmp_file = Path(tempfile.gettempdir()) / f"_doctest_{self.path.stem}_{self.name}.py"
        self._tmp_file.write_text(self._code, encoding="utf-8")
        exec(compile(self._code, str(self._tmp_file), "exec"), namespace)

    def teardown(self):
        if hasattr(self, "_tmp_file"):
            self._tmp_file.unlink(missing_ok=True)

    def repr_failure(self, excinfo):
        return f"Runnable block '{self.name}' in {self.path} failed:\n\n{excinfo.getrepr()}\n\nCode:\n{self._code}"

    def reportinfo(self):
        return self.path, None, f"runnable:{self.name}"
