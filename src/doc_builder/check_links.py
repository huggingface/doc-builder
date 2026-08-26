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

"""
Fast link checker for documentation files.

This module checks internal links in markdown/mdx files to ensure they point
to valid files and anchors. It handles links without extensions (e.g., `./fp16`
instead of `./fp16.md`) and checks fragment anchors against headings and IDs.
"""

import importlib
import importlib.util
import os
import re
from bisect import bisect_right
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from functools import lru_cache
from html import unescape
from importlib.metadata import packages_distributions
from pathlib import Path
from urllib.parse import unquote

try:
    from tqdm import tqdm

    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

_re_heading = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$")
_re_setext_heading = re.compile(r"^\s{0,3}(?:=+|-+)\s*$")
_re_custom_anchor = re.compile(r"\[\[([^\]]+)\]\]\s*$")
_re_fence = re.compile(r"^(`{3,}|~{3,})([^\n]*)")
_re_autodoc = re.compile(r"^\s*\[\[autodoc\]\]\s+(\S+)\s*$")
_STATIC_ATTRIBUTE_VALUE = r"""(?:"([^"]*)"|'([^']*)'|\{\s*"([^"]*)"\s*\}|\{\s*'([^']*)'\s*\}|([^\s"'=<>`{}]+))"""
_re_html_id = re.compile(rf"""(?<![\w:-])id\s*=\s*{_STATIC_ATTRIBUTE_VALUE}""", re.IGNORECASE)
_re_html_name = re.compile(rf"""(?<![\w:-])name\s*=\s*{_STATIC_ATTRIBUTE_VALUE}""", re.IGNORECASE)
_re_quoted_title = re.compile(r"""^(?:"(?:\\.|[^"])*"|'(?:\\.|[^'])*')$""")
_re_uri_scheme = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)
_re_heading_reference = re.compile(r"(!?)\[([^\]]*)\]\s*\[[^\]]*\]")
_re_heading_brackets = re.compile(r"\[([^\[\]]+)]")
_re_code_span = re.compile(r"(`+)(.*?)\1")
_re_heading_emphasis = re.compile(r"(?<!\\)(\*{1,3}|_{2,3}|~~)(.+?)(?<!\\)\1")
_re_heading_html = re.compile(r"(</?[A-Za-z][^<>]*>)")
_re_heading_html_comment = re.compile(r"<!--.*?-->", re.DOTALL)
_re_entity = re.compile(r"&(?:#[0-9]+|#[xX][0-9A-Fa-f]+|[A-Za-z][A-Za-z0-9]+);")
_re_list_item = re.compile(r"^(?:[-+*]|\d+[.)])\s+")
_re_interrupting_list_item = re.compile(r"^(?:[-+*]|1[.)])\s+")
_re_katex_marker = re.compile(r"katexparse[0-9]+marker")
_re_katex_display = re.compile(r"\n\$\$([\s\S]+?)\$\$")
_re_katex_inline = re.compile(r"\s\\\\\(([\s\S]+?)\\\\\)")
_re_katex_inline_dollar = re.compile(r"(\s)(\$)([^$\n`<>]+?)(\$)(\s)")
_re_blank_line = re.compile(r"\r?\n[ \t]*\r?\n")
_re_thematic_break = re.compile(r"^ {0,3}(?:(?:\*[ \t]*){3,}|(?:_[ \t]*){3,}|(?:-[ \t]*){3,})$")

# Native elements preserve an ``id`` attribute in the rendered DOM. MDX
# components do not necessarily do so (for example, ``<Youtube id=...>`` uses
# ``id`` as a video key), so only standard HTML tags are considered here.
_HTML_TAGS = frozenset(
    """
    a abbr address area article aside audio b base bdi bdo blockquote body br button canvas caption cite code col
    colgroup data datalist dd del details dfn dialog div dl dt em embed fieldset figcaption figure footer form h1 h2
    h3 h4 h5 h6 head header hgroup hr html i iframe img input ins kbd label legend li link main map mark
    math menu menuitem meta meter nav noscript object ol optgroup option output p param picture pre progress q rb rp rt
    rtc ruby s samp script search section select slot small source span strong style sub summary sup svg table tbody td
    template textarea tfoot th thead time title tr track u ul var video wbr
    """.split()
)

# Descendants of a native ``svg`` element are preserved by mdsvex even though
# they are not part of the ``html-tags`` package used for top-level elements.
_SVG_TAGS = frozenset(
    """
    animate animateMotion animateTransform circle clipPath defs desc ellipse feBlend feColorMatrix feComponentTransfer
    feComposite feConvolveMatrix feDiffuseLighting feDisplacementMap feDistantLight feDropShadow feFlood feFuncA feFuncB
    feFuncG feFuncR feGaussianBlur feImage feMerge feMergeNode feMorphology feOffset fePointLight feSpecularLighting
    feSpotLight feTile feTurbulence filter foreignObject g image line linearGradient marker mask metadata mpath path pattern
    polygon polyline radialGradient rect set stop switch symbol text textPath title tspan use view
    """.split()
)

_MATHML_TAGS = frozenset(
    """
    annotation annotation-xml maction maligngroup malignmark menclose merror mfenced mfrac mglyph mi mlabeledtr
    mlongdiv mmultiscripts mn mo mover mpadded mphantom mroot mrow ms mscarries mscarry msgroup msline mspace msqrt
    msrow mstack mstyle msub msubsup msup mtable mtd mtext mtr munder munderover semantics
    """.split()
)
_SVG_TAGS_LOWER = frozenset(tag.lower() for tag in _SVG_TAGS)
_MATHML_TAGS_LOWER = frozenset(tag.lower() for tag in _MATHML_TAGS)

# CommonMark block tags whose contents remain raw HTML until the next blank
# line. Links in those blocks are not parsed as Markdown by mdsvex.
_HTML_BLOCK_TAGS = frozenset(
    """
    address article aside base basefont blockquote body caption center col colgroup dd details dialog dir div dl dt
    fieldset figcaption figure footer form frame frameset h1 h2 h3 h4 h5 h6 head header hgroup hr html iframe legend
    li link main menu menuitem nav noframes ol optgroup option p param search section summary table tbody td tfoot th
    thead title tr track ul
    """.split()
)
# This must match the mdsvex block tokenizer bundled by doc-builder. Unlike
# modern CommonMark, that tokenizer treats ``textarea`` as a blank-ended HTML
# block rather than a raw-text block.
_HTML_RAW_TEXT_TAGS = frozenset({"pre", "script", "style"})
_HTML_ANCHOR_OPAQUE_TAGS = frozenset({"iframe", "script", "style", "textarea", "title"})
_HTML_REMOVED_TAGS = frozenset({"noscript", "template"})


@dataclass(frozen=True)
class _Fence:
    character: str
    length: int
    blockquote_depth: int
    container_indent: int


@dataclass(frozen=True)
class _MarkdownLink:
    start: int
    end: int
    destination_start: int
    label: str
    destination: str
    is_image: bool


@dataclass(frozen=True)
class _HtmlBlock:
    raw_text_tag: str | None = None
    end_marker: str | None = None
    blockquote_depth: int = 0
    list_indent: int = 0


@dataclass(frozen=True)
class _HtmlTag:
    start: int
    end: int
    closing: bool
    name: str
    attributes_start: int
    attributes_end: int
    attributes: str


@dataclass(frozen=True)
class _HtmlNodeRange:
    start: int
    end: int
    serialized: bool
    is_comment: bool = False
    blockquote_depth: int = 0
    list_indent: int = 0


@dataclass(frozen=True)
class _AnchorIndex:
    exact: frozenset[str]
    autodoc_objects: frozenset[str]
    uncertain_math: frozenset[str]


_RESOLVED_AUTODOC_ANCHORS: dict[str, str | None] = {}


class LinkCheckResult:
    """Container for link check results."""

    def __init__(self):
        self.broken_links: list[tuple[Path, str, str, int]] = []  # (file, link_text, link_url, line_number)
        self.files_checked: int = 0
        self.links_checked: int = 0

    def add_broken_link(self, file_path: Path, link_text: str, link_url: str, line_number: int):
        """Add a broken link to the results."""
        self.broken_links.append((file_path, link_text, link_url, line_number))

    def has_broken_links(self) -> bool:
        """Check if any broken links were found."""
        return len(self.broken_links) > 0

    def get_summary(self) -> str:
        """Get a summary of the check results."""
        if not self.has_broken_links():
            return f"✓ All links valid! Checked {self.links_checked} links in {self.files_checked} files."

        summary = f"✗ Found {len(self.broken_links)} broken link(s) in {self.files_checked} files:\n\n"
        for file_path, link_text, link_url, line_number in self.broken_links:
            summary += f"  {file_path}:{line_number}\n"
            summary += f"    Link text: [{link_text}]\n"
            summary += f"    Link URL: {link_url}\n\n"
        return summary

    def get_list_output(self) -> str:
        """Get a compact list of broken links (file:line - URL format)."""
        if not self.has_broken_links():
            return f"✓ All links valid! Checked {self.links_checked} links in {self.files_checked} files."

        output = f"✗ Found {len(self.broken_links)} broken link(s) in {self.files_checked} files:\n\n"
        for file_path, _, link_url, line_number in self.broken_links:
            output += f"{file_path}:{line_number} - {link_url}\n"
        return output


