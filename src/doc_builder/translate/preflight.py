# Copyright 2026 The HuggingFace Team. Licensed under the Apache License, Version 2.0.
"""CPU-only label inventory and synthetic translation checks; no model or Hub calls."""

import re
from collections import Counter

from . import pipeline, segment


def sample(unit, move=False):
    if not segment.required(unit):
        return unit["text"]
    text = re.sub(
        r"¤\d+¤|[^¤]+",
        lambda m: m[0]
        if m[0].startswith("¤") or not m[0].strip()
        else re.match(r"\s*", m[0])[0] + "翻訳です。" + re.search(r"\s*$", m[0])[0],
        unit["text"],
    )
    # Move the first complete link/formatting pair ahead of its introductory prose.
    # Keep spaces and all other prose in place so the probe does not invent invalid Markdown.
    if move and unit["tokens"] and unit["tokens"][0]["kind"] == "open":
        closing = next(
            i for i, t in enumerate(unit["tokens"]) if t["kind"] == "close" and t["pair"] == unit["tokens"][0]["pair"]
        )
        match = re.search(rf"¤0¤.*?¤{closing}¤", text, re.S)
        if match and text[: match.start()].strip():
            text = match[0] + " " + text[: match.start()].strip() + " " + text[match.end() :].lstrip()
    return text


def fences(text):
    opened = None
    lines = []
    indent = 0
    for line in text.splitlines(keepends=True):
        if opened:
            lines.append(line)
            if re.fullmatch(
                r" {0," + str(indent + 3) + "}" + re.escape(opened[0]) + r"{" + str(len(opened)) + r",}[ \t]*\r?\n?",
                line,
            ):
                yield "".join(lines)
                opened = None
                lines = []
        elif m := re.match(r"^( {0,3})(`{3,}|~{3,})[^\r\n]*", line):
            indent = len(m[1])
            opened = m[2]
            lines = [line]
    if opened:
        yield "".join(lines)


def check(files, config):
    documents = pipeline.prepare_documents(files, config)
    blocks = {
        name: Counter(fences(data.decode()))
        for name, data in files.items()
        if name in documents and name != "_toctree.yml"
    }
    report = {
        "fenced_blocks": sum(sum(v.values()) for v in blocks.values()),
        "pages": len(documents) - 1,
        "preserved_labels": [],
        "review_labels": [],
        "errors": [],
    }
    for name, plans in documents.items():
        for pi, plan in enumerate(plans):
            for ui, unit in enumerate(plan["units"]):
                text = segment.PLACEHOLDER_RE.sub(lambda m, unit=unit: unit["tokens"][int(m[1])]["raw"], unit["text"])
                item = {"page": name, "part": pi + 1, "unit": ui + 1, "kind": unit["kind"], "text": text}
                if not segment.required(unit):
                    report["preserved_labels"].append(item)
                elif unit.get("translate") is None and len(text) <= 80 and len(text.split()) <= 6:
                    # Candidates for human review, never an automatic exemption from translation.
                    report["review_labels"].append(item)
    # Validate batches to avoid starting Node once per page, but attribute failures individually.
    for move in (False, True):
        originals, translations, owners = [], [], []
        for name, plans in documents.items():
            for plan in plans:
                try:
                    translated = segment.render_page(plan, [sample(u, move) for u in plan["units"]])
                    for block, count in blocks.get(name, {}).items():
                        if plan["source"].count(block) < count or translated.count(block) < count:
                            raise ValueError("Fenced code changed")
                    translations.append(translated)
                    originals.append(plan)
                    owners.append(name)
                except ValueError as exc:
                    report["errors"].append({"page": name, "move_prose": move, "error": str(exc)})
        extracted = segment.extract_pages(translations, originals[0]["keep"] if originals else ())
        for name, before, after in zip(owners, originals, extracted, strict=True):
            if segment.structure(before) != segment.structure(after):
                report["errors"].append({"page": name, "move_prose": move, "error": "Structure changed"})
    return report
