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
import json
import os
import re
import shutil
import subprocess
import unicodedata
from collections.abc import Sequence
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote

import yaml
from packaging import version as package_version

from .html_to_markdown import html_to_markdown

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
    pyproject_file = Path(path) / "pyproject.toml"
    if not pyproject_file.exists():
        return False
    content = pyproject_file.read_text(encoding="utf-8")
    return re.search(r"""^name\s*=\s*["']hf-doc-builder["']""", content, flags=re.MULTILINE) is not None


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
_DOCBUILD_COMMENT_RE = re.compile(r"<!--\s*HF\s*DOCBUILD\s*BODY\s*(?:START|END)\s*-->", re.IGNORECASE)
_DOCBODY_LINE_RE = re.compile(r"^\s*HF_DOC_BODY_(?:START|END)\s*$", re.MULTILINE)


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

    cleaned = _DOCBUILD_COMMENT_RE.sub("", cleaned)
    cleaned = _DOCBODY_LINE_RE.sub("", cleaned)
    cleaned = cleaned.replace("HF_DOC_BODY_START", "").replace("HF_DOC_BODY_END", "")
    return cleaned.lstrip().rstrip()


def write_markdown_route_file(source_file, destination_file):
    """
    Convert a generated `.mdx` file into the Markdown format expected by SvelteKit routes.

    The transformation removes a leading `<script>...</script>` block and ensures the
    resulting file starts directly with Markdown content.
    """

    with open(source_file, encoding="utf-8") as f:
        content = convert_mdx_to_markdown_text(f.read())

    # Strip HTML from the markdown content before writing
    content = strip_html_from_markdown(content)

    destination_path = Path(destination_file)
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    with open(destination_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)

    return content


# Per-section full text, next to llms-full.txt: `llms-full/<section>.txt`.
LLMS_SECTIONS_DIR = "llms-full"
# A page's description in llms.txt: its first sentence, up to this many characters.
LLMS_DESCRIPTION_MAX = 200
# The end of a sentence: not the period of an abbreviation such as "e.g.".
_SENTENCE_END_RE = re.compile(
    r"(?<!\be\.g\.)(?<!\bi\.e\.)(?<!\betc\.)(?<!\bvs\.)(?<!\bcf\.)(?<=[.!?])\s+(?=[A-Z0-9\"“(\[`])|(?<=[。！？])"
)


def _strip_fenced_code(markdown_text: str) -> list[str]:
    """The lines of `markdown_text` outside fenced code blocks (each fence is replaced by an empty line)."""
    lines, fence = [], None
    for line in markdown_text.splitlines():
        match = re.match(r"\s*(?:>\s*)*(`{3,}|~{3,})", line)
        if fence is None and match:
            fence = match.group(1)
            lines.append("")
        elif fence is not None:
            if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence):
                fence = None
        else:
            lines.append(line)
    return lines