def _parse_link_destination(link_url: str) -> str | None:
    """Parse a Markdown destination, excluding its optional quoted title."""
    link_url = link_url.strip()
    if link_url.startswith("<"):
        cursor = 1
        while cursor < len(link_url):
            if link_url[cursor] == "\\" and cursor + 1 < len(link_url):
                cursor += 2
                continue
            if link_url[cursor] == "<":
                return None
            if link_url[cursor] == ">":
                break
            cursor += 1
        if cursor == len(link_url):
            return None
        destination = link_url[1:cursor]
        remainder = link_url[cursor + 1 :].strip()
    else:
        cursor = 0
        parenthesis_depth = 0
        while cursor < len(link_url):
            character = link_url[cursor]
            if character == "\\" and cursor + 1 < len(link_url):
                cursor += 2
                continue
            if character.isspace():
                break
            if character in "<>":
                return None
            if character == "(":
                parenthesis_depth += 1
            elif character == ")":
                parenthesis_depth -= 1
                if parenthesis_depth < 0:
                    return None
            cursor += 1
        if parenthesis_depth:
            return None
        destination = link_url[:cursor]
        remainder = link_url[cursor:].strip()

    if remainder and _re_quoted_title.fullmatch(remainder) is None:
        return None

    destination = unescape(destination)
    return re.sub(r"\\([!\"#$%&'()*+,./:;<=>?@\[\]^_`{|}~-])", r"\1", destination)


def _link_destination(link_url: str) -> str:
    """Return a normalized destination, falling back to the stripped input."""
    destination = _parse_link_destination(link_url)
    return link_url.strip() if destination is None else destination


def is_external_link(url: str) -> bool:
    """
    Check if a URL is external (http/https/mailto/etc).

    Args:
        url: The URL to check

    Returns:
        True if the URL is external, False otherwise
    """
    url = _link_destination(url).lower()

    return url.startswith("//") or _re_uri_scheme.match(url) is not None


def is_anchor_only(url: str) -> bool:
    """
    Check if a URL is just an anchor link (starts with #).

    Args:
        url: The URL to check

    Returns:
        True if the URL is just an anchor, False otherwise
    """
    return _link_destination(url).startswith("#")


def split_link_url(link_url: str) -> tuple[str, str | None]:
    """Split a local link into its path/query portion and fragment anchor."""
    link_url = _link_destination(link_url)
    path_url, separator, anchor = link_url.partition("#")
    path_url = unquote(path_url.split("?", 1)[0])
    return path_url, unquote(anchor) if separator else None


def resolve_link_path(source_file: Path, link_url: str) -> Path | None:
    """
    Resolve a relative link URL to an absolute path.

    Args:
        source_file: The file containing the link
        link_url: The link URL to resolve

    Returns:
        The resolved path, or None if the link is external or has no local path
    """
    # Strip query parameters and fragments from URL
    # For example: "./file.md?query=value#section" -> "./file.md"
    link_url, anchor = split_link_url(link_url)

    # An empty path with a fragment points back to the source file. This also
    # covers angle-bracket and query forms such as ``<#intro>`` and
    # ``?view=full#intro``.
    if not link_url:
        return source_file if anchor is not None else None

    # Skip external links
    if is_external_link(link_url):
        return None

    # Root-relative URLs point at the published site rather than the source tree.
    if link_url.startswith("/"):
        return None

    # Resolve relative path
    source_dir = source_file.parent
    link_path = (source_dir / link_url).resolve()

    return link_path


def _is_escaped(text: str, index: int) -> bool:
    prefix = text[:index]
    backslash_count = len(prefix) - len(prefix.rstrip("\\"))
    return backslash_count % 2 == 1


def _inline_code_ranges(line: str, block_boundaries: set[int] | None = None) -> list[tuple[int, int]]:
    """Return character ranges enclosed by matching, unescaped backtick runs."""
    block_boundaries = block_boundaries or set()
    runs = [match for match in re.finditer(r"`+", line) if not _is_escaped(line, match.start())]
    ranges = []
    run_index = 0
    while run_index < len(runs):
        opening = runs[run_index]
        closing_index = next(
            (
                index
                for index in range(run_index + 1, len(runs))
                if runs[index].group() == opening.group()
                and not any(opening.start() < boundary < runs[index].end() for boundary in block_boundaries)
            ),
            None,
        )
        if closing_index is None:
            run_index += 1
            continue
        ranges.append((opening.start(), runs[closing_index].end()))
        run_index = closing_index + 1
    return ranges


def _iter_markdown_links(
    line: str,
    inline_code_ranges: list[tuple[int, int]],
    block_boundaries: set[int] | None = None,
) -> list[_MarkdownLink]:
    """Return inline Markdown links, balancing brackets and parentheses."""
    links = []
    cursor = 0
    block_boundaries = block_boundaries or set()

    while cursor < len(line):
        label_start = line.find("[", cursor)
        if label_start == -1:
            break
        if _is_escaped(line, label_start) or any(start <= label_start < end for start, end in inline_code_ranges):
            cursor = label_start + 1
            continue

        label_cursor = label_start + 1
        bracket_depth = 1
        while label_cursor < len(line) and bracket_depth:
            if line[label_cursor] == "\\" and label_cursor + 1 < len(line):
                label_cursor += 2
                continue
            if line[label_cursor] == "[":
                bracket_depth += 1
            elif line[label_cursor] == "]":
                bracket_depth -= 1
            label_cursor += 1

        if bracket_depth or label_cursor >= len(line) or line[label_cursor] != "(":
            cursor = label_start + 1
            continue

        destination_start = label_cursor + 1
        destination_cursor = destination_start
        parenthesis_depth = 1
        in_angle_destination = False
        title_quote = None
        title_may_start = False
        while destination_cursor < len(line) and parenthesis_depth:
            character = line[destination_cursor]
            if character == "\\" and destination_cursor + 1 < len(line):
                destination_cursor += 2
                continue
            if title_quote is not None:
                if character == title_quote:
                    title_quote = None
                destination_cursor += 1
                continue
            if in_angle_destination:
                if character == ">":
                    in_angle_destination = False
                destination_cursor += 1
                continue
            if destination_cursor == destination_start and character == "<":
                in_angle_destination = True
            elif title_may_start and character in "\"'":
                title_quote = character
                title_may_start = False
            elif character.isspace() and parenthesis_depth == 1:
                title_may_start = True
            elif character == "(":
                parenthesis_depth += 1
                title_may_start = False
            elif character == ")":
                parenthesis_depth -= 1
                if parenthesis_depth == 0:
                    break
                title_may_start = False
            else:
                title_may_start = False
            destination_cursor += 1

        if parenthesis_depth:
            cursor = label_start + 1
            continue

        if any(label_start < boundary < destination_cursor + 1 for boundary in block_boundaries):
            cursor = label_start + 1
            continue

        label = line[label_start + 1 : label_cursor - 1]
        destination = line[destination_start:destination_cursor]
        if _re_blank_line.search(label) or _re_blank_line.search(destination):
            cursor = label_start + 1
            continue
        is_image = label_start > 0 and line[label_start - 1] == "!" and not _is_escaped(line, label_start - 1)
        # Images may be nested inside a link, as in a clickable badge. Both
        # destinations are independently rendered and need validation.
        for nested_link in _iter_markdown_links(label, _inline_code_ranges(label)):
            if nested_link.is_image:
                links.append(
                    _MarkdownLink(
                        start=label_start + 1 + nested_link.start,
                        end=label_start + 1 + nested_link.end,
                        destination_start=label_start + 1 + nested_link.destination_start,
                        label=nested_link.label,
                        destination=nested_link.destination,
                        is_image=True,
                    )
                )
        links.append(
            _MarkdownLink(
                start=label_start,
                end=destination_cursor + 1,
                destination_start=destination_start,
                label=label,
                destination=destination,
                is_image=is_image,
            )
        )
        cursor = destination_cursor + 1

    return links


def _without_inline_code(line: str) -> str:
    """Replace inline code spans with spaces so their contents are not parsed."""
    characters = list(line)
    for start, end in _inline_code_ranges(line):
        characters[start:end] = " " * (end - start)
    return "".join(characters)


