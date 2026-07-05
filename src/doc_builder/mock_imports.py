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

"""
Mock heavy dependencies (torch, tensorflow, ...) so that a documented library can be
imported — and introspected with `inspect` — without installing them.

doc-builder needs to import the documented library because docstrings are often built
dynamically (e.g. transformers' `add_start_docstrings` decorators), which rules out
purely static analysis. But importing e.g. `transformers` or `accelerate` requires
torch and friends, which are slow to install and may need custom containers (GPU
wheels, compiled extensions) just to build documentation.

`mock_deps(["torch", ...])` installs a `sys.meta_path` finder that provides, for each
mocked package and any of its submodules:

- importable module objects whose attributes are auto-created **mock classes**, so
  `from torch import nn` and `class Model(nn.Module)` work;
- pass-through decorator behavior: calling a mock with a single function/class returns
  it unchanged, so `@torch.no_grad()`-style decorators don't swallow the docstrings
  that doc-builder is trying to read (same heuristic as Sphinx's `autodoc_mock_imports`);
- a `repr` equal to the dotted path (`repr(torch.float32) == "torch.float32"`), so
  mocked default values render in signatures exactly like the real ones;
- fake distribution metadata, so availability checks in HF libraries — typically
  `importlib.util.find_spec(pkg)` plus `importlib.metadata.metadata(pkg)` — treat the
  mocked package as installed instead of routing to dummy objects.

The documented library itself (and its light dependencies) must still be really
installed: `inspect` reads the real source, docstrings and signatures from it.
"""

import importlib.abc
import importlib.machinery
import importlib.metadata
import sys

MOCK_VERSION = "9999.0.0"


class _MockObject:
    """
    A mock value for a dotted path (e.g. `torch.float32`): attribute access chains,
    calls behave as pass-through decorators, `repr` is the dotted path, and using it
    as a base class substitutes a plain-`type` base (PEP 560 `__mro_entries__`), so
    real subclasses keep a normal metaclass and `inspect.signature` reads their real
    `__init__` instead of a mock's.
    """

    def __init__(self, display_name):
        object.__setattr__(self, "__display_name__", display_name)
        # annotations render via `__qualname__`/`__name__` (e.g. `torch.nn.Module`
        # in a signature shows as `Module`, like the real class). Instance attributes
        # shadow the class's own `__qualname__` string.
        short_name = display_name.rsplit(".", 1)[-1]
        object.__setattr__(self, "__name__", short_name)
        object.__setattr__(self, "__qualname__", short_name)

    def __repr__(self):
        return self.__display_name__

    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return _make_mock(f"{self.__display_name__}.{name}")

    def __call__(self, *args, **kwargs):
        # pass decorated functions/classes through unchanged so their docstrings and
        # signatures stay intact (a mock used as a decorator, e.g. `@torch.no_grad()`)
        if len(args) == 1 and not kwargs and (callable(args[0]) or isinstance(args[0], type)):
            return args[0]
        return _make_mock(f"{self.__display_name__}()")

    def __mro_entries__(self, bases):
        return (_make_base_class(self.__display_name__),)

    # keep common import-time expressions working
    def __iter__(self):
        return iter(())

    def __contains__(self, item):
        return False

    def __index__(self):
        return 0

    def __bool__(self):
        return True

    def __eq__(self, other):
        return self is other

    def __hash__(self):
        return hash(self.__display_name__)

    def __lt__(self, other):
        return False

    def __gt__(self, other):
        return False

    def __le__(self, other):
        return True

    def __ge__(self, other):
        return True


_mock_cache = {}
_base_class_cache = {}


def _make_mock(display_name):
    """Creates (and caches) a mock object for a dotted path."""
    if display_name not in _mock_cache:
        _mock_cache[display_name] = _MockObject(display_name)
    return _mock_cache[display_name]


def _make_base_class(display_name):
    """
    Creates (and caches) the plain class substituted when a mock is used as a base
    class (`class Model(nn.Module)`). It provides permissive `__init__`/`__getattr__`
    fallbacks but has metaclass `type`, keeping subclass introspection intact.
    """
    if display_name not in _base_class_cache:
        _base_class_cache[display_name] = type(
            display_name.rsplit(".", 1)[-1],
            (object,),
            {
                "__display_name__": display_name,
                "__module__": display_name.rsplit(".", 1)[0] if "." in display_name else display_name,
                "__init__": lambda self, *args, **kwargs: None,
                "__getattr__": lambda self, name: _make_mock(f"{display_name}.{name}"),
                "__init_subclass__": classmethod(lambda cls, **kwargs: None),
                "__class_getitem__": classmethod(lambda cls, item: cls),
            },
        )
    return _base_class_cache[display_name]


class _MockDistribution(importlib.metadata.Distribution):
    """Just enough metadata for `importlib.metadata.metadata/version` to succeed."""

    def __init__(self, name):
        self._name = name

    def read_text(self, filename):
        if filename == "METADATA":
            return f"Metadata-Version: 2.1\nName: {self._name}\nVersion: {MOCK_VERSION}\n"
        return None

    def locate_file(self, path):
        return None


class MockFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Meta path finder+loader serving mock modules and metadata for mocked packages."""

    def __init__(self, packages):
        self.packages = set(packages)

    def _is_mocked(self, fullname):
        root = fullname.split(".", 1)[0]
        return root in self.packages

    def find_spec(self, fullname, path=None, target=None):
        if not self._is_mocked(fullname):
            return None
        spec = importlib.machinery.ModuleSpec(fullname, self, is_package=True)
        return spec

    def create_module(self, spec):
        import types

        module = types.ModuleType(spec.name)
        module.__version__ = MOCK_VERSION
        module.__path__ = []
        module.__getattr__ = lambda name: _make_mock(f"{spec.name}.{name}")
        return module

    def exec_module(self, module):
        pass

    def find_distributions(self, context=importlib.metadata.DistributionFinder.Context()):
        name = context.name
        if name is None:
            return []
        # normalize the distribution name the way importlib.metadata does
        if name.replace("-", "_").lower() in {p.replace("-", "_").lower() for p in self.packages}:
            return [_MockDistribution(name)]
        return []


def mock_deps(packages):
    """
    Makes `packages` (e.g. `["torch"]`) importable as mocks. Must be called before the
    documented library is imported. No-op for packages that are actually installed
    (the real package takes precedence since the finder is appended last... but
    availability must be consistent, so mocked packages that are really installed are
    skipped explicitly).
    """
    packages = [p.strip() for p in packages if p.strip()]
    to_mock = []
    for package in packages:
        try:
            real = importlib.util.find_spec(package)
        except (ImportError, ValueError):
            real = None
        if real is not None:
            print(f"[mock-deps] `{package}` is actually installed, not mocking it")
            continue
        to_mock.append(package)
    if to_mock:
        finder = MockFinder(to_mock)
        sys.meta_path.insert(0, finder)
        print(f"[mock-deps] mocking imports for: {', '.join(sorted(to_mock))}")
    return to_mock
