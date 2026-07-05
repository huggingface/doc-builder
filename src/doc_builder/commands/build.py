# Copyright 2021 The HuggingFace Team. All rights reserved.
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


import argparse
import importlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from doc_builder import build_doc, update_versions_file
from doc_builder.build_cache import PageCache, hash_kit_tree, page_cache_key
from doc_builder.mock_imports import mock_deps
from doc_builder.utils import (
    get_default_branch_name,
    get_doc_config,
    locate_kit_folder,
    markdownify_file_route,
    read_doc_config,
    sveltify_file_route,
    write_llms_feeds,
    write_markdown_route_file,
)

# The kit (SvelteKit) build currently runs on Vite 7, which requires Node.js >= 20.
MIN_NODE_MAJOR_VERSION = 20

# Build artifacts and dependencies do not need to be staged: `npm ci` recreates
# node_modules and the build regenerates `.svelte-kit` and `build`.
KIT_COPY_IGNORE = shutil.ignore_patterns("node_modules", ".svelte-kit", "build")


def check_node_is_available():
    """
    Raises if Node.js is missing or older than `MIN_NODE_MAJOR_VERSION`.
    """
    try:
        p = subprocess.run(
            [resolve_npm_sibling("node"), "-v"],
            capture_output=True,
            check=True,
            encoding="utf-8",
        )
        version = p.stdout.strip()
    except Exception as e:
        raise OSError(
            f"This command requires Node.js v{MIN_NODE_MAJOR_VERSION} or newer, but node was not found in your system."
        ) from e

    major = int(version.removeprefix("v").split(".")[0])
    if major < MIN_NODE_MAJOR_VERSION:
        raise OSError(
            f"This command requires Node.js v{MIN_NODE_MAJOR_VERSION} or newer, but the version in your system is "
            f"lower ({version.removeprefix('v')})."
        )


def resolve_npm_sibling(executable):
    """
    Resolves `node`/`npm` to a full path, which also works on Windows where
    `npm` is `npm.cmd` (not directly runnable by `subprocess` without a shell).
    """
    resolved = shutil.which(executable)
    if resolved is None:
        raise OSError(f"`{executable}` was not found in your system (PATH).")
    return resolved


def run_npm(npm_args, cwd, env=None, quiet=True):
    """
    Runs `npm <npm_args>` in `cwd`. With `quiet=True`, stdout is captured
    (stderr passes through so errors stay visible).
    """
    subprocess.run(
        [resolve_npm_sibling("npm"), *npm_args],
        stdout=subprocess.PIPE if quiet else None,
        check=True,
        encoding="utf-8",
        cwd=str(cwd),
        env=env,
    )


def docs_node_env(library_name, version, language):
    """
    Environment for the kit build/dev server: DOCS_* variables end up as compile-time
    constants (see kit/vite.config.ts) and in the base path (see kit/svelte.config.js).
    """
    env = os.environ.copy()
    env["DOCS_LIBRARY"] = env.get("package_name") or library_name
    env["DOCS_VERSION"] = version
    env["DOCS_LANGUAGE"] = language
    return env


def stage_kit_routes(kit_folder, tmp_dir, output_path):
    """
    Stages the SvelteKit app in `tmp_dir` with the generated doc files as routes:

    1. copies the kit folder (without dependencies/build artifacts),
    2. copies the generated files from `output_path` into `src/routes`,
    3. renames `.mdx` files to the SvelteKit routing convention (`foo.mdx` ->
       `foo/+page.svelte`) and writes the markdown (`foo.md`) route files.

    Returns `(kit_dir, routes_dir, markdown_exports)` where `markdown_exports` is a
    list of `(relative_posix_path, markdown_content)` tuples.
    """
    kit_dir = Path(tmp_dir) / "kit"
    routes_dir = kit_dir / "src" / "routes"

    shutil.copytree(kit_folder, kit_dir, ignore=KIT_COPY_IGNORE)

    # Manual copy and overwrite from output_path to src/routes: we don't use
    # shutil.copytree as it exists and contains important files.
    for f in Path(output_path).iterdir():
        dest = routes_dir / f.name
        if f.is_dir():
            if dest.is_dir():
                shutil.rmtree(dest)
            shutil.copytree(f, dest)
        else:
            shutil.copy(f, dest)

    # make mdx file paths comply with the sveltekit routing mechanism
    # see more: https://svelte.dev/docs/kit/routing
    markdown_exports = []
    for mdx_file_path in routes_dir.rglob("*.mdx"):
        new_page_svelte = sveltify_file_route(mdx_file_path)
        new_markdown = markdownify_file_route(mdx_file_path)
        content = write_markdown_route_file(mdx_file_path, new_markdown)
        markdown_exports.append((Path(new_markdown).relative_to(routes_dir).as_posix(), content))
        Path(new_page_svelte).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(mdx_file_path, new_page_svelte)

    return kit_dir, routes_dir, markdown_exports