def _iter_html_tags(source: str) -> list[_HtmlTag]:
    """Parse HTML-like tags while respecting quoted ``<`` and ``>`` values."""
    tags = []
    cursor = 0
    while cursor < len(source):
        tag_start = source.find("<", cursor)
        if tag_start == -1:
            break
        name_start = tag_start + 1
        closing = name_start < len(source) and source[name_start] == "/"
        if closing:
            name_start += 1
        name_match = re.match(r"[A-Za-z][A-Za-z0-9-]*", source[name_start:])
        if name_match is None:
            cursor = tag_start + 1
            continue
        name_end = name_start + name_match.end()
        if name_end < len(source) and not (source[name_end].isspace() or source[name_end] in "/>"):
            cursor = tag_start + 1
            continue

        quote = None
        tag_end = name_end
        while tag_end < len(source):
            character = source[tag_end]
            if quote is not None:
                if character == "\\" and tag_end + 1 < len(source):
                    tag_end += 2
                    continue
                if character == quote:
                    quote = None
            elif character in "\"'":
                quote = character
            elif character == ">":
                break
            tag_end += 1
        if tag_end == len(source):
            cursor = tag_start + 1
            continue

        tags.append(
            _HtmlTag(
                start=tag_start,
                end=tag_end + 1,
                closing=closing,
                name=source[name_start:name_end],
                attributes_start=name_end,
                attributes_end=tag_end,
                attributes=source[name_end:tag_end],
            )
        )
        cursor = tag_end + 1
    return tags


def _without_html_attributes(
    source: str,
    protected_ranges: list[tuple[int, int]] | None = None,
) -> str:
    """Mask tag attributes so Markdown-looking attribute values stay literal."""
    protected_ranges = protected_ranges or []
    characters = list(source)
    for tag in _iter_html_tags(source):
        if any(start <= tag.start < end for start, end in protected_ranges):
            continue
        for index in range(tag.attributes_start, tag.attributes_end):
            if characters[index] not in "\r\n":
                characters[index] = " "
    return "".join(characters)


def _without_blockquote_markers(source: str) -> str:
    """Mask blockquote container prefixes while retaining source offsets."""
    characters = list(source)
    offset = 0
    for line in source.splitlines(keepends=True):
        cursor = 0
        while True:
            match = re.match(r"^ {0,3}>[ \t]?", line[cursor:])
            if match is None:
                break
            for index in range(offset + cursor, offset + cursor + match.end()):
                if characters[index] not in "\r\n":
                    characters[index] = " "
            cursor += match.end()
        offset += len(line)
    return "".join(characters)


def _markdown_block_boundaries(source: str) -> set[int]:
    """Return line starts that cannot continue the preceding inline block."""
    boundaries = set()
    active_blockquote_depth = 0
    active_list_indent = 0
    list_blank_pending = False
    previous_block_closed = True
    offset = 0
    for line_number, line in enumerate(source.splitlines(keepends=True)):
        container_line, blockquote_depth = _strip_blockquote_prefix(line)
        stripped = container_line.strip()
        list_match = re.match(r"^( *)(?:[-+*]|\d+[.)])(?:[ \t]+|(?=\r?\n?$))", container_line)
        _, direct_list_indent = _strip_list_marker(container_line)
        interrupts_paragraph = _re_interrupting_list_item.match(container_line.lstrip(" ")) is not None
        interrupts_active_list = bool(
            active_list_indent and list_match is not None and len(list_match.group(1)) < active_list_indent
        )
        blockquote_increase = blockquote_depth > active_blockquote_depth
        if line_number and (
            not stripped
            or blockquote_increase
            or interrupts_paragraph
            or interrupts_active_list
            or _re_fence.match(container_line.lstrip(" "))
            or _re_heading.match(container_line)
            or _re_setext_heading.match(container_line)
            or _re_thematic_break.match(container_line.rstrip("\r\n"))
        ):
            boundaries.add(offset)

        if direct_list_indent and (
            interrupts_paragraph or interrupts_active_list or active_list_indent or previous_block_closed
        ):
            active_list_indent = direct_list_indent
            list_blank_pending = False
        elif not stripped:
            list_blank_pending = bool(active_list_indent)
        elif list_blank_pending:
            leading_indent = len(container_line) - len(container_line.lstrip(" "))
            if leading_indent < active_list_indent:
                active_list_indent = 0
            list_blank_pending = False
        elif active_list_indent:
            leading_indent = len(container_line) - len(container_line.lstrip(" "))
            if leading_indent < active_list_indent and (
                _re_fence.match(container_line.lstrip(" "))
                or _re_heading.match(container_line)
                or _re_setext_heading.match(container_line)
                or _re_thematic_break.match(container_line.rstrip("\r\n"))
            ):
                active_list_indent = 0
        if not stripped:
            active_blockquote_depth = 0
        elif blockquote_increase:
            active_blockquote_depth = blockquote_depth
        previous_block_closed = bool(
            not stripped
            or _re_fence.match(container_line.lstrip(" "))
            or _re_heading.match(container_line)
            or _re_setext_heading.match(container_line)
            or _re_thematic_break.match(container_line.rstrip("\r\n"))
        )
        offset += len(line)
    return boundaries


def _without_html_comments(
    line: str,
    in_comment: bool,
    *,
    protected_ranges: list[tuple[int, int]] | None = None,
    line_offset: int = 0,
) -> tuple[str, bool]:
    """Mask HTML comments while preserving line length and comment state."""
    if protected_ranges is None:
        protected_ranges = _inline_code_ranges(line)
    characters = list(line)
    cursor = 0
    while cursor < len(line):
        if in_comment:
            comment_end = line.find("-->", cursor)
            end = len(line) if comment_end == -1 else comment_end + 3
            for index in range(cursor, end):
                if characters[index] not in "\r\n":
                    characters[index] = " "
            if comment_end == -1:
                return "".join(characters), True
            in_comment = False
            cursor = end
            continue

        while True:
            comment_start = line.find("<!--", cursor)
            if comment_start == -1:
                return "".join(characters), False
            absolute_start = line_offset + comment_start
            if not any(start <= absolute_start < end for start, end in protected_ranges):
                break
            cursor = comment_start + 4
        in_comment = True
        cursor = comment_start

    return "".join(characters), in_comment


def _strip_blockquote_prefix(line: str) -> tuple[str, int]:
    """Remove Markdown blockquote container markers from one line."""
    depth = 0
    while True:
        match = re.match(r"^ {0,3}>[ \t]?", line)
        if match is None:
            return line, depth
        line = line[match.end() :]
        depth += 1


def _strip_list_marker(line: str) -> tuple[str, int]:
    """Remove nested Markdown list markers and return their content indentation."""
    total_indent = 0
    while True:
        match = re.match(r"^ {0,3}(?:[-+*]|\d+[.)])[ \t]+", line)
        if match is None:
            empty_match = re.match(r"^ {0,3}(?:[-+*]|\d+[.)])(?=\r?\n?$)", line)
            if empty_match is None:
                return line, total_indent
            return line[empty_match.end() :], total_indent + empty_match.end() + 1
        line = line[match.end() :]
        total_indent += match.end()


def _list_marker_indents(line: str) -> list[int]:
    """Return cumulative content columns for nested list markers on a line."""
    indents = []
    total_indent = 0
    while True:
        match = re.match(r"^ {0,3}(?:[-+*]|\d+[.)])[ \t]+", line)
        if match is not None:
            total_indent += match.end()
            indents.append(total_indent)
            line = line[match.end() :]
            continue
        empty_match = re.match(r"^ {0,3}(?:[-+*]|\d+[.)])(?=\r?\n?$)", line)
        if empty_match is not None:
            indents.append(total_indent + empty_match.end() + 1)
        return indents


def _fence_context(line: str) -> tuple[str, int, int, int]:
    line, blockquote_depth = _strip_blockquote_prefix(line)
    line_indent = len(line) - len(line.lstrip(" "))
    fence_line, list_indent = _strip_list_marker(line)
    if list_indent:
        nested_indent = len(fence_line) - len(fence_line.lstrip(" "))
        return fence_line[nested_indent:], blockquote_depth, line_indent, list_indent + nested_indent
    if line_indent >= 4:
        return line[line_indent:], blockquote_depth, line_indent, line_indent
    return line[line_indent:], blockquote_depth, line_indent, 0


