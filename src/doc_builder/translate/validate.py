"""
Checks a translated page before we publish it.

Nobody on the team reads Japanese, so we cannot tell whether the writing is any good. What
we can tell is whether the page still holds together: are the code samples intact, are the
headings still there, did the model actually translate anything. That is what happens here,
and it is the only thing standing between a bad translation and the live docs.

Four checks can reject a page. A fifth, the glossary one, only prints a warning -- odd
word choice reads a little off, it does not break the page, and throwing away a good
translation over it would be worse.

We do not separately count code blocks, `[[autodoc]]` directives, HTML tags or URLs. All of
those were swapped out for markers before translation, so if the markers survived then those
did too. Checking them again would just be more code doing the same job.

Links are the one exception, and it is worth knowing why. Hiding a URL guarantees the URL
cannot change. It does not guarantee the link still works, because the opening `[` of
`[text](url)` was never hidden -- so the model can drift the marker away from its bracket,
leave every marker present and correct, and still produce a broken link. Two different
things, and only the first is covered by the marker check.

The first checks look at the page while the markers are still in place. That is what makes
the heading count trustworthy: a `#` inside a shell snippet is already hidden, so it cannot
be mistaken for a heading.
"""

import re
from collections import Counter
from dataclasses import dataclass, field

from .segment import PLACEHOLDER_RE, placeholder_indices

HEADING_RE = re.compile(r"^(#{1,6})[ \t]+\S", re.MULTILINE)

# A markdown link or image, e.g. [text](url). It deliberately will not match across a line
# break -- that restriction is what lets us notice a marker that has drifted onto another line.
MD_LINK_RE = re.compile(r"!?\[[^\]\n]*\]\([^)\n]*\)")


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


def check_links(source, restored):
    """Are the links still put together properly?

    This looks like it repeats the marker check, but it does not. Only the `](url)` half of
    a link is hidden; the opening `[` is left alone. So the model sees `[Sign up⟦0⟧` and has
    to keep the marker next to its bracket. If it moves the marker elsewhere, every marker is
    still present exactly once -- the marker check is happy -- but the link is broken.

    This one runs on the finished page rather than the marked-up one. It catches a marker
    that has moved to a different line, which is the realistic mistake. A marker shuffled
    around within the same line can still slip past, because the link is then merely
    pointing at the wrong words rather than malformed.
    """
    want = len(MD_LINK_RE.findall(source))
    got = len(MD_LINK_RE.findall(restored))
    if got < want:
        return [f"markdown links broken: {want} in source, {got} well-formed in output"]
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
    if source is not None and restored is not None:
        result.failures += check_links(source, restored)
    if glossary:
        result.warnings += check_glossary(masked_source, masked_translation, glossary)
    return result


def summarize(results):
    """Summarise how the run went.

    Keep an eye on the rejection rate. If it starts creeping up, something has gone wrong
    with the model or the prompt, and it is the only warning we get.
    """
    total = len(results)
    failed = [r for r in results if not r.ok]
    warned = sum(1 for r in results if r.warnings)
    rate = len(failed) / total if total else 0.0
    lines = [
        f"[validate] {total - len(failed)}/{total} pages passed, rejection rate {rate:.1%}, {warned} with warnings"
    ]
    if rate > 0.02:
        lines.append(f"[validate] WARNING rejection rate {rate:.1%} exceeds 2% -- investigate")
    for r in failed:
        lines.append(str(r))
    return "\n".join(lines)
