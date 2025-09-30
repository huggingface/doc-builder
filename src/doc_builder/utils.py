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

import importlib.machinery
import importlib.util
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import yaml
from packaging import version as package_version

hf_cache_home = os.path.expanduser(
    os.getenv("HF_HOME", os.path.join(os.getenv("XDG_CACHE_HOME", "~/.cache"), "huggingface"))
)
default_cache_path = os.path.join(hf_cache_home, "doc_builder")
DOC_BUILDER_CACHE = os.getenv("DOC_BUILDER_CACHE", default_cache_path)


def get_default_branch_name(repo_folder):
    config = get_doc_config()
    if config is not None and hasattr(config, "default_branch_name"):
        print(config.default_branch_name)
        return config.default_branch_name
    try:
        p = subprocess.run(
            "git symbolic-ref refs/remotes/origin/HEAD".split(),
            capture_output=True,
            check=True,
            encoding="utf-8",
            cwd=repo_folder,
        )
        branch = p.stdout.strip().split("/")[-1]
        return branch
    except Exception:
        # Just in case git is not installed, we need a default
        return "main"


def update_versions_file(build_path, version, doc_folder):
    """
    Insert new version into _versions.yml file of the library
    Assumes that _versions.yml exists and has its first entry as main version
    """
    main_branch = get_default_branch_name(doc_folder)
    if version == main_branch:
        return
    with open(os.path.join(build_path, "_versions.yml")) as versions_file:
        versions = yaml.load(versions_file, yaml.FullLoader)

        if versions[0]["version"] != main_branch:
            raise ValueError(f"{build_path}/_versions.yml does not contain a {main_branch} version")

        main_version, sem_versions = versions[0], versions[1:]
        new_version = {"version": version}
        did_insert = False
        for i, value in enumerate(sem_versions):
            if package_version.parse(new_version["version"]) == package_version.parse(value["version"]):
                # Nothing to do, the version is here already.
                return
            elif package_version.parse(new_version["version"]) > package_version.parse(value["version"]):
                sem_versions.insert(i, new_version)
                did_insert = True
                break
        if not did_insert:
            sem_versions.append(new_version)

    with open(os.path.join(build_path, "_versions.yml"), "w") as versions_file:
        versions_updated = [main_version] + sem_versions
        yaml.dump(versions_updated, versions_file)


doc_config = None


def read_doc_config(doc_folder):
    """
    Execute the `_config.py` file inside the doc source directory and executes it as a Python module.
    """
    global doc_config

    if os.path.isfile(os.path.join(doc_folder, "_config.py")):
        loader = importlib.machinery.SourceFileLoader("doc_config", os.path.join(doc_folder, "_config.py"))
        spec = importlib.util.spec_from_loader("doc_config", loader)
        doc_config = importlib.util.module_from_spec(spec)
        loader.exec_module(doc_config)


def get_doc_config():
    """
    Returns the `doc_config` if it has been loaded.
    """
    return doc_config


def is_watchdog_available():
    """
    Checks if soft dependency `watchdog` exists.
    """
    return importlib.util.find_spec("watchdog") is not None


def is_doc_builder_repo(path):
    """
    Detects whether a folder is the `doc_builder` or not.
    """
    setup_file = Path(path) / "setup.py"
    if not setup_file.exists():
        return False
    with open(os.path.join(path, "setup.py")) as f:
        first_line = f.readline()
    return first_line == "# Doc-builder package setup.\n"


def locate_kit_folder():
    """
    Returns the location of the `kit` folder of `doc-builder`.

    Will clone the doc-builder repo and cache it, if it's not found.
    """
    # First try: let's search where the module is.
    repo_root = Path(__file__).parent.parent.parent
    kit_folder = repo_root / "kit"
    if kit_folder.is_dir():
        return kit_folder

    # Second try, maybe we are inside the doc-builder repo
    current_dir = Path.cwd()
    while current_dir.parent != current_dir and not (current_dir / ".git").is_dir():
        current_dir = current_dir.parent
    kit_folder = current_dir / "kit"
    if kit_folder.is_dir() and is_doc_builder_repo(current_dir):
        return kit_folder

    # Otherwise, let's clone the repo and cache it.
    return Path(get_cached_repo()) / "kit"


