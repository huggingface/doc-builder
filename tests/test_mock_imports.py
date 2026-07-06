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
        # the metaclass must not define `__call__`: it would shadow the subclass's
        # real `__init__` under `inspect.signature`
        self.assertNotIn("__call__", type(Model).__dict__)

    def test_mock_decorator_passes_through(self):
        module = importlib.import_module(PKG)

        @module.no_grad()
        def documented(a: int, b: str = "x"):
            """Docstring survives mocked decorators."""

        self.assertEqual(documented.__doc__, "Docstring survives mocked decorators.")
        self.assertEqual(list(inspect.signature(documented).parameters), ["a", "b"])

    def test_pep604_unions_are_real_typing_unions(self):
        import typing

        module = importlib.import_module(PKG)
        union = module.Tensor | None
        # a real typing.Union, so tools unwrapping Optional via get_origin/get_args
        # (e.g. transformers' auto_docstring) treat it like the real annotation
        self.assertIs(typing.get_origin(union), typing.Union)
        args = typing.get_args(union)
        self.assertIs(args[1], type(None))
        self.assertEqual(getattr(args[0], "__module__", None), PKG)
        self.assertEqual(getattr(args[0], "__qualname__", None), "Tensor")
        # reflected form with a real type on the left
        union = int | module.Tensor
        self.assertIs(typing.get_origin(union), typing.Union)

    def test_subclass_inherits_mock_class_attributes(self):
        module = importlib.import_module(PKG)

        class Model(module.nn.Module):
            pass

        # class-level fallback: the real base (e.g. nn.Module) would provide `forward`
        self.assertIsNotNone(getattr(Model, "forward", None))

    def test_dotted_submodule_mock(self):
        # a registered dotted name mocks a missing submodule of a real (namespace)
        # package, like `optimum.onnxruntime` when only `optimum` is installed
        finder = MockFinder(["unittest.doc_builder_missing_sibling"])
        sys.meta_path.insert(0, finder)
        try:
            module = importlib.import_module("unittest.doc_builder_missing_sibling.sub")
            self.assertEqual(module.__name__, "unittest.doc_builder_missing_sibling.sub")
            import unittest as real_unittest

            # the real parent package is untouched
            self.assertIs(real_unittest.TestCase, unittest.TestCase)
        finally:
            sys.meta_path.remove(finder)
            for name in list(sys.modules):
                if name.startswith("unittest.doc_builder_missing_sibling"):
                    del sys.modules[name]

    def test_registry_mock_deps(self):
        from doc_builder.mock_imports import get_registry_mock_deps

        deps = get_registry_mock_deps("transformers")
        self.assertIn("torch", deps)
        self.assertIn("tensorflow", deps)
        # comments are stripped
        self.assertTrue(all(not d.startswith("#") for d in deps))
        # unknown library -> empty
        self.assertEqual(get_registry_mock_deps("not-a-real-library"), [])
        # validated as needing no mocks -> empty but present
        self.assertEqual(get_registry_mock_deps("datasets"), [])

    def test_installed_packages_are_not_mocked(self):
        # `json` is really installed, so it must be skipped
        mocked = mock_deps(["json"])
        self.assertEqual(mocked, [])
        import json

        self.assertTrue(json.dumps({"a": 1}))
