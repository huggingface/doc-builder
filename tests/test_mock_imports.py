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

import importlib.metadata
import importlib.util
import inspect
import sys
import unittest

from doc_builder.mock_imports import MOCK_VERSION, MockFinder, mock_deps

PKG = "doc_builder_test_mocked_pkg"


class MockImportsTester(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.finder = MockFinder([PKG])
        sys.meta_path.insert(0, cls.finder)

    @classmethod
    def tearDownClass(cls):
        sys.meta_path.remove(cls.finder)
        for name in list(sys.modules):
            if name.startswith(PKG):
                del sys.modules[name]

    def test_mocked_module_imports(self):
        module = importlib.import_module(PKG)
        self.assertEqual(module.__version__, MOCK_VERSION)
        submodule = importlib.import_module(f"{PKG}.sub.module")
        self.assertIsNotNone(submodule)

    def test_availability_checks_pass(self):
        # the two checks HF libraries typically combine
        self.assertIsNotNone(importlib.util.find_spec(PKG))
        self.assertIsNotNone(importlib.metadata.metadata(PKG))
        self.assertEqual(importlib.metadata.version(PKG), MOCK_VERSION)

    def test_mock_repr_and_name(self):
        module = importlib.import_module(PKG)
        mock = module.nn.Module
        self.assertEqual(repr(mock), f"{PKG}.nn.Module")
        self.assertEqual(mock.__name__, "Module")
        self.assertEqual(mock.__qualname__, "Module")

    def test_subclass_keeps_real_signature(self):
        module = importlib.import_module(PKG)

        class Model(module.nn.Module):
            """A real class inheriting from a mocked base."""

            def __init__(self, hidden_size: int = 8, dropout: float = 0.1):
                pass

        self.assertEqual(list(inspect.signature(Model).parameters), ["hidden_size", "dropout"])
        self.assertEqual(Model.__doc__, "A real class inheriting from a mocked base.")
        # metaclass stays `type`, like a normal class
        self.assertIs(type(Model), type)

    def test_mock_decorator_passes_through(self):
        module = importlib.import_module(PKG)

        @module.no_grad()
        def documented(a: int, b: str = "x"):
            """Docstring survives mocked decorators."""

        self.assertEqual(documented.__doc__, "Docstring survives mocked decorators.")
        self.assertEqual(list(inspect.signature(documented).parameters), ["a", "b"])

    def test_installed_packages_are_not_mocked(self):
        # `json` is really installed, so it must be skipped
        mocked = mock_deps(["json"])
        self.assertEqual(mocked, [])
        import json

        self.assertTrue(json.dumps({"a": 1}))
