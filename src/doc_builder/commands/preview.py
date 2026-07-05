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
import shutil
import tempfile
import time
from pathlib import Path
from threading import Thread

from doc_builder import build_doc
from doc_builder.commands.build import check_node_is_available, docs_node_env, run_npm, stage_kit_routes
from doc_builder.commands.convert_doc_file import find_root_git
from doc_builder.mock_imports import mock_deps
from doc_builder.utils import (
    is_watchdog_available,
    locate_kit_folder,
    markdownify_file_route,
    read_doc_config,
    sveltify_file_route,
    write_llms_feeds,
    write_markdown_route_file,
)

if is_watchdog_available():
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    class WatchEventHandler(FileSystemEventHandler):
        """
        Utility class for building updated mdx files when a file change event is recorded.
        """

        def __init__(self, args, source_files_mapping, kit_routes_folder):
            super().__init__()
            self.args = args
            self.source_files_mapping = source_files_mapping
            self.kit_routes_folder = kit_routes_folder

        def on_created(self, event):
            super().on_created(event)
            is_valid, src_path, relative_path = self.transform_path(event)
            if is_valid:
                self.build(src_path, relative_path)

        def on_modified(self, event):
            super().on_modified(event)
            is_valid, src_path, relative_path = self.transform_path(event)
            if is_valid:
                self.build(src_path, relative_path)

        def transform_path(self, event):
            """
            Check if a file is a doc file (mdx, or py file used as autodoc).
            If so, returns mdx file path.
            """
            src_path = event.src_path
            parent_path_absolute = str(Path(self.args.path_to_docs).absolute())
            relative_path = event.src_path[len(parent_path_absolute) + 1 :]
            is_valid_file = False
            if not event.is_directory:
                if src_path.endswith(".py") and src_path in self.source_files_mapping:
                    src_path = self.source_files_mapping[src_path]
                if src_path.endswith((".mdx", ".md")):
                    is_valid_file = True
            return is_valid_file, src_path, relative_path

        def build(self, src_path, relative_path):
            """
            Build single mdx file in a temp dir.
            """
            print(f"Building: {src_path}")
            try:
                with tempfile.TemporaryDirectory() as tmp_input_dir, tempfile.TemporaryDirectory() as tmp_out_dir:
                    # copy the file into tmp_input_dir
                    shutil.copy(src_path, tmp_input_dir)

                    build_doc(
                        self.args.library_name,
                        tmp_input_dir,
                        tmp_out_dir,
                        version=self.args.version,
                        language=self.args.language,
                        is_python_module=not self.args.not_python_module,
                        watch_mode=True,
                    )

                    if str(src_path).endswith(".md"):
                        src_path += "x"
                        relative_path += "x"
                    src = Path(tmp_out_dir) / Path(src_path).name
                    svelte_dest = sveltify_file_route(self.kit_routes_folder / relative_path)
                    markdown_dest = markdownify_file_route(self.kit_routes_folder / relative_path)
                    write_markdown_route_file(src, markdown_dest)
                    Path(svelte_dest).parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(src, svelte_dest)
            except Exception as e:
                print(f"Error building: {src_path}\n{e}")


def start_watcher(path, event_handler):
    """
    Starts `pywatchdog.observer` for listening changes in `path`.
    """
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    print(f"\nWatching for changes in: {path}\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


def start_sveltekit_dev(kit_dir, env):
    """
    Installs sveltekit node dependencies & starts sveltekit in dev mode.
    """
    print("Installing node dependencies")
    run_npm(["ci"], cwd=kit_dir)

    # start sveltekit in dev mode
    run_npm(["run", "dev"], cwd=kit_dir, env=env, quiet=False)


def preview_command(args):
    if args.mock_deps:
        # must happen before the documented library is imported
        mock_deps(args.mock_deps.split(","))
    if not is_watchdog_available():
        raise ImportError(
            "Please install `watchdog` to run `doc-builder preview` command.\nYou can do so through pip: `pip install watchdog`"
        )

    read_doc_config(args.path_to_docs)
    # Error at the beginning if node is not properly installed.
    check_node_is_available()
    # Error at the beginning if we can't locate the kit folder
    kit_folder = locate_kit_folder()
    if kit_folder is None:
        raise OSError(
            "Requires the kit subfolder of the doc-builder repo. We couldn't find it with "
            "the doc-builder package installed, so you need to run the command from inside the doc-builder repo."
        )

    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / args.library_name / args.version / args.language

        print("Initial build docs for", args.library_name, args.path_to_docs, output_path)
        source_files_mapping = build_doc(
            args.library_name,
            args.path_to_docs,
            output_path,
            clean=True,
            version=args.version,
            language=args.language,
            is_python_module=not args.not_python_module,
        )

        # files/folders cannot have a name that starts with `__` since it is a reserved Sveltekit keyword
        for p in output_path.glob("**/*__*"):
            if not p.exists():
                continue
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()

        kit_dir, kit_routes_folder, markdown_exports = stage_kit_routes(kit_folder, tmp_dir, output_path)

        write_llms_feeds(
            kit_routes_folder,
            markdown_exports,
            package_name=args.library_name,
            version=args.version,
            language=args.language,
            is_python_module=not args.not_python_module,
        )

        # Node dev server (daemon: it must not keep the process alive after Ctrl-C)
        env = docs_node_env(args.library_name, args.version, args.language)
        Thread(target=start_sveltekit_dev, args=(kit_dir, env), daemon=True).start()

        git_folder = find_root_git(args.path_to_docs)
        event_handler = WatchEventHandler(args, source_files_mapping, kit_routes_folder)
        start_watcher(git_folder, event_handler)


def preview_command_parser(subparsers=None):
    if subparsers is not None:
        parser = subparsers.add_parser("preview")
    else:
        parser = argparse.ArgumentParser("Doc Builder preview command")

    parser.add_argument("library_name", type=str, help="Library name")
    parser.add_argument(
        "path_to_docs",
        type=str,
        help="Local path to library documentation. The library should be cloned, and the folder containing the "
        "documentation files should be indicated here.",
    )
    parser.add_argument("--language", type=str, help="Language of the documentation to generate", default="en")
    parser.add_argument("--version", type=str, help="Version of the documentation to generate", default="main")
    parser.add_argument(
        "--not_python_module",
        action="store_true",
        help="Whether docs files do NOT have corresponding python module (like HF course & hub docs).",
    )
    parser.add_argument(
        "--mock_deps",
        type=str,
        default=None,
        help="Comma-separated list of heavy dependencies (e.g. `torch,tensorflow`) to mock instead of importing, so "
        "the documented library can be introspected without installing them. Packages that are actually installed "
        "are never mocked.",
    )

    if subparsers is not None:
        parser.set_defaults(func=preview_command)
    return parser
