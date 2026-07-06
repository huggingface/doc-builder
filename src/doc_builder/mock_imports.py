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

import abc
import importlib.abc
import importlib.machinery
import importlib.metadata
import sys
import types
import typing
from pathlib import Path

MOCK_VERSION = "9999.0.0"


class _MockVersionString(str):
    """
    Version string comparable against tuples, like torch's `TorchVersion`
    (libraries write e.g. `torch.__version__ >= (2, 6)`).
    """

    def _as_tuple(self):
        return tuple(int(p) for p in self.split(".") if p.isdigit())

    def _coerce(self, other):
        if isinstance(other, tuple):
            return tuple(int(p) if not isinstance(p, int) else p for p in other)
        return None

    def __ge__(self, other):
        coerced = self._coerce(other)
        return self._as_tuple() >= coerced if coerced is not None else str.__ge__(self, other)

    def __gt__(self, other):
        coerced = self._coerce(other)
        return self._as_tuple() > coerced if coerced is not None else str.__gt__(self, other)

    def __le__(self, other):
        coerced = self._coerce(other)
        return self._as_tuple() <= coerced if coerced is not None else str.__le__(self, other)

    def __lt__(self, other):
        coerced = self._coerce(other)
        return self._as_tuple() < coerced if coerced is not None else str.__lt__(self, other)


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
        # tools rendering type names as `__module__.__qualname__` (e.g. transformers'
        # auto_docstring) must see the mocked path, not this module's
        parent = display_name.rsplit(".", 1)[0] if "." in display_name else display_name
        object.__setattr__(self, "__module__", parent)

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

    # PEP 604 unions in runtime-evaluated annotations (`torch.Tensor | None`): build a
    # *real* typing.Union (mocks pass `typing._type_check` because they are callable),
    # so tools that unwrap Optional/Union via typing.get_origin/get_args — like
    # transformers' auto_docstring — treat it exactly like the real annotation
    def __or__(self, other):
        try:
            return typing.Union[self, other]  # noqa: UP007
        except TypeError:
            return _make_mock(f"typing.Union[{self.__display_name__}, {_annotation_name(other)}]")

    def __ror__(self, other):
        try:
            return typing.Union[other, self]  # noqa: UP007
        except TypeError:
            return _make_mock(f"typing.Union[{_annotation_name(other)}, {self.__display_name__}]")

    def __getitem__(self, item):
        # subscripted generics on mocks (`torch.Tensor[int]`-style, rare)
        return self

    # keep common import-time expressions working
    def __len__(self):
        return 0

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

    # `issubclass(cls, torch.Tensor)` / `isinstance(x, torch.Tensor)` against a mock
    # would be a TypeError (mocks are instances, not classes); scipy>=1.17 probes
    # exactly this way when it sees `torch` in sys.modules. Nothing real is a
    # subclass/instance of a mocked type, so answer False.
    def __subclasscheck__(self, subclass):
        return False

    def __instancecheck__(self, instance):
        return False

    def __lt__(self, other):
        return False

    def __gt__(self, other):
        return False

    def __le__(self, other):
        return True

    def __ge__(self, other):
        return True


def _annotation_name(obj):
    """Renders `obj` the way `typing` renders it inside a union."""
    display_name = getattr(obj, "__display_name__", None)
    if display_name is not None:
        return display_name
    if isinstance(obj, type):
        module = getattr(obj, "__module__", "")
        qualname = getattr(obj, "__qualname__", str(obj))
        return qualname if module in ("builtins", "") else f"{module}.{qualname}"
    return str(obj)


_mock_cache = {}
_base_class_cache = {}


def _make_mock(display_name):
    """Creates (and caches) a mock object for a dotted path."""
    if display_name not in _mock_cache:
        _mock_cache[display_name] = _MockObject(display_name)
    return _mock_cache[display_name]


