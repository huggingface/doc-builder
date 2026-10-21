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
Read and rewrite the prose of a built doc page's Markdown (`<page>.md`, served by moon-landing for
"Copy page" and `Accept: text/plain`).

The page is split into units: paragraphs, list items, blockquote paragraphs, table cells and
heading text. Fenced code, heading anchors, list markers, quote prefixes and table pipes are kept
as is. Inside a unit, inline code, images, autolinks and URLs are frozen; link text and emphasis
become movable tags of the same light markup as the HTML (see `translate_html.to_markup`), so the
same model prompt, validation and cache apply.
"""

import html
import re
from concurrent.futures import ThreadPoolExecutor

FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
HEADING_RE = re.compile(r"^(#{1,6} +)(.*?)((?:\[\[[^\]]+\]\])?\s*)$")
LIST_RE = re.compile(r"^(\s*(?:[-*+]|\d+[.)]) +)(.*)$")
QUOTE_RE = re.compile(r"^(\s*>+ ?)(.*)$")
TABLE_RE = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
ADMONITION_RE = re.compile(r"^\[!\w+\]\s*$")
# a docstring parameter: `name (`type`, *optional*) : description`
PARAMETER_RE = re.compile(r"^([A-Za-z_][\w.]*) (?=\(|: )")

INLINE_RE = re.compile(
    r"(?P<code>(`+)(?:(?!\2).)+?\2)"
    r"|(?P<image>!\[[^\]]*\]\((?:[^()\s]|\([^()]*\))*\))"
    r"|(?P<autolink><https?://[^>\s]+>)"
    r"|(?P<tag></?[A-Za-z][^<>]*>)"
    r"|(?P<escape>\\[!-/:-@\[-`{-~])"
    r"|(?P<link>\[(?P<text>(?:[^\[\]]|\[[^\[\]]*\])*)\]\((?P<url>(?:[^()\s]|\([^()]*\))*(?:\s+\"[^\"]*\")?)\))"
    r"|(?P<strong>(?P<strong_delimiter>\*\*|__)(?=\S)(?P<strong_text>.+?)(?<=\S)(?P=strong_delimiter))"
    r"|(?P<em>(?<![\w*])\*(?=[^\s*])(?P<em_text>[^*]+?)(?<=\S)\*(?![\w*])|(?<!\w)_(?=\S)(?P<em_text2>[^_]+?)(?<=\S)_(?!\w))",
    re.S,
)


def has_prose(text):
    """Whether inline Markdown has English words outside code, URLs and other frozen parts."""
    markup, _ = to_markup(text)
    return bool(re.search(r"[A-Za-z]{2}", re.sub(r"<c(\d+)>.*?</c\1>|</?t\d+/?>", "", markup, flags=re.S)))


class Unit:
    """A translatable piece of a Markdown page: `prefix` + inline Markdown `text` + `suffix`."""

    def __init__(self, prefix, text, suffix="", frozen=""):
        self.prefix, self.text, self.suffix, self.frozen = prefix, text, suffix, frozen


def parse(md):
    """Split a page into raw strings and `Unit`s, in order; joining them back gives the page."""
    trailing_newline = md.endswith("\n")
    lines = (md[:-1] if trailing_newline else md).split("\n")
    out, i = [], 0

    def unit(prefix, text, suffix=""):
        # keep a docstring parameter's name out of the prose
        m = PARAMETER_RE.match(text)
        frozen = m[0] if m else ""
        out.append(Unit(prefix + frozen, text[len(frozen) :], suffix))

    while i < len(lines):
        line = lines[i]
        if m := FENCE_RE.match(line):
            fence = m[1]
            j = i + 1
            while j < len(lines) and not re.match(rf"^\s*{re.escape(fence[0])}{{{len(fence)},}}\s*$", lines[j]):
                j += 1
            out.append("\n".join(lines[i : j + 1]) + "\n")
            i = j + 1
            continue
        if not line.strip():
            out.append(line + "\n")
            i += 1
            continue
        if m := HEADING_RE.match(line):
            unit(m[1], m[2], m[3] + "\n")
            i += 1
            continue
        if TABLE_RE.match(line):
            if TABLE_SEPARATOR_RE.match(line):
                out.append(line + "\n")
            else:
                cells = re.split(r"(?<!\\)(\|)", line)
                for piece in cells:
                    if piece == "|" or not piece.strip():
                        out.append(piece)
                    else:
                        lead, trail = re.match(r"\s*", piece)[0], re.search(r"\s*$", piece)[0]
                        out.append(Unit(lead, piece.strip(), trail))
                out.append("\n")
            i += 1
            continue
        if m := QUOTE_RE.match(line):
            prefix, text = m[1], m[2]
            if fence := FENCE_RE.match(text):
                # a code block inside a quote: kept verbatim up to its closing fence
                close = rf"^\s*{re.escape(fence[1][0])}{{{len(fence[1])},}}\s*$"
                j = i + 1
                while j < len(lines) and (q := QUOTE_RE.match(lines[j])) and not re.match(close, q[2]):
                    j += 1
                out.append("\n".join(lines[i : j + 1]) + "\n")
                i = j + 1
                continue
            if not text.strip() or ADMONITION_RE.match(text.strip()):
                out.append(line + "\n")
                i += 1
                continue
            j = i + 1
            while (
                j < len(lines)
                and (q := QUOTE_RE.match(lines[j]))
                and q[2].strip()
                and not ADMONITION_RE.match(q[2].strip())
                and not FENCE_RE.match(q[2])
            ):
                text += " " + q[2].strip()
                j += 1
            unit(prefix, text, "\n")
            i = j
            continue
        if m := LIST_RE.match(line):
            prefix, text = m[1], m[2]
            j = i + 1
            while (
                j < len(lines)
                and lines[j].strip()
                and lines[j].startswith(" ")
                and not LIST_RE.match(lines[j])
                and not FENCE_RE.match(lines[j])
            ):
                text += " " + lines[j].strip()
                j += 1
            unit(prefix, text, "\n")
            i = j
            continue
        # paragraph: until a blank line or another block starts
        text, j = line.strip(), i + 1
        lead = re.match(r"\s*", line)[0]
        while (
            j < len(lines)
            and lines[j].strip()
            and not any(r.match(lines[j]) for r in (FENCE_RE, HEADING_RE, LIST_RE, QUOTE_RE, TABLE_RE))
        ):
            text += " " + lines[j].strip()
            j += 1
        if has_prose(text):
            unit(lead, text, "\n")
        else:
            out.append("\n".join(lines[i:j]) + "\n")
        i = j
    if not trailing_newline and out:
        last = out[-1]
        if isinstance(last, str) and last.endswith("\n"):
            out[-1] = last[:-1]
        elif isinstance(last, Unit) and last.suffix.endswith("\n"):
            last.suffix = last.suffix[:-1]
    return out


def to_markup(text):
    """Inline Markdown -> `(markup, elements)` in the light markup of `translate_html.to_markup`."""
    elements, out = {}, []

    def visit(s):
        pos = 0
        for m in INLINE_RE.finditer(s):
            out.append(html.escape(s[pos : m.start()], quote=False))
            n = len(elements)
            if m["link"] is not None:
                elements[n] = {"open": "[", "close": f"]({m['url']})"}
                out.append(f"<t{n}>")
                visit(m["text"])
                out.append(f"</t{n}>")
            elif m["strong"] is not None:
                elements[n] = {"open": m["strong_delimiter"], "close": m["strong_delimiter"]}
                out.append(f"<t{n}>")
                visit(m["strong_text"])
                out.append(f"</t{n}>")
            elif m["em"] is not None:
                delimiter = m["em"][0]
                elements[n] = {"open": delimiter, "close": delimiter}
                out.append(f"<t{n}>")
                visit(m["em_text"] if m["em_text"] is not None else m["em_text2"])
                out.append(f"</t{n}>")
            else:  # code, image, autolink, inline HTML, escape: kept verbatim
                raw = m[0]
                elements[n] = {"raw": raw}
                shown = raw.strip("`") if m["code"] is not None else raw
                out.append(f"<c{n}>{html.escape(shown, quote=False)}</c{n}>")
            pos = m.end()
        out.append(html.escape(s[pos:], quote=False))

    visit(text)
    return "".join(out), elements


def from_markup(markup, elements):
    out, pos = [], 0
    for m in re.finditer(r"<c(\d+)>.*?</c\1>|<(/?)t(\d+)/?>", markup, re.S):
        out.append(html.unescape(markup[pos : m.start()]))
        if m[1] is not None:
            out.append(elements[int(m[1])]["raw"])
        else:
            element = elements[int(m[3])]
            out.append(element["close"] if m[2] else element["open"])
        pos = m.end()
    out.append(html.unescape(markup[pos:]))
    return "".join(out)


def rewrite_links(md, library, version, language):
    """Point page links at the translated folder, as in the HTML."""
    source = f"](/docs/{library}/{version}/en/"
    return md.replace(source, f"](/docs/{library}/{version}/{language}/")


def translate_md(md, translate_markup, library, version, language, workers=8):
    """
    Translate a page's Markdown; `translate_markup` translates one unit's markup (raising on
    failure). Returns `(markdown, units, units_kept_in_english)`; a failed unit stays in English.
    """
    from .translate_model import TranslationFailed

    pieces = parse(md)
    units = [p for p in pieces if isinstance(p, Unit) and has_prose(p.text)]

    def work(unit):
        markup, elements = to_markup(unit.text)
        try:
            return from_markup(translate_markup(markup), elements)
        except TranslationFailed as exc:
            print(f"  kept in English ({exc}): {unit.text[:80]!r}")
            return None

    with ThreadPoolExecutor(workers) as pool:
        results = list(pool.map(work, units))
    translated = {id(u): r for u, r in zip(units, results, strict=True) if r is not None}
    failed = len(units) - len(translated)
    result = "".join(p if isinstance(p, str) else p.prefix + translated.get(id(p), p.text) + p.suffix for p in pieces)
    return rewrite_links(result, library, version, language), len(units), failed