def _advance_fence(line: str, fence: _Fence | None) -> tuple[bool, _Fence | None]:
    """Update fenced-code state, including list and blockquote containers."""
    container_line, blockquote_depth = _strip_blockquote_prefix(line)
    line_indent = len(container_line) - len(container_line.lstrip(" "))
    if fence is not None:
        container_ended = blockquote_depth < fence.blockquote_depth or (
            fence.container_indent and line.strip() and line_indent < fence.container_indent
        )
        if container_ended:
            if blockquote_depth < fence.blockquote_depth:
                # A fence can close on a lazily continued, unquoted line.
                closing_match = _re_fence.match(container_line[line_indent:])
                if closing_match:
                    marker, remainder = closing_match.groups()
                    if (
                        line_indent <= 3
                        and marker[0] == fence.character
                        and len(marker) >= fence.length
                        and not remainder.strip()
                    ):
                        return True, None
            # A list dedent ends the contained fence first. A bare marker on
            # that line is then a new top-level opening fence.
            fence = None
        elif blockquote_depth == fence.blockquote_depth:
            closing_line = container_line[fence.container_indent :]
            closing_indent = len(closing_line) - len(closing_line.lstrip(" "))
            closing_match = _re_fence.match(closing_line[closing_indent:])
            if closing_match:
                marker, remainder = closing_match.groups()
                if (
                    closing_indent <= 3
                    and marker[0] == fence.character
                    and len(marker) >= fence.length
                    and not remainder.strip()
                ):
                    return True, None
        if fence is not None:
            return False, fence

    fence_line, blockquote_depth, _, opening_container_indent = _fence_context(line)
    match = _re_fence.match(fence_line)
    if match is None:
        return False, None

    marker, info = match.groups()
    # A backtick may not occur in the info string of a backtick fence.
    if marker[0] == "`" and "`" in info:
        return False, None
    return True, _Fence(marker[0], len(marker), blockquote_depth, opening_container_indent)


def _advance_html_block(line: str, block: _HtmlBlock | None) -> tuple[bool, _HtmlBlock | None]:
    """Update the raw HTML block state used by doc-builder's mdsvex parser."""
    container_line, blockquote_depth = _strip_blockquote_prefix(line)
    container_line, list_indent = _strip_list_marker(container_line)

    if block is not None:
        sibling_match = re.match(r"^( *)(?:[-+*]|\d+[.)])\s+", _strip_blockquote_prefix(line)[0])
        if block.list_indent and sibling_match and len(sibling_match.group(1)) < block.list_indent:
            return False, None
        if block.raw_text_tag is not None:
            if re.search(rf"</{re.escape(block.raw_text_tag)}\s*>", container_line, re.IGNORECASE):
                return True, None
            return True, block
        if block.end_marker is not None:
            return (True, None) if block.end_marker in container_line else (True, block)
        if not container_line.strip():
            return True, None
        return True, block

    start = container_line.lstrip(" ")

    raw_text_match = re.match(r"<([A-Za-z]+)(?=\s|>|$)", start)
    if raw_text_match and raw_text_match.group(1).lower() in _HTML_RAW_TEXT_TAGS:
        tag_name = raw_text_match.group(1).lower()
        if re.search(rf"</{tag_name}\s*>", start[raw_text_match.end() :], re.IGNORECASE):
            return True, None
        return True, _HtmlBlock(
            raw_text_tag=tag_name,
            blockquote_depth=blockquote_depth,
            list_indent=list_indent,
        )

    if start.startswith("<!--"):
        return (
            (True, None)
            if "-->" in start[4:]
            else (
                True,
                _HtmlBlock(
                    end_marker="-->",
                    blockquote_depth=blockquote_depth,
                    list_indent=list_indent,
                ),
            )
        )

    for opening, closing in (("<![CDATA[", "]]>"), ("<?", "?>")):
        if start.startswith(opening):
            return (
                (True, None)
                if closing in start[len(opening) :]
                else (
                    True,
                    _HtmlBlock(
                        end_marker=closing,
                        blockquote_depth=blockquote_depth,
                        list_indent=list_indent,
                    ),
                )
            )

    if re.match(r"<![A-Z]", start):
        return (
            (True, None)
            if ">" in start[2:]
            else (
                True,
                _HtmlBlock(
                    end_marker=">",
                    blockquote_depth=blockquote_depth,
                    list_indent=list_indent,
                ),
            )
        )

    block_match = re.match(r"</?([A-Za-z.]*[A-Za-z][A-Za-z0-9.]*)(?=\s|/?>|$)", start)
    if block_match:
        return True, _HtmlBlock(
            blockquote_depth=blockquote_depth,
            list_indent=list_indent,
        )

    # CommonMark type 7: a complete tag on its own line starts a raw HTML
    # block (including Svelte/MDX component names) until the next blank line.
    if re.fullmatch(r"</?[A-Za-z][A-Za-z0-9-]*\b[^<>]*/?>", start.strip()):
        return True, _HtmlBlock(
            blockquote_depth=blockquote_depth,
            list_indent=list_indent,
        )
    return False, None


def _setext_continues(candidate_line: str, underline_line: str) -> bool:
    """Whether an underline promotes the candidate in the same container."""
    candidate, candidate_blockquote_depth = _strip_blockquote_prefix(candidate_line)
    _, candidate_list_indent = _strip_list_marker(candidate)

    underline, underline_blockquote_depth = _strip_blockquote_prefix(underline_line)
    underline_indent = len(underline) - len(underline.lstrip(" "))
    underline, underline_list_indent = _strip_list_marker(underline)
    if underline_list_indent or underline_blockquote_depth > candidate_blockquote_depth:
        return False
    if candidate_list_indent:
        if underline_indent < candidate_list_indent:
            return False
        underline = underline[candidate_list_indent:]
    return _re_setext_heading.match(underline) is not None


def _normalized_html_line(line: str, blockquote_depth: int, list_indent: int, *, opening: bool) -> str:
    """Remove only the container prefixes that enclose a raw HTML node."""
    for _ in range(blockquote_depth):
        match = re.match(r"^ {0,3}>[ \t]?", line)
        if match is None:
            break
        line = line[match.end() :]
    if opening:
        list_line, direct_list_indent = _strip_list_marker(line)
        if direct_list_indent:
            return list_line
    if list_indent and line.startswith(" " * list_indent):
        line = line[list_indent:]
    return line


def _html_node_ranges(source: str) -> list[_HtmlNodeRange]:
    """Return the raw HTML nodes produced by doc-builder's Markdown parser."""
    lines = source.splitlines(keepends=True)
    starts = []
    offset = 0
    for line in lines:
        starts.append(offset)
        offset += len(line)

    ranges = []
    fence = None
    active_list_indents: list[int] = []
    list_blank_pending = False
    line_index = 0
    while line_index < len(lines):
        line = lines[line_index]
        container_line, blockquote_depth = _strip_blockquote_prefix(line)
        _, direct_list_indent = _strip_list_marker(container_line)
        direct_list_indents = _list_marker_indents(container_line)
        active_list_indent = active_list_indents[-1] if active_list_indents else 0
        if direct_list_indent:
            marker_match = re.match(r"^( *)", container_line)
            marker_column = len(marker_match.group(1)) if marker_match is not None else 0
            retained_indents = [indent for indent in active_list_indents if indent <= marker_column]
            active_list_indents = [*retained_indents, *direct_list_indents]
            list_blank_pending = False
        elif not container_line.strip():
            list_blank_pending = bool(active_list_indents)
        elif list_blank_pending:
            leading_indent = len(container_line) - len(container_line.lstrip(" "))
            while active_list_indents and leading_indent < active_list_indents[-1]:
                active_list_indents.pop()
            list_blank_pending = False
        elif active_list_indents:
            leading_indent = len(container_line) - len(container_line.lstrip(" "))
            if leading_indent < active_list_indents[-1] and (
                _re_fence.match(container_line.lstrip(" "))
                or _re_heading.match(container_line)
                or _re_setext_heading.match(container_line)
                or _re_thematic_break.match(container_line.rstrip("\r\n"))
            ):
                while active_list_indents and leading_indent < active_list_indents[-1]:
                    active_list_indents.pop()
        active_list_indent = active_list_indents[-1] if active_list_indents else 0
        inherited_list_indent = direct_list_indent or active_list_indent

        is_fence_line, fence = _advance_fence(line, fence)
        if is_fence_line or fence is not None:
            line_index += 1
            continue

        # Setext headings are tokenized before HTML, even if their candidate
        # begins with a native tag or an HTML comment.
        if line_index + 1 < len(lines) and _setext_continues(line, lines[line_index + 1]):
            line_index += 1
            continue

        is_html_line, block = _advance_html_block(line, None)
        if block is not None and inherited_list_indent and not block.list_indent:
            block = _HtmlBlock(
                raw_text_tag=block.raw_text_tag,
                end_marker=block.end_marker,
                blockquote_depth=blockquote_depth,
                list_indent=inherited_list_indent,
            )
        normalized = _normalized_html_line(
            line,
            blockquote_depth,
            inherited_list_indent,
            opening=True,
        ).lstrip(" ")
        is_comment = normalized.startswith("<!--")
        if not is_html_line:
            line_index += 1
            continue

        block_start_index = line_index
        normalized_lines = [normalized]
        line_index += 1

        while block is not None and line_index < len(lines):
            next_line = lines[line_index]
            # Blank-ended HTML blocks stop before the blank. Exact-marker
            # blocks (comments, declarations, raw text) consume through their
            # closing line instead.
            if block.raw_text_tag is None and block.end_marker is None:
                blank_line, _ = _strip_blockquote_prefix(next_line)
                if not blank_line.strip():
                    break

            consumed, next_block = _advance_html_block(next_line, block)
            if not consumed:
                break
            normalized_lines.append(
                _normalized_html_line(
                    next_line,
                    blockquote_depth,
                    inherited_list_indent,
                    opening=False,
                )
            )
            line_index += 1
            block = next_block

        node_value = "".join(normalized_lines).strip()
        serialized_match = re.fullmatch(r"<(\w+)[^>]*>.*</\1>", node_value, re.DOTALL)
        serialized = serialized_match is not None and serialized_match.group(1) in _HTML_TAGS
        block_end = starts[line_index] if line_index < len(lines) else len(source)
        ranges.append(
            _HtmlNodeRange(
                start=starts[block_start_index],
                end=block_end,
                serialized=serialized,
                is_comment=is_comment,
                blockquote_depth=blockquote_depth,
                list_indent=inherited_list_indent,
            )
        )

    return ranges


