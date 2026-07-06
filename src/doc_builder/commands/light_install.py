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
import re
import shlex
import subprocess
import sys

from doc_builder.mock_imports import get_registry_real_deps, registry_file_path


def _library_requirements(library_name):
    """
    The documented library's own declared requirements (marker-free ones), as a
    mapping of normalized name -> version specifier string. Empty when the library
    is not installed yet.
    """
    from packaging.requirements import Requirement

    requirements = {}
    for dist_name in (library_name, library_name.replace(".", "-")):
        try:
            requires = importlib.metadata.requires(dist_name) or []
        except importlib.metadata.PackageNotFoundError:
            continue
        for raw in requires:
            try:
                requirement = Requirement(raw)
            except Exception:
                continue
            if requirement.marker is not None:
                continue  # extras & platform-conditional requirements
            name = re.sub(r"[-_.]+", "-", requirement.name).lower()
            if requirement.specifier:
                requirements[name] = str(requirement.specifier)
        break
    return requirements


def _refine(specs, requirements):
    """
    Pins bare registry names to the documented library's own declared version
    range, so registry files don't have to chase pins like transformers'
    `tokenizers>=0.22,<=0.23`.
    """
    refined = []
    for spec in specs:
        if re.fullmatch(r"[A-Za-z0-9._-]+", spec):
            name = re.sub(r"[-_.]+", "-", spec).lower()
            if name in requirements:
                refined.append(spec + requirements[name])
                continue
        refined.append(spec)
    return refined


def light_install_command(args):
    """
    Installs the real (non-mocked) dependencies a light docs build of `library_name`
    needs, from the `real:`/`nodeps:` lines of its mock-deps registry file. The
    documented library itself is not installed — install it first with `--no-deps`
    (its heavy dependencies are mocked automatically at build time); bare registry
    names are then pinned to the library's own declared version ranges.

    Exits with code 3 when the library has no registry entry, so callers can fall
    back to a full install:

        if doc-builder light-install my_package --check; then
            uv pip install ./my_package --no-deps
            doc-builder light-install my_package
        else
            uv pip install "./my_package[dev]"
        fi
    """
    if not registry_file_path(args.library_name).is_file():
        print(
            f"No mock-deps registry entry for `{args.library_name}` "
            f"(expected {registry_file_path(args.library_name)}); do a full install instead.",
            file=sys.stderr,
        )
        sys.exit(3)
    if args.check:
        print(f"`{args.library_name}` has a mock-deps registry entry.")
        return
    resolved, nodeps = get_registry_real_deps(args.library_name)
    requirements = _library_requirements(args.library_name)
    # target the interpreter running doc-builder, whether or not a venv is "active"
    uv_pip_install = ["uv", "pip", "install", "--python", sys.executable]
    for specs, extra_flags in [(resolved, []), (nodeps, ["--no-deps"])]:
        if not specs:
            continue
        specs = _refine(specs, requirements)
        if args.dry_run:
            print(" ".join(["uv", "pip", "install", *extra_flags, *(shlex.quote(spec) for spec in specs)]))
            continue
        subprocess.run([*uv_pip_install, *extra_flags, *specs], check=True)
    if not (resolved or nodeps):
        print(f"`{args.library_name}` needs no real dependencies beyond the library itself.")


def light_install_command_parser(subparsers=None):
    if subparsers is not None:
        parser = subparsers.add_parser("light-install")
    else:
        from argparse import ArgumentParser

        parser = ArgumentParser("Doc Builder light-install command")
    parser.add_argument(
        "library_name", type=str, help="Library whose registered real doc-build dependencies to install."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only check whether the library has a registry entry (exit code 3 when it does not).",
    )
    parser.add_argument(
        "--dry_run",
        dest="dry_run",
        action="store_true",
        help="Print the install commands instead of running them.",
    )
    if subparsers is not None:
        parser.set_defaults(func=light_install_command)
    return parser
