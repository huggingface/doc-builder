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

from doc_builder import style_doc_files


def style_command(args):
    changed = style_doc_files(*args.files, max_len=args.max_len, check_only=args.check_only)
    if args.check_only and len(changed) > 0:
        raise ValueError(f"{len(changed)} files should be restyled!")
    elif len(changed) > 0:
        print(f"Cleaned {len(changed)} files!")


def style_command_parser(subparsers=None):
    if subparsers is not None:
        parser = subparsers.add_parser("style")
    else:
        parser = argparse.ArgumentParser("Doc Builder style command")

    parser.add_argument("files", nargs="+", help="The file(s) or folder(s) to restyle.")
    parser.add_argument("--max_len", type=int, default=119, help="The maximum length of lines.")
    parser.add_argument("--check_only", action="store_true", help="Whether to only check and not fix styling issues.")

    if subparsers is not None:
        parser.set_defaults(func=style_command)
    return parser
