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
# It also looks nothing like a bracket, which was meant to stop the model muddling a marker
# with the `]` of a link. That turned out not to be the problem: with `¤` markers the model
# still returns `Gemma 4⟧¤396¤` -- dropping the `[` and inventing a `⟧` it was never shown.
# So the delimiter was never the cause. What fixed it was hiding both of a link's brackets
# (see `link_open` below), which turns a mangled link into an ordinary missing marker. `¤` is
# kept anyway; there is no reason to prefer a bracket-shaped marker.
PH_OPEN = "¤"
PH_CLOSE = "¤"

# Brackets the model reaches for when it decides to rewrite a marker in its own notation, e.g.
# `⟦0⟧` beside the real `¤0¤`. Declared here, with the marker vocabulary, because two modules
# act on it -- pipeline.py strips the numbered form, validate.py rejects anything else using
# these characters -- and a family added to one but not the other means either litter shipping
# silently or good pages failing wholesale.
FOREIGN_BRACKETS = "⟦⟧"

PLACEHOLDER_RE = re.compile(f"{PH_OPEN}(\\d+){PH_CLOSE}")

# What sits between the parentheses of a link, e.g. `(../cb)` or `(https://hf.co "title")`.
#
# The parentheses have to be counted rather than stopped at the first `)`. Nine links in the
# docs put a bracketed phrase inside the URL -- `Fine_(LED)_guide.ipynb` -- and stopping at the
# first `)` left `_guide.ipynb)` in front of the model as ordinary prose. The model was free to
# rewrite that, and `check_links` never noticed, because its own regex made the same partial
# match on both sides and the counts came out equal.
#
# One level of nesting is all this allows. Nothing in the docs nests deeper, and anything that
# did would need a real parser rather than a regex.
LINK_DEST = r"\((?:[^()\n]|\([^()\n]*\))*\)"

# What sits between the brackets of a link: the words a reader sees. One nested link or image is
# allowed, because the docs are full of `[![Open In Colab](badge.svg)](notebook.ipynb)` -- 142 of
# them -- where the outer link's label is an entire image.
#
# A label grammar that only allowed one level of bare brackets did not cover that shape, so the
# outer link went unrecognised: masking left the `!` bare in the text, and the check only ever
# saw the inner `badge.svg`. Deleting that `!` kept every marker in place and passed every check.
#
# Shared with validate.py, so what gets masked and what gets checked cannot drift apart. That
# drift is what let a rewritten URL through last time.
# Each alternative below is written so that only one of them can match at any position. With two
# ways to read every `![x](y)` -- as one nested link, or as a `!`, a `[x]` and some loose
# characters -- the engine tries every combination before giving up, and
# `mask("![" + "![x](y)"*16)` never finished. So the plain-character branch refuses the `!` that
# starts an image, and the bare-brackets branch refuses a `]` that a destination follows.
# A soft line break inside a label is allowed -- 25 links across 20 pages wrap their label
# across source lines, and forbidding it masked only the closing half, leaving the opening `[`
# in front of the model. A blank line still stops it, so a runaway `[` cannot cross a paragraph.
#
# This does give up one thing: `check_links` used to notice a marker that had drifted onto
# another line, because a link spanning a newline could not match. That mattered when one
# bracket was raw text. Both brackets are markers now, so a drifted marker fails the ordinary
# marker check instead.
_SOFT_BREAK = r"\n(?![ \t]*\n)"
LINK_LABEL = rf"(?:(?!!\[)[^\[\]\n]|{_SOFT_BREAK}|!?\[[^\[\]\n]*\]{LINK_DEST}|\[[^\[\]\n]*\](?!\())*"