def _without_html_nodes(source: str) -> str:
    """Mask raw HTML nodes whose contents are not parsed as Markdown."""
    characters = list(source)
    for node_range in _html_node_ranges(source):
        for index in range(node_range.start, node_range.end):
            if characters[index] not in "\r\n":
                characters[index] = " "
    return "".join(characters)


def _smartypants(text: str) -> str:
    """Apply mdsvex's default smart punctuation to a text-node approximation."""
    text = re.sub(r"(?<!-)--(?!-)", "—", text)
    text = re.sub(r"\.{3,}", "…", text)
    text = text.replace("``", "“").replace("''", "”")

    characters = list(text)
    for index, character in enumerate(characters):
        if character not in "\"'":
            continue
        previous = characters[index - 1] if index else ""
        following = characters[index + 1] if index + 1 < len(characters) else ""
        if character == "'" and previous.isalnum() and following.isalnum():
            characters[index] = "’"
        elif following and not following.isspace() and (not previous or previous.isspace() or previous in "([{—–"):
            characters[index] = "“" if character == '"' else "‘"
        else:
            characters[index] = "”" if character == '"' else "’"
    return "".join(characters)


def _replace_heading_links(heading_text: str) -> str:
    """Replace inline links with their labels and images with empty text."""
    while True:
        links = sorted(
            _iter_markdown_links(heading_text, _inline_code_ranges(heading_text)),
            key=lambda link: (link.start, -link.end),
        )
        top_level_links = []
        enclosing_end = -1
        for link in links:
            if link.start < enclosing_end:
                continue
            top_level_links.append(link)
            enclosing_end = link.end
        if not top_level_links:
            return heading_text

        for link in reversed(top_level_links):
            start = link.start - 1 if link.is_image else link.start
            replacement = " " if link.is_image else f" {link.label} "
            heading_text = heading_text[:start] + replacement + heading_text[link.end :]


def _heading_inline_text(heading_text: str) -> str:
    """Approximate mdsvex's visible text for the inline syntax used in headings."""
    protected = []

    def protect(content: str) -> str:
        token = f"\ufff0{len(protected)}\ufff1"
        protected.append((token, content))
        return token

    def protect_code(match: re.Match) -> str:
        content = match.group(2)
        if content.startswith(" ") and content.endswith(" ") and content.strip():
            content = content[1:-1]
        return protect(content)

    heading_text = _re_code_span.sub(protect_code, heading_text)
    heading_text = _re_heading_html_comment.sub(lambda match: protect(match.group()), heading_text)
    heading_text = _re_heading_html.sub(lambda match: protect(match.group(1)), heading_text)
    heading_text = re.sub(r"\\([\[\]])", lambda match: protect(match.group(1)), heading_text)
    heading_text = _replace_heading_links(heading_text)
    heading_text = _re_heading_reference.sub(
        lambda match: " " if match.group(1) else f" {match.group(2)} ", heading_text
    )
    previous = None
    while previous != heading_text:
        previous = heading_text
        heading_text = _re_heading_emphasis.sub(r" \2 ", heading_text)
    heading_text = _re_heading_html.sub(r" \1 ", heading_text)
    heading_text = _re_heading_brackets.sub(r" \1 ", heading_text)
    heading_text = _re_entity.sub(lambda match: f" {match.group()} ", heading_text)
    heading_text = re.sub(r"\\([!\"#$%'()*+,./:;<=>?@\[\]^_`{|}~-])", r" \1 ", heading_text)
    heading_text = _smartypants(unescape(heading_text))
    for token, content in protected:
        heading_text = heading_text.replace(token, f" {content} ")
    return re.sub(r"\s+", " ", heading_text).strip()


def _heading_anchor(heading_text: str, *, atx: bool = True) -> str | None:
    """Return the generated anchor for a Markdown heading, if it has one."""
    if atx:
        # Ignore optional closing hashes in ATX headings, e.g. ``## Title ##``.
        heading_text = re.sub(r"\s+#+\s*$", "", heading_text).strip()

    custom_match = _re_custom_anchor.search(heading_text)
    if custom_match:
        return _heading_inline_text(custom_match.group(1)) or None

    # Escaped brackets become separate text nodes. When they end a heading,
    # the renderer's legacy ``[ local ]`` rule uses their contents as the ID.
    escaped_custom_match = re.search(r"\\\[(.*?)\\\]\s*$", heading_text)
    if escaped_custom_match:
        return _heading_inline_text(escaped_custom_match.group(1)) or None

    heading_text = _heading_inline_text(heading_text)
    anchor = re.sub(r"\s+", "-", heading_text.lower())
    anchor = "".join(character for character in anchor if character.isalnum() or character == "-")
    return anchor or None


def _attribute_value(match: re.Match, expression_mode: str) -> str | None:
    """Return an HTML attribute's rendered value.

    Static Svelte expressions are evaluated when mdsvex leaves an HTML node
    alone. Paired native HTML blocks instead pass through Cheerio, which turns
    the expression syntax into literal attribute text.
    """
    for group_index, group in enumerate(match.groups(), start=1):
        if group is None:
            continue
        if group_index == 3:
            if expression_mode == "ignore":
                return None
            return group if expression_mode == "evaluate" else f'{{"{group}"}}'
        if group_index == 4:
            if expression_mode == "ignore":
                return None
            return group if expression_mode == "evaluate" else f"{{'{group}'}}"
        return group
    return None


def _rendered_attribute_value(match: re.Match, expression_mode: str) -> str | None:
    """Return the DOM value, preserving entities inside evaluated JS strings."""
    value = _attribute_value(match, expression_mode)
    if value is None:
        return None
    is_evaluated_expression = expression_mode == "evaluate" and (
        match.group(3) is not None or match.group(4) is not None
    )
    return value if is_evaluated_expression else unescape(value)


def _html_block_render_modes(source: str) -> list[tuple[int, int, bool]]:
    """Return raw HTML block ranges and whether mdsvex serializes each one."""
    return [(node.start, node.end, node.serialized) for node in _html_node_ranges(source)]


def _without_html_container_markers(source: str, html_nodes: list[_HtmlNodeRange]) -> str:
    """Mask list/quote prefixes while keeping HTML tag offsets unchanged."""
    characters = list(source)
    for node in html_nodes:
        line_start = node.start
        opening = True
        while line_start < node.end:
            newline = source.find("\n", line_start, node.end)
            line_end = node.end if newline == -1 else newline + 1
            line = source[line_start:line_end]
            cursor = 0
            for _ in range(node.blockquote_depth):
                match = re.match(r"^ {0,3}>[ \t]?", line[cursor:])
                if match is None:
                    break
                for index in range(line_start + cursor, line_start + cursor + match.end()):
                    if characters[index] not in "\r\n":
                        characters[index] = " "
                cursor += match.end()
            if opening and node.list_indent:
                list_line, direct_indent = _strip_list_marker(line[cursor:])
                if direct_indent:
                    prefix_length = len(line[cursor:]) - len(list_line)
                    for index in range(line_start + cursor, line_start + cursor + prefix_length):
                        if characters[index] not in "\r\n":
                            characters[index] = " "
            opening = False
            line_start = line_end
    return "".join(characters)


