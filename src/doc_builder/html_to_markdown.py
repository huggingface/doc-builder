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
Turn the HTML left in a generated MDX page into Markdown, for the `.md` version of the page
(served to agents, "Copy page", llms.txt).

- Raw HTML blocks (cards, grids, tables, lists, ...) are rendered the way a reader sees them:
  links, images, list items, table rows and headings become their Markdown equivalent, and
  the indentation of the HTML source is dropped (left as is, it turns lines into code blocks).
- Tab groups (`<hfoptions>`, `<frameworkcontent>`) keep the label of each tab, so the
  alternatives can be told apart.
- Svelte components (`<Tip>`, `<EditOnGithub/>`, ...) lose their tags; their content is Markdown
  and stays as such.
- Fenced code and inline code are never touched.
"""

import html
import re
import textwrap
from html.parser import HTMLParser

# Code is stashed away while the HTML is converted, behind placeholders made of private-use
# characters: they can't appear in the docs, and the HTML parser treats them as text.
_STASH_OPEN, _STASH_CLOSE = chr(0xE000), chr(0xE001)
_FENCE_PLACEHOLDER_RE = re.compile(f"{_STASH_OPEN}F\\d+{_STASH_CLOSE}")
_STASHED_RE = re.compile(f"{_STASH_OPEN}[FC](\\d+){_STASH_CLOSE}")
# A line break (`<br>`) while inline content is assembled, so that collapsing whitespace keeps it.
_LINE_BREAK = chr(0xE002)
# Where a callout (a `<Tip>`) starts and ends, until its content is final Markdown that can be quoted.
_CALLOUT_START, _CALLOUT_END = chr(0xE003), chr(0xE004)
_CALLOUT_RE = re.compile(
    f"^([ \\t]*){_CALLOUT_START}(\\w+)\\n((?:(?!{_CALLOUT_START}).)*?)\\n[ \\t]*{_CALLOUT_END}$",
    re.DOTALL | re.MULTILINE,
)

_FENCED_CODE_RE = re.compile(
    r"^[ \t]*(?:>[ \t]?)*(`{3,}|~{3,})[^\n]*\n(?:.*?\n)??[ \t]*(?:>[ \t]?)*\1[`~]*[ \t]*$", re.DOTALL | re.MULTILINE
)
# A code span may go on over the next lines of its paragraph, not across a blank line.
_INLINE_CODE_RE = re.compile(r"`[^`\n]+(?:\n[^`\n]+)*`")
_COMMENT_RE = re.compile(r"<!--(?!\s*(?:WRAP CODE BLOCKS|STRETCH TABLES)\s*-->).*?-->", re.DOTALL)

# Attribute values may contain `>`: quoted strings, and svelte expressions (with one level of nested braces).
_ATTRS = r"""(?:[^<>"'{}]|"[^"]*"|'[^']*'|\{(?:[^{}]|\{[^{}]*\})*\})*"""
# `/` only right before `>`: `<https://...>` is an autolink, not a tag.
_TAG_RE = re.compile(rf"<(/?)([A-Za-z][\w.:-]*)(?=\s|/?>)({_ATTRS})>")
_TAG_LINE_START_RE = re.compile(r"[ \t]*</?[A-Za-z][\w.:-]*(?=\s|/?>|$)")
_ATTR_RE = re.compile(r"""([\w:.-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))""")

_ID_ATTR = r"""\s+id=(?:"([^"]*)"|'([^']*)')\s*"""
_HFOPTIONS_RE = re.compile(rf"<hfoptions{_ID_ATTR}>(.*?)</hfoptions>", re.DOTALL)
_HFOPTION_RE = re.compile(rf"<hfoption{_ID_ATTR}>(.*?)</hfoption>", re.DOTALL)
_FRAMEWORKCONTENT_RE = re.compile(r"<frameworkcontent>(.*?)</frameworkcontent>", re.DOTALL)
_FRAMEWORKS = (("pt", "PyTorch"), ("tf", "TensorFlow"), ("jax", "JAX"))
# Lowercase tags of doc-builder components (the other components are capitalized, like svelte's).
_COMPONENT_TAGS = {"hfoptions", "hfoption", "frameworkcontent", "pt", "tf", "jax", "anchor"}

_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
# Elements whose content isn't text the reader sees.
_DROPPED = {"script", "style", "svg", "math", "noscript", "template", "head", "title", "colgroup", "col", "button"}
_DROPPED |= {"input", "select", "textarea", "meta", "link", "base", "track", "area", "map", "canvas", "object"}
_BLOCK = {"address", "article", "aside", "blockquote", "body", "caption", "center", "dd", "details", "dialog"}
_BLOCK |= {"div", "dl", "dt", "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5"}
_BLOCK |= {"h6", "header", "hgroup", "hr", "li", "main", "menu", "nav", "ol", "p", "pre", "section", "summary"}
_BLOCK |= {"table", "tbody", "td", "tfoot", "th", "thead", "tr", "ul", "video", "audio", "iframe", "embed"}
_INLINE = {"a", "abbr", "b", "bdi", "bdo", "big", "br", "cite", "code", "data", "del", "dfn", "em", "font", "html"}
_INLINE |= {"i", "img", "ins", "kbd", "label", "mark", "nobr", "picture", "q", "s", "samp", "small", "source"}
_INLINE |= {"span", "strike", "strong", "sub", "sup", "time", "tt", "u", "var", "wbr"}
_HTML_TAGS = _VOID | _DROPPED | _BLOCK | _INLINE
_EMPHASIS = {"strong": "**", "b": "**", "em": "*", "i": "*", "s": "~~", "del": "~~", "strike": "~~"}
_CODE = {"code", "kbd", "samp", "tt"}
_MEDIA = {"video", "audio", "iframe", "embed"}


def _split_space(text):
    """`text` as (leading space, content, trailing space), the spaces reduced to one."""
    match = re.fullmatch(r"(\s*)(.*?)(\s*)", text, re.DOTALL)
    lead, body, trail = match.groups()
    return (" " if lead else ""), body, (" " if trail else "")


def _wrap(text, marker):
    lead, body, trail = _split_space(text)
    return f"{lead}{marker}{body}{marker}{trail}" if body else lead or trail


def _url(value):
    return value.strip().replace(" ", "%20")


def _link(text, href):
    lead, body, trail = _split_space(text)
    if not href or not body:
        return text
    return f"{lead}[{body}]({_url(href)}){trail}"


def _image(src, alt):
    return f"![{_collapse(alt).strip()}]({_url(src)})" if src and src.strip() else ""


def _code(text):
    return _wrap(text, "``" if "`" in text else "`")


def _collapse(text):
    return re.sub(r"\s+", " ", text) if text else ""


def _finish_inline(text, single_line=False):
    """The inline content of a block: whitespace collapsed, `<br>` kept as a line break."""
    text = _collapse(text)
    if single_line:
        return _collapse(text.replace(_LINE_BREAK, " ")).strip()
    return "\n".join(line.strip() for line in text.split(_LINE_BREAK)).strip()


class _Element:
    __slots__ = ("tag", "attrs", "children", "dropped")

    def __init__(self, tag, attrs):
        self.tag = tag
        self.attrs = {name: value or "" for name, value in attrs}
        self.children = []
        # not text the reader sees, or the dark-mode copy of an image (`class="hidden dark:block"`)
        self.dropped = tag in _DROPPED or _is_dark_mode_copy(self.attrs.get("class", ""))


def _is_dark_mode_copy(classes):
    classes = classes.split()
    return "hidden" in classes and any(name.startswith("dark:") for name in classes)


class _TreeBuilder(HTMLParser):
    """A lenient HTML parser: unclosed elements stay open, stray end tags are ignored."""

    def __init__(self):
        # entities are decoded by hand, to keep `&lt;`/`&gt;`: decoded, they'd read as tags later on
        super().__init__(convert_charrefs=False)
        self.root = _Element("root", ())
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        if tag not in _HTML_TAGS and not attrs:
            # not an HTML element: a placeholder such as `<user>/<repo>` in prose
            self.handle_data(self.get_starttag_text())
            return
        element = _Element(tag, attrs)
        self.stack[-1].children.append(element)
        if tag not in _VOID:
            self.stack.append(element)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(_Element(tag, attrs))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return
        if tag not in _HTML_TAGS:
            self.handle_data(f"</{tag}>")

    def handle_entityref(self, name):
        self.handle_data(f"&{name};" if name in ("lt", "gt") else html.unescape(f"&{name};"))

    def handle_charref(self, name):
        char = html.unescape(f"&#{name};")
        self.handle_data(f"&#{name};" if char in "<>" else char)

    def handle_data(self, data):
        children = self.stack[-1].children
        if children and isinstance(children[-1], str):
            children[-1] += data
        else:
            children.append(data)

    @property
    def open_elements(self):
        return len(self.stack) - 1

    @property
    def inside_tag(self):
        # an unfinished tag (an `<img` whose attributes go on over the next lines) waits in `rawdata`
        return "<" in self.rawdata[self.rawdata.rfind(">") + 1 :]


def _text_content(node):
    if isinstance(node, str):
        return node
    if node.dropped:
        return ""
    if node.tag == "br":
        return "\n"
    return "".join(_text_content(child) for child in node.children)


def _has_block(node):
    for child in node.children:
        if isinstance(child, str):
            if _FENCE_PLACEHOLDER_RE.search(child):
                return True
        elif not child.dropped and (child.tag in _BLOCK or (child.tag not in _VOID and _has_block(child))):
            return True
    return False


class _Renderer:
    def __init__(self, single_line=False):
        # table cells: no line breaks
        self.single_line = single_line

    # Inline content

    def inline(self, children):
        return "".join(self.inline_node(child) for child in children)

    def inline_node(self, node):
        if isinstance(node, str):
            return _collapse(node)
        tag = node.tag
        if node.dropped:
            return ""
        if tag == "br":
            return _LINE_BREAK
        if tag == "img":
            return _image(node.attrs.get("src"), node.attrs.get("alt", ""))
        if tag == "a":
            return _link(self.inline(node.children), node.attrs.get("href", "").strip())
        if tag in _EMPHASIS:
            text = self.inline(node.children)
            marker = _EMPHASIS[tag]
            stripped = text.strip()
            if len(stripped) > 2 * len(marker) and stripped.startswith(marker) and stripped.endswith(marker):
                return text  # `<b><strong>...` would give `****...`
            return _wrap(text, marker)
        if tag in _CODE:
            return _code(_collapse(_text_content(node)))
        if tag in _MEDIA:
            return self.media(node)
        # span, sup, small, label, elements this doesn't know, ...: their content
        return self.inline(node.children)

    def media(self, node):
        src = node.attrs.get("src", "")
        for child in node.children:
            if not src and isinstance(child, _Element) and child.tag == "source":
                src = child.attrs.get("src", "")
        if not src.strip():
            return ""
        label = node.attrs.get("title") or {"video": "Video", "audio": "Audio"}.get(node.tag) or src
        return f"[{_collapse(label).strip()}]({_url(src)})"

    # Block content

    def blocks(self, children):
        """`children` as a list of Markdown blocks (paragraphs, lists, tables, ...)."""
        out, inline = [], []  # inline: (node, its Markdown)

        def flush():
            items = [(node, text) for node, text in inline if not isinstance(node, str) or node.strip()]
            if (
                len(items) > 1
                and not self.single_line
                and all(isinstance(node, _Element) and node.tag == "a" and text.strip() for node, text in items)
            ):
                # links side by side, with nothing else (a menu, a grid of links): a list
                out.append("\n".join(f"- {_finish_inline(text, single_line=True)}" for _, text in items))
            else:
                text = _finish_inline("".join(text for _, text in inline), self.single_line)
                if text:
                    out.append(text)
            inline.clear()

        for child in children:
            if isinstance(child, str):
                # stashed fenced code is a block of its own
                last = 0
                for match in _FENCE_PLACEHOLDER_RE.finditer(child):
                    inline.append((child[last : match.start()], _collapse(child[last : match.start()])))
                    flush()
                    out.append(match.group(0))
                    last = match.end()
                inline.append((child[last:], _collapse(child[last:])))
            elif child.dropped:
                continue
            elif child.tag in _BLOCK or (child.tag not in _VOID and _has_block(child)):
                flush()
                out.extend(self.block(child))
            else:
                inline.append((child, self.inline_node(child)))
        flush()
        return out

    def block(self, node):
        tag = node.tag
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = _finish_inline(self.inline(node.children), single_line=True)
            return [f"{'#' * int(tag[1])} {text}"] if text else []
        if tag == "summary":
            text = _finish_inline(self.inline(node.children), single_line=True)
            return [text if text.startswith("**") and text.endswith("**") else f"**{text}**"] if text else []
        if tag in ("ul", "ol", "menu"):
            return self.list(node)
        if tag == "li":
            return self.list(_Element("ul", ()), items=[node])
        if tag == "table":
            return self.table(node)
        if tag == "pre":
            code = _text_content(node).strip("\n")
            return [f"```\n{code}\n```"] if code.strip() else []
        if tag == "blockquote":
            inner = "\n\n".join(self.blocks(node.children))
            return ["\n".join(f"> {line}" if line else ">" for line in inner.split("\n"))] if inner else []
        if tag == "hr":
            return ["---"]
        if tag in _MEDIA:
            link = self.media(node)
            return [link] if link else []
        if tag == "a":
            return self.block_link(node)
        return self.blocks(node.children)

    def block_link(self, node):
        """A link around blocks (a card): the link goes on its first block, the card's title in practice."""
        blocks = self.blocks(node.children)
        href = node.attrs.get("href", "").strip()
        if not href or not blocks:
            return blocks
        match = re.fullmatch(r"(#+ )?(\*\*)?(.+?)(\*\*)?", blocks[0])
        if not match or "\n" in blocks[0] or _FENCE_PLACEHOLDER_RE.search(blocks[0]):
            return [f"[{href}]({_url(href)})"] + blocks
        heading, title = match.group(1) or "", match.group(3)
        if bool(match.group(2)) != bool(match.group(4)):  # not emphasis after all
            title = (match.group(2) or "") + title + (match.group(4) or "")
        return [f"{heading}[{title}]({_url(href)})"] + blocks[1:]

    def list(self, node, items=None):
        if items is None:
            items = [child for child in node.children if isinstance(child, _Element) and child.tag == "li"]
        start = node.attrs.get("start", "1")
        number = int(start) if start.isdigit() else 1
        rendered, loose = [], False
        for item in items:
            blocks = self.blocks(item.children)
            if not blocks:
                continue
            marker = f"{number}. " if node.tag == "ol" else "- "
            number += 1
            loose = loose or len(blocks) > 1
            lines = "\n\n".join(blocks).split("\n")
            indent = " " * len(marker)
            rendered.append("\n".join([marker + lines[0]] + [indent + line if line else "" for line in lines[1:]]))
        return [("\n\n" if loose else "\n").join(rendered)] if rendered else []

    def table(self, node):
        rows = []

        def collect(element):
            for child in element.children:
                if isinstance(child, _Element):
                    if child.tag == "tr":
                        rows.append(child)
                    elif child.tag in ("thead", "tbody", "tfoot"):
                        collect(child)

        collect(node)
        cell_renderer = _Renderer(single_line=True)
        table = []
        for row in rows:
            cells = []
            for cell in row.children:
                if isinstance(cell, _Element) and cell.tag in ("td", "th"):
                    text = " ".join(cell_renderer.blocks(cell.children)).replace("\n", " ")
                    cells.append(text.replace("|", "\\|"))
                    span = cell.attrs.get("colspan", "1")
                    cells.extend([""] * (int(span) - 1 if span.isdigit() else 0))
            if cells:
                table.append(cells)
        if not table:
            return []
        width = max(len(cells) for cells in table)
        table = [cells + [""] * (width - len(cells)) for cells in table]
        lines = ["| " + " | ".join(table[0]) + " |", "|" + " --- |" * width]
        lines += ["| " + " | ".join(cells) + " |" for cells in table[1:]]
        caption = next((c for c in node.children if isinstance(c, _Element) and c.tag == "caption"), None)
        caption = _finish_inline(self.inline(caption.children), single_line=True) if caption else ""
        return ([caption] if caption else []) + ["\n".join(lines)]


class _CodeStash:
    """Code put aside behind placeholders while the HTML around it is converted."""

    def __init__(self):
        self.code = []

    def stash(self, content):
        def replace(kind):
            def placeholder(match):
                self.code.append(match.group(0))
                return f"{_STASH_OPEN}{kind}{len(self.code) - 1}{_STASH_CLOSE}"

            return placeholder

        content = _FENCED_CODE_RE.sub(replace("F"), content)
        return _INLINE_CODE_RE.sub(replace("C"), content)

    def restore(self, content):
        return _STASHED_RE.sub(lambda m: self.code[int(m.group(1))], content)

    def dedent(self, text):
        """The content of a component as Markdown: without the indentation it has in the component, code included."""
        return self.stash(textwrap.dedent(self.restore(text).strip("\n")).strip("\n"))


def _convert_tab_groups(content, code):
    """Tabs keep their label, as `**Option: <label>**` before their content."""

    def tab(label, body):
        return f"\n\n**Option: {label.strip()}**\n\n{code.dedent(body)}\n\n"

    def hfoptions(match):
        def hfoption(option):
            label = option.group(1) if option.group(1) is not None else option.group(2)
            return tab(label, option.group(3))

        return "\n\n" + _HFOPTION_RE.sub(hfoption, match.group(3)) + "\n\n"

    def frameworkcontent(match):
        tabs = []
        for tag, label in _FRAMEWORKS:
            framework = re.search(rf"<{tag}>(.*?)</{tag}>", match.group(1), re.DOTALL)
            if framework:
                tabs.append(tab(label, framework.group(1)))
        return "\n\n" + "".join(tabs) + "\n\n"

    content = _HFOPTIONS_RE.sub(hfoptions, content)
    return _FRAMEWORKCONTENT_RE.sub(frameworkcontent, content)


def _is_component(name):
    return name[0].isupper() or ":" in name or "." in name or name in _COMPONENT_TAGS


_PAIRED_COMPONENT_RE = re.compile(
    rf"(^[ \t]*)?<([A-Z][\w.:-]*)(?=\s|>)({_ATTRS})(?<!/)>(.*?)</\2>", re.DOTALL | re.MULTILINE
)


def _remove_components(content, code):
    """
    Drop the tags of svelte components. Their content is Markdown and stays, dedented. A `<Tip>`
    becomes a callout (`> [!TIP]`, `> [!WARNING]`), between markers until its content is final.
    """

    def paired(match):
        indent, inner = match.group(1), _remove_components(match.group(4), code)
        if match.group(2) == "Tip":
            kind = "WARNING" if re.search(r"\bwarning\b(?!\s*=\s*\{?\s*false)", match.group(3)) else "TIP"
            indent = indent or ""
            return f"\n\n{indent}{_CALLOUT_START}{kind}\n\n{code.dedent(inner)}\n\n{indent}{_CALLOUT_END}\n\n"
        if indent is not None and "\n" in inner:
            return f"{indent}\n\n{code.dedent(inner)}\n\n"
        return (indent or "") + inner

    content = _PAIRED_COMPONENT_RE.sub(paired, content)
    return _TAG_RE.sub(lambda m: "" if _is_component(m.group(2)) else m.group(0), content)


def _convert_html_blocks(content):
    """
    Render each raw HTML block as Markdown. A block starts on a line that starts with a tag and goes
    on until a blank line, or until the next line is Markdown again: it doesn't start with a tag, and
    all the elements opened so far are closed.
    """
    lines = content.split("\n")
    out, i = [], 0
    while i < len(lines):
        if not _TAG_LINE_START_RE.match(lines[i]):
            out.append(lines[i])
            i += 1
            continue
        builder = _TreeBuilder()
        start = i
        while i < len(lines) and lines[i].strip():
            builder.feed(lines[i] + "\n")
            i += 1
            if i < len(lines) and not (
                builder.open_elements or builder.inside_tag or _TAG_LINE_START_RE.match(lines[i])
            ):
                break
        builder.close()
        markdown = "\n\n".join(_Renderer().blocks(builder.root.children))
        # keep the indentation of a block nested in a list item, not the one of nested HTML (a code block)
        indent = re.match(r"[ \t]*", lines[start]).group(0)
        indent = indent if len(indent.expandtabs()) < 4 else ""
        markdown = "\n".join(indent + line if line else "" for line in markdown.split("\n"))
        if _has_block(builder.root):
            # a table or a list must not run into the Markdown around it
            markdown = f"\n{markdown}\n" if markdown else ""
        out.append(markdown)
    return "\n".join(out)


# Inline elements: within a paragraph (an element left open doesn't swallow the next paragraphs).
_IN_PARAGRAPH = r"(?:(?!\n[ \t]*\n).)*?"
_INLINE_A_RE = re.compile(rf"<a(?=[\s>])({_ATTRS})>((?:(?!<a[\s>]|\n[ \t]*\n).)*?)</a>", re.DOTALL | re.IGNORECASE)
_INLINE_IMG_RE = re.compile(rf"<img(?=\s|/?>)({_ATTRS})>", re.IGNORECASE)
_INLINE_EMPHASIS_RE = re.compile(rf"<(strong|b|em|i|s|del|strike)>({_IN_PARAGRAPH})</\1>", re.DOTALL | re.IGNORECASE)
_INLINE_CODE_TAG_RE = re.compile(rf"<(code|kbd|samp|tt)>({_IN_PARAGRAPH})</\1>", re.DOTALL | re.IGNORECASE)
_BR_RE = re.compile(r"[ \t]*<br\s*/?>[ \t]*", re.IGNORECASE)


def _attr(attrs, name):
    for match in _ATTR_RE.finditer(attrs):
        if match.group(1) == name:
            return html.unescape(next(value for value in match.groups()[1:] if value is not None))
    return None


def _convert_inline_html(content):
    """Inline HTML inside Markdown (links, images, emphasis, ...). The Markdown around it stays as is."""

    def image(match):
        if _is_dark_mode_copy(_attr(match.group(1), "class") or ""):
            return ""
        return _image(_attr(match.group(1), "src"), _attr(match.group(1), "alt") or "")

    content = _INLINE_IMG_RE.sub(image, content)
    content = _INLINE_A_RE.sub(
        lambda m: _link(_collapse(_convert_inline_html(m.group(2))), (_attr(m.group(1), "href") or "").strip()),
        content,
    )
    content = _INLINE_EMPHASIS_RE.sub(lambda m: _wrap(m.group(2), _EMPHASIS[m.group(1).lower()]), content)
    content = _INLINE_CODE_TAG_RE.sub(lambda m: _code(m.group(2)), content)
    # a line break inside a table row can't be a newline
    content = "\n".join(
        _BR_RE.sub(" " if line.lstrip().startswith("|") else "\n", line) if "<" in line else line
        for line in content.split("\n")
    )

    # Other tags go, their content stays. A tag that isn't HTML and has no attributes stays: it's a
    # placeholder in prose, such as `<user>/<repo>`.
    with_attributes = {m.group(2) for m in _TAG_RE.finditer(content) if m.group(3).strip(" \t\n/")}

    def tag(match):
        name = match.group(2)
        return "" if name.lower() in _HTML_TAGS or _is_component(name) or name in with_attributes else match.group(0)

    return _TAG_RE.sub(tag, content)


def html_to_markdown(content):
    """Convert the HTML in a Markdown document (a generated MDX page) to Markdown."""
    code = _CodeStash()
    content = code.stash(content)
    content = _COMMENT_RE.sub("", content)
    content = _convert_tab_groups(content, code)
    content = _remove_components(content, code)
    content = _convert_html_blocks(content)
    content = _convert_inline_html(content)
    # lines that only held HTML (or its indentation)
    content = re.sub(r"^[ \t]+$", "", content, flags=re.MULTILINE)
    content = re.sub(r"\n{3,}", "\n\n", content).strip("\n")
    content = code.restore(content)

    def callout(match):
        indent, kind, body = match.group(1), match.group(2), match.group(3).strip("\n")
        lines = [f"[!{kind}]"] + body.split("\n")
        return "\n".join(f"{indent}> {line}" if line.strip() else f"{indent}>" for line in lines)

    # innermost callouts first
    while _CALLOUT_RE.search(content):
        content = _CALLOUT_RE.sub(callout, content)
    # a callout whose end went missing (it can't, but its markers must never reach the page)
    content = content.replace(_CALLOUT_START, "").replace(_CALLOUT_END, "")
    return content + "\n" if content else ""