# A URL as it appears in running text. Shared with validate.py, same reason as the link
# patterns: what gets hidden and what gets checked have to be the same thing.
#
# The trailing character class is the fussy part. Prose puts full stops and commas after a URL
# -- "see https://hf.co/docs." -- and brackets around it, and none of those belong to the
# address, so the last character has to be one that can really end one.
#
# Parentheses are counted rather than excluded, for the same reason link destinations count them:
# excluding them stopped `https://e/Foo_(bar)` after `Foo_` and handed `(bar)` to the model as
# prose. That is worse than not masking at all, because `check_links` makes the same partial
# match on both sides, so the counts agree and a rewritten suffix goes unnoticed. A `)` still
# only counts when a `(` opened it, so "(see https://hf.co/docs)" keeps its closing bracket.
_URL_CHAR = r"""[^\s<>()\[\]{}"'`]"""
# A parenthesised run inside a URL. Punctuation is allowed in here but not at the very end of
# the address, which is what the trailing alternative below is for.
_URL_PARENS = rf"(?:\((?:{_URL_CHAR}|[.,;:!?])*\))"
BARE_URL = rf"https?://(?:{_URL_CHAR}|{_URL_PARENS})*(?:{_URL_CHAR}(?<![.,;:!?])|{_URL_PARENS})"

# A reference definition, e.g. `[altup]: https://proceedings.neurips.cc/…`, on a line of its own.
REF_DEF_RE = re.compile(r"^[ \t]*\[([^\[\]\n]+)\]:[ \t]+\S[^\n]*$", re.MULTILINE)


def _ref_link_patterns(text):
    """Patterns for the reference-style links this page actually defines.

    Built per page rather than written into the list below, because `[a][b]` on its own is not
    enough to go on: the docs are full of Python indexing like `outputs["train"][0]`, and 116
    of those match that shape against four real reference links. A reference only counts if the
    page defines it, which is also what CommonMark says -- an undefined one renders as plain
    text, so masking it would be wrong as well as risky.

    This runs after code and fences are already hidden, so definitions quoted inside a shell
    session -- `[rank0]: ncclInternalError` in `model_doc/deepseek_v3.md` -- are out of sight
    by the time we look.
    """
    labels = {m.group(1).lower() for m in REF_DEF_RE.finditer(text)}
    if not labels:
        return []
    alternatives = "|".join(re.escape(label) for label in sorted(labels, key=len, reverse=True))
    close = rf"\]\[(?:{alternatives})\]"
    return [
        # `!?` for the same reason the inline rule has it: left bare, the `!` is one character of
        # ordinary text between two markers, and dropping it turns `![Diagram][fig]` into a link
        # with every marker still in place.
        re.compile(rf"!?\[(?=(?:[^\[\]\n]|\[[^\[\]\n]*\])*{close})", re.IGNORECASE),
        re.compile(close, re.IGNORECASE),
    ]


