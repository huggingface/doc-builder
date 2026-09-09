# Copyright 2026 The HuggingFace Team. Licensed under the Apache License, Version 2.0.
"""Source-position extraction and translation acceptance."""

import re

PLACEHOLDER_RE = re.compile(r"¤(\d+)¤")


def placeholder_indices(text):
    return [int(m[1]) for m in PLACEHOLDER_RE.finditer(text)]


def extract_pages(sources, keep=(), normalize=False):
    """Extract prose containers through the kit's parser in one subprocess."""
    import json
    import subprocess

    from ..utils import locate_kit_folder

    helper = locate_kit_folder() / "preprocessors" / "translate.cjs"
    result = subprocess.run(
        ["node", str(helper)],
        input=json.dumps({"pages": sources, "keep": list(keep), "normalize": normalize}),
        text=True,
        encoding="utf-8",
        capture_output=True,
    )
    if result.returncode:
        raise ValueError(f"Cannot extract translation source: {result.stderr.strip()}")
    return json.loads(result.stdout)


def required(unit):
    """Only explicit keep terms, syntax, numbers and punctuation are exempt."""
    return any(c.isalpha() for c in PLACEHOLDER_RE.sub("", unit["text"]))


def accept_unit(unit, response):
    """Accept prose while preserving marker identities and inline pair nesting."""
    if not isinstance(response, str):
        raise ValueError("Missing translation")
    # Newlines in responses are prose reflow. Original structural line breaks are tokens.
    response = " ".join(response.split())
    ids = placeholder_indices(response)
    if sorted(ids) != list(range(len(unit["tokens"]))):
        raise ValueError("Translation changed protected markers")
    stack = []
    for i in ids:
        token = unit["tokens"][i]
        if token["kind"] == "open":
            stack.append(token["pair"])
        elif token["kind"] == "close":
            if not stack or stack.pop() != token["pair"]:
                raise ValueError("Translation changed inline nesting")
    if stack:
        raise ValueError("Translation left an inline element open")
    if token_structure(unit["tokens"]) != token_structure([unit["tokens"][i] for i in ids]):
        raise ValueError("Translation changed inline element containment")
    plain = PLACEHOLDER_RE.sub("", response)
    if re.search(r"[⟦⟧]\d+[⟦⟧]", plain):
        raise ValueError("Translation invented a marker")
    if re.search(r"[¤\\`*_[\]{}<>|~!#$]", plain):
        raise ValueError("Translation introduced markup")
    if required(unit):

        def words(text):
            return "".join(c.lower() for c in PLACEHOLDER_RE.sub("", text) if c.isalnum())

        if not any(c.isalpha() for c in plain) or words(response) == words(unit["text"]):
            raise ValueError("Translation is empty or echoes the source")
    elif response != " ".join(unit["text"].split()):
        raise ValueError("Translation changed a protected-only unit")
    leading = re.match(r"\s*", unit["text"])[0]
    trailing = re.search(r"\s*$", unit["text"])[0]
    return leading + response.strip() + trailing


def render_page(plan, responses):
    if len(responses) != len(plan["units"]):
        raise ValueError("Incomplete translated page")
    pieces = []
    for prefix, unit, response in zip(plan["pieces"][:-1], plan["units"], responses, strict=True):
        accepted = accept_unit(unit, response) if required(unit) else unit["text"]
        pieces.append(prefix + PLACEHOLDER_RE.sub(lambda m, unit=unit: unit["tokens"][int(m[1])]["raw"], accepted))
    return "".join(pieces) + plan["pieces"][-1]


def token_structure(tokens):
    roots, stack = [], []
    for token in tokens:
        if token["kind"] == "close":
            if not stack or stack[-1][0] != token["pair"]:
                raise ValueError("Invalid inline nesting")
            _, opening, children = stack.pop()
            item = ("pair", opening, token["raw"], tuple(sorted(children)))
        elif token["kind"] == "open":
            stack.append((token["pair"], token["raw"], []))
            continue
        else:
            item = ("opaque", token["raw"])
        (stack[-1][2] if stack else roots).append(item)
    if stack:
        raise ValueError("Unclosed inline element")
    return tuple(sorted(roots))


def structure(plan):
    return (plan["pieces"], [(u["kind"], token_structure(u["tokens"])) for u in plan["units"]])


def validate_pages(originals, translations, keep=()):
    plans = extract_pages(translations, keep)
    for original, translated in zip(originals, plans, strict=True):
        if structure(original) != structure(translated):
            raise ValueError("Translation changed document structure or protected content")
        for before, after in zip(original["units"], translated["units"], strict=True):
            if required(before):
                accept_unit({**after, "text": before["text"]}, after["text"])
    return plans