def _html_anchors(source: str) -> set[str]:
    """Extract static fragment targets from rendered native HTML tags."""
    anchors = set()
    html_nodes = _html_node_ranges(source)
    html_block_modes = [(node.start, node.end, node.serialized) for node in html_nodes]
    tag_source = _without_html_container_markers(source, html_nodes)
    html_tags = _iter_html_tags(tag_source)
    comment_ranges = []
    comment_cursor = 0
    while comment_cursor < len(tag_source):
        comment_start = tag_source.find("<!--", comment_cursor)
        if comment_start == -1:
            break
        containing_tag = next((tag for tag in html_tags if tag.start < comment_start < tag.end), None)
        if containing_tag is not None:
            comment_cursor = comment_start + 4
            continue
        comment_end = tag_source.find("-->", comment_start + 4)
        range_end = len(tag_source) if comment_end == -1 else comment_end + 3
        comment_ranges.append((comment_start, range_end))
        comment_cursor = range_end

    # ``onHtml`` parses paired native nodes as full HTML documents and keeps
    # only Cheerio's body. Document wrappers lose their own attributes, and
    # root/head content is omitted from the rendered Svelte output.
    cheerio_head_roots = {"base", "head", "link", "meta", "script", "style", "title"}
    cheerio_suppressed_ranges = []
    for node in html_nodes:
        if not node.serialized:
            continue
        node_tags = [tag for tag in html_tags if node.start <= tag.start < node.end]
        root_tag = next((tag for tag in node_tags if not tag.closing), None)
        if root_tag is not None and root_tag.name in cheerio_head_roots:
            closing_tag = next(
                (tag for tag in node_tags if tag.closing and tag.name == root_tag.name and tag.start > root_tag.start),
                None,
            )
            cheerio_suppressed_ranges.append((root_tag.start, node.end if closing_tag is None else closing_tag.end))
        for head_tag in (tag for tag in node_tags if not tag.closing and tag.name == "head"):
            closing_head = next(
                (tag for tag in node_tags if tag.closing and tag.name == "head" and tag.start > head_tag.start),
                None,
            )
            cheerio_suppressed_ranges.append((head_tag.start, node.end if closing_head is None else closing_head.end))
    svg_depth = 0
    mathml_depth = 0
    opaque_stack: list[str] = []
    for tag in html_tags:
        if any(start <= tag.start < end for start, end in comment_ranges):
            continue
        if any(start <= tag.start < end for start, end in cheerio_suppressed_ranges):
            continue
        closing, tag_name, attributes = tag.closing, tag.name, tag.attributes
        lower_tag_name = tag_name.lower()
        # mdsvex performs a case-sensitive lookup against ``html-tags``;
        # uppercase spellings such as ``<DIV>`` are escaped before Svelte.
        if opaque_stack:
            if closing and tag_name == opaque_stack[-1]:
                opaque_stack.pop()
            elif (
                not closing
                and not attributes.rstrip().endswith("/")
                and (tag_name in _HTML_ANCHOR_OPAQUE_TAGS or tag_name in _HTML_REMOVED_TAGS)
            ):
                opaque_stack.append(tag_name)
            continue
        if closing:
            if tag_name == "svg" and svg_depth:
                svg_depth -= 1
            elif tag_name == "math" and mathml_depth:
                mathml_depth -= 1
            continue

        is_native = tag_name in _HTML_TAGS
        is_svg_descendant = svg_depth > 0 and lower_tag_name in _SVG_TAGS_LOWER
        is_mathml_descendant = mathml_depth > 0 and lower_tag_name in _MATHML_TAGS_LOWER
        if tag_name not in _HTML_REMOVED_TAGS and (is_native or is_svg_descendant or is_mathml_descendant):
            block_mode = next(
                (serialized for start, end, serialized in html_block_modes if start <= tag.start < end), None
            )
            if block_mode is None:
                # Braced attributes in ordinary inline Markdown are escaped by
                # mdsvex rather than becoming Svelte attributes.
                expression_mode = "ignore"
            else:
                expression_mode = "literal" if block_mode else "evaluate"
            id_match = None if block_mode and tag_name in {"body", "head", "html"} else _re_html_id.search(attributes)
            if id_match:
                anchor = _rendered_attribute_value(id_match, expression_mode)
                if anchor:
                    anchors.add(anchor)

            if tag_name == "a":
                name_match = _re_html_name.search(attributes)
                if name_match:
                    anchor = _rendered_attribute_value(name_match, expression_mode)
                    if anchor:
                        anchors.add(anchor)

        if not attributes.rstrip().endswith("/"):
            if tag_name == "svg":
                svg_depth += 1
            elif tag_name == "math":
                mathml_depth += 1
            elif tag_name in _HTML_ANCHOR_OPAQUE_TAGS or tag_name in _HTML_REMOVED_TAGS:
                opaque_stack.append(tag_name)
    return anchors


def _increment_anchor(anchors: Counter, anchor: str | None) -> None:
    if anchor:
        anchors[anchor] += 1


def _decrement_anchor(anchors: Counter, anchor: str | None) -> None:
    if anchor and anchors[anchor] > 0:
        anchors[anchor] -= 1


def _mark_katex_placeholders(content: str) -> str:
    """Mirror mdsvex's math placeholders while retaining source line numbers."""
    counter = 0

    def marker(match: re.Match) -> str:
        nonlocal counter
        replacement = f"KATEXPARSE{counter}MARKER"
        counter += 1
        # mdsvex removes newlines captured by display and ``\\(...)`` math.
        # Keeping them after the marker preserves source-line correspondence;
        # the added blank lines cannot affect heading text.
        return replacement + "\n" * match.group(0).count("\n")

    content = _re_katex_display.sub(marker, content)
    content = _re_katex_inline.sub(marker, content)

    def dollar_marker(match: re.Match) -> str:
        nonlocal counter
        replacement = f"{match.group(1)}KATEXPARSE{counter}MARKER{match.group(5)}"
        counter += 1
        return replacement

    return _re_katex_inline_dollar.sub(dollar_marker, content)


def _autodoc_heading_targets(lines: list[str]) -> dict[int, int | None]:
    """Map autodoc lines to the raw ATX heading modified by resolve_autodoc."""
    targets = {}
    last_heading = None
    in_backtick_fence = False
    for line_number, line in enumerate(lines):
        if _re_autodoc.search(line) is not None:
            targets[line_number] = last_heading
            # A successful autodoc consumes the pending heading. Whether an
            # object imports successfully is unknowable to this source check.
            last_heading = None
            continue
        if line.startswith("```"):
            in_backtick_fence = not in_backtick_fence
        if line.startswith("#") and not in_backtick_fence:
            last_heading = line_number
    return targets


def _setext_candidate(line: str) -> tuple[str, int, int] | None:
    """Return the immediately preceding line if mdsvex can promote it."""
    line, blockquote_depth = _strip_blockquote_prefix(line)
    line, list_indent = _strip_list_marker(line)
    stripped = line.strip()
    if not stripped or _re_heading.match(line) or _re_setext_heading.match(line) or _re_autodoc.match(line):
        return None
    return stripped, blockquote_depth, list_indent


