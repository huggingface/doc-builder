"""One fixture per check -- three, not eight.

Each test forces exactly one check to fire, so a regression names the check that broke.
"""

from doc_builder.translate import segment, validate

GLOSSARY = {"pin": {"tokenizer": "トークナイザー"}, "keep": ["Hub"]}


def masked(text):
    return segment.mask(text)[0]


def test_clean_page_passes():
    src = masked("# Title\n\nThe `tokenizer` converts text.\n")
    trans = masked("# タイトル\n\n¤0¤はテキストを変換します。\n")
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
    r = validate.validate_page("p.md", src, "¤0¤と¤0¤を呼びます。\n")
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


def test_stray_bracket_after_a_link_fails():
    """Regression: `[text](url)]` is a valid link plus junk, so counting links let it through.

    This shipped on chat_templating.md's first line -- 3 of them -- and the page passed.
    """
    source = "See [the guide](https://hf.co/docs) for details.\n"
    junk = "詳しくは[ガイド](https://hf.co/docs)]を参照してください。\n"
    assert validate.check_links(source, junk)
    assert "stray" in validate.check_links(source, junk)[0]


def test_stray_bracket_already_in_the_source_is_not_flagged():
    """Only count brackets the model added, not ones the English page already had."""
    source = "Odd but legal: [x](https://a.b)]\n"
    same = "変だが合法: [x](https://a.b)]\n"
    assert validate.check_links(source, same) == []


def test_keep_published_rejects_a_page_that_no_longer_passes(tmp_path):
    """Regression: a page published under weaker checks survived later runs.

    continuous_batching.md sat in the bucket with 8 stray brackets for two runs, kept each time
    because the fresh attempt failed for an unrelated reason.
    """
    from doc_builder.commands.translate import keep_published
    from doc_builder.translate.pipeline import add_disclosure

    source = "See [the guide](https://hf.co/docs) now.\n"
    page = tmp_path / "p.md"

    def check(text):
        page.write_text(text, encoding="utf-8")
        return keep_published(page, source, "p.md", "ja", "transformers")

    assert (
        check(add_disclosure("詳しくは[ガイド](https://hf.co/docs)]を参照。\n", "p.md", "ja", "transformers")) is None
    )

    # It gives back the text rather than a yes/no, because the tree is now assembled in memory
    # before any of it is published, so the caller needs the page itself and not permission.
    clean = add_disclosure("詳しくは[ガイド](https://hf.co/docs)を参照。\n", "p.md", "ja", "transformers")
    assert check(clean) == clean

    assert keep_published(tmp_path / "missing.md", source, "p.md", "ja", "transformers") is None


def test_keep_published_accepts_what_this_command_publishes(tmp_path):
    """A page produced by this command has to survive its own retention check.

    It did not. Every published page carries the machine-translation banner, and the banner's
    two links were compared against the bare English source, so `check_links` reported them as
    invented and threw the page away -- meaning the "keep the last good translation" path never
    once kept anything, and every failed update replaced good Japanese with raw English.
    """
    from doc_builder.commands.translate import keep_published
    from doc_builder.translate.pipeline import add_disclosure

    source = "# Title\n\nSee [the guide](https://hf.co/docs) and [another](https://hf.co/x).\n"
    japanese = "# タイトル\n\n[ガイド](https://hf.co/docs)と[もう一つ](https://hf.co/x)を参照。\n"
    published = add_disclosure(japanese, "p.md", "ja", "transformers")
    page = tmp_path / "p.md"
    page.write_text(published, encoding="utf-8")

    assert keep_published(page, source, "p.md", "ja", "transformers") == published


def test_image_links_are_counted():
    source = "![Diagram](https://hf.co/a.png)\n"
    assert validate.check_links(source, "画像なし\n")


def test_link_check_needs_both_texts_to_run():
    """validate_page must not silently skip the check when only one side is passed."""
    src = masked("See [x](https://a.b) here.\n")
    # a link is two markers now -- one per bracket -- so a good translation carries both
    r = validate.validate_page("p.md", src, "¤0¤x¤1¤を見てください。\n")
    assert r.ok  # no source/restored supplied -> link check not applicable
    r2 = validate.validate_page(
        "p.md",
        src,
        "¤0¤x¤1¤を見てください。\n",
        source="See [x](https://a.b) here.\n",
        restored="を見てください。\n(https://a.b)\n",
    )
    assert not r2.ok
    # the destination is named, not just counted -- that is what makes the message actionable
    assert any("lost or altered" in f and "https://a.b" in f for f in r2.failures)


def test_invented_bracket_fails():
    """Regression: 176 of these shipped across 26 pages, passing every check there was.

    The model copies a marker back in different brackets next to the real one. Both real
    markers are present and correct, so the marker check is happy, the link count is
    unchanged, and `⟦0⟧` lands in the published page.
    """
    src = masked("See [the guide](https://hf.co/docs) now.\n")
    r = validate.validate_page("p.md", src, "⟦0⟧¤0¤ガイド¤1¤⟦1⟧をご覧ください。\n")
    assert not r.ok
    assert any("invented bracket" in f for f in r.failures)


def test_invented_bracket_already_in_the_source_is_not_flagged():
    src = masked("Maths: ⟦x⟧ is a thing.\n")
    r = validate.validate_page("p.md", src, "数学: ⟦x⟧ というものです。\n")
    assert r.ok, r.failures


