# Copyright 2026 The HuggingFace Team. All rights reserved.
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
Read and rewrite the prose of a built doc page (`<page>.html` from `doc-builder build --html`).

A built page is line 1 (`<meta name="hf:doc:metadata">`, read by moon-landing) followed by the
SvelteKit-rendered fragment. The fragment hydrates against the page's JS, so translation only
changes text, never tags:

- Every block (paragraph, list item, heading, table cell) is translated as one unit.
- In a *static* block (no Svelte hydration markers `<!--…-->` inside), the links, code and
  formatting may be moved to fit the target language's word order: hydration never walks into it.
- In a block with markers (headings, docstring parameters), only the text nodes between the
  inline elements are replaced, in their original order.
"""

import html
import json
import re
from dataclasses import dataclass, field

TAG_RE = re.compile(r"<(?:[^>\"']|\"[^\"]*\"|'[^']*')*>")
TOKEN_RE = re.compile(r"<!--.*?-->|" + TAG_RE.pattern + r"|[^<]+", re.S)
BLOCK_TAGS = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th", "dt", "dd", "figcaption"}
# Prose outside any block (e.g. raw HTML in the docs: `<div>Title</div> <a>link</a>`) is translated with its
# nearest `div` as the block, when hydration never walks into that div.
LOOSE_TEXT_CONTAINER = "div"
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
# Content of these elements is never prose.
CODE_TAGS = {"pre", "code", "kbd", "script", "style", "svg", "math"}
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
METADATA_RE = re.compile(r'(<meta name="hf:doc:metadata" content=")(\{.*?\})(")')


@dataclass
class TextNode:
    start: int
    end: int
    raw: str


@dataclass
class Block:
    tag: str
    start: int  # offsets of the block's inner HTML in the page body
    end: int
    nodes: list[TextNode] = field(default_factory=list)
    anchor: str | None = None  # heading id, used to translate the page metadata
    has_children: bool = False  # contains other blocks, e.g. a list item with a nested list
    loose: bool = False  # a LOOSE_TEXT_CONTAINER holding prose outside any other block


def split_page(page):
    """Returns `(metadata_line, body)`; moon-landing splits a page at its first newline."""
    metadata, _, body = page.partition("\n")
    return metadata, body


def is_hydration_safe(body):
    """
    Pages built before huggingface/doc-builder#851 lose any translation during hydration: their
    docstrings contain stray module scripts and invalid nesting, and headings are text nodes.
    """
    if '<script context="module">' in body:
        return False
    titles = re.findall(r'<h[1-6] class="relative group">.*?</a> <span>(.{0,7})', body, re.S)
    return all(t.startswith("<!---->") for t in titles)


def _tag_name(tag):
    m = re.match(r"</?\s*([A-Za-z][\w:-]*)", tag)
    return m[1].lower() if m else None


def find_blocks(body):
    """Blocks that contain English prose, in document order."""
    stack, blocks, parents = [], [], {}  # stack entries: (tag, block, is_code, end of the opening tag)
    for m in TOKEN_RE.finditer(body):
        token = m[0]
        if token.startswith("<!--"):
            continue
        if token.startswith("</"):
            name = _tag_name(token)
            for i in range(len(stack) - 1, -1, -1):
                if stack[i][0] == name:
                    for _, block, _, _ in stack[i:]:
                        if block is not None:
                            block.end = m.start()
                    del stack[i:]
                    break
        elif token.startswith("<"):
            name = _tag_name(token)
            if name is None or name in VOID_TAGS or token.endswith("/>"):
                continue
            in_code = any(code for _, _, code, _ in stack)
            # monospace elements hold code, e.g. docstring signatures
            is_code = name in CODE_TAGS or "font-mono" in token
            block = None
            if name in BLOCK_TAGS and not in_code and not is_code:
                for _, ancestor, _, _ in stack:
                    if ancestor is not None:
                        ancestor.has_children = True
                block = Block(tag=name, start=m.end(), end=-1)
                blocks.append(block)
            stack.append((name, block, is_code, m.end()))
        elif not any(code for _, _, code, _ in stack):
            block = next((b for _, b, _, _ in reversed(stack) if b is not None), None)
            container = next((i for i in range(len(stack) - 1, -1, -1) if stack[i][0] == LOOSE_TEXT_CONTAINER), None)
            if block is None and container is not None and re.search(r"[A-Za-z]{2}", token):
                name, _, is_code, start = stack[container]
                # blocks made since the div opened are inside it
                block = Block(
                    tag=name, start=start, end=-1, loose=True, has_children=any(b.start >= start for b in blocks)
                )
                blocks.append(block)
                stack[container] = (name, block, is_code, start)
            if block is not None and re.search(r"[A-Za-z]{2}", token):
                block.nodes.append(TextNode(m.start(), m.end(), token))
                parents[m.start()] = stack[-1][0]
    blocks = [b for b in blocks if b.nodes and b.end >= 0]
    # a loose block with hydration markers holds component output, not raw HTML
    blocks = sorted((b for b in blocks if not (b.loose and "<!--" in body[b.start : b.end])), key=lambda b: b.start)
    for b in blocks:
        if b.tag in HEADING_TAGS:
            anchor = re.search(r'<a id="([^"]+)"', body[b.start : b.end])
            b.anchor = anchor[1] if anchor else None
        # a docstring parameter starts with its name in <strong>: an identifier, not prose
        first = b.nodes[0]
        if (
            parents[first.start] == "strong"
            and not is_static(body, b)
            and not visible_text(body[b.start : first.start])
        ):
            b.nodes.pop(0)
    return [b for b in blocks if b.nodes]


def is_static(body, block):
    """
    Whether the whole block can be re-emitted with its inline elements moved: hydration never walks
    into it, and it contains no other block (which is translated, and replaced, on its own).
    """
    return not block.has_children and "<!--" not in body[block.start : block.end]


def html_region(body, block):
    """
    `(start, end)` of the `{@html …}` content that holds all of a block's prose, or None.

    Svelte renders `{@html x}` as the only child of an element as `<span><!---->x<!----></span>` and
    adopts that content as is during hydration, so it can be translated like a static block, with
    its inline elements moved (e.g. docstring parameter descriptions and headings).
    """
    if block.has_children:
        return None
    inner = body[block.start : block.end]
    comments = list(re.finditer(r"<!--.*?-->", inner, re.S))
    for first, second in zip(comments, comments[1:], strict=False):
        start, end = block.start + first.end(), block.start + second.start()
        if (
            first[0] == second[0] == "<!---->"
            and inner[: first.start()].endswith(">")
            and not inner[: first.start()].endswith("/>")
            and re.match(r"<[A-Za-z]", inner[inner.rfind("<", 0, first.start()) :])  # right after an opening tag
            and inner[second.end() :].startswith("</")  # right before its closing tag
            and all(start <= n.start and n.end <= end for n in block.nodes)
        ):
            return start, end
    return None


def visible_text(fragment):
    fragment = re.sub(r"<(svg|script|style)\b.*?</\1>", "", fragment, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", "", fragment))).strip()


# --------------------------------------------------------------------- static blocks: markup


def to_markup(inner, freeze_leading_strong=False):
    """
    Static block inner HTML -> `(markup, elements)`.

    Links and formatting become `<tN>…</tN>`, line breaks and images `<tN/>`, code `<cN>…</cN>`
    (content shown for context, restored verbatim). Text is HTML-escaped. With
    `freeze_leading_strong`, a leading `<strong>` (a docstring parameter name) is kept as code.
    """
    elements, out, stack = {}, [], []
    tokens = [m[0] for m in TOKEN_RE.finditer(inner)]
    first = next((i for i, t in enumerate(tokens) if t.strip()), None)
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("<!--"):
            raise ValueError("Block has hydration markers")
        if token.startswith("</"):
            n = stack.pop()
            elements[n]["close"] = token
            out.append(f"</t{n}>")
        elif token.startswith("<"):
            name, n = _tag_name(token), len(elements)
            frozen = freeze_leading_strong and i == first and name == "strong"
            if name in VOID_TAGS or token.endswith("/>"):
                elements[n] = {"open": token, "close": ""}
                out.append(f"<t{n}/>")
            elif name in CODE_TAGS or frozen:
                depth, j = 1, i + 1
                while depth:
                    if _tag_name(tokens[j]) == name and not tokens[j].endswith("/>"):
                        depth += -1 if tokens[j].startswith("</") else 1
                    j += 1
                raw = "".join(tokens[i:j])
                elements[n] = {"raw": raw}
                out.append(f"<c{n}>{html.escape(visible_text(raw), quote=False)}</c{n}>")
                i = j
                continue
            else:
                elements[n] = {"open": token}
                stack.append(n)
                out.append(f"<t{n}>")
        else:
            out.append(html.escape(html.unescape(token), quote=False))
        i += 1
    return "".join(out), elements


def markup_structure(markup):
    """`(shape of each tag: kind, self-closing, parent; code contents)`; raises ValueError on malformed markup."""
    parent, code, stack = {}, {}, []
    for m in re.finditer(r"<(/?)([tc])(\d+)(/?)>|[<>]", markup):
        if m[0] in "<>":
            raise ValueError("unescaped < or > in text")
        closing, kind, n, self_closing = m[1], m[2], int(m[3]), m[4]
        if closing:
            # a closing tag must close the innermost open tag of the same kind and number
            if self_closing or not stack or stack[-1][:2] != (kind, n):
                raise ValueError(f"misnested </{kind}{n}>")
            _, _, start = stack.pop()
            if kind == "c":
                content = markup[start : m.start()]
                if code.setdefault(n, content) != content:
                    raise ValueError("code was changed")
        else:
            here = stack[-1][1] if stack else None
            # the shape catches a link turned into a self-closing tag, which would leave its <a> unclosed
            shape = (kind, bool(self_closing), here)
            # code may be mentioned twice (e.g. "the former" spelled out) with the same shape; links may not
            if n in parent and not (kind == "c" and parent[n] == shape):
                raise ValueError(f"duplicated or changed tag <{kind}{n}>")
            parent[n] = shape
            if not self_closing:
                stack.append((kind, n, m.end()))
    if stack:
        raise ValueError("unclosed tag")
    return parent, code


def drop_invented_tags(source, translated):
    """
    Remove tags the source doesn't have, keeping their content: models wrap names in code tags of
    their own (`<cN>ByteFallback</cN>`) or a whole answer in an element (`<comment id="c1">…`).
    Source text is HTML-escaped, so any other raw tag in an answer was invented.
    """
    known = set(re.findall(r"</?([tc]\d+)/?>", source))
    return re.sub(r"</?([A-Za-z][\w:-]*)(?:\s[^<>]*)?/?>", lambda m: m[0] if m[1] in known else "", translated).strip()


def check_markup(source, translated):
    """Raises ValueError unless `translated` keeps every tag of `source` with the same nesting and code."""
    want_parent, want_code = markup_structure(source)
    parent, code = markup_structure(translated)
    if parent != want_parent:
        raise ValueError("tags were dropped, added or nested differently")
    if code != want_code:
        raise ValueError("code was changed")

    def outside_code(markup):
        return html.unescape(re.sub(r"<c(\d+)>.*?</c\1>", "", markup, flags=re.S))

    for content in want_code.values():
        content = html.unescape(content)
        # prose may mention code too (e.g. "-100"); only an extra occurrence is a duplicate
        if len(content) > 3 and outside_code(translated).count(content) > outside_code(source).count(content):
            raise ValueError(f"code {content!r} repeated outside its tag")


def from_markup(markup, elements):
    out, pos = [], 0
    for m in re.finditer(r"<c(\d+)>.*?</c\1>|<(/?)t(\d+)/?>", markup, re.S):
        out.append(html.escape(html.unescape(markup[pos : m.start()]), quote=False))
        if m[1] is not None:
            out.append(elements[int(m[1])]["raw"])
        else:
            element = elements[int(m[3])]
            out.append(element["close"] if m[2] else element["open"])
        pos = m.end()
    out.append(html.escape(html.unescape(markup[pos:]), quote=False))
    return "".join(out)


# ------------------------------------------------------- blocks with markers: text segments


def _split_node(node):
    """`(fixed prefix, prose, trailing whitespace)` of a text node, unescaped.

    Punctuation before the first letter (e.g. `) — ` after a docstring type) is structure,
    not prose, so it is never sent to the model.
    """
    text = html.unescape(node.raw)
    prefix = re.match(r"[^A-Za-z]*", text)[0]
    trail = re.search(r"\s*$", text)[0]
    return prefix, text[len(prefix) : len(text) - len(trail)], trail


def segments(body, block):
    """Numbered text nodes, interleaved with the fixed visible text around them."""
    out, pos = [], block.start
    for i, node in enumerate(block.nodes):
        prefix, prose, _ = _split_node(node)
        if fixed := " ".join(filter(None, [visible_text(body[pos : node.start]), prefix.strip()])):
            out.append({"fixed": fixed})
        out.append({"id": i, "text": prose})
        pos = node.end
    if fixed := visible_text(body[pos : block.end]):
        out.append({"fixed": fixed})
    return out


def replace_text_nodes(block, translations):
    """Edits `(start, end, html)` replacing the prose of each text node; prefixes and whitespace stay."""
    edits = []
    for i, node in enumerate(block.nodes):
        prefix, _, trail = _split_node(node)
        text = translations[str(i)].strip()
        # the prefix is kept as is; a model that repeats its punctuation would double it (", , ")
        mark = prefix.rstrip()[-1:]
        if mark in (",", ".", ";", ":") and text.startswith(mark):
            text = text[1:].lstrip()
        # never empty: removing a text node could shift Svelte's hydration walk
        edits.append((node.start, node.end, html.escape(prefix + (text or " ") + trail, quote=False)))
    return edits


def apply_edits(body, edits):
    for start, end, new in sorted(edits, key=lambda e: e[0], reverse=True):
        body = body[:start] + new + body[end:]
    return body


# --------------------------------------------------------------------------- page level


def rewrite_links(body, library, version, language):
    """Point page links at the translated folder; `_app` assets stay on the English build."""
    source = f'href="/docs/{library}/{version}/en/'
    return re.sub(re.escape(source) + r"(?!_app/)", f'href="/docs/{library}/{version}/{language}/', body)


def translate_metadata(metadata_line, titles_by_anchor):
    """
    Translate the titles of the page metadata (page title and heading menu) by heading anchor.

    Titles are replaced in place: moon-landing decodes this attribute with its own unescaping,
    so the rest of the encoded JSON must stay byte-identical.
    """
    if not METADATA_RE.search(metadata_line):
        raise ValueError("Page has no hf:doc:metadata")
    pair = re.compile(
        r"&quot;title&quot;:&quot;((?:(?!&quot;).)*)&quot;,&quot;local&quot;:&quot;((?:(?!&quot;).)*)&quot;"
    )

    def replace(m):
        anchor = html.unescape(m[2])
        if anchor not in titles_by_anchor:
            return m[0]
        encoded = json.dumps(titles_by_anchor[anchor], ensure_ascii=False)[1:-1]
        encoded = html.escape(encoded, quote=False).replace('"', "&quot;")
        return f"&quot;title&quot;:&quot;{encoded}&quot;,&quot;local&quot;:&quot;{m[2]}&quot;"

    return pair.sub(replace, metadata_line)


def page_title(metadata_line):
    m = METADATA_RE.search(metadata_line)
    return json.loads(html.unescape(m[2])).get("title") if m else None