@lru_cache(maxsize=1024)
def _extract_anchor_index_cached(file_path: Path, _modified_ns: int, _size: int) -> _AnchorIndex | None:
    """Extract exact and build-generated anchor metadata from a Markdown/MDX file."""
    try:
        with open(file_path, encoding="utf-8-sig") as f:
            raw_content = f.read()
    except Exception as e:
        print(f"Warning: Could not read {file_path} to check anchors: {e}")
        return None

    raw_lines = raw_content.splitlines()
    content = _mark_katex_placeholders(raw_content)
    lines = content.splitlines()
    content_line_offsets = []
    content_offset = 0
    for content_line in content.splitlines(keepends=True):
        content_line_offsets.append(content_offset)
        content_offset += len(content_line)
    # Placeholder replacement intentionally preserves line correspondence.
    if len(lines) < len(raw_lines):
        lines.extend([""] * (len(raw_lines) - len(lines)))

    anchors = Counter()
    autodoc_objects = set()
    uncertain_math = set()
    fence = None
    in_comment = False
    setext_candidate = None
    rendered_headings = {}
    autodoc_heading_targets = _autodoc_heading_targets(raw_lines)
    raw_autodoc_objects = {
        line_number: match.group(1)
        for line_number, line in enumerate(raw_lines)
        if (match := _re_autodoc.search(line)) is not None
    }
    processed_autodoc_lines = set()
    html_source_lines = [""] * len(lines)
    html_node_starts = {node.start: node.end for node in _html_node_ranges(content)}
    html_node_end = -1
    markdown_content = _without_html_nodes(content)
    markdown_boundaries = _markdown_block_boundaries(markdown_content)
    protected_ranges = _inline_code_ranges(markdown_content, markdown_boundaries)
    protected_ranges.extend((tag.start, tag.end) for tag in _iter_html_tags(markdown_content))
    protected_ranges.extend(
        (link.start, link.end)
        for link in _iter_markdown_links(markdown_content, protected_ranges, markdown_boundaries)
    )
    # KaTeX markers are assigned in three whole-document passes (display,
    # ``\\(...)``, then dollar-inline math). Generated autodoc math anywhere
    # in the file can therefore shift any source marker, even an earlier one.
    math_counter_uncertain = bool(raw_autodoc_objects)

    for line_number, line in enumerate(lines):
        raw_line = raw_lines[line_number] if line_number < len(raw_lines) else ""
        line_offset = content_line_offsets[line_number] if line_number < len(content_line_offsets) else content_offset
        if line_offset in html_node_starts:
            html_node_end = html_node_starts[line_offset]
        if line_offset < html_node_end:
            html_source_lines[line_number] = line
            setext_candidate = None
            continue

        is_fence_line, fence = _advance_fence(line, fence)
        if is_fence_line:
            in_comment = False
            setext_candidate = None
            continue
        if fence is not None:
            in_comment = False
            setext_candidate = None
            continue

        preserves_comment = line_number + 1 < len(lines) and _setext_continues(line, lines[line_number + 1])
        if not preserves_comment or in_comment:
            if in_comment and line_offset in markdown_boundaries:
                in_comment = False
            line, in_comment = _without_html_comments(
                line,
                in_comment,
                protected_ranges=protected_ranges,
                line_offset=line_offset,
            )

        line_without_code = _without_inline_code(line)
        heading_line, heading_blockquote_depth = _strip_blockquote_prefix(line)
        heading_line, _ = _strip_list_marker(heading_line)

        if setext_candidate is not None and _setext_continues(lines[setext_candidate[0]], line):
            candidate_line_number, candidate_text, _, _ = setext_candidate
            anchor = _heading_anchor(candidate_text, atx=False)
            _increment_anchor(anchors, anchor)
            if anchor and math_counter_uncertain and _re_katex_marker.search(anchor):
                uncertain_math.add(anchor)
            html_source_lines[candidate_line_number] = ""
            setext_candidate = None
            continue

        heading_match = _re_heading.match(heading_line)
        if heading_match:
            anchor = _heading_anchor(heading_match.group(1))
            _increment_anchor(anchors, anchor)
            if anchor and math_counter_uncertain and _re_katex_marker.search(anchor):
                uncertain_math.add(anchor)
            if raw_line.startswith("#"):
                rendered_headings[line_number] = anchor
            setext_candidate = None
            continue

        autodoc_match = _re_autodoc.match(line_without_code)
        if autodoc_match:
            autodoc_objects.add(autodoc_match.group(1))
            processed_autodoc_lines.add(line_number)
            # resolve_autodoc appends the generated object anchor to the most
            # recent raw ATX heading. That heading may itself be hidden in a
            # comment or a fence, so only remove it if mdsvex rendered it.
            target_line = autodoc_heading_targets.get(line_number)
            _decrement_anchor(anchors, rendered_headings.get(target_line))
            setext_candidate = None
            continue

        html_source_lines[line_number] = line_without_code
        candidate = _setext_candidate(line)
        setext_candidate = (line_number, *candidate) if candidate is not None else None

    # resolve_autodoc runs before Markdown parsing. A directive hidden in a
    # code fence or HTML comment can therefore still replace a preceding
    # visible heading, even though its generated Docstring remains hidden.
    for line_number, object_name in raw_autodoc_objects.items():
        if line_number in processed_autodoc_lines:
            continue
        target_line = autodoc_heading_targets.get(line_number)
        if target_line in rendered_headings:
            autodoc_objects.add(object_name)
            _decrement_anchor(anchors, rendered_headings[target_line])

    for anchor in _html_anchors("\n".join(html_source_lines)):
        _increment_anchor(anchors, anchor)

    exact = {
        anchor
        for anchor, count in anchors.items()
        if count > 0 and not (anchor in uncertain_math and _re_katex_marker.search(anchor))
    }
    uncertain_math_templates = {
        _re_katex_marker.sub("katexparse<number>marker", anchor) for anchor in uncertain_math if anchors[anchor] > 0
    }

    return _AnchorIndex(
        exact=frozenset(exact),
        autodoc_objects=frozenset(autodoc_objects),
        uncertain_math=frozenset(uncertain_math_templates),
    )


def _extract_anchor_index(file_path: Path) -> _AnchorIndex | None:
    try:
        file_stat = file_path.stat()
    except Exception as e:
        print(f"Warning: Could not read {file_path} to check anchors: {e}")
        return None
    return _extract_anchor_index_cached(file_path, file_stat.st_mtime_ns, file_stat.st_size)


def extract_anchors(file_path: Path) -> set[str] | None:
    """Extract exact, source-verifiable anchors from a Markdown/MDX file."""
    anchor_index = _extract_anchor_index(Path(file_path))
    return None if anchor_index is None else set(anchor_index.exact)


def _is_autodoc_anchor(anchor: str, object_name: str) -> bool:
    """Whether an anchor belongs to an unresolved autodoc object namespace."""
    anchor_parts = tuple(anchor.split("."))
    object_parts = tuple(object_name.split("."))
    # get_shortest_path() always prefixes generated anchors with the package.
    if len(anchor_parts) < 2 or not object_parts or not all(anchor_parts) or not all(object_parts):
        return False

    def matches_object_path(generated_parts: tuple[str, ...], candidate_parts: tuple[str, ...]) -> bool:
        if not generated_parts or not candidate_parts:
            return False
        if len(candidate_parts) == 1:
            return generated_parts[0] == candidate_parts[0]
        module_parts, object_leaf = candidate_parts[:-1], candidate_parts[-1]
        return any(
            generated_parts[: prefix_length + 1] == (*module_parts[:prefix_length], object_leaf)
            for prefix_length in range(len(module_parts) + 1)
        )

    # ``check-links`` receives a docs directory rather than the imported
    # package, whose ``__name__`` may itself contain dots. Try every non-empty
    # package prefix; this is necessarily conservative when package metadata
    # is unavailable. get_shortest_path() then keeps zero or more relative
    # module segments before the public object name, followed by members.
    for package_length in range(1, len(anchor_parts)):
        package_parts = anchor_parts[:package_length]
        generated_parts = anchor_parts[package_length:]
        candidates = [object_parts]
        if object_parts[:package_length] == package_parts:
            candidates.append(object_parts[package_length:])
        if any(matches_object_path(generated_parts, candidate) for candidate in candidates):
            return True
    return False


def _anchor_exists(anchor: str, anchor_index: _AnchorIndex | None) -> bool:
    if anchor_index is None or anchor in anchor_index.exact:
        return True
    if _re_katex_marker.search(anchor):
        template = _re_katex_marker.sub("katexparse<number>marker", anchor)
        if template in anchor_index.uncertain_math:
            return True
    for object_name in anchor_index.autodoc_objects:
        if object_name in _RESOLVED_AUTODOC_ANCHORS:
            resolved_anchor = _RESOLVED_AUTODOC_ANCHORS[object_name]
            if resolved_anchor and (anchor == resolved_anchor or anchor.startswith(f"{resolved_anchor}.")):
                return True
        elif _is_autodoc_anchor(anchor, object_name):
            return True
    return False


def _initialize_autodoc_anchors(resolved_anchors: dict[str, str | None]) -> None:
    """Install the parent-resolved autodoc anchors in a link-check worker."""
    global _RESOLVED_AUTODOC_ANCHORS
    _RESOLVED_AUTODOC_ANCHORS = resolved_anchors


def _normalized_project_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _detect_package_name(doc_folder: Path) -> str | None:
    """Conservatively infer the documented import name from its repository."""
    resolved_folder = doc_folder.resolve()
    candidates = [resolved_folder, *resolved_folder.parents]
    project_root = next((path for path in candidates if (path / ".git").exists()), None)
    if project_root is None:
        project_root = next(
            (path for path in candidates if (path / "pyproject.toml").exists() or (path / "setup.py").exists()),
            None,
        )
    if project_root is None:
        return None

    project_name = _normalized_project_name(project_root.name)
    package_distributions = packages_distributions()

    def importable(import_name: str) -> bool:
        try:
            return importlib.util.find_spec(import_name) is not None
        except (ImportError, AttributeError, ValueError):
            return False

    direct_matches = {
        import_name
        for import_name in package_distributions
        if _normalized_project_name(import_name) == project_name and importable(import_name)
    }
    if len(direct_matches) == 1:
        return direct_matches.pop()

    distribution_matches = {
        import_name
        for import_name, distributions in package_distributions.items()
        if any(_normalized_project_name(distribution) == project_name for distribution in distributions)
        and importable(import_name)
    }
    return distribution_matches.pop() if len(distribution_matches) == 1 else None


