# Copyright 2026 The HuggingFace Team. Licensed under the Apache License, Version 2.0.
"""Source-position extraction and translation acceptance."""

import re
from collections import Counter

PLACEHOLDER_RE = re.compile(r"¤(\d+)¤")


class InvalidUnit(ValueError):
    def __init__(self, message, page, unit):
        super().__init__(message)
        self.page, self.unit = page, unit


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
    return [{**plan, "keep": list(keep)} for plan in json.loads(result.stdout)]


def required(unit):
    """Preserve isolated acronym labels, numbers, and protected content."""
    if unit.get("translate") is not None:
        return unit["translate"]
    prose = PLACEHOLDER_RE.sub("", unit["text"])
    # Strip identifiers only for label classification; surrounding prose still needs translation.
    prose = re.sub(
        r"\b(?=[\w.-]*(?:[a-z][A-Z]|[A-Z]{2,}[a-z]|[A-Za-z][.-]?\d|\d[.-]?[A-Za-z]|_))[\w.-]+\b",
        "",
        prose,
    )
    if re.fullmatch(r"(?:v\d+)?/[\w./-]+", prose.strip()):
        return False
    # Units and benchmark notation are labels, not English sentences.
    prose = re.sub(r"\bTop\s+\d+|\b\d+(?:\.\d+)?(?:[eE][+-]?\d+|[kKMGTB](?:-[a-z])?)?", "", prose)
    words = [
        word for word in re.findall(r"[^\W\d_]+", prose) if word not in {"tok", "s", "ms", "px", "m", "MB", "GB", "TB"}
    ]
    return bool(words) and not re.fullmatch(r"[A-Z]+(?: [A-Z])?", " ".join(words))


def accept_unit(unit, response):
    """Accept prose while preserving marker identities and inline pair nesting."""
    if not isinstance(response, str):
        raise ValueError("Missing translation")
    # Newlines in responses are prose reflow. Original structural line breaks are tokens.
    response = " ".join(response.split())
    ids = placeholder_indices(response)
    if sorted(ids) != list(range(len(unit["tokens"]))):
        raise ValueError(
            f"Translation changed protected markers: expected IDs {list(range(len(unit['tokens'])))}, got {ids}"
        )
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
    if required(unit):
        names = {i for i, t in enumerate(unit["tokens"]) if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 .()-]*", t["raw"])}
        for i in names:
            response = re.sub(rf"(?<=[A-Za-z0-9])¤{i}¤", f" ¤{i}¤", response)
            response = re.sub(rf"¤{i}¤(?=[A-Za-z0-9])", f"¤{i}¤ ", response)
        response = re.sub(
            r"¤(\d+)¤(?=¤(\d+)¤)",
            lambda m: m[0] + (" " if int(m[1]) in names and int(m[2]) in names else ""),
            response,
        )
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


def token_structure(tokens, names=None):
    roots, stack = [], []
    for token in tokens:
        # Repeated prose names are not new syntax; required occurrences still retain their containment.
        if token["kind"] == "name" and names is not None:
            if not names[token["raw"]]:
                continue
            names[token["raw"]] -= 1
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
    plans = extract_pages(translations, originals[0].get("keep", keep) if originals else keep)
    for pi, (original, translated) in enumerate(zip(originals, plans, strict=True)):
        if original["pieces"] != translated["pieces"] or len(original["units"]) != len(translated["units"]):
            raise ValueError(
                "Translation changed document structure or protected content: page skeleton or unit count"
            )
        for ui, (before, after) in enumerate(zip(original["units"], translated["units"], strict=True)):
            try:
                if before["kind"] != after["kind"] or token_structure(before["tokens"]) != token_structure(
                    after["tokens"], Counter(t["raw"] for t in before["tokens"] if t["kind"] == "name")
                ):
                    raise ValueError(f"Translation changed document structure or protected content in unit {ui + 1}")
                accept_unit({**after, "text": before["text"], "translate": before.get("translate")}, after["text"])
            except ValueError as exc:
                raise InvalidUnit(str(exc), pi, ui) from exc
    return plans
