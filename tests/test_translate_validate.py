"""One fixture per check -- three, not eight.

Each test forces exactly one check to fire, so a regression names the check that broke.
"""

from doc_builder.translate import segment, validate

GLOSSARY = {"pin": {"tokenizer": "トークナイザー"}, "keep": ["Hub"]}


def masked(text):
    return segment.mask(text)[0]


def test_clean_page_passes():
    src = masked("# Title\n\nThe `tokenizer` converts text.\n")
    trans = masked("# タイトル\n\n⟦0⟧はテキストを変換します。\n")
    r = validate.validate_page("p.md", src, trans)
    assert r.ok, r.failures


def test_dropped_placeholder_fails():
    src = masked("Use `from_pretrained` to load.\n")
    r = validate.validate_page("p.md", src, "読み込みます。\n")
    assert not r.ok
    assert any("dropped" in f for f in r.failures)


def test_invented_placeholder_fails():
    src = masked("Plain prose here.\n")
    r = validate.validate_page("p.md", src, f"訳文 {segment.PH_OPEN}99{segment.PH_CLOSE}\n")
    assert not r.ok
    assert any("invented" in f for f in r.failures)


def test_duplicated_placeholder_fails():
    src = masked("Call `fit` once.\n")
    r = validate.validate_page("p.md", src, "⟦0⟧と⟦0⟧を呼びます。\n")
    assert not r.ok
    assert any("duplicated" in f for f in r.failures)


def test_heading_loss_fails():
    src = masked("# One\n\n## Two\n\nProse.\n")
    trans = masked("# いち\n\nプロース。\n")
    r = validate.validate_page("p.md", src, trans)
    assert not r.ok
    assert any("heading structure" in f for f in r.failures)


def test_heading_depth_change_fails():
    src = masked("# One\n\n## Two\n")
    trans = masked("# いち\n\n### に\n")
    r = validate.validate_page("p.md", src, trans)
    assert not r.ok
    assert any("heading structure" in f for f in r.failures)


def test_english_echo_fails():
    src = masked("The model loads weights.\n")
    r = validate.validate_page("p.md", src, "The model loads weights.\n")
    assert not r.ok
    assert any("echoed its input" in f for f in r.failures)


def test_echo_check_is_language_general():
    """Regression: a CJK-only check rejected 100% of pages for ko, fr, es and de."""
    src = masked("The model loads weights.\n")
    for translation in ("모델이 가중치를 로드합니다.\n", "Le modele charge les poids.\n"):
        assert validate.validate_page("p.md", src, translation).ok


def test_empty_translation_fails():
    src = masked("Some prose.\n")
    r = validate.validate_page("p.md", src, "   \n")
    assert not r.ok
    assert any("empty" in f for f in r.failures)


def test_heading_inside_code_fence_is_not_counted():
    """A `#` in a shell snippet must not register as a heading.

    This is why validation runs on masked text: the fence is already a placeholder.
    """
    src = masked("# Real\n\n```bash\n# a comment, not a heading\necho hi\n```\n")
    assert validate.heading_levels(src) == [1]


def test_link_moved_to_another_line_fails():
    """The gap check 1 cannot see: placeholder present, but its `[` left behind."""
    source = "See [the guide](https://hf.co/docs) for details.\n"
    broken = "詳しくは[ガイドを参照してください。\n(https://hf.co/docs)\n"
    assert validate.check_links(source, broken)


def test_link_kept_adjacent_passes():
    source = "See [the guide](https://hf.co/docs) for details.\n"
    good = "詳しくは[ガイド](https://hf.co/docs)を参照してください。\n"
    assert validate.check_links(source, good) == []


def test_image_links_are_counted():
    source = "![Diagram](https://hf.co/a.png)\n"
    assert validate.check_links(source, "画像なし\n")


def test_link_check_needs_both_texts_to_run():
    """validate_page must not silently skip the check when only one side is passed."""
    src = masked("See [x](https://a.b) here.\n")
    r = validate.validate_page("p.md", src, "⟦0⟧を見てください。\n")
    assert r.ok  # no source/restored supplied -> link check not applicable
    r2 = validate.validate_page(
        "p.md",
        src,
        "⟦0⟧を見てください。\n",
        source="See [x](https://a.b) here.\n",
        restored="を見てください。\n(https://a.b)\n",
    )
    assert not r2.ok
    assert any("links broken" in f for f in r2.failures)


def test_glossary_drift_warns_but_does_not_fail():
    src = masked("The tokenizer lives on the Hub.\n")
    trans = "トークナイザーはハブにあります。\n"  # 'Hub' translated away
    r = validate.validate_page("p.md", src, trans, glossary=GLOSSARY)
    assert r.ok, r.failures
    assert any("Hub" in w for w in r.warnings)


def test_glossary_with_empty_keep_does_not_crash():
    """Regression: `keep:` with no items parses to None and raised TypeError mid-run."""
    gloss = {"pin": {"tokenizer": "トークナイザー"}, "keep": None}
    src = masked("The tokenizer is on the Hub.\n")
    r = validate.validate_page("p.md", src, "トークナイザー\n", glossary=gloss)
    assert r.ok, r.failures


def test_glossary_with_empty_pin_does_not_crash():
    gloss = {"pin": None, "keep": ["Hub"]}
    src = masked("On the Hub.\n")
    assert validate.validate_page("p.md", src, "Hub にあります。\n", glossary=gloss).ok


def test_glossary_satisfied_gives_no_warning():
    src = masked("The tokenizer lives on the Hub.\n")
    trans = "トークナイザーは Hub にあります。\n"
    r = validate.validate_page("p.md", src, trans, glossary=GLOSSARY)
    assert r.ok and not r.warnings


def test_summary_flags_high_rejection_rate():
    results = [validate.Result(page=f"p{i}.md") for i in range(100)]
    for r in results[:5]:
        r.failures.append("boom")
    out = validate.summarize(results)
    assert "95/100" in out and "5.0%" in out and "exceeds 2%" in out


def test_summary_clean_run_has_no_warning():
    out = validate.summarize([validate.Result(page="p.md")])
    assert "1/1" in out and "exceeds" not in out
