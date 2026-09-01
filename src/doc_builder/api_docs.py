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

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

_BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "br",
    "dd",
    "div",
    "dl",
    "dt",
    "figcaption",
    "figure",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "ul",
}
_SKIPPED_TAGS = {"pre", "script", "style", "svg"}
_VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
_DETAIL_SECTION = re.compile(
    r"^(?:args?|arguments?|attributes?|class attributes?|components?|example(?:s| usage)?|inputs?|outputs?|"
    r"parameters?|raises?|returns?|usage(?: example)?|yields?)(?:\s*:.*)?$",
    re.IGNORECASE,
)
_PARAMETER_DEFINITION = re.compile(
    r"^[A-Za-z_][\w.]*"
    r"(?:\s*,\s*[A-Za-z_][\w.]*)*"
    r"\s+\(.*\)\s*(?::|—|–|-)\s*"
)


@dataclass
class _Docstring:
    root_depth: int
    order: int
    api_id: str | None = None
    body: list[str] = field(default_factory=list)
    signature_started: bool = False
    signature_done: bool = False
    nested_docstrings: int = 0


@dataclass
class _Element:
    tag: str
    docstring: _Docstring | None = None
    signature_for: list[_Docstring] = field(default_factory=list)
    skipped: bool = False


def _normalize_body(parts: list[str]) -> str:
    lines = []
    for line in "".join(parts).splitlines():
        normalized = re.sub(r"\s+", " ", line).strip()
        if not normalized:
            continue
        if (
            normalized.lower() == "copied"
            or _DETAIL_SECTION.match(normalized)
            or _PARAMETER_DEFINITION.match(normalized)
        ):
            break
        lines.append(normalized)
    return "\n".join(lines)


class _APIDocstringParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._elements: list[_Element] = []
        self._docstrings: list[_Docstring] = []
        self._skipped_depth = 0
        self.results: list[tuple[int, str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        self._open_element(tag, attrs, is_void=tag in _VOID_TAGS)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]):
        self._open_element(tag, attrs, is_void=True)

    def handle_endtag(self, tag: str):
        matching_index = next(
            (index for index in range(len(self._elements) - 1, -1, -1) if self._elements[index].tag == tag),
            None,
        )
        if matching_index is None:
            return

        closing_elements = self._elements[matching_index:]
        del self._elements[matching_index:]
        for element in reversed(closing_elements):
            self._close_element(element)

    def _close_element(self, element: _Element):
        if element.skipped:
            self._skipped_depth -= 1

        for docstring in element.signature_for:
            docstring.signature_done = True

        if element.docstring is not None:
            docstring = element.docstring
            self.results.append((docstring.order, docstring.api_id or "", _normalize_body(docstring.body)))
            self._docstrings.remove(docstring)
            for parent in self._docstrings:
                parent.nested_docstrings -= 1

        if element.tag in _BLOCK_TAGS:
            self._append_breaks()

    def handle_data(self, data: str):
        if self._skipped_depth:
            return
        for docstring in self._docstrings:
            if self._captures_body(docstring):
                docstring.body.append(data)

    def _open_element(self, tag: str, attrs: list[tuple[str, str | None]], is_void: bool):
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        is_docstring = "docstring" in classes

        signature_for = []
        for docstring in self._docstrings:
            if not docstring.signature_started and len(self._elements) == docstring.root_depth:
                docstring.signature_started = True
                signature_for.append(docstring)

        if is_docstring:
            for parent in self._docstrings:
                parent.nested_docstrings += 1
        elif tag in _BLOCK_TAGS:
            self._append_breaks()

        api_id = attributes.get("id")
        if api_id:
            for docstring in self._docstrings:
                if docstring.signature_started and not docstring.signature_done and docstring.api_id is None:
                    docstring.api_id = api_id

        element = _Element(
            tag=tag,
            signature_for=signature_for,
            skipped=tag in _SKIPPED_TAGS,
        )

        if is_docstring:
            docstring = _Docstring(
                root_depth=len(self._elements) + 1,
                order=len(self.results) + len(self._docstrings),
            )
            element.docstring = docstring
            self._docstrings.append(docstring)

        if element.skipped:
            self._skipped_depth += 1

        if is_void:
            if element.skipped:
                self._skipped_depth -= 1
            for docstring in signature_for:
                docstring.signature_done = True
            if tag in _BLOCK_TAGS:
                self._append_breaks()
            return

        self._elements.append(element)

    def _append_breaks(self):
        if self._skipped_depth:
            return
        for docstring in self._docstrings:
            if self._captures_body(docstring):
                docstring.body.append("\n")

    @staticmethod
    def _captures_body(docstring: _Docstring) -> bool:
        return docstring.signature_done and docstring.nested_docstrings == 0


def extract_api_docstrings(html: str) -> list[tuple[str, str]]:
    parser = _APIDocstringParser()
    parser.feed(html)
    parser.close()
    return [(api_id, body) for _, api_id, body in sorted(parser.results)]
