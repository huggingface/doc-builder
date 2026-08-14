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
Hide everything in a doc page that must not be translated, then put it back afterwards.

A doc page is a mix of prose and things that have to stay exactly as they are: code
samples, URLs, HTML tags, `[[autodoc]]` directives. If we handed the whole page to a
translation model, it would happily "translate" a variable name or a link.

So we do this instead:

1. Find each of those things and swap it for a numbered marker like `¤0¤`.
2. Send only what is left -- the prose -- to the model.
3. Swap the real content back in afterwards.

The model never sees the code, so it cannot damage it. And because the markers have to
come back unchanged, we can check afterwards whether the model kept them (see
validate.py). That check is the main thing protecting these pages.

Each thing on the page is either hidden or translated, never partly both.
"""

import re

# The marker delimiters. `¤` is the Unicode "generic currency sign" -- a character that exists
# to stand in for something else -- and it appears nowhere in the English or Japanese docs.
#
# It deliberately looks nothing like a bracket. The first version used `⟦ ⟧`, which sit right
# next to the `]` of a link in `[some text]⟦0⟧`, and the model confused the two: it returned
# `Gemma 4⟧⟦396⟧`, having eaten the `[` and turned the `]` into a `⟧`. Two links on one page
# were lost that way, and every one of the ~4,900 links in the docs was exposed to it.
PH_OPEN = "¤"
PH_CLOSE = "¤"

PLACEHOLDER_RE = re.compile(f"{PH_OPEN}(\\d+){PH_CLOSE}")

# The patterns run top to bottom. Once something is hidden, later patterns cannot see it,
# so the order is doing real work:
#
#   comments go first, because a comment can contain literally anything, even code blocks
#   code blocks before inline code, so ``` is not mistaken for a short `snippet`
#   [[autodoc]] before the general [[...]] rule, so it keeps its indented list of methods
#   inline code before tags, so `<mask>` in backticks is hidden as one piece
#
# Two of the patterns are deliberately fussy, to stop them swallowing half the page:
#
#   "tag" needs a letter or / right after the `<`, because real prose says things like
#   "when n < m". It stops at the next `<` and gives up after 600 characters. It is
#   allowed to run across several lines: 88 tags in the docs are `<img>` or `<iframe>`
#   elements split over two lines, and if we left those alone their URLs would be handed
#   to the model as if they were prose. We checked -- allowing this picks up those 88 and
#   nothing else. The longest real tag is 326 characters, so the 600 limit is just a
#   backstop for a malformed tag that never closes.
#
#   "code" is not allowed to cross a line break, so one stray backtick cannot hide the
#   rest of the document.
MASK_PATTERNS = [
    ("comment", re.compile(r"<!--.*?-->", re.DOTALL)),
    ("fence", re.compile(r"^[ \t]*(`{3,}|~{3,}).*?^[ \t]*\1[ \t]*$", re.DOTALL | re.MULTILINE)),
    # Matches what build_doc actually accepts (see _re_autodoc and _re_list_item there):
    # the directive may be indented, and blank lines may sit before its list of methods.
    # An earlier version only matched it at the start of a line, which missed the indented
    # one in the docs and sent `[[autodoc]] LevitImageProcessor` off to be translated.
    ("autodoc", re.compile(r"^[ \t]*\[\[autodoc\]\][^\n]*(?:(?:\n[ \t]*)*\n[ \t]*-[ \t]+[^\n]*)*", re.MULTILINE)),
    ("directive", re.compile(r"\[\[[^\]\n]*\]\]")),
    ("math_block", re.compile(r"\$\$.*?\$\$", re.DOTALL)),
    ("math_inline", re.compile(r"\\\\\(.*?\\\\\)", re.DOTALL)),
    ("code", re.compile(r"(`+)[^\n]*?\1")),
    ("tag", re.compile(r"</?[a-zA-Z][^<>]{0,600}>")),
    # Only the `(url)` half, so the `[text]` brackets stay balanced. Hiding `](url)` instead
    # left the model looking at `[some text⟦0⟧` -- an opening bracket that never closes -- and
    # it would helpfully "repair" that by adding a `]`, producing `[text](url)]` once the
    # marker was put back. Thirty of those in one six-page run. Telling it not to in the prompt
    # did not help, because the unbalanced bracket is a much stronger cue than an instruction.
    ("link", re.compile(r"(?<=\])\([^)\n]*\)")),
    ("callout", re.compile(r">[ \t]*\[!\w+\]")),
]

# A blank line marks the end of one chunk and the start of the next. The blank lines are
# kept as part of the split so we can rebuild the page with its original spacing.
BLOCK_SPLIT_RE = re.compile(r"(\n[ \t]*\n)")


def mask(text):
    """Swap everything that must not be translated for numbered markers.

    Gives back the rewritten page and a list of what was taken out, where item `i` is what
    `¤i¤` used to be.
    """
    placeholders = []

    def _replace(match):
        placeholders.append(match.group(0))
        return f"{PH_OPEN}{len(placeholders) - 1}{PH_CLOSE}"

    for _name, pattern in MASK_PATTERNS:
        text = pattern.sub(_replace, text)
    return text, placeholders


def restore(text, placeholders):
    """Put the real content back where the markers are.

    This runs in a loop because markers can end up inside other markers. A real example
    from the docs is `[here](<INSERT LINK HERE>)`: the tag rule hides `<INSERT LINK HERE>`
    first, and then the link rule hides the `(¤12¤)` around it. Python does not look again at
    text it has just substituted in, so a single pass would leave a stray `¤12¤` sitting in the
    finished page.

    This only matters when putting things back. The page we send to the model has just the
    outer markers in it, so the checks in validate.py can stay simple.

    Raises an error if the text contains a marker we never created -- if the model invents
    a `¤99¤`, we want to hear about it here rather than publish a broken page.
    """

    def _replace(match):
        index = int(match.group(1))
        if index >= len(placeholders):
            raise ValueError(f"placeholder {index} out of range ({len(placeholders)} known)")
        return placeholders[index]

    # Markers can only nest as deep as the number of patterns, so this many rounds is
    # always enough. The limit is only here so a self-referencing marker cannot loop forever.
    for _ in range(len(MASK_PATTERNS) + 1):
        restored = PLACEHOLDER_RE.sub(_replace, text)
        if restored == text:
            return restored
        text = restored
    raise ValueError("placeholder restore did not converge")


def split_blocks(masked_text):
    """Cut the page into chunks at blank lines.

    The result alternates: chunk, blank line, chunk, blank line, and so on. So the chunks
    are at the even positions and the spacing between them at the odd ones. `join_blocks`
    puts it back together exactly as it was.
    """
    return BLOCK_SPLIT_RE.split(masked_text)


def join_blocks(parts):
    """Glue the pieces from `split_blocks` back into one page."""
    return "".join(parts)


def is_translatable(block):
    """Is there anything in this chunk worth sending to the model?

    A chunk that is only a marker or two -- a code block on its own, say, or an
    `[[autodoc]]` directive -- has no prose in it, so we pass it through untouched.
    """
    return bool(PLACEHOLDER_RE.sub("", block).strip())


def placeholder_indices(text):
    """List the marker numbers found in the text, including any repeats.

    Repeats matter: validate.py uses this to spot a model that copied a marker twice.
    """
    return [int(m.group(1)) for m in PLACEHOLDER_RE.finditer(text)]
