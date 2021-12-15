# coding=utf-8
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

from doc_builder import build_doc, update_versions_file


def build_command(args):
    if args.version is None:
        module = importlib.import_module(args.library_name)
        version = module.__version__

        if "dev" in version:
            version = "master"
        else:
            version = f"v{version}"
    else:
        version = args.version

    output_path = os.path.join(args.build_dir, os.path.sep.join([args.library_name, version, args.language]))

    print("Building docs for", args.library_name, args.path_to_docs, output_path)
    build_doc(
        args.library_name,
        args.path_to_docs,
        output_path,
        clean=args.clean,
        version=version,
        language=args.language,
        notebook_dir=args.notebook_dir,
    )

    package_doc_path = os.path.join(args.build_dir, args.library_name)
    if os.path.isfile(os.path.join(package_doc_path, "_versions.yml")):
        update_versions_file(os.path.join(args.build_dir, args.library_name), version)


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
        help="Version under which to push the files. Will not affect the actual files generated, as these are"
        " generated according to the `path_to_docs` argument.",
    )
    parser.add_argument("--notebook_dir", type=str, help="Where to save the generated notebooks.", default=None)

    if subparsers is not None:
        parser.set_defaults(func=build_command)
    return parser
