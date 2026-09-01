"""
Checks a translated page before we publish it.

Nobody on the team reads Japanese, so we cannot tell whether the writing is any good. What
we can tell is whether the page still holds together: are the code samples intact, are the
headings still there, did the model actually translate anything. That is what happens here,
and it is the only thing standing between a bad translation and the live docs.

Five checks can reject a page. A sixth, the glossary one, only prints a warning -- odd
word choice reads a little off, it does not break the page, and throwing away a good
translation over it would be worse.

We do not separately count code blocks, `[[autodoc]]` directives, HTML tags or URLs. All of
those were swapped out for markers before translation, so if the markers survived then those
did too. Checking them again would just be more code doing the same job.

Links are the one exception, and it is worth knowing why. Hiding a URL guarantees the URL
cannot change. It does not guarantee the link still holds together: the marker check only
says every piece came back, not that the pieces are still arranged into working links. A
marker that drifts to the wrong place leaves every marker present and correct and a broken
link behind it. Two different things, and only the first is covered by the marker check.

The first checks look at the page while the markers are still in place. That is what makes
the heading count trustworthy: a `#` inside a shell snippet is already hidden, so it cannot
be mistaken for a heading.
"""

import re
from collections import Counter
from dataclasses import dataclass, field

from .segment import BARE_URL, FOREIGN_BRACKETS, LINK_DEST, PLACEHOLDER_RE, REF_DEF_RE, placeholder_indices

HEADING_RE = re.compile(r"^(#{1,6})[ \t]+\S", re.MULTILINE)

# A link destination, anchored so it can be matched at a known position. Shared with segment.py
# so what gets masked and what gets checked cannot drift apart: when they did, a URL with
# brackets in it matched partially on both sides, the counts agreed, and a rewritten URL got
# through unnoticed.
LINK_DEST_RE = re.compile(LINK_DEST)

# Markdown link and image openers, found by scanning rather than by one big pattern. See
# `link_targets` for why.
OPENER_RE = re.compile(r"!?\[")

# The reference-style equivalents, `[text][ref]` and the `[ref]: url` lines that define them.
REF_LINK_RE = re.compile(r"(?P<image>!?)\[[^\]\n]*\]\[(?P<dest>[^\]\n]*)\]")

# Every URL on the page, wherever it sits. Run over both versions the same way, so a URL inside
# a link destination appears on both sides and cancels out; what is left is a URL that changed.
BARE_URL_RE = re.compile(BARE_URL)

# A link with a leftover `]` stuck to the end of it, e.g. `[text](url)]`. This is what a marker
# nudged one character out of place leaves behind, and counting links alone will not see it --
# the link itself is perfectly well formed, the bracket just sits there rendering as junk.
ORPHAN_BRACKET_RE = re.compile(r"\]\([^)\n]*\)\]")

# Brackets the model invents. The character set lives in segment.py next to the real markers,
# so the stripper there and the check here cannot learn about a new family separately.
FOREIGN_BRACKET_RE = re.compile(f"[{FOREIGN_BRACKETS}]")


@dataclass
class Result:
    page: str
    failures: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def ok(self):
        return not self.failures

    def __str__(self):
        bits = [f"{'OK  ' if self.ok else 'FAIL'} {self.page}"]
        bits += [f"    fail: {f}" for f in self.failures]
        bits += [f"    warn: {w}" for w in self.warnings]
        return "\n".join(bits)


def heading_levels(masked_text):
    """Heading depths in document order, e.g. [1, 2, 2, 3]."""
    return [len(m.group(1)) for m in HEADING_RE.finditer(masked_text)]


def check_placeholders(masked_source, masked_translation):
    """Did every marker come back, exactly once, with nothing invented?

    This is the check that does most of the work. Code samples, tags, links, maths and
    `[[autodoc]]` directives were all swapped for markers, so this one comparison covers
    all of them at once.
    """
    want = placeholder_indices(masked_source)
    got = placeholder_indices(masked_translation)
    problems = []

    dup = sorted(i for i, n in Counter(got).items() if n > 1)
    if dup:
        problems.append(f"placeholder(s) duplicated: {dup}")

    missing = sorted(set(want) - set(got))
    if missing:
        problems.append(f"placeholder(s) dropped: {missing}")

    invented = sorted(set(got) - set(want))
    if invented:
        problems.append(f"placeholder(s) invented: {invented}")

    return problems


