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

"""Parameterized runnable blocks: run one documented snippet on several checkpoints and load options.

A page lists the values in its frontmatter, under ``runnable``:

    ---
    runnable:
      checkpoints:
        - HuggingFaceTB/SmolLM-135M
        - HuggingFaceTB/SmolLM-360M
      load_kwargs:
        default: {}
        eager: {attn_implementation: eager}
    ---

A block opts in with fence attributes naming where the values go:

    ```py runnable:generate checkpoints="model_id" load_kwargs="model"

``checkpoints`` names the variable whose string literal is the checkpoint; ``load_kwargs`` names the
variable assigned from a ``from_pretrained(...)`` call, which receives the load options as keyword
arguments. Both are removed from the rendered page, so the docs show the snippet as written.
"""

import ast
import re
import shlex

import yaml

FRONTMATTER_KEY = "runnable"
PARAMETER_ATTRIBUTES = ("checkpoints", "load_kwargs")

_FRONTMATTER = re.compile(r"\A---\n(?P<body>.*?\n)?---\n", re.DOTALL)


def parse_fence_attributes(flags: str) -> dict[str, str]:
    """``key=value`` tokens of a fence's info string (after the language), quotes optional."""
    attributes = {}
    for token in shlex.split(flags):
        key, sep, value = token.partition("=")
        if sep:
            attributes[key] = value
    return attributes


def parse_runnable_frontmatter(text: str) -> dict:
    """The page's ``runnable`` frontmatter section, or ``{}``."""
    match = _FRONTMATTER.match(text)
    if not match:
        return {}
    data = yaml.safe_load(match.group("body") or "") or {}
    section = data.get(FRONTMATTER_KEY, {}) if isinstance(data, dict) else {}
    if not isinstance(section, dict):
        raise ValueError(f"frontmatter `{FRONTMATTER_KEY}` must be a mapping, got {section!r}")
    load_kwargs = section.get("load_kwargs", {})
    if not isinstance(load_kwargs, dict) or not all(isinstance(v, dict) for v in load_kwargs.values()):
        raise ValueError("frontmatter `runnable.load_kwargs` must map a name to keyword arguments")
    return section


def strip_runnable_frontmatter(text: str) -> str:
    """Remove the ``runnable`` key from the frontmatter, and the frontmatter itself if nothing else is left."""
    match = _FRONTMATTER.match(text)
    if not match:
        return text
    kept, skipping = [], False
    for line in (match.group("body") or "").splitlines(keepends=True):
        if re.match(rf"{FRONTMATTER_KEY}\s*:", line):
            skipping = True
            continue
        if skipping and (not line.strip() or line[0] in " \t"):
            continue
        skipping = False
        kept.append(line)
    if not "".join(kept).strip():
        return text[match.end() :].lstrip("\n")
    return f"---\n{''.join(kept)}---\n" + text[match.end() :]


def parameter_cases(attributes: dict[str, str], frontmatter: dict) -> list[tuple[str, str | None, dict | None]]:
    """``(case id, checkpoint, load kwargs)`` for each combination a block asks for; ``[]`` if none."""
    checkpoints = frontmatter.get("checkpoints") if "checkpoints" in attributes else None
    load_kwargs = frontmatter.get("load_kwargs") if "load_kwargs" in attributes else None
    if not checkpoints and not load_kwargs:
        return []
    cases = []
    for checkpoint in checkpoints or [None]:
        for name, kwargs in (load_kwargs or {None: None}).items():
            parts = [checkpoint.rsplit("/", 1)[-1] if checkpoint else None, name]
            cases.append(("-".join(p for p in parts if p), checkpoint, kwargs))
    return cases


def bind_runnable_code(code: str, attributes: dict[str, str], checkpoint=None, load_kwargs=None) -> str:
    """The block's code with ``checkpoint`` and ``load_kwargs`` swapped in, everything else byte for byte.

    Raises ``ValueError`` when an attribute names nothing to bind, so a renamed variable cannot
    silently test the documented default instead.
    """
    tree = ast.parse(code)
    offsets = _line_offsets(code)
    edits = []  # (start, end, replacement), as character offsets

    def span(node):
        return _offset(code, offsets, node.lineno, node.col_offset), _offset(
            code, offsets, node.end_lineno, node.end_col_offset
        )

    def assignments(name):
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(isinstance(t, ast.Name) and t.id == name for t in targets):
                    yield node.value

    if checkpoint is not None:
        name = attributes["checkpoints"]
        literals = [v for v in assignments(name) if isinstance(v, ast.Constant) and isinstance(v.value, str)]
        if not literals:
            raise ValueError(f'checkpoints={name!r}: no `{name} = "..."` assignment in the block')
        edits += [(*span(v), repr(checkpoint)) for v in literals]

    if load_kwargs:
        name = attributes["load_kwargs"]
        calls = [
            node
            for value in assignments(name)
            for node in ast.walk(value)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "from_pretrained"
        ]
        if not calls:
            raise ValueError(f"load_kwargs={name!r}: no `{name} = ....from_pretrained(...)` in the block")
        for call in calls:
            given = {kw.arg: kw for kw in call.keywords if kw.arg}
            added = []
            for key, value in load_kwargs.items():
                if key in given:  # the snippet already passes it: the case's value wins
                    edits.append((*span(given[key].value), repr(value)))
                else:
                    added.append(f"{key}={value!r}")
            if not added:
                continue
            last = [*call.args, *call.keywords][-1:] if (call.args or call.keywords) else []
            if last:
                edits.append((span(last[0])[1], span(last[0])[1], ", " + ", ".join(added)))
            else:
                end = span(call)[1] - 1  # the closing parenthesis
                edits.append((end, end, ", ".join(added)))

    for start, end, replacement in sorted(edits, reverse=True):
        code = code[:start] + replacement + code[end:]
    return code


def _line_offsets(code):
    offsets, total = [], 0
    for line in code.splitlines(keepends=True):
        offsets.append(total)
        total += len(line)
    return offsets


def _offset(code, offsets, lineno, col_offset):
    """Character offset of an AST position (``col_offset`` counts UTF-8 bytes)."""
    start = offsets[lineno - 1]
    line = code[start : offsets[lineno] if lineno < len(offsets) else len(code)]
    return start + len(line.encode("utf-8")[:col_offset].decode("utf-8"))