def _plain_inline(text: str) -> str:
    """Markdown inline text without its markup: images go, links keep their text, emphasis markers go."""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[\[[^\]]*\]\]", "", text)
    text = re.sub(r"(\*\*|__)(.+?)\1", r"\2", text)
    text = re.sub(r"(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def markdown_page_title(markdown_text: str) -> str | None:
    """The H1 of a page (not a heading inside code), without its `[[anchor]]`."""
    for line in _strip_fenced_code(markdown_text):
        match = re.match(r"# (.+?)\s*#*\s*$", line)
        if match:
            title = _plain_inline(re.sub(r"\[\[[^\]]*\]\]\s*$", "", match.group(1)))
            if title:
                return title
    return None


def markdown_page_description(markdown_text: str) -> str:
    """
    The first sentence of a page's first paragraph of prose after its H1: no heading, list, table,
    quote, code, image or tab label. Empty if the page has none.
    """
    lines = _strip_fenced_code(markdown_text)
    h1 = next((i for i, line in enumerate(lines) if line.startswith("# ")), None)
    paragraphs, current = [], []
    for line in lines[h1 + 1 if h1 is not None else 0 :] + [""]:
        if line.strip():
            current.append(line.strip())
        elif current:
            paragraphs.append(current)
            current = []
    for paragraph in paragraphs:
        first = paragraph[0]
        if re.match(r"(#|>|\||<|!\[|\[!\[|\[\[|[-*+] |\d+[.)] |---|\*\*\*|___|\*\*Option: )", first):
            continue
        text = " ".join(paragraph)
        # links only (`Paper · Code`) or a bare URL: not a description
        if not re.search(r"\w", re.sub(r"!?\[[^\]]*\]\([^)]*\)|<?https?://\S+>?", "", text)):
            continue
        text = _plain_inline(text)
        sentence = _SENTENCE_END_RE.split(text, maxsplit=1)[0].strip()
        if len(sentence) > LLMS_DESCRIPTION_MAX:
            sentence = sentence[:LLMS_DESCRIPTION_MAX].rsplit(" ", 1)[0].rstrip(",;:") + "…"
        return sentence
    return ""


def _toctree_sections(toctree, pages: set[str]) -> list[tuple[list[str], list[tuple[str, str]]]]:
    """
    The pages of the table of contents, as `(group titles, [(page, title), ...])` sections in sidebar
    order: a group's own page and pages come first, then its subgroups. Pages listed at the top level
    (not in a group) share a "Docs" section; a page listed twice is kept where it comes first.
    """

    def local_page(entry):
        local = entry.get("local")
        if not isinstance(local, str):
            return None
        local = local.split("#", 1)[0].strip().strip("/")
        return local if local in pages else None

    # the entry where each page comes first, in sidebar order
    first_entry: dict[str, int] = {}

    def find_first(items):
        for item in items or []:
            if isinstance(item, dict):
                page = local_page(item)
                if page:
                    first_entry.setdefault(page, id(item))
                if isinstance(item.get("sections"), list):
                    find_first(item["sections"])

    find_first(toctree if isinstance(toctree, list) else [])

    def entry_page(entry):
        page = local_page(entry)
        return page if page and first_entry.get(page) == id(entry) else None

    def title_of(entry, page):
        return str(entry.get("title") or "").strip() or page

    def walk(items, trail):
        entries, subgroups = [], []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            page = entry_page(item)
            if isinstance(item.get("sections"), list):
                subgroups.append((item, page))
            elif page:
                entries.append((page, title_of(item, page)))
        sections = [(trail, entries)] if entries else []
        for item, page in subgroups:
            title = str(item.get("title") or "").strip()
            own = [(page, title or page)] if page else []
            group = walk(item["sections"], trail + [title])
            if group and group[0][0] == trail + [title]:
                group[0] = (group[0][0], own + group[0][1])
            elif own:
                group.insert(0, (trail + [title], own))
            sections.extend(group)
        return sections

    sections = walk(toctree if isinstance(toctree, list) else [], [])
    return [(trail or ["Docs"], entries) for trail, entries in sections]


def _slug(title: str) -> str:
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")


def _size(num_bytes: int) -> str:
    if num_bytes >= 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    return f"{max(1, round(num_bytes / 1024))} KB"


def _link_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def _collect_markdown_from_output(output_dir: Path) -> list[tuple[str, str]]:
    markdown_items: list[tuple[str, str]] = []
    for mdx_file in sorted(output_dir.glob("**/*.mdx")):
        relative_path = mdx_file.relative_to(output_dir).with_suffix(".md").as_posix()
        with open(mdx_file, encoding="utf-8") as f:
            markdown_text = convert_mdx_to_markdown_text(f.read())
        markdown_items.append((relative_path, markdown_text))
    return markdown_items


def write_llms_feeds(
    output_dir: Path,
    markdown_items: Sequence[tuple[str, str]] | None = None,
    base_url: str | None = None,
    package_name: str | None = None,
    version: str | None = None,
    language: str | None = None,
    is_python_module: bool = True,
    toctree: list | None = None,
) -> list[str]:
    """
    Generate llms.txt and llms-full.txt files alongside the documentation output.

    - llms.txt (https://llmstxt.org) lists the pages section by section of the table of contents
      (`toctree`, read from `output_dir/_toctree.yml` when not given), with their sidebar title and
      the first sentence of the page. Pages that aren't in the table of contents come last, under
      "Optional".
    - llms-full.txt is llms.txt followed by the text of every page, in the same order.
    - `llms-full/<section>.txt` has the text of the pages of one section, for a size in between.

    Returns the files written, relative to `output_dir`.
    """

    output_dir = Path(output_dir)
    if markdown_items is None:
        markdown_items = _collect_markdown_from_output(output_dir)
    else:
        markdown_items = [(str(path).replace(os.sep, "/"), text) for path, text in markdown_items]

    markdown_items = [item for item in markdown_items if item[0]]
    if not markdown_items:
        return []

    parts = list(output_dir.parts)
    if len(parts) >= 1 and language is None:
        language = parts[-1]
    if len(parts) >= 2 and version is None:
        version = parts[-2]
    if len(parts) >= 3 and package_name is None:
        package_name = parts[-3]

    base_host = "https://huggingface.co/docs"
    normalized_package = (package_name or "").strip()
    if normalized_package.endswith("course") or normalized_package == "cookbook":
        base_host = "https://huggingface.co/learn"

    def should_include_language(lang: str | None) -> bool:
        return bool(lang and lang.lower() != "en")

    def should_include_version(is_module: bool, ver: str | None) -> bool:
        return is_module and ver is not None

    if base_url is None and package_name:
        url_parts = [base_host, quote(package_name, safe="")]
        if should_include_version(is_python_module, version):
            url_parts.append(quote(version, safe=""))
        if should_include_language(language):
            url_parts.append(quote(language, safe=""))
        base_url = "/".join(url_parts)
    elif base_url is not None and base_url.startswith("https://") and package_name:
        normalized_base = base_url.rstrip("/")
        # Ensure host respects learn/docs rules when caller passes a minimal base_url
        if normalized_base.endswith(f"/docs/{package_name}") and (
            normalized_package.endswith("course") or normalized_package == "cookbook"
        ):
            base_url = normalized_base.replace("/docs/", "/learn/", 1)

    def build_url(relative_path: str) -> str:
        relative_path = relative_path.lstrip("/")
        if base_url:
            return f"{base_url.rstrip('/')}/{quote(relative_path, safe='/')}"
        return f"/{relative_path}"

    if toctree is None and (output_dir / "_toctree.yml").is_file():
        try:
            toctree = yaml.safe_load((output_dir / "_toctree.yml").read_text(encoding="utf-8"))
        except yaml.YAMLError:
            toctree = None

    # page (path without `.md`) -> (path, Markdown)
    pages: dict[str, tuple[str, str]] = {}
    for relative_path, markdown_text in markdown_items:
        pages.setdefault(relative_path.removesuffix(".md"), (relative_path, markdown_text.strip()))

    if toctree:
        sections = _toctree_sections(toctree, set(pages))
    else:
        sections = [(["Docs"], [(page, markdown_page_title(text) or page) for page, (_, text) in pages.items()])]
    listed = {page for _, entries in sections for page, _ in entries}
    titles = {title for _, entries in sections for _, title in entries}
    optional = []
    for page in sorted(set(pages) - listed):
        title = markdown_page_title(pages[page][1])
        if not title:
            name = Path(page).name.replace("-", " ").replace("_", " ")
            title = name[:1].upper() + name[1:]
        if title in titles:
            title = f"{title} ({page})"
        titles.add(title)
        optional.append((page, title))
    if optional:
        sections.append((["Optional"], optional))

    # sections grouped under their top-level heading: [(heading, [(subheadings, entries), ...]), ...]
    groups: list[tuple[str, list]] = []
    for trail, entries in sections:
        if not groups or groups[-1][0] != trail[0]:
            groups.append((trail[0], []))
        groups[-1][1].append((trail[1:], entries))

    def entry_line(page: str, title: str) -> str:
        relative_path, markdown_text = pages[page]
        line = f"- [{_link_text(title)}]({build_url(relative_path)})"
        description = markdown_page_description(markdown_text)
        return f"{line}: {description}" if description else line

    def index_lines(heading: str, subsections: list) -> list[str]:
        lines = [f"## {heading}", ""]
        for subheadings, entries in subsections:
            if subheadings:
                lines += [f"### {' / '.join(subheadings)}", ""]
            lines += [entry_line(page, title) for page, title in entries] + [""]
        return lines

    def full_text(subsections: list) -> list[str]:
        lines = []
        for _, entries in subsections:
            for page, title in entries:
                relative_path, markdown_text = pages[page]
                lines += [f"### {title}", build_url(relative_path), ""]
                lines += [markdown_text, ""] if markdown_text else []
        return lines

    def text_of(lines: list[str]) -> str:
        return "\n".join(lines).rstrip() + "\n"

    # the docs' own name ("LeRobot") rather than the package's ("Lerobot")
    header_title = markdown_page_title(pages["index"][1]) if "index" in pages else None
    header_title = header_title or (normalized_package.title() if normalized_package else "Documentation")
    header = [f"# {header_title}", ""]
    summary = markdown_page_description(pages["index"][1]) if "index" in pages else ""
    if summary:
        header += [f"> {summary}", ""]

    index = [line for heading, subsections in groups for line in index_lines(heading, subsections)]
    full = full_text([subsection for _, subsections in groups for subsection in subsections])

    # one file per section, for when llms-full.txt is too big
    sections_dir = output_dir / LLMS_SECTIONS_DIR
    if sections_dir.is_dir():
        shutil.rmtree(sections_dir)
    section_files, slugs = [], set()
    for i, (heading, subsections) in enumerate(groups, 1):
        base = _slug(heading) or f"section-{i}"
        slug, n = base, 2
        while slug in slugs:
            slug, n = f"{base}-{n}", n + 1
        slugs.add(slug)
        relative_path = f"{LLMS_SECTIONS_DIR}/{slug}.txt"
        text = text_of(
            [f"# {header_title}: {heading}", ""] + index_lines(heading, subsections) + full_text(subsections)
        )
        page_count = sum(len(entries) for _, entries in subsections)
        section_files.append((heading, relative_path, text, page_count))

    full_size = _size(len(text_of(header + index + full).encode("utf-8")))
    header += [
        "Each page below links to its Markdown. The text of every page is in "
        f"[llms-full.txt]({build_url('llms-full.txt')}) ({full_size}), and the text of each section in:",
        "",
    ]
    for heading, path, text, count in section_files:
        pages_count = f"{count} page{'s' if count > 1 else ''}"
        header.append(
            f"- [{_link_text(heading)}]({build_url(path)}): {pages_count}, {_size(len(text.encode('utf-8')))}"
        )
    header.append("")

    written = ["llms.txt", "llms-full.txt"]
    output_dir.joinpath("llms.txt").write_text(text_of(header + index), encoding="utf-8")
    output_dir.joinpath("llms-full.txt").write_text(text_of(header + index + full), encoding="utf-8")
    sections_dir.mkdir(parents=True, exist_ok=True)
    for _, relative_path, text, _ in section_files:
        output_dir.joinpath(relative_path).write_text(text, encoding="utf-8")
        written.append(relative_path)
    return written


def chunk_list(lst, n):
    """
    Create a list of chunks
    """
    return [lst[i : i + n] for i in range(0, len(lst), n)]


class HTMLStripper(HTMLParser):
    """Helper class to strip HTML tags while preserving text content."""

    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = []

    def handle_data(self, data):
        self.text.append(data)

    def get_data(self):
        return "".join(self.text)


def strip_html_tags(text: str) -> str:
    """Strip HTML tags from text while preserving content."""
    stripper = HTMLStripper()
    stripper.feed(text)
    return stripper.get_data()


def _extract_svelte_prop(props: str, prop_name: str):
    """
    Read the JSON value of a `name={<json>}` svelte attribute out of an opening-tag
    attribute string, or return `None` if the prop is absent or malformed.

    The JSON is parsed with `raw_decode` so values containing `}` or `>` (type
    annotations, defaults, ...) don't confuse the extraction.
    """
    match = re.search(rf"\b{prop_name}=\{{", props)
    if match is None:
        return None
    try:
        value, end = json.JSONDecoder().raw_decode(props, match.end())
    except ValueError:
        return None
    if not props[end:].lstrip().startswith("}"):
        return None
    return value


def _extract_section(block: str, tag: str):
    """Return the (stripped) content of `<tag>...</tag>` in `block`, or `None`."""
    match = re.search(rf"<{tag}>(.*?)</{tag}>", block, re.DOTALL)
    return match.group(1).strip() if match else None


def extract_docstring_info(docstring_block: str) -> dict:
    """
    Extract information from a `<Docstring ...>...</Docstring>` block.

    Metadata (name, anchor, source, signature) comes from the component props, the
    markdown-bearing sections (parameters, returns, ...) from the component body.
    See `doc_builder.autodoc.get_signature_component_svelte` for the emitted shape.
    """
    info = {
        "name": None,
        "anchor": None,
        "source": None,
        "parameters": None,
        "paramsdesc": None,
        "paramsgroups": [],
        "rettype": None,
        "retdesc": None,
        "yieldtype": None,
        "yielddesc": None,
        "raisederrors": None,
        "raises": None,
        "is_getset_descriptor": False,
    }

    open_tag = re.match(r"<Docstring\s(?P<props>[^\n]*)>", docstring_block)
    props = open_tag.group("props") if open_tag else ""

    name = _extract_svelte_prop(props, "name")
    if name:
        # Remove "class " or "def " prefix if present
        info["name"] = re.sub(r"^(class|def)\s+", "", name.strip())

    anchor = _extract_svelte_prop(props, "anchor")
    # `anchor` is stringified python-side, so a missing anchor arrives as `"None"`.
    if anchor and anchor != "None":
        info["anchor"] = anchor.strip()

    source = _extract_svelte_prop(props, "source")
    if source:
        info["source"] = source.strip()

    parameters = _extract_svelte_prop(props, "parameters")
    if isinstance(parameters, list):
        info["parameters"] = parameters

    info["is_getset_descriptor"] = bool(_extract_svelte_prop(props, "isGetSetDescriptor"))

    for key, tag in (
        ("paramsdesc", "paramsdesc"),
        ("rettype", "rettype"),
        ("retdesc", "retdesc"),
        ("yieldtype", "yieldtype"),
        ("yielddesc", "yielddesc"),
        ("raisederrors", "raisederrors"),
        ("raises", "raises"),
    ):
        info[key] = _extract_section(docstring_block, tag)

    # Extra parameter groups, e.g. transformers' "Parameters for sequence generation".
    for group in re.findall(r"<paramsgroup>(.*?)</paramsgroup>", docstring_block, re.DOTALL):
        info["paramsgroups"].append(
            {
                "title": _extract_section(group, "paramsgrouptitle"),
                "desc": _extract_section(group, "paramsgroupdesc"),
            }
        )

    return info


def format_parameters(paramsdesc: str) -> str:
    """
    Format parameter descriptions by:
    - Removing bullets (-)
    - Removing bold formatting (**)
    - Changing -- to :
    - Adding blank lines between parameters
    """
    lines = paramsdesc.split("\n")
    formatted_params = []
    current_param = []

    for line in lines:
        # Check if this is a new parameter line (starts with "- **")
        if re.match(r"^\s*-\s+\*\*", line):
            # Save the previous parameter if exists
            if current_param:
                param_text = " ".join(current_param)
                # Remove - and ** formatting
                param_text = re.sub(r"^\s*-\s+\*\*([^*]+)\*\*", r"\1", param_text)
                # Change -- to :
                param_text = re.sub(r"\s+--\s+", " : ", param_text, count=1)
                formatted_params.append(param_text)
                formatted_params.append("")  # Add blank line between parameters
                current_param = []

            # Start new parameter
            current_param.append(line)
        elif current_param:
            # Continuation of current parameter description
            current_param.append(line.strip())

    # Don't forget the last parameter
    if current_param:
        param_text = " ".join(current_param)
        param_text = re.sub(r"^\s*-\s+\*\*([^*]+)\*\*", r"\1", param_text)
        param_text = re.sub(r"\s+--\s+", " : ", param_text, count=1)
        formatted_params.append(param_text)

    return "\n".join(formatted_params)


def format_call_signature(name: str, parameters) -> str:
    """
    Render the `parameters` prop (a list of `{"name": ..., "val": ...}`) as a call
    signature, e.g. ``HfApi.merge_pull_request(discussion_num: int, token = None)``.
    """
    args = ", ".join(f"{param.get('name', '')}{param.get('val', '')}".strip() for param in parameters)
    return f"{name}({args})"


def format_type(value: str) -> str:
    """
    Wrap a return/yield/raise type in backticks, unless it already carries markup
    (a resolved `[Name](url)` doc link, inline code, ...) that backticks would break.
    """
    return value if re.search(r"[`\[\]<>]", value) else f"`{value}`"


def process_docstring_block(docstring_block: str) -> str:
    """
    Process a docstring block by:
    1. Extracting the class/function name and relevant info
    2. Stripping all HTML tags
    3. Converting to clean markdown with level 4 header
    """
    # Extract structured information from the docstring
    info = extract_docstring_info(docstring_block)

    # Build the cleaned markdown
    parts = []

    # Add the name as level 4 header with anchor
    if info["name"]:
        if info["anchor"]:
            parts.append(f"#### {info['name']}[[{info['anchor']}]]")
        else:
            parts.append(f"#### {info['name']}")
        parts.append("")

        # Add the call signature (properties are not callable, so they have none)
        if info["parameters"] is not None and not info["is_getset_descriptor"]:
            parts.append("```python")
            parts.append(format_call_signature(info["name"], info["parameters"]))
            parts.append("```")
            parts.append("")

    # Add source link if available
    if info["source"]:
        # Strip any HTML from source
        source_clean = strip_html_tags(info["source"])
        parts.append(f"[Source]({source_clean})")
        parts.append("")

    # Add parameters description
    if info["paramsdesc"]:
        parts.append("**Parameters:**")
        parts.append("")
        # Format parameters: remove bullets and bold, change -- to :, add blank lines
        formatted_params = format_parameters(info["paramsdesc"])
        parts.append(formatted_params)
        parts.append("")

    # Add the extra parameter groups, if any
    for group in info["paramsgroups"]:
        if not group["desc"]:
            continue
        parts.append(f"**{group['title'] or 'Parameters'}:**")
        parts.append("")
        parts.append(format_parameters(group["desc"]))
        parts.append("")

    # Add the returns / yields / raises sections
    for type_key, desc_key, label in (
        ("rettype", "retdesc", "Returns"),
        ("yieldtype", "yielddesc", "Yields"),
        ("raisederrors", "raises", "Raises"),
    ):
        if not info[type_key] and not info[desc_key]:
            continue
        header = f"**{label}:**"
        if info[type_key]:
            header += f" {format_type(info[type_key])}"
        parts.append(header)
        parts.append("")
        if info[desc_key]:
            parts.append(info[desc_key])
            parts.append("")

    result = "\n".join(parts)

    # Clean up excessive newlines
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result.strip()


def strip_remaining_html(content: str) -> str:
    """
    Convert the HTML left in a page to Markdown: raw HTML blocks (cards, tables, ...) keep their
    links, images and structure, tabs keep their labels, and component tags (`<Tip>`, ...) go.

    Fenced code blocks and inline code are preserved verbatim so literal
    angle-bracketed content (e.g. ``<YOUR_TOKEN>`` placeholders, or code
    such as ``if idx < n:``) survives the cleanup.
    """
    return html_to_markdown(content)


def strip_html_from_markdown(content: str) -> str:
    """
    Strip HTML from markdown content.

    Handles:
    - `<Docstring ...>...</Docstring>` components emitted by autodoc, which become a
      level-4 heading with the signature, then the `**Parameters:**`/`**Returns:**`
      sections. The object description follows the component in the source, so it
      keeps its place right after those (same order as the rendered HTML page).
    - Other HTML tags throughout the document
    """
    result = content

    # The opening tag's attribute values are single-line JSON (see
    # `get_signature_component_svelte`), so it ends at the last `>` on its own line.
    docstring_pattern = r"<Docstring\s[^\n]*>\n.*?</Docstring>"

    def replace_docstring(match):
        block = match.group(0)
        # Trailing newline: the object description directly follows the component (with a
        # single newline in between), and must not end up glued to the last section.
        return process_docstring_block(block) + "\n"

    result = re.sub(docstring_pattern, replace_docstring, result, flags=re.DOTALL)

    # Strip remaining HTML tags (like <Tip>, </Tip>, <ExampleCodeBlock>, etc.)
    # But preserve markdown code blocks
    result = strip_remaining_html(result)

    return result
