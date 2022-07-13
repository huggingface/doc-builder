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

import nbformat

from ..style_doc import format_code_example


def notebook_to_mdx_command(args):
    notebook = nbformat.read(args.notebook_file, as_version=4)
    content = []
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            code = cell["source"]
            outputs = [
                o for o in cell["outputs"] if ("text" in o and o.get("name", None) == "stdout") or "text/plain" in o
            ]
            if len(outputs) > 0:
                code_lines = code.split("\n")
                # We can add >>> everywhere without worrying as format_code_examples will replace them by ...
                # when needed.
                code_lines = [f">>> {l}" if not len(l) == 0 or l.isspace() else l for l in code_lines]
                code = "\n".join(code_lines)
                code = format_code_example(code, max_len=args.max_len)[0]
                content.append(f"```python\n{code}\n```")

                output = outputs[0]["text"] if "text" in outputs[0] else outputs[0]["text/plain"]
                output = output.strip()
                content.append(f"```python out\n{output}\n```")
            else:
                code = format_code_example(code, max_len=args.max_len)[0]
                content.append(f"```python\n{code}\n```")
        elif cell["cell_type"] == "markdown":
            content.append(cell["source"])
        else:
            content.append(f"```\n{cell['source']}\n```")

    dest_file = args.dest_file if args.dest_file is not None else args.notebook_file.replace(".ipynb", ".mdx")
    with open(dest_file, "w", encoding="utf-8") as f:
        f.write("\n\n".join(content))


def notebook_to_mdx_command_parser(subparsers=None):
    if subparsers is not None:
        parser = subparsers.add_parser("notebook-to-mdx")
    else:
        parser = argparse.ArgumentParser("Doc Builder convert notebook to MDX command")

    parser.add_argument("notebook_file", type=str, help="The notebook to convert.")
    parser.add_argument(
        "--max_len",
        type=int,
        default=119,
        help="The number of maximum characters per line.",
    )
    parser.add_argument("--dest_file", type=str, default=None, help="Where to save the result.")

    if subparsers is not None:
        parser.set_defaults(func=notebook_to_mdx_command)
    return parser
