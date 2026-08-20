from doc_builder.check_links import check_file_links, check_links, extract_anchors


def test_check_file_links_validates_local_and_fragment_links(tmp_path):
    source = tmp_path / "source.md"
    target = tmp_path / "target.md"
    source.write_text(
        """# Source

[current section](#source)
[target section](target.md#target-section)
[extensionless target](target#target-section)
[missing target anchor](target.md#removed-section)
[missing current anchor](#renamed-section)
[external anchor](https://example.com/target#removed-section)
""",
        encoding="utf-8",
    )
    target.write_text("## Target Section\n", encoding="utf-8")

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 5
    assert {(link_text, link_url, line) for link_text, link_url, line in broken_links} == {
        ("missing target anchor", "target.md#removed-section", 6),
        ("missing current anchor", "#renamed-section", 7),
    }


def test_extract_anchors_supports_custom_and_explicit_anchors(tmp_path):
    document = tmp_path / "document.mdx"
    document.write_text(
        """## A Generated Heading
## A Custom Heading [ custom-heading ]
## A Legacy Custom Heading[[legacy-custom-heading]]
<a id='legacy-anchor'></a>
<Component id="component-anchor" />

```md
## Not A Heading
<a id="not-an-anchor"></a>
```
""",
        encoding="utf-8",
    )

    assert extract_anchors(document) == {
        "a-generated-heading",
        "custom-heading",
        "legacy-custom-heading",
        "legacy-anchor",
        "component-anchor",
    }


def test_check_links_reports_broken_fragment_links(tmp_path):
    (tmp_path / "index.md").write_text("[missing](page.md#missing)\n", encoding="utf-8")
    (tmp_path / "page.md").write_text("# Existing\n", encoding="utf-8")

    result = check_links(tmp_path, max_workers=1, show_progress=False)

    assert result.has_broken_links()
    assert result.broken_links == [(tmp_path / "index.md", "missing", "page.md#missing", 1)]