# The patterns run top to bottom. Once something is hidden, later patterns cannot see it,
# so the order is doing real work:
#
#   comments go first, because a comment can contain literally anything, even code blocks
#   code blocks before inline code, so ``` is not mistaken for a short `snippet`
#   [[autodoc]] before the general [[...]] rule, so it keeps its indented list of methods
#   inline code before tags, so `<mask>` in backticks is hidden as one piece
#   reference links before reference definitions, since finding the links means reading the
#   definitions, and masking a definition puts it out of reach
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
    # The closing fence has to be the same character as the opener and *at least* as long --
    # not exactly as long. An earlier version used a plain backreference, which meant a three
    # backtick block closed by four backticks never found its closer: masking ran on to the
    # next bare ``` further down the page and swallowed the prose and code in between. Two
    # pages in the corpus do this (`model_doc/mms.md`, `model_doc/mistral3.md`), and the
    # paragraphs they hid were never translated and never seen by any check -- masked text is
    # preserved by definition, so the round-trip test passed the whole time.
    #
    # `fence` is the opener's run of delimiters, `fchar` the single character it is made of,
    # so the closer is "that run, plus any number of the same character".
    (
        "fence",
        re.compile(
            r"^[ \t]*(?P<fence>(?P<fchar>[`~])(?P=fchar){2,}).*?^[ \t]*(?P=fence)(?P=fchar)*[ \t]*$",
            re.DOTALL | re.MULTILINE,
        ),
    ),
    # Matches what build_doc actually accepts (see _re_autodoc and _re_list_item there):
    # the directive may be indented, and blank lines may sit before its list of methods.
    # An earlier version only matched it at the start of a line, which missed the indented
    # one in the docs and sent `[[autodoc]] LevitImageProcessor` off to be translated.
    ("autodoc", re.compile(r"^[ \t]*\[\[autodoc\]\][^\n]*(?:(?:\n[ \t]*)*\n[ \t]*-[ \t]+[^\n]*)*", re.MULTILINE)),
    ("directive", re.compile(r"\[\[[^\]\n]*\]\]")),
    ("math_block", re.compile(r"\$\$.*?\$\$", re.DOTALL)),
    ("math_inline", re.compile(r"\\\\\(.*?\\\\\)", re.DOTALL)),
    ("xref", re.compile(r"\[`[^`\n]+`\](?!\()")),
    ("code", re.compile(r"(`+)[^\n]*?\1")),
    # Ordinary `$x$` formulas. Only `$$...$$` and the escaped-parenthesis form were covered, so
    # 170 inline formulas across 9 pages went to the model as prose -- `$K_{\text{past}}$` could
    # come back corrupted with nothing to notice.
    #
    # Deliberately narrow, because a lone `$` is also just a dollar sign. What keeps prose out is
    # the space rule: a formula never has a space just inside its delimiters, or has one on both
    # sides. `costs $5 and $10 today` fails both -- the closing `$` has a space before it, and
    # the opening one has none after it -- so a run of prose between two prices is not a formula.
    #
    # It may span lines but not a blank one, because `model_doc/reformer.md` wraps formulas
    # across source lines mid-paragraph. The length cap and the paragraph boundary together are
    # what stop a stray `$` reaching across the page.
    #
    # It runs after `code` on purpose. Ahead of it, a `$` inside one inline-code span paired
    # with a `$` in a later span on the same line -- `Set `$HOME` and `$PATH`` masked the word
    # "and" into a fake formula and broke the backtick pairing, and the page still round-tripped
    # so nothing caught it.
    (
        "math_dollar",
        re.compile(
            r"(?<![\\$])\$(?:"
            # no padding: `$x^2$`
            r"(?![\s$])(?:[^$\n]|\n(?![ \t]*\n)){0,200}?(?<![\s\\])"
            r"|"
            # padded on both sides: `$ K_{\text{past}} $`
            r"[ \t](?![\s$])(?:[^$\n]|\n(?![ \t]*\n)){0,200}?(?<![\s\\])[ \t]"
            # Not a formula if a digit follows the closing `$`: `US$5 to US$10` used to mask as
            # `$5 to US$`, quietly shielding ordinary prose from translation. Only a digit, and
            # not punctuation -- `$\sigma$-VAE` in `model_doc/vibevoice.md` is a real formula
            # followed by a hyphenated word, and forbidding `-` here un-masked it.
            r")\$(?![\d$])"
        ),
    ),
    # doc-builder's cross-reference: [`Pipeline`] with no (url) after it, which the build turns
    # into a link to that class or method. Hidden whole, and hidden before the inline-code rule
    # gets to it -- otherwise only the backticked name goes and the model is left looking at
    # `[¤7¤]`, both brackets raw. That is the same shape that caused all the link damage, and
    # there are 2,307 of them across 463 of the 732 pages.
    #
    # It is worth hiding the whole thing here, unlike a link, because what sits between the
    # brackets is always an API name -- it is in backticks, so by definition it is not prose.
    # There is nothing to translate and nothing to lose.
    #
    # Losing one of these is quieter than losing a link: `[Pipeline]` with a bracket missing is
    # not malformed markdown, it just stops resolving, so it renders as plain text and no check
    # would ever notice. Hiding it whole turns that into an ordinary missing marker.
    ("tag", re.compile(r"</?[a-zA-Z][^<>]{0,600}>")),
    # Links get both brackets hidden, leaving only the label between two markers:
    #
    #     [continuous batching](../cb)  ->  ¤0¤continuous batching¤1¤
    #
    # The label is still translated -- worth doing, since 80% of the 4,711 links in the docs
    # have a real phrase there rather than an identifier -- but there is no markdown left for
    # the model to get wrong. That matters because every earlier arrangement left one bracket
    # exposed as raw text, and the model kept "fixing" it: first adding a `]` when the opening
    # bracket looked unclosed, then dropping the `[` and inventing a `⟧` in its place. Neither
    # was detectable by the marker check, because the brackets were not markers.
    #
    # Now they are, so a mangled link is just a missing marker, and the ordinary check catches
    # it with no special case. `link_open` only fires on a `[` that actually starts a link,
    # which is what the lookahead is for.
    # The lookahead allows one level of brackets inside the label, because 144 links in the docs
    # have them: `[![Open In Colab](img)](link)` wraps an image in a link, and
    # `[huggingface_hub[cli]](url)` has them in the text. A simpler lookahead that forbade any
    # `]` before the `](` skipped those, so only the closing bracket got hidden and the exposed
    # `[` came back -- along with the model's habit of "closing" it.
    # One entry for both `[` and `![`, because they differ only by that character and the label
    # grammar after them is identical. The `!` has to go with the bracket rather than being left
    # in the text: on its own it is a single character between two markers, and the model
    # dropped it -- which turns an image into a link, keeps every marker intact, and renders as
    # a broken picture.
    ("link_open", re.compile(rf"!?\[(?={LINK_LABEL}\]{LINK_DEST})")),
    ("link_close", re.compile(rf"\]{LINK_DEST}")),
    # Reference-style links: `[Alternating Updates][altup]`, with `[altup]: https://...` further
    # down the page. Only four of these exist in the docs, all in `model_doc/gemma3n.md`, and
    # none of them were masked at all -- so the label `altup` went to the model as prose, where
    # translating it would break the link silently.
    #
    # Handled the same way as an ordinary link: both brackets and the reference become markers,
    # the visible text between them stays translatable.
    ("ref_link", _ref_link_patterns),
    # The definitions themselves go whole. There is nothing to translate in `[altup]: https://…`
    # -- the label is an identifier and the rest is a URL.
    ("ref_def", REF_DEF_RE),
    ("callout", re.compile(r">[ \t]*\[!\w+\]")),
    # A URL written straight into a sentence, with no markdown around it. Nothing hid these, so
    # the model was free to rewrite one and no check compared them -- 53 of them across 32 pages,
    # in a module whose whole promise is that URLs come back exact.
    #
    # Runs last of the link rules, so a URL that is already inside a destination or a tag is
    # long gone by the time we look and only the genuinely bare ones are left.
    #
    # The trailing character class is the fussy part. Prose puts full stops and commas after a
    # URL -- "see https://hf.co/docs." -- and closing brackets around it, and none of those
    # belong to the address. So the last character has to be one that can really end a URL.
    ("bare_url", re.compile(BARE_URL)),
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
        # Most entries are one compiled pattern. A couple need to look at the page first --
        # reference links depend on which references it defines -- so those are a function that
        # gets handed the text as it stands and gives back the patterns to run.
        for compiled in pattern(text) if callable(pattern) else [pattern]:
            text = compiled.sub(_replace, text)
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

    # Every round resolves every marker currently visible, so nesting cannot outlast one round
    # per marker. Nothing in the docs nests more than three deep and the loop returns as soon as
    # it converges -- the bound is only here so a self-referencing marker cannot spin forever.
    # It is tied to the placeholders themselves rather than to the length of the pattern list,
    # which is neither the number of patterns run nor related to how deeply they nest.
    for _ in range(len(placeholders) + 1):
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


def has_prose(text):
    """Is there anything here besides markers and whitespace?

    Asked in two directions, which is why it lives in one place. On the way in: a chunk that is
    only a marker or two -- a code block on its own, say, or an `[[autodoc]]` directive -- has
    no prose to send. On the way out: a translation with no prose in it is not a translation,
    and used to be accepted, which silently deleted the paragraph.
    """
    return bool(PLACEHOLDER_RE.sub("", text).strip())


def placeholder_indices(text):
    """List the marker numbers found in the text, including any repeats.

    Repeats matter: validate.py uses this to spot a model that copied a marker twice.
    """
    return [int(m.group(1)) for m in PLACEHOLDER_RE.finditer(text)]