def check_headings(masked_source, masked_translation):
    """Are the headings still there, and still nested the same way?

    Heading text does get translated, so headings are not covered by the marker check.
    This is the one piece of page structure we have to look at separately.
    """
    want, got = heading_levels(masked_source), heading_levels(masked_translation)
    if want != got:
        return [f"heading structure changed: {len(want)} headings {want} -> {len(got)} {got}"]
    return []


def check_translated(masked_source, masked_translation):
    """Did the model actually translate anything, or just hand the English back?

    We compare against the English rather than looking for Japanese characters. Checking for
    a particular alphabet only works for the one language it was written for -- the same
    check would reject every single page of a Korean, French or Spanish run. A model echoing
    its input looks the same in any language, so that is what we look for.
    """
    prose = PLACEHOLDER_RE.sub("", masked_translation).strip()
    if not prose:
        return ["translation is empty once placeholders are removed"]
    if prose == PLACEHOLDER_RE.sub("", masked_source).strip():
        return ["translation is identical to the English source (model echoed its input)"]
    return []


def scan_links(text):
    """Find every markdown link and image by walking the text once.

    A scanner rather than a regex, because the regex that did this job could be made to take
    unbounded time. Its label had to allow one nested link -- `[![badge](img)](target)` is all
    over the docs -- and a label grammar with a nested alternation has two ways to read every
    `![x](y)`: as one nested link, or as a `!`, a `[x]`, and some loose characters. With N
    images after a bracket that never closes, the engine tries all of those combinations, and
    on `"[" + "![x](y)"*N` it measured 105ms at N=12, 8.5s at N=16 and 12.4 minutes at N=20.
    `check_links` runs on every page twice, so one malformed line would have hung the nightly
    job until its six-hour timeout.

    Walking the text is linear and has no combinations to try. Openers go on a stack; a `](`
    with a destination after it closes the most recent one, which is what makes nesting fall
    out for free. An opener that never closes is simply dropped, the same as CommonMark, and
    costs nothing.

    Gives back (kind, destination) pairs, innermost first within a nesting.
    """
    found = []
    stack = []
    i, n = 0, len(text)
    while i < n:
        char = text[i]
        if char == "\n":
            # Links do not span lines here, and that restriction is what lets the marker checks
            # notice one that drifted onto the next line. Openers left over cannot close later.
            stack.clear()
            i += 1
            continue
        if char == "!" and text.startswith("![", i):
            stack.append(("image", i))
            i += 2
            continue
        if char == "[":
            stack.append(("link", i))
            i += 1
            continue
        if char == "]" and i + 1 < n and text[i + 1] == "(":
            dest = LINK_DEST_RE.match(text, i + 1)
            if dest is not None:
                if stack:
                    kind, _start = stack.pop()
                    found.append((kind, dest.group(0)))
                i = dest.end()
                continue
        i += 1
    return found


def link_targets(text):
    """Every link in the text as (kind, destination), so two versions can be compared.

    Destinations rather than a count, and the kind alongside, because both can be damaged
    without changing how many links there are. A count is the same number whether or not the
    links still point anywhere near the right place, and turning an image into a link leaves
    the count untouched too.
    """
    targets = list(scan_links(text))
    for match in REF_LINK_RE.finditer(text):
        targets.append(("ref", match.group("dest").lower()))
    for match in REF_DEF_RE.finditer(text):
        targets.append(("ref-def", match.group(1).lower()))
    targets.extend(("url", m.group(0)) for m in BARE_URL_RE.finditer(text))
    return targets


def check_links(source, restored):
    """Are the links still put together properly, and still pointing where they did?

    This looks like it repeats the marker check, but it does not. The marker check only says
    every piece came back; it cannot say the pieces are still assembled into links. A marker
    that drifts away from its bracket leaves every marker present exactly once and a broken
    link behind it.

    This one runs on the finished page rather than the marked-up one, and compares the actual
    destinations as a multiset. A multiset rather than a list, because Japanese word order
    moves links around the sentence and that is fine; what is not fine is a destination
    appearing, vanishing or changing.
    """
    problems = []

    want, got = Counter(link_targets(source)), Counter(link_targets(restored))
    lost = want - got
    gained = got - want
    if lost:
        shown = sorted(f"{kind} {dest}" for kind, dest in lost.elements())[:3]
        problems.append(f"{sum(lost.values())} link(s) lost or altered: {shown}")
    if gained:
        shown = sorted(f"{kind} {dest}" for kind, dest in gained.elements())[:3]
        problems.append(f"{sum(gained.values())} link(s) not in the source: {shown}")

    # Counting links alone missed this one: the model produced `[text](url)]`, which is a valid
    # link plus a stray bracket, so the count matched and the page shipped with visible junk in
    # its first line. Compared against the source, in case a page legitimately writes that.
    orphans = len(ORPHAN_BRACKET_RE.findall(restored)) - len(ORPHAN_BRACKET_RE.findall(source))
    if orphans > 0:
        problems.append(f"{orphans} link(s) followed by a stray ']'")

    return problems


