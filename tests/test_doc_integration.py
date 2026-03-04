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
