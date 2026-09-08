"""Source-position adapter feasibility gate; no model, Bucket, or GPU required."""

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def extract(pages):
    result = subprocess.run(
        ["node", str(ROOT / "kit/preprocessors/translate.cjs")],
        input=json.dumps({"pages": pages}),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def restore(plan):
    return "".join(
        piece
        + (
            re.sub(r"¤(\d+)¤", lambda m, i=i: plan["units"][i]["tokens"][int(m[1])]["raw"], plan["units"][i]["text"])
            if i < len(plan["units"])
            else ""
        )
        for i, piece in enumerate(plan["pieces"])
    )


CASES = [
    ("<Tip>\nRead **this** [guide](url).\n</Tip>\n", ["Read", "this", "guide"], ["<Tip>", "url"]),
    ("[[autodoc]] BertModel\n\n    - forward\n\nMore prose.\n", ["More prose"], ["BertModel", "forward"]),
    ("```python\nx = 1\n````\n\nTranslate this.\n", ["Translate this"], ["x = 1"]),
    ("> ~~~python\n> x = 1\n> ~~~~\n>\n> Translate this.\n", ["Translate this"], ["x = 1"]),
    (
        "## 😀 Introduction\n\nRead 😀 [technical\nreport](https://e/Fine_(LED)).\n",
        ["Introduction", "technical", "report"],
        ["https://"],
    ),
    ("| Name | Value |\n| --- | --- |\n| Hello | World |\n", ["Name", "Value", "Hello", "World"], []),
    ("[![Open notebook](badge.svg)](notebook.ipynb)\n", ["Open notebook"], ["badge.svg", "notebook.ipynb"]),
    ("![Diagram][fig]\n\n[fig]: foo.png\n", ["Diagram"], ["fig", "foo.png"]),
    ("Use $x$ and \\\\(y\\\\). Costs US$5 to US$10 or $5-$10.\n", ["Use", "and", "Costs", "to", "or"], ["(y", "x$"]),
    (
        '<literalinclude>\n{"path": "examples/script.py"}\n</literalinclude>\n\nRead this.\n',
        ["Read this"],
        ["examples/script.py"],
    ),
    ("Use [`Pipeline`] to run.\n", ["Use", "to run"], ["Pipeline"]),
    ("Go to https://hf.co/docs now.\n", ["Go to", "now"], ["https://"]),
]


@pytest.mark.parametrize("source,visible,hidden", CASES)
def test_source_visibility(source, visible, hidden):
    plan = extract([source])[0]
    assert restore(plan) == source
    prose = "\n".join(u["text"] for u in plan["units"])
    for word in visible:
        assert word in prose
    for word in hidden:
        assert word not in prose


def test_corpus_roundtrip_and_visibility():
    root = Path(os.environ.get("EN_DOCS", ROOT / "tests/fixtures/translate_corpus"))
    paths = sorted(p for p in root.rglob("*") if p.suffix in {".md", ".mdx"} and p.name != "README.md")
    assert paths, f"No corpus at {root}"
    sources = [p.read_text() for p in paths]
    for path, source, plan in zip(paths, sources, extract(sources), strict=True):
        assert restore(plan) == source, path
        assert plan["units"], path
        visible = "\n".join(u["text"] for u in plan["units"])
        assert not re.search(r"https?://|\[\[autodoc\]\]", visible), (path, visible)


def test_translated_corpus_structure():
    from doc_builder.translate.segment import extract_pages, render_page, required

    root = Path(os.environ.get("EN_DOCS", ROOT / "tests/fixtures/translate_corpus"))
    paths = sorted(p for p in root.rglob("*") if p.suffix in {".md", ".mdx"} and p.name != "README.md")
    plans = extract_pages([p.read_text() for p in paths], normalize=True)
    translations = []
    for plan in plans:
        responses = []
        for unit in plan["units"]:
            responses.append(
                re.sub(
                    r"¤\d+¤|[^¤]+",
                    lambda m: m[0]
                    if m[0].startswith("¤")
                    else (
                        re.match(r"\s*", m[0])[0] + "翻訳です。" + re.search(r"\s*$", m[0])[0]
                        if m[0].strip()
                        else m[0]
                    ),
                    unit["text"],
                )
                if required(unit)
                else unit["text"]
            )
        translations.append(render_page(plan, responses))
    translated_plans = extract_pages(translations)
    from doc_builder.translate.segment import structure

    for path, before, after in zip(paths, plans, translated_plans, strict=True):
        assert structure(before) == structure(after), path
