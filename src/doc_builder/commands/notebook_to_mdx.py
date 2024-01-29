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
import subprocess
from pathlib import Path

from tqdm import tqdm


def notebook_to_mdx_command(args):
    src_path = Path(args.notebook_src).resolve()
    src_dir = src_path.parent if src_path.is_file() else src_path
    notebook_paths = [str(src_path)] if src_path.is_file() else [*src_dir.glob("*.ipynb")]
    output_dir = src_dir if args.output_dir is None else Path(args.output_dir).resolve()

    try:
        for notebook_path in tqdm(notebook_paths, desc="Converting .ipynb files to .md files"):
            subprocess.run(
                ["jupyter", "nbconvert", notebook_path, "--to", "markdown", "--output-dir", output_dir],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                encoding="utf-8",
            )
    except subprocess.CalledProcessError as e:
        print("Encoutnered error while using nbconvert:\n", e.stderr)


def notebook_to_mdx_command_parser(subparsers=None):
    if subparsers is not None:
        parser = subparsers.add_parser("notebook-to-mdx")
    else:
        parser = argparse.ArgumentParser("Doc Builder convert notebook to MD command")

    parser.add_argument("notebook_src", type=str, help="The notebook or directory containing notebook(s) to convert.")
    parser.add_argument(
        "--output_dir",
        type=str,
        help="Where the markdown files will be. Defaults to notebook source dir.",
        default=None,
    )

    if subparsers is not None:
        parser.set_defaults(func=notebook_to_mdx_command)
    return parser
