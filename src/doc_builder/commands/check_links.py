# Copyright 2025 The HuggingFace Team. All rights reserved.
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
import re
import sys

from doc_builder.check_links import check_links


def check_links_command(args):
    """Run the link checker command."""
    print(f"Checking links in {args.path_to_docs}...")
    result = check_links(
        args.path_to_docs,
        max_workers=args.max_workers,
        show_progress=not args.no_progress,
        package_name=args.package_name,
        check_external=not args.skip_external,
        external_options={
            "max_concurrency": args.external_concurrency,
            "per_host_concurrency": args.external_per_host,
            "timeout": args.external_timeout,
            "ignore_patterns": args.external_ignore,
        },
    )

    # Choose output format
    if args.format == "list":
        print(result.get_list_output())
    else:
        print(result.get_summary())

    if result.has_broken_links():
        sys.exit(1)


def _regex(value: str) -> str:
    try:
        re.compile(value)
    except re.error as e:
        raise argparse.ArgumentTypeError(f"invalid regex {value!r}: {e}") from e
    return value


def check_links_command_parser(subparsers=None):
    """Create the argument parser for the check-links command."""
    if subparsers is not None:
        parser = subparsers.add_parser("check-links", help="Check links in documentation files for broken references")
    else:
        parser = argparse.ArgumentParser("Doc Builder check-links command")

    parser.add_argument("path_to_docs", type=str, help="Path to the documentation folder to check")
    parser.add_argument(
        "--package_name",
        "--package-name",
        dest="package_name",
        type=str,
        default=None,
        help="Import name of the documented Python package (auto-detected when omitted)",
    )
    parser.add_argument(
        "--max_workers",
        type=int,
        default=None,
        help="Maximum number of parallel workers (default: auto-detect based on CPU count)",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["detailed", "list"],
        default="detailed",
        help="Output format: 'detailed' (default, shows link text and URL) or 'list' (compact, file:line - URL)",
    )
    parser.add_argument(
        "--skip-external",
        action="store_true",
        help="Only check internal links, without requesting external http(s) URLs over the network",
    )
    parser.add_argument(
        "--external-concurrency",
        type=int,
        default=128,
        help="Maximum number of external requests in flight at once (default: 128)",
    )
    parser.add_argument(
        "--external-per-host",
        type=int,
        default=None,
        help="Maximum number of concurrent requests to each host (default: 8, or 32 for huggingface.co and hf.co)",
    )
    parser.add_argument(
        "--external-timeout",
        type=float,
        default=15.0,
        help="Timeout in seconds for each external request (default: 15)",
    )
    parser.add_argument(
        "--external-ignore",
        action="append",
        default=[],
        type=_regex,
        metavar="REGEX",
        help="Skip external URLs matching this regex (repeatable). localhost and example.com are always skipped",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress bar (useful for CI/CD or when tqdm is not available)",
    )

    if subparsers is not None:
        parser.set_defaults(func=check_links_command)
    return parser