def test_echoed_markers_are_stripped_before_the_check_sees_them():
    """The numbered form is litter next to a correct translation, so it is removed, not rejected."""
    from doc_builder.translate.pipeline import strip_echoed_markers

    assert strip_echoed_markers("⟦0⟧¤0¤ガイド¤1¤⟦1⟧をご覧ください。") == "¤0¤ガイド¤1¤をご覧ください。"
    # the model is not consistent about which bracket it uses at each end
    assert strip_echoed_markers("🙂 ポジティブ⟧1⟧、🙁 ネガティブ⟧1⟧") == "🙂 ポジティブ、🙁 ネガティブ"
    # a lone bracket is not the known form, so it survives for the check to reject
    assert strip_echoed_markers("Gemma 4⟧¤396¤") == "Gemma 4⟧¤396¤"


def test_stray_bracket_costs_one_paragraph_not_the_page():
    """A lone `⟧` drops its own paragraph to English; the rest of the page still publishes.

    Two pages in the first full run had exactly one stray character in them. Rejecting the
    whole page for that would throw away a page of good Japanese.
    """
    from doc_builder.translate.pipeline import PagePlan, assemble_page

    plan = PagePlan("p.md", "First para.\n\nSecond para.\n", "ja", "m", "sha")
    keys = [u.key for u in plan.units.values()]
    _, restored, outcome = assemble_page(plan, {keys[0]: "最初の段落。", keys[1]: "二番目の段落⟧"})

    assert outcome.rejected == [keys[1]]
    assert "最初の段落。" in restored  # good paragraph kept
    assert "Second para." in restored  # bad one back to English
    assert "⟧" not in restored


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
    out = validate.summarize(results, 0.02)
    assert "95/100" in out and "5.0%" in out and "exceeds 2%" in out


def test_summary_shows_warnings_on_pages_that_passed():
    """Regression: a page could pass with an English paragraph in it and say nothing.

    Only failures were printed, so "quicktour.md passed" hid the very number worth watching.
    """
    passed_with_warning = validate.Result(page="quicktour.md")
    passed_with_warning.warnings.append("1 paragraph(s) kept in English: markers not preserved")
    silent = validate.Result(page="installation.md")

    out = validate.summarize([passed_with_warning, silent], 0.02)
    assert "2/2 pages passed" in out
    assert "quicktour.md" in out  # shown despite passing
    assert "kept in English" in out
    assert "installation.md" not in out  # nothing to report, stays quiet


def test_summary_clean_run_has_no_warning():
    out = validate.summarize([validate.Result(page="p.md")], 0.02)
    assert "1/1" in out and "exceeds" not in out


def test_image_turned_into_a_link_is_caught():
    """Dropping the `!` keeps every marker and changes what the page shows.

    `[![Open In Colab](badge.svg)](notebook.ipynb)` with the `!` removed is still well-formed
    markdown with the same link count, so nothing but the kind gives it away.
    """
    source = "[![Open In Colab](badge.svg)](notebook.ipynb)\n"
    # a set, because check_links compares multisets -- Japanese word order moves links about
    assert set(validate.link_targets(source)) == {("link", "(notebook.ipynb)"), ("image", "(badge.svg)")}
    problems = validate.check_links(source, source.replace("[!", "["))
    assert problems
    assert any("image (badge.svg)" in p for p in problems)


def test_nested_link_destinations_are_both_recorded():
    """The outer destination used to be invisible -- only the inner one was ever compared."""
    source = "[![alt](inner.svg)](outer.ipynb)\n"
    assert set(validate.link_targets(source)) == {("link", "(outer.ipynb)"), ("image", "(inner.svg)")}
    # rewriting only the outer destination has to be caught
    assert validate.check_links(source, "[![alt](inner.svg)](other.ipynb)\n")


def test_correct_japanese_after_a_bare_url_is_not_rejected():
    """Japanese attaches particles with no space, and that is not a changed URL.

    Regression: bare URLs were rediscovered in the finished page, so
    `https://…/DeepSeek-V3を参照してください` read as one longer URL and a perfectly correct
    translation came back as one URL lost and another gained -- failing every page in the corpus
    that mentions a URL in prose.
    """
    source = "See https://github.com/deepseek-ai/DeepSeek-V3 for details.\n"
    translated = "https://github.com/deepseek-ai/DeepSeek-V3を参照してください。\n"
    assert validate.check_links(source, translated) == []


def test_a_changed_bare_url_is_caught_by_the_marker_check():
    """The URL guarantee comes from masking, not from re-reading the output.

    A bare URL is a placeholder by the time the model sees it, so it cannot be edited without
    the marker going missing -- which is what makes rescanning the finished page unnecessary as
    well as wrong.
    """
    source = "See https://github.com/deepseek-ai/DeepSeek-V3 for details.\n"
    masked, placeholders = segment.mask(source)
    assert placeholders == ["https://github.com/deepseek-ai/DeepSeek-V3"]
    assert validate.check_placeholders(masked, "参照してください。\n")


def test_nested_opener_is_closed_by_a_plain_bracket():
    """A `]` closes its opener whether or not a destination follows it.

    Regression: the scanner popped only on `](`, so deleting the inner `[` of
    `[huggingface_hub[cli]](url)` left a stale opener that paired with the later destination.
    The targets came out identical and the damage passed.
    """
    source = "[huggingface_hub[cli]](https://hf.co/x)\n"
    damaged = "[huggingface_hubcli]](https://hf.co/x)\n"
    assert validate.check_links(source, damaged)


def test_reference_image_kind_is_recorded():
    """`![Diagram][fig]` losing its `!` keeps the reference and the target; only the kind moves."""
    source = "![Diagram][fig]\n\n[fig]: https://hf.co/a.png\n"
    assert ("ref-image", "fig") in validate.link_targets(source)
    assert validate.check_links(source, source.replace("![", "[", 1))