def build_command(args):
    if args.mock_deps:
        # must happen before the documented library is imported
        mock_deps(args.mock_deps.split(","))
    read_doc_config(args.path_to_docs)
    if args.html:
        # Error at the beginning if node is not properly installed.
        check_node_is_available()
        # Error at the beginning if we can't locate the kit folder
        kit_folder = locate_kit_folder()
        if kit_folder is None:
            raise OSError(
                "Using the --html flag requires the kit subfolder of the doc-builder repo. We couldn't find it with "
                "the doc-builder package installed, so you need to run the command from inside the doc-builder repo."
            )

    default_version = get_default_branch_name(args.path_to_docs)
    if args.not_python_module and args.version is None:
        version = default_version
    elif args.version is None:
        module = importlib.import_module(args.library_name)
        version = module.__version__

        if "dev" in version:
            version = default_version
        else:
            version = f"v{version}"
    else:
        version = args.version

    # `version` will always start with prefix `v`
    # `version_tag` does not have to start with prefix `v` (see: https://github.com/huggingface/datasets/tags)
    version_tag = version
    if version != default_version:
        doc_config = get_doc_config()
        version_prefix = getattr(doc_config, "version_prefix", "v")
        version_ = version[1:]  # v2.1.0 -> 2.1.0
        version_tag = f"{version_prefix}{version_}"

    # Disable notebook building for non-master version
    if version != default_version:
        args.notebook_dir = None

    notebook_dir = Path(args.notebook_dir) / args.language if args.notebook_dir is not None else None
    output_path = Path(args.build_dir) / args.library_name / version / args.language

    print("Building docs for", args.library_name, args.path_to_docs, output_path)
    build_doc(
        args.library_name,
        args.path_to_docs,
        output_path,
        clean=args.clean,
        version=version,
        version_tag=version_tag,
        language=args.language,
        notebook_dir=notebook_dir,
        is_python_module=not args.not_python_module,
        version_tag_suffix=args.version_tag_suffix,
        repo_owner=args.repo_owner,
        repo_name=args.repo_name,
        emit_warning=args.emit_warning,
    )

    # dev build should not update _versions.yml
    package_doc_path = Path(args.build_dir) / args.library_name
    if "pr_" not in version and (package_doc_path / "_versions.yml").is_file():
        update_versions_file(package_doc_path, version, args.path_to_docs)

    # If asked, convert the MDX files into HTML files.
    if args.html:
        package_name = os.environ.get("package_name") or args.library_name

        # Page-level HTML cache: reuse previously built pages whose generated mdx (and
        # the kit itself) did not change, so the SvelteKit build only renders the rest.
        page_cache = None
        page_keys, manifest, reused = {}, {}, {}
        if args.html_page_cache:
            page_cache = PageCache(
                args.html_page_cache,
                package=package_name,
                version=version,
                language=args.language,
                write=args.html_page_cache_write,
            )
            kit_hash = hash_kit_tree(kit_folder)
            for mdx_file in output_path.rglob("*.mdx"):
                rel = mdx_file.relative_to(output_path).as_posix()
                page_keys[rel] = page_cache_key(
                    mdx_file.read_text(encoding="utf-8"), kit_hash, package_name, version, args.language
                )
            manifest = page_cache.load_manifest()
            reused = page_cache.fetch_pages(page_keys, manifest)
            print(f"[page-cache] reusing {len(reused)}/{len(page_keys)} cached page(s)")

        with tempfile.TemporaryDirectory() as tmp_dir:
            kit_dir, routes_dir, markdown_exports = stage_kit_routes(kit_folder, tmp_dir, output_path)

            # Cached pages don't need to be prerendered again
            for page in reused:
                staged_route = Path(sveltify_file_route(routes_dir / page))
                if staged_route.is_file():
                    staged_route.unlink()

            # Move the objects.inv file at the root
            if not args.not_python_module:
                shutil.move(kit_dir / "src" / "routes" / "objects.inv", Path(tmp_dir) / "objects.inv")

            # Build doc with node
            print("Installing node dependencies")
            run_npm(["ci"], cwd=kit_dir)

            print("Building HTML files. This will take a while :-)")
            run_npm(["run", "build"], cwd=kit_dir, env=docs_node_env(args.library_name, version, args.language))

            # Copy result back in the build_dir.
            shutil.rmtree(output_path)
            shutil.copytree(kit_dir / "build", output_path)

            # Merge the cached pages into the build output
            for page, fetched in reused.items():
                cached_dest = output_path / (page.removesuffix(".mdx") + ".html")
                cached_dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(fetched.html_path, cached_dest)

            # Store the freshly built pages (no-op unless --html_page_cache_write)
            if page_cache is not None:
                built = {}
                for page, key in page_keys.items():
                    if page in reused:
                        continue
                    built_html = output_path / (page.removesuffix(".mdx") + ".html")
                    if built_html.is_file():
                        built[page] = (key, built_html)
                page_cache.store_pages(built, manifest, reused)
            # write markdown routes alongside the generated html output
            for relative_path, content in markdown_exports:
                markdown_dest = output_path / relative_path
                markdown_dest.parent.mkdir(parents=True, exist_ok=True)
                markdown_dest.write_text(content, encoding="utf-8", newline="\n")
            write_llms_feeds(
                output_path,
                markdown_exports,
                package_name=args.library_name,
                version=version,
                language=args.language,
                is_python_module=not args.not_python_module,
            )
            # Move the objects.inv file back
            if not args.not_python_module:
                shutil.move(Path(tmp_dir) / "objects.inv", output_path / "objects.inv")