def get_cached_repo():
    """
    Clone and cache the `doc-builder` repo.
    """
    os.makedirs(DOC_BUILDER_CACHE, exist_ok=True)
    cache_repo_path = Path(DOC_BUILDER_CACHE) / "doc-builder-repo"
    if not cache_repo_path.is_dir():
        print(
            "To build the HTML doc, we need the kit subfolder of the `doc-builder` repo. Cloning it and caching at "
            f"{cache_repo_path}."
        )
        _ = subprocess.run(
            "git clone https://github.com/huggingface/doc-builder.git".split(),
            stderr=subprocess.PIPE,
            check=True,
            encoding="utf-8",
            cwd=DOC_BUILDER_CACHE,
        )
        shutil.move(Path(DOC_BUILDER_CACHE) / "doc-builder", cache_repo_path)
    else:
        _ = subprocess.run(
            ["git", "pull"],
            capture_output=True,
            check=True,
            encoding="utf-8",
            cwd=cache_repo_path,
        )
    return cache_repo_path


_SCRIPT_BLOCK_RE = re.compile(r"^\s*<script\b[^>]*>.*?</script>\s*", re.DOTALL)
_SCRIPT_MARKERS = ("HF_DOC_BODY_START", "HF_DOC_BODY_END")


def sveltify_file_route(filename):
    """Convert an `.mdx` file path into the corresponding SvelteKit `+page.svelte` route."""
    filename = str(filename)
    if filename.endswith(".mdx"):
        return filename.rsplit(".", 1)[0] + "/+page.svelte"
    return filename


def markdownify_file_route(filename):
    """Return the `.md` companion file path for a given `.mdx` route."""
    filename = str(filename)
    if filename.endswith(".mdx"):
        return filename.rsplit(".", 1)[0] + ".md"
    return filename


def convert_mdx_to_markdown_text(content: str) -> str:
    """Reduce MDX content to Markdown-only text suitable for distribution."""

    content = _SCRIPT_BLOCK_RE.sub("", content, count=1)

    heading_match = re.search(r"^#", content, flags=re.MULTILINE)
    if heading_match:
        cleaned = content[heading_match.start() :]
    else:
        index_candidates = [content.find(marker) for marker in _SCRIPT_MARKERS if marker in content]
        index_candidates = [idx for idx in index_candidates if idx >= 0]
        cleaned = content[min(index_candidates) :] if index_candidates else content

    return cleaned.lstrip()


def write_markdown_route_file(source_file, destination_file):
    """
    Convert a generated `.mdx` file into the Markdown format expected by SvelteKit routes.

    The transformation removes a leading `<script>...</script>` block and ensures the
    resulting file starts directly with Markdown content.
    """

    with open(source_file, encoding="utf-8") as f:
        content = convert_mdx_to_markdown_text(f.read())

    destination_path = Path(destination_file)
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    with open(destination_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)

    return content


def _collect_markdown_from_output(output_dir: Path) -> List[Tuple[str, str]]:
    markdown_items: List[Tuple[str, str]] = []
    for mdx_file in sorted(output_dir.glob("**/*.mdx")):
        relative_path = mdx_file.relative_to(output_dir).with_suffix(".md").as_posix()
        with open(mdx_file, encoding="utf-8") as f:
            markdown_text = convert_mdx_to_markdown_text(f.read())
        markdown_items.append((relative_path, markdown_text))
    return markdown_items


def write_llms_feeds(
    output_dir: Path,
    markdown_items: Optional[Sequence[Tuple[str, str]]] = None,
    base_url: Optional[str] = None,
):
    """Generate llms.txt and llms-full.txt files alongside the documentation output."""

    output_dir = Path(output_dir)
    if markdown_items is None:
        markdown_items = _collect_markdown_from_output(output_dir)
    else:
        markdown_items = [(str(path).replace(os.sep, "/"), text) for path, text in markdown_items]

    markdown_items = [item for item in markdown_items if item[0]]
    if not markdown_items:
        return

    def build_url(relative_path: str) -> str:
        relative_path = relative_path.lstrip("/")
        if base_url:
            return f"{base_url.rstrip('/')}/{relative_path}"
        return f"/{relative_path}"

    index_lines: List[str] = []
    full_lines: List[str] = []

    for relative_path, markdown_text in markdown_items:
        url = build_url(relative_path)
        index_lines.append(url)
        markdown_text = markdown_text.strip()
        if markdown_text:
            full_lines.append(f"## {url}\n\n{markdown_text}\n")
        else:
            full_lines.append(f"## {url}\n")

    output_dir.joinpath("llms.txt").write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    output_dir.joinpath("llms-full.txt").write_text("\n".join(full_lines) + "\n", encoding="utf-8")


def chunk_list(lst, n):
    """
    Create a list of chunks
    """
    return [lst[i : i + n] for i in range(0, len(lst), n)]
