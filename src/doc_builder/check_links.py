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

import os
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

try:
    from tqdm import tqdm

    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

# Regex to match markdown links [text](url) and image links ![alt](url)
# Captures the link text and URL separately
_re_md_link = re.compile(r"!?\[([^\]]*)\]\(([^)]+)\)")
_re_heading = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$")
_re_custom_anchor = re.compile(r"(?:\[\[([^\]]+)\]\]|\[\s+([^\]]*?)\s+\])\s*$")
_re_html_anchor = re.compile(r'''\b(?:id|name)\s*=\s*(?:"([^"]+)"|'([^']+)')''', re.IGNORECASE)
_re_fence = re.compile(r"^\s{0,3}(`{3,}|~{3,})")


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


def is_external_link(url: str) -> bool:
    """
    Check if a URL is external (http/https/mailto/etc).

    Args:
        url: The URL to check

    Returns:
        True if the URL is external, False otherwise
    """
    # Check for common external URL schemes
    external_schemes = ("http://", "https://", "mailto:", "ftp://", "tel:", "//")
    return any(url.startswith(scheme) for scheme in external_schemes)


def is_anchor_only(url: str) -> bool:
    """
    Check if a URL is just an anchor link (starts with #).

    Args:
        url: The URL to check

    Returns:
        True if the URL is just an anchor, False otherwise
    """
    return url.startswith("#")


def split_link_url(link_url: str) -> tuple[str, str | None]:
    """Split a local link into its path/query portion and fragment anchor."""
    path_url, separator, anchor = link_url.partition("#")
    path_url = path_url.split("?", 1)[0]
    return path_url, anchor if separator else None


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
    original_link_url = link_url
    link_url, _ = split_link_url(link_url)

    # An anchor-only link points back to the source file.
    if not link_url:
        return source_file if is_anchor_only(original_link_url) else None

    # Skip external links
    if is_external_link(link_url):
        return None

    # Resolve relative path
    source_dir = source_file.parent
    link_path = (source_dir / link_url).resolve()

    return link_path


def _heading_anchor(heading_text: str) -> str | None:
    """Return the generated anchor for a Markdown heading, if it has one."""
    custom_match = _re_custom_anchor.search(heading_text)
    if custom_match:
        return (custom_match.group(1) or custom_match.group(2)).strip() or None

    # Ignore optional closing hashes in ATX headings, e.g. ``## Title ##``.
    heading_text = re.sub(r"\s+#+\s*$", "", heading_text).strip()
    anchor = re.sub(r"\s+", "-", heading_text.lower())
    anchor = "".join(character for character in anchor if character.isalnum() or character == "-")
    return anchor or None


def extract_anchors(file_path: Path) -> set[str] | None:
    """Extract generated and explicit anchors from a Markdown/MDX file."""
    try:
        with open(file_path, encoding="utf-8-sig") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Warning: Could not read {file_path} to check anchors: {e}")
        return None

    anchors = set()
    in_fence = False
    fence_char = None

    for line in lines:
        fence_match = _re_fence.match(line)
        if fence_match:
            marker = fence_match.group(1)
            marker_char = marker[0]
            if not in_fence:
                in_fence = True
                fence_char = marker_char
            elif marker_char == fence_char:
                in_fence = False
                fence_char = None
            continue

        if in_fence:
            continue

        for html_match in _re_html_anchor.finditer(line):
            anchor = html_match.group(1) or html_match.group(2)
            if anchor:
                anchors.add(anchor)

        heading_match = _re_heading.match(line)
        if heading_match:
            anchor = _heading_anchor(heading_match.group(1))
            if anchor:
                anchors.add(anchor)
            continue

    return anchors


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

    # If the link has no extension or an .html extension, try adding .md or .mdx
    if link_path.suffix in ("", ".html"):
        # Try with .md extension
        md_path = link_path.with_suffix(".md")
        if md_path.exists():
            return md_path

        # Try with .mdx extension
        mdx_path = link_path.with_suffix(".mdx")
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
    anchor_cache: dict[Path, set[str] | None] = {}

    try:
        with open(file_path, encoding="utf-8-sig") as f:
            lines = f.readlines()

        for line_num, line in enumerate(lines, start=1):
            # Find all markdown links in the line
            for match in _re_md_link.finditer(line):
                link_text, link_url = match.groups()

                # Skip external links. Anchor-only links are checked against the
                # headings and explicit IDs in the current file.
                if is_external_link(link_url):
                    continue

                # Count this as an internal link
                total_links += 1

                # Resolve the link path
                link_path = resolve_link_path(file_path, link_url)
                if link_path is None:
                    continue

                # Check if target exists
                target = find_target_file(link_path)
                _, anchor = split_link_url(link_url)
                anchor_exists = True
                if target is not None and anchor and target.is_file():
                    if target not in anchor_cache:
                        anchor_cache[target] = extract_anchors(target)
                    target_anchors = anchor_cache[target]
                    # A read failure is already reported as a warning, so do
                    # not turn it into a false broken-anchor result.
                    anchor_exists = target_anchors is None or anchor in target_anchors

                if target is None or not anchor_exists:
                    broken_links.append((link_text, link_url, line_num))

    except Exception as e:
        # If we can't read the file, report it as a warning but don't fail
        print(f"Warning: Could not read {file_path}: {e}")

    return broken_links, total_links


def check_links(doc_folder: str | Path, max_workers: int | None = None, show_progress: bool = True) -> LinkCheckResult:
    """
    Check all internal links in documentation files.

    Args:
        doc_folder: Path to the documentation folder
        max_workers: Maximum number of parallel workers (default: auto-detect CPU count)
        show_progress: Show progress bar during checking (default: True, requires tqdm)

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

    # Check files in parallel using ProcessPoolExecutor to bypass GIL
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
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