def build_command_parser(subparsers=None):
    if subparsers is not None:
        parser = subparsers.add_parser("build")
    else:
        parser = argparse.ArgumentParser("Doc Builder build command")

    parser.add_argument("library_name", type=str, help="Library name")
    parser.add_argument(
        "path_to_docs",
        type=str,
        help="Local path to library documentation. The library should be cloned, and the folder containing the "
        "documentation files should be indicated here.",
    )
    parser.add_argument("--build_dir", type=str, help="Where the built documentation will be.", default="./build/")
    parser.add_argument("--clean", action="store_true", help="Whether or not to clean the output dir before building.")
    parser.add_argument("--language", type=str, help="Language of the documentation to generate", default="en")
    parser.add_argument(
        "--version",
        type=str,
        help="Version of the documentation to generate. Will default to the version of the package module (using "
        "`main` for a version containing dev).",
    )
    parser.add_argument("--notebook_dir", type=str, help="Where to save the generated notebooks.", default=None)
    parser.add_argument("--html", action="store_true", help="Whether or not to build HTML files instead of MDX files.")
    parser.add_argument(
        "--not_python_module",
        action="store_true",
        help="Whether docs files do NOT have corresponding python module (like HF course & hub docs).",
    )
    parser.add_argument(
        "--version_tag_suffix",
        type=str,
        default="src/",
        help="Suffix to add after the version tag (e.g. 1.3.0 or main) in the documentation links. For example, the default `src/` suffix will result in a base link as `https://github.com/huggingface/{package_name}/blob/{version_tag}/src/`.",
    )
    parser.add_argument(
        "--repo_owner",
        type=str,
        default="huggingface",
        help="Owner of the repo (e.g. huggingface, rwightman, etc.).",
    )
    parser.add_argument(
        "--repo_name",
        type=str,
        default=None,
        help="Name of the repo (e.g. transformers, pytorch-image-models, etc.). By default, this is the same as the library_name.",
    )
    parser.add_argument(
        "--emit-warning",
        action="store_true",
        help="Emit conversion warnings, such as bare asserts in runnable markdown code blocks.",
    )
    parser.add_argument(
        "--html_page_cache",
        type=str,
        default=None,
        help="Page-level HTML build cache location: an HF storage bucket path (e.g. "
        "`hf://buckets/hf-doc-build/doc-build-cache`) or a local directory. Only used with --html. Pages whose "
        "generated mdx did not change are reused from the cache instead of being prerendered again.",
    )
    parser.add_argument(
        "--mock_deps",
        type=str,
        default=None,
        help="Comma-separated list of heavy dependencies (e.g. `torch,tensorflow`) to mock instead of importing, so "
        "the documented library can be introspected without installing them. Packages that are actually installed "
        "are never mocked.",
    )
    parser.add_argument(
        "--html_page_cache_write",
        action="store_true",
        help="Also write freshly built pages to the page cache. Enable only on trusted builds (e.g. main-branch "
        "builds), never on PR builds, so that untrusted code cannot poison the cache.",
    )
    if subparsers is not None:
        parser.set_defaults(func=build_command)
    return parser