def check_invented_brackets(masked_source, masked_translation):
    """Did the model make up markers of its own?

    It has a habit of copying a marker back in a different pair of brackets -- `⟦0⟧` next to
    the real `¤0¤`. The numbered form is cleaned up before we get here (see
    `strip_echoed_markers`), so anything still using these brackets is a shape we have not
    seen, and it should stop the page rather than quietly ship.

    Worth its own check because nothing else could see it: `⟦` is not a marker, not a bracket
    the link check counts, and it leaves the link count untouched. 176 of them reached the
    published docs before this existed.
    """
    # Called once per accepted paragraph -- about 15,000 times on a cold run -- and almost
    # always negative, so get out on a substring test before building any sets.
    if not any(bracket in masked_translation for bracket in FOREIGN_BRACKETS):
        return []
    stray = set(FOREIGN_BRACKET_RE.findall(masked_translation)) - set(FOREIGN_BRACKET_RE.findall(masked_source))
    if stray:
        count = sum(masked_translation.count(c) for c in stray)
        return [f"{count} invented bracket(s) not in the source: {sorted(stray)}"]
    return []


def check_glossary(masked_source, masked_translation, glossary):
    """Did the model stick to the agreed wording? Warning only, never a rejection.

    Getting one of these wrong reads a bit off. It does not break anything, and rejecting an
    otherwise fine page over word choice would do more harm than good.
    """
    warnings = []
    src_low = masked_source.lower()

    # `or []` rather than a default value: a glossary with `keep:` and nothing under it reads
    # back as None, and looping over None would crash the whole run -- after we had already
    # paid for the GPU time.
    for term in glossary.get("keep") or []:
        if term.lower() in src_low and term not in masked_translation:
            warnings.append(f"do-not-translate term missing from output: {term!r}")

    for term, rendering in (glossary.get("pin") or {}).items():
        if term.lower() in src_low and rendering not in masked_translation:
            warnings.append(f"term {term!r} not rendered as {rendering!r}")

    return warnings


def validate_page(page, masked_source, masked_translation, glossary=None, source=None, restored=None):
    """Run all the checks. If `Result.ok` comes back false, do not publish the page.

    `source` and `restored` are the page before the markers went in and after they came out.
    Pass both to get the link check, which needs the finished page to work on.
    """
    result = Result(page=page)
    result.failures += check_placeholders(masked_source, masked_translation)
    result.failures += check_headings(masked_source, masked_translation)
    result.failures += check_translated(masked_source, masked_translation)
    result.failures += check_invented_brackets(masked_source, masked_translation)
    if source is not None and restored is not None:
        result.failures += check_links(source, restored)
    if glossary:
        result.warnings += check_glossary(masked_source, masked_translation, glossary)
    return result


def summarize(results, warn_rate):
    """Summarise how the run went.

    Keep an eye on the rejection rate. If it starts creeping up, something has gone wrong
    with the model or the prompt, and it is the only warning we get.

    `warn_rate` is passed in rather than known here. It used to be a hardcoded 2%, which
    silently shadowed the command's `--warn-failure-rate`: raising that flag still printed
    "exceeds 2% -- investigate", and the two numbers had nothing tying them together.
    """
    total = len(results)
    failed = [r for r in results if not r.ok]
    warned = sum(1 for r in results if r.warnings)
    rate = len(failed) / total if total else 0.0
    lines = [
        f"[validate] {total - len(failed)}/{total} pages passed, rejection rate {rate:.1%}, {warned} with warnings"
    ]
    if rate > warn_rate:
        lines.append(f"[validate] WARNING rejection rate {rate:.1%} exceeds {warn_rate:.0%} -- investigate")

    # Show every page that had anything to say, not just the ones that failed. A page can pass
    # while still having paragraphs left in English, and printing only failures hid exactly the
    # number worth watching: "quicktour.md passed" said nothing about the English paragraph
    # sitting in the middle of it.
    for r in results:
        if not r.ok or r.warnings:
            lines.append(str(r))
    return "\n".join(lines)