def _resolve_autodoc_anchors(all_files: list[Path], package_name: str | None) -> dict[str, str | None]:
    """Resolve directive names to the canonical anchors emitted by autodoc."""
    if not package_name:
        return {}

    object_names = set()
    for file_path in all_files:
        try:
            content = file_path.read_text(encoding="utf-8-sig")
        except Exception:
            continue
        object_names.update(
            match.group(1) for line in content.splitlines() if (match := _re_autodoc.match(line)) is not None
        )
    if not object_names:
        return {}

    try:
        package = importlib.import_module(package_name)
        from .autodoc import find_object_in_package, get_shortest_path
    except Exception:
        return {}

    resolved_anchors = {}
    for object_name in object_names:
        try:
            obj = find_object_in_package(object_name, package)
            if obj is None:
                continue
            shortest_path = get_shortest_path(obj, package)
            resolved_anchors[object_name] = "None" if shortest_path is None else shortest_path
        except Exception:
            # Keep the source-only fallback for an object whose optional
            # dependencies prevent it from being inspected in this process.
            continue
    return resolved_anchors


def find_target_file(link_path: Path) -> Path | None:
    """
    Find the target file for a link, handling missing extensions.

    This function handles cases where links don't include the .md or .mdx extension.
    For example, `./fp16` should match `./fp16.md` or `./fp16.mdx`.

    Args:
        link_path: The resolved link path

    Returns:
        The actual file path if found, None otherwise
    """
    # If the exact path exists (file or directory), return it
    if link_path.exists():
        return link_path

    # Try adding .md or .mdx for extensionless links, including names such as
    # ``t5v1.1`` whose final dot is part of the page name.
    if link_path.suffix not in (".md", ".mdx"):
        base_path = link_path.with_suffix("") if link_path.suffix == ".html" else link_path

        # Try with .md extension
        md_path = base_path.with_name(base_path.name + ".md")
        if md_path.exists():
            return md_path

        # Try with .mdx extension
        mdx_path = base_path.with_name(base_path.name + ".mdx")
        if mdx_path.exists():
            return mdx_path

    return None


def check_file_links(file_path: Path, doc_folder: Path) -> tuple[list[tuple[str, str, int]], int]:
    """
    Check all internal links in a single file.

    Args:
        file_path: Path to the file to check
        doc_folder: Root documentation folder

    Returns:
        Tuple of (broken_links, total_links_checked) where broken_links is a list
        of (link_text, link_url, line_number) tuples and total_links_checked is the
        count of all internal links found
    """
    broken_links = []
    total_links = 0
    anchor_cache: dict[Path, _AnchorIndex | None] = {}

    try:
        with open(file_path, encoding="utf-8-sig") as f:
            content = f.read()

        markdown_content = _without_html_nodes(content)
        raw_block_boundaries = _markdown_block_boundaries(markdown_content)
        raw_code_ranges = _inline_code_ranges(markdown_content, raw_block_boundaries)
        protected_ranges = [*raw_code_ranges, *((tag.start, tag.end) for tag in _iter_html_tags(markdown_content))]
        protected_ranges.extend(
            (link.start, link.end)
            for link in _iter_markdown_links(markdown_content, raw_code_ranges, raw_block_boundaries)
        )
        visible_lines = []
        fence = None
        in_comment = False
        line_offset = 0
        for raw_line in markdown_content.splitlines(keepends=True):
            line = raw_line
            is_fence_line, fence = _advance_fence(line, fence)
            if is_fence_line or fence is not None:
                in_comment = False
                line = re.sub(r"[^\r\n]", " ", line)
            else:
                if in_comment and line_offset in raw_block_boundaries:
                    in_comment = False
                line, in_comment = _without_html_comments(
                    line,
                    in_comment,
                    protected_ranges=protected_ranges,
                    line_offset=line_offset,
                )
            visible_lines.append(line)
            line_offset += len(raw_line)

        visible_content = "".join(visible_lines)
        block_boundaries = _markdown_block_boundaries(visible_content)
        link_source = _without_blockquote_markers(visible_content)
        pre_attribute_code_ranges = _inline_code_ranges(link_source, block_boundaries)
        destination_ranges = [
            (link.destination_start, link.destination_start + len(link.destination))
            for link in _iter_markdown_links(link_source, pre_attribute_code_ranges, block_boundaries)
        ]
        link_source = _without_html_attributes(link_source, destination_ranges)
        inline_code_ranges = _inline_code_ranges(link_source, block_boundaries)
        line_starts = [0, *(match.end() for match in re.finditer("\n", visible_content))]

        # Find all Markdown links, including labels and destinations that span
        # source lines. The sanitized text has identical offsets to ``content``.
        for link in _iter_markdown_links(link_source, inline_code_ranges, block_boundaries):
            link_text = visible_content[link.start + 1 : link.start + 1 + len(link.label)]
            link_url = visible_content[link.destination_start : link.destination_start + len(link.destination)]
            parsed_link_url = link.destination
            # Parenthesized prose such as ``[text span](bounding boxes)``
            # is not a Markdown link. Only count valid destinations.
            if _parse_link_destination(parsed_link_url) is None:
                continue

            # Skip external links. Anchor-only links are checked against the
            # headings and explicit IDs in the current file.
            if is_external_link(parsed_link_url):
                continue

            # Count this as an internal link
            total_links += 1
            line_num = bisect_right(line_starts, link.start)

            # Resolve the link path
            link_path = resolve_link_path(file_path, parsed_link_url)
            if link_path is None:
                continue

            # Check if target exists
            target = find_target_file(link_path)
            _, anchor = split_link_url(parsed_link_url)
            anchor_exists = True
            if target is not None and anchor and target.is_file():
                if target not in anchor_cache:
                    anchor_cache[target] = _extract_anchor_index(target)
                target_anchors = anchor_cache[target]
                # A read failure is already reported as a warning, so do
                # not turn it into a false broken-anchor result.
                anchor_exists = _anchor_exists(anchor, target_anchors)

            if target is None or not anchor_exists:
                broken_links.append((link_text, link_url, line_num))

    except Exception as e:
        # If we can't read the file, report it as a warning but don't fail
        print(f"Warning: Could not read {file_path}: {e}")

    return broken_links, total_links


def check_links(
    doc_folder: str | Path,
    max_workers: int | None = None,
    show_progress: bool = True,
    package_name: str | None = None,
) -> LinkCheckResult:
    """
    Check all internal links in documentation files.

    Args:
        doc_folder: Path to the documentation folder
        max_workers: Maximum number of parallel workers (default: auto-detect CPU count)
        show_progress: Show progress bar during checking (default: True, requires tqdm)
        package_name: Documented Python import name (auto-detected when omitted)

    Returns:
        LinkCheckResult with details about broken links
    """
    doc_folder = Path(doc_folder)
    result = LinkCheckResult()

    # Auto-detect optimal worker count if not specified
    if max_workers is None:
        max_workers = os.cpu_count() or 4  # Fallback to 4 if cpu_count() returns None

    # Find all markdown and mdx files
    md_files = list(doc_folder.glob("**/*.md"))
    mdx_files = list(doc_folder.glob("**/*.mdx"))
    all_files = md_files + mdx_files

    result.files_checked = len(all_files)
    package_name = package_name or os.environ.get("DOCS_LIBRARY") or _detect_package_name(doc_folder)
    resolved_autodoc_anchors = _resolve_autodoc_anchors(all_files, package_name)

    # Check files in parallel using ProcessPoolExecutor to bypass GIL
    with ProcessPoolExecutor(
        max_workers=max_workers,
        initializer=_initialize_autodoc_anchors,
        initargs=(resolved_autodoc_anchors,),
    ) as executor:
        # Submit all tasks
        future_to_file = {
            executor.submit(check_file_links, file_path, doc_folder): file_path for file_path in all_files
        }

        # Create progress bar iterator
        futures = as_completed(future_to_file)
        if show_progress and HAS_TQDM:
            futures = tqdm(futures, total=len(all_files), desc="Checking links", unit="file")

        # Process results as they complete
        for future in futures:
            file_path = future_to_file[future]
            try:
                broken_links, links_count = future.result()
                result.links_checked += links_count
                for link_text, link_url, line_num in broken_links:
                    result.add_broken_link(file_path, link_text, link_url, line_num)
            except Exception as e:
                # Use tqdm.write if available to avoid disrupting progress bar
                if show_progress and HAS_TQDM:
                    tqdm.write(f"Error checking {file_path}: {e}")
                else:
                    print(f"Error checking {file_path}: {e}")

    return result


def check_links_cli(doc_folder: str | Path) -> int:
    """
    CLI interface for link checking.

    Args:
        doc_folder: Path to the documentation folder

    Returns:
        Exit code (0 for success, 1 for broken links found)
    """
    print(f"Checking links in {doc_folder}...")
    result = check_links(doc_folder)

    print(result.get_summary())

    return 1 if result.has_broken_links() else 0
