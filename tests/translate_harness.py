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
Shared machinery for attacking the translation pipeline on purpose.

Three questions keep coming back in review, and each one is a property of the whole pipeline
rather than of any one function, so each one needs a way to be asked repeatedly:

  1. Did we publish something incomplete, or something that quietly reverted to English?
  2. Can a second publisher, or a repair, damage or delete the generation the pointer names?
  3. Can protected Markdown be changed without a check noticing?

`assert_published_tree_is_sound` answers the first, `mutations` and `fake_translation` set up the
third, and the fault-injection helpers here are what the tests use for the second.

Nothing in here needs a GPU.
"""

import re
import threading

from doc_builder.translate import pipeline, publish, segment, validate

# ---------------------------------------------------------------- what a published tree must be


def published_pages(root):
    """Every published page, as {path: text}, taken from the generation the pointer names."""
    out = publish.current_dir(root)
    if out is None:
        return None
    return {p.relative_to(out).as_posix(): p.read_text(encoding="utf-8") for p in out.rglob("*") if p.is_file()}


def english_fallbacks(root, en_dir):
    """Published pages that are byte-for-byte their English source, i.e. not translated at all.

    A page that failed its checks falls back on purpose, so this is not automatically a fault --
    but a run that reported success and left pages here has published English under a Japanese
    banner, which is the thing worth catching.
    """
    tree = published_pages(root) or {}
    fallbacks = []
    for page, text in tree.items():
        if page == publish.TOCTREE:
            continue
        source = en_dir / page
        if source.is_file() and text == source.read_text(encoding="utf-8"):
            fallbacks.append(page)
    return sorted(fallbacks)


def assert_published_tree_is_sound(root, en_dir, allow_fallbacks=0):
    """Everything that must be true of a published tree, whatever the run did to get there.

    Call this after any run, successful or not. It is the check that a partial publish, a
    dangling sidebar entry or a silent revert to English cannot slip past.
    """
    current = publish.read_pointer(root)
    assert current, "nothing is published: CURRENT is missing or unreadable"

    out = publish.current_dir(root)
    assert out is not None, f"CURRENT names {current}, which is not a directory"

    tree = published_pages(root)
    assert publish.TOCTREE in tree, "the published generation has no sidebar"

    # the generation must be exactly what it claims to be
    assert publish.verify_generation(root, current, tree) == [], f"generation {current} does not verify against itself"

    # every sidebar entry must resolve to a page that is actually there
    import yaml

    sidebar = yaml.safe_load(tree[publish.TOCTREE])
    listed = set(pipeline.toctree_values(sidebar, "local"))
    present = {page.removesuffix(".md") for page in tree if page != publish.TOCTREE}
    assert not (listed - present), f"sidebar lists pages that are not published: {sorted(listed - present)[:5]}"

    fallbacks = english_fallbacks(root, en_dir)
    assert len(fallbacks) <= allow_fallbacks, f"{len(fallbacks)} page(s) published as raw English: {fallbacks[:5]}"
    return current


def assert_pointer_intact_after(root, before):
    """The pointer either did not move, or moved to a generation that is present and complete."""
    current = publish.read_pointer(root)
    assert current, "CURRENT disappeared"
    assert publish.current_dir(root) is not None, f"CURRENT names {current}, which is gone from the bucket"
    if current != before:
        tree = published_pages(root)
        assert publish.verify_generation(root, current, tree) == [], "promoted a generation that does not verify"


# ---------------------------------------------------------------------------- fault injection


def make_unreadable(path):
    """Make a page fail to read, on any platform.

    Not `chmod(0o000)`: Windows ignores POSIX permission bits, so the file stays readable, the
    run publishes happily, and a test meant to prove we fail closed proves nothing. It passed on
    Linux and macOS and failed only in CI.

    A directory where a file should be raises `OSError` from `read_text()` everywhere
    (`IsADirectoryError` on POSIX, `PermissionError` on Windows), and `rglob("*.md")` still
    lists it -- so the page is planned and then fails to read, which is the path under test.
    """
    path.unlink()
    path.mkdir()


class FailingWrites:
    """Make the Nth page write fail, the way a network filesystem does mid-run.

    Used to check that a run which dies partway leaves the published tree exactly as it was.
    """

    def __init__(self, monkeypatch, fail_on):
        self.calls = 0
        self.fail_on = fail_on
        import pathlib

        real = pathlib.Path.write_text

        def patched(path, data, *args, **kwargs):
            self.calls += 1
            if self.calls == self.fail_on:
                raise OSError("injected write failure")
            return real(path, data, *args, **kwargs)

        monkeypatch.setattr(pathlib.Path, "write_text", patched)


def pause_before_promote(monkeypatch, release):
    """Hold a publisher just before it moves the pointer, so another can overtake it.

    This is how an overlap is staged deterministically: A gets as far as a complete generation,
    B publishes a different one, then A is let go. Whatever order they finish in, the pointer has
    to end up naming a generation that is present and complete.
    """
    real = publish.promote

    def patched(root, generation):
        release.wait(timeout=10)
        return real(root, generation)

    monkeypatch.setattr(publish, "promote", patched)


def run_in_thread(fn):
    thread = threading.Thread(target=fn, daemon=True)
    thread.start()
    return thread


# ------------------------------------------------------------------- protected-Markdown attacks


def fake_translation(text):
    """A stand-in translation: keeps every marker, changes every piece of prose.

    Appending a character is enough. Markers and heading levels are untouched, and the prose
    differs from the English, so a clean page passes every check without needing a model.
    """
    masked, placeholders = segment.mask(text)
    parts = segment.split_blocks(masked)
    for i, part in enumerate(parts):
        if i % 2 == 0 and segment.has_prose(part):
            parts[i] = part + "。"
    masked_translation = segment.join_blocks(parts)
    return masked_translation, segment.restore(masked_translation, placeholders)


def validate_page(page, source, masked_translation, restored):
    masked_source, _ = segment.mask(source)
    return validate.validate_page(
        page, masked_source, masked_translation, glossary=None, source=source, restored=restored
    )


# What the model can actually damage
# ----------------------------------
#
# It is tempting to test protection by editing a finished page -- change a URL, drop the `!` of an
# image, rename an `[[autodoc]]` symbol -- and asserting a check objects. That test is worthless,
# and worse, it passes for the wrong reason. All of those things are placeholders by the time the
# model sees them, and `restore()` puts back the text taken from the *source*, so the model has no
# way to alter them. Editing the restored page injects damage at a point no code path can reach.
# (Measured: on a typical corpus page, not one raw `[` survives masking.)
#
# So the protection rests on one thing: was it masked at all? That is what `visible_hazards`
# checks. Anything it finds is something the model can edit and nothing downstream can miss --
# which is precisely the shape of every masking bug found in review so far.
#
# The damage the model *can* do is limited to the text it is handed: the markers, and the prose.
# `marker_mutations` covers the first, `structural_mutations` the second.

HAZARDS = {
    "markdown link or image": re.compile(rf"!?\[[^\]\n]*\]{segment.LINK_DEST}"),
    "reference link": re.compile(r"!?\[[^\]\n]*\]\[[^\]\n]*\]"),
    "reference definition": segment.REF_DEF_RE,
    "bare URL": re.compile(segment.BARE_URL),
    "code fence": re.compile(r"^[ \t]*(?:`{3,}|~{3,})", re.MULTILINE),
    "inline code": re.compile(r"`[^`\n]+`"),
    "html tag": re.compile(r"</?[a-zA-Z][^<>]{0,200}>"),
    "autodoc directive": re.compile(r"\[\[autodoc\]\]"),
    "doc-builder directive": re.compile(r"\[\[[^\]\n]*\]\]"),
    "block math": re.compile(r"\$\$"),
    "escaped-paren math": re.compile(r"\\\\\("),
    "html comment": re.compile(r"<!--"),
    "callout marker": re.compile(r"\[!\w+\]"),
    "inline math": re.compile(r"(?<![\\$])\$(?![\s$])[^$\n]{1,120}?(?<![\s\\])\$(?![\d$])"),
    "cross reference": re.compile(r"\[`[^`\n]+`\]"),
}


# A bracket pair whose entire contents is a marker. Ordinary prose brackets hold words --
# `[WIP]`, `list[str]`, `[ImagesKwargs]`, and 104 more like them across the corpus, which is why
# a raw bracket cannot simply be banned. A pair holding nothing but a marker is different: it is
# a link or a cross-reference that lost half its masking, so the model is looking at raw
# Markdown syntax it can "correct".
LEAKED_REF_DEF = re.compile(r"^[ \t]*\[[^\]\n]+\]:[ \t]*$", re.MULTILINE)

MARKER_ONLY_BRACKETS = re.compile(rf"\[\s*(?:{segment.PH_OPEN}\d+{segment.PH_CLOSE}\s*)+\]")


def _leaked_autodoc_members(source, visible):
    """Autodoc member lines the model can see, judged by the builder's own definition.

    The one hazard the patterns above cannot spot: an exposed `- forward` under an `[[autodoc]]`
    directive is indistinguishable from an ordinary bullet list, so looking for it with the same
    rule that is supposed to mask it proves nothing.

    So the oracle is `build_doc`, which decides what an autodoc block really is when the docs are
    built. Anything it calls a member of an autodoc block must not be visible here -- translate
    `forward` and the built page loses a method.
    """
    from doc_builder.build_doc import _re_autodoc, _re_list_item

    leaked = []
    in_block = False
    for line in source.splitlines():
        if _re_autodoc.match(line):
            in_block = True
            continue
        if in_block:
            member = _re_list_item.match(line)
            if member:
                if f"- {member.group(1)}" in visible:
                    leaked.append(("autodoc member line left visible", line.strip()[:60]))
                continue
            if line.strip():
                in_block = False
    return leaked


def visible_hazards(source):
    """Anything the model must not be able to touch, but still can.

    Run over the text as the model receives it: masked, with the markers blanked so a marker
    cannot be mistaken for content. Whatever comes back is unprotected.

    Complete constructs are only half of it. A masking rule that half-fires leaves a fragment --
    a `[` whose `](url)` was masked away -- and looking for whole links would never see it. So
    the bracket balance is checked too: correct masking either hides both brackets or neither.
    """
    masked, _ = segment.mask(source)
    visible = segment.PLACEHOLDER_RE.sub(" ", masked)
    found = []
    for kind, pattern in HAZARDS.items():
        for match in pattern.finditer(visible):
            found.append((kind, match.group(0)[:60]))
    for match in MARKER_ONLY_BRACKETS.finditer(masked):
        found.append(("bracket pair holding only a marker", match.group(0)[:60]))
    found.extend(_leaked_autodoc_members(source, visible))
    # A line that is nothing but `[label]:` once the markers are blanked. The URL was masked and
    # the label was not, so the model can translate a reference name and break the link. Looking
    # for the bracket pair alone would not do: `[WIP]` and `list[str]` are ordinary prose, and
    # there are 104 of those. A bracket pair alone on a line, followed by a colon, is not.
    for match in LEAKED_REF_DEF.finditer(visible):
        found.append(("reference definition label left visible", match.group(0).strip()[:60]))
    opens, closes = visible.count("["), visible.count("]")
    if opens != closes:
        found.append(("unbalanced brackets left visible", f"{opens} '[' against {closes} ']'"))
    return found


def marker_mutations(masked_translation):
    """Damage at the marker level -- the model dropping, repeating or inventing one."""
    indices = segment.placeholder_indices(masked_translation)
    out = {}
    if indices:
        first = f"{segment.PH_OPEN}{indices[0]}{segment.PH_CLOSE}"
        out["marker dropped"] = masked_translation.replace(first, "", 1)
        out["marker duplicated"] = masked_translation.replace(first, first + first, 1)
    out["marker invented"] = masked_translation + f"\n\n{segment.PH_OPEN}9999{segment.PH_CLOSE}\n"
    return out


def structural_mutations(masked_translation):
    """Damage to the prose the model is allowed to rewrite, but not to restructure."""
    out = {}
    heading = re.search(r"^(#{1,6})([ \t]+\S)", masked_translation, re.MULTILINE)
    if heading:
        out["heading level changed"] = (
            masked_translation[: heading.start()]
            + "#"
            + heading.group(1)
            + heading.group(2)
            + masked_translation[heading.end() :]
        )
        out["heading removed"] = (
            masked_translation[: heading.start()] + heading.group(2).strip() + masked_translation[heading.end() :]
        )
    return out