class _MockBaseMeta(abc.ABCMeta):
    """
    Metaclass for mock base classes providing *class-level* attribute fallback: real
    subclasses may rely on attributes the real base would provide (e.g. a model class
    without its own `forward` inherits `torch.nn.Module.forward`). It intentionally
    does NOT define `__call__`, so `inspect.signature` on subclasses still reads their
    real `__init__` (a metaclass `__call__` would shadow it). Deriving from `ABCMeta`
    keeps mock bases combinable with real ABC bases without metaclass conflicts.
    """

    # only fall back for methods commonly inherited from framework bases and
    # documented as such (e.g. `[[autodoc]] SomeModel - forward` where the model
    # doesn't override nn.Module.forward). A blanket fallback would make
    # `hasattr(cls, anything)` true and break libraries' own attribute checks
    # (e.g. peft's prefix-registration validation).
    _FALLBACK_ATTRIBUTES = {"forward", "call"}

    def __getattr__(cls, name):
        if name not in _MockBaseMeta._FALLBACK_ATTRIBUTES:
            raise AttributeError(name)
        base_display_name = getattr(cls, "__display_name__", cls.__name__)
        return _make_mock(f"{base_display_name}.{name}")


def _make_base_class(display_name):
    """
    Creates (and caches) the class substituted when a mock is used as a base class
    (`class Model(nn.Module)`). It provides permissive `__init__` and instance/class
    attribute fallbacks while keeping subclass introspection intact.
    """
    if display_name not in _base_class_cache:
        _base_class_cache[display_name] = _MockBaseMeta(
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


class _MockModule(types.ModuleType):
    """
    Mock module supporting the same expression surface as `_MockObject`: once code runs
    `import torch.X`, the import system binds a real module object as the `X` attribute
    of `torch` (shadowing the mock), and that module may then appear in runtime
    expressions like PEP 604 annotations (`torch.Tensor | None` when `torch.Tensor` was
    imported as a module path) or be called/subclassed.
    """

    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return _make_mock(f"{self.__name__}.{name}")

    def __call__(self, *args, **kwargs):
        return _make_mock(f"{self.__name__}")(*args, **kwargs)

    def __or__(self, other):
        return _make_mock(f"{self.__name__}").__or__(other)

    def __ror__(self, other):
        return _make_mock(f"{self.__name__}").__ror__(other)

    def __mro_entries__(self, bases):
        return (_make_base_class(self.__name__),)

    def __getitem__(self, item):
        return self


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
        # prefix matching so a registered name can be a submodule of a namespace
        # package (e.g. mock `optimum.onnxruntime` while the real `optimum` and
        # `optimum.intel` stay importable)
        return any(fullname == package or fullname.startswith(package + ".") for package in self.packages)

    def find_spec(self, fullname, path=None, target=None):
        if not self._is_mocked(fullname):
            return None
        spec = importlib.machinery.ModuleSpec(fullname, self, is_package=True)
        return spec

    def create_module(self, spec):
        module = _MockModule(spec.name)
        module.__version__ = _MockVersionString(MOCK_VERSION)
        module.__path__ = []
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


def registry_file_path(library_name):
    """Path of a documented library's registry file (which may not exist)."""
    return Path(__file__).parent / "mock_deps" / f"{library_name}.txt"


def _read_registry(library_name):
    registry_file = registry_file_path(library_name)
    if not registry_file.is_file():
        return []
    lines = []
    for line in registry_file.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            lines.append(line)
    return lines


def get_registry_mock_deps(library_name):
    """
    Returns the registered list of mockable heavy dependencies for a documented
    library, from `doc_builder/mock_deps/<library_name>.txt` (one import name per
    line, `#` comments). Lines prefixed with `real:` or `nodeps:` list packages to
    install for real instead (see `get_registry_real_deps`) and are skipped here.
    Empty when the library has no registry entry.
    """
    return [line for line in _read_registry(library_name) if not line.startswith(("real:", "nodeps:"))]


def get_registry_real_deps(library_name):
    """
    Returns the registered dependencies a light docs build must install for real
    (not mock), as a tuple `(resolved, nodeps)` of pip requirement lists:
    `real:<spec>` lines resolve normally, `nodeps:<spec>` lines must be installed
    with `--no-deps` (their own dependency trees pull in heavy packages).
    """
    resolved, nodeps = [], []
    for line in _read_registry(library_name):
        if line.startswith("real:"):
            resolved.append(line[len("real:") :].strip())
        elif line.startswith("nodeps:"):
            nodeps.append(line[len("nodeps:") :].strip())
    return resolved, nodeps


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
