import pytest

from doc_builder.testing import DocIntegrationTest


def test_runnable_block_failure_has_context(tmp_path):
    md_path = tmp_path / "doc.md"
    md_path.write_text("```py runnable\nraise RuntimeError('boom')\n```", encoding="utf-8")

    class FailingDocTest(DocIntegrationTest):
        doc_path = md_path

    # Dynamic test should be created with the default name.
    assert hasattr(FailingDocTest, "test_doc_block_0")

    with pytest.raises(AssertionError) as excinfo:
        FailingDocTest(methodName="test_doc_block_0").test_doc_block_0()

    message = str(excinfo.value)
    assert "doc_block_0" in message
    assert str(md_path) in message
    assert "raise RuntimeError('boom')" in message


def test_named_runnable_blocks_have_clean_test_names(tmp_path):
    md_path = tmp_path / "doc.md"
    md_path.write_text(
        "```py runnable:foo\nx = 1\n```\n```py runnable:test_bar\nraise ValueError('x')\n```",
        encoding="utf-8",
    )

    class CustomDocTest(DocIntegrationTest):
        doc_path = md_path

    # Methods derived from names: foo -> test_foo, test_bar stays test_bar
    assert hasattr(CustomDocTest, "test_foo")
    assert hasattr(CustomDocTest, "test_bar")

    # First block should succeed
    CustomDocTest(methodName="test_foo").test_foo()

    # Second block should fail with contextual message
    with pytest.raises(AssertionError) as excinfo:
        CustomDocTest(methodName="test_bar").test_bar()

    message = str(excinfo.value)
    assert "test_bar" in message
    assert "raise ValueError('x')" in message


def test_custom_runnable_flag(tmp_path):
    md_path = tmp_path / "doc.md"
    md_path.write_text("```py docrun:test_alpha\nx = 1\nassert x == 1\n```", encoding="utf-8")

    class CustomFlagDocTest(DocIntegrationTest):
        doc_path = md_path
        runnable_flag = "docrun"

    assert hasattr(CustomFlagDocTest, "test_alpha")
    CustomFlagDocTest(methodName="test_alpha").test_alpha()


def test_runnable_block_continuations_share_state_and_cleanup(tmp_path):
    md_path = tmp_path / "doc.md"
    md_path.write_text(
        "\n".join(
            [
                "```py runnable:test_basic",
                "state = ['first']",
                "```",
                "```py runnable:test_basic:2",
                "state.append('second')",
                "assert state == ['first', 'second']",
                "```",
                "```py runnable:test_isolated",
                "assert 'state' not in globals()",
                "```",
            ]
        ),
        encoding="utf-8",
    )

    cleanup_calls = []

    def cleanup():
        cleanup_calls.append("cleanup")

    class ContinuedDocTest(DocIntegrationTest):
        doc_path = md_path
        cleanup_func = staticmethod(cleanup)

    assert hasattr(ContinuedDocTest, "test_basic")
    assert not hasattr(ContinuedDocTest, "test_basic:2")
    assert hasattr(ContinuedDocTest, "test_isolated")

    ContinuedDocTest(methodName="test_basic").test_basic()
    ContinuedDocTest(methodName="test_isolated").test_isolated()

    assert cleanup_calls == ["cleanup", "cleanup"]


def test_numeric_suffix_stays_part_of_label_without_base_block():
    blocks = DocIntegrationTest._collect_runnable_blocks_from_text("```py runnable:release:2026\nx = 1\n```")

    assert [block.name for block in blocks] == ["release:2026"]
    assert [block.code for block in blocks] == ["x = 1"]


def test_pytest_decorator_parsed_and_stripped_from_code():
    text = "```py runnable:test_deco\n# pytest-decorator: unittest.skip\nx = 1\n```"
    blocks = DocIntegrationTest._collect_runnable_blocks_from_text(text)

    assert len(blocks) == 1
    assert blocks[0].decorators == ["unittest.skip"]
    assert "pytest-decorator" not in blocks[0].code
    assert blocks[0].code == "x = 1"


def test_pytest_decorator_multiple_comma_separated():
    text = "```py runnable:test_multi\n# pytest-decorator: unittest.skip, unittest.expectedFailure\nx = 1\n```"
    blocks = DocIntegrationTest._collect_runnable_blocks_from_text(text)

    assert blocks[0].decorators == ["unittest.skip", "unittest.expectedFailure"]


def test_pytest_decorator_applied_to_dynamic_test(tmp_path):
    md_path = tmp_path / "doc.md"
    md_path.write_text(
        "```py runnable:test_skipped\n# pytest-decorator: unittest.skip\nassert False, 'should not run'\n```",
        encoding="utf-8",
    )

    class SkippedDocTest(DocIntegrationTest):
        doc_path = md_path

    assert hasattr(SkippedDocTest, "test_skipped")

    import unittest

    result = unittest.TestResult()
    SkippedDocTest(methodName="test_skipped").run(result)
    assert result.skipped == [(result.skipped[0][0], "")]
    assert result.failures == []
    assert result.errors == []


def test_pytest_decorator_no_decorators_by_default():
    text = "```py runnable:test_plain\nx = 1\n```"
    blocks = DocIntegrationTest._collect_runnable_blocks_from_text(text)

    assert blocks[0].decorators == []


def test_pytest_decorator_unresolvable_is_silently_ignored(tmp_path):
    md_path = tmp_path / "doc.md"
    md_path.write_text(
        "```py runnable:test_bad_dec\n# pytest-decorator: nonexistent.module.decorator\nassert True\n```",
        encoding="utf-8",
    )

    class BadDecDocTest(DocIntegrationTest):
        doc_path = md_path

    assert hasattr(BadDecDocTest, "test_bad_dec")

    # Should run fine despite unresolvable decorator
    BadDecDocTest(methodName="test_bad_dec").test_bad_dec()
