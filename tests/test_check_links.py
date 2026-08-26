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

from doc_builder.check_links import _resolve_autodoc_anchors, check_file_links, check_links, extract_anchors
from doc_builder.commands.check_links import check_links_command_parser


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
[angle-bracket external](<https://example.com/target#removed-section>)
``[inline code](missing.md)``

```python
[code example](missing.md)
```
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


def test_extract_anchors_matches_rendered_headings_and_native_html(tmp_path):
    document = tmp_path / "document.mdx"
    document.write_text(
        """## A Generated Heading
## A Bracket Heading [ custom-heading ]
## A Linked [Heading](target.md)
## A Formatted **Heading** with `code`
## Reusing `generate`'s input
## Tight**emphasis**text
## Tight__underscore__text
## Inline <span>HTML</span>
## Escaped \\*star\\*
## \\[escaped bracket\\]
## Before![image](image.png)after
## A Legacy Custom Heading[[legacy-custom-heading]]
## Custom code[[dequantizing-`bitsandbytes`-models]]
## Custom punctuation[[advanced-tool-use--function-calling]]
## Custom entity[[rock&amp;roll]]
## A [nested [label]](target.md)
First paragraph line
Setext [Heading](target.md)
----------------------------
<span>Inline Setext</span>
----------------------------
> Quoted Setext
----------------------------
- ## List ATX Heading
1. ### Ordered List Heading
> - ## Quoted List Heading
- List Setext Heading
  --------------------
1. list item
----------------------------
Plain paragraph
> ----------------------------

<a id=unquoted-anchor></a>
<a name='legacy-name'></a>
<div id="section-anchor"></div>
<div
  id="multiline-anchor"
></div>
<svg><path id="svg-path-anchor" /></svg>
<svg><PATH id="uppercase-svg-path-anchor" /></svg>
<math><MI id="uppercase-mathml-anchor">x</MI></math>

<div id={"literal-expression-anchor"}></div>

<div id={"self-closing-expression-anchor"} />

Before <span id={"inline-expression-not-an-anchor"} /> after

<div id={dynamic_not_an_anchor}></div>
<script>const example = '<div id="script-phantom">';</script>
<textarea><div id="textarea-phantom"></textarea>
<div data-id="not-an-anchor"></div>
<meta name="not-an-anchor">
<Component id="component-anchor" />
<DIV id="uppercase-not-an-anchor"></DIV>

`<a id="inline-code-anchor"></a>`

<!-- <a id="comment-anchor"></a> -->

<!-- comment --><div id="after-comment-anchor"></div>

<!-- multiline comment
--> <div id="after-multiline-comment-anchor"></div>

```md
## Not A Heading
<a id="not-an-anchor"></a>
```
""",
        encoding="utf-8",
    )

    assert extract_anchors(document) == {
        "a-generated-heading",
        "a-bracket-heading-custom-heading",
        "a-linked-heading",
        "a-formatted-heading-with-code",
        "reusing-generate-s-input",
        "tight-emphasis-text",
        "tight-underscore-text",
        "inline-span-html-span",
        "escaped--star-",
        "escaped bracket",
        "before-after",
        "legacy-custom-heading",
        "dequantizing- bitsandbytes -models",
        "advanced-tool-use—function-calling",
        "rock & roll",
        "a-nested-label",
        "setext-heading",
        "span-inline-setext-span",
        "quoted-setext",
        "list-atx-heading",
        "ordered-list-heading",
        "quoted-list-heading",
        "list-setext-heading",
        "unquoted-anchor",
        "legacy-name",
        "section-anchor",
        "multiline-anchor",
        "svg-path-anchor",
        "uppercase-svg-path-anchor",
        "uppercase-mathml-anchor",
        '{"literal-expression-anchor"}',
        "self-closing-expression-anchor",
        "after-comment-anchor",
        "after-multiline-comment-anchor",
    }


def test_svelte_expression_ids_follow_mdsvex_html_serialization(tmp_path):
    target = tmp_path / "target.mdx"
    target.write_text(
        '<div id={"paired"}></div>\n\n<div id={"self-closing"} />\n',
        encoding="utf-8",
    )
    source = tmp_path / "source.md"
    source.write_text(
        """[paired source value](target.mdx#paired)
[paired rendered value](target.mdx#%7B%22paired%22%7D)
[self-closing value](target.mdx#self-closing)
""",
        encoding="utf-8",
    )

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 3
    assert broken_links == [("paired source value", "target.mdx#paired", 1)]


def test_svelte_expression_ids_respect_html_nodes_and_containers(tmp_path):
    document = tmp_path / "document.mdx"
    document.write_text(
        """> <div id={"quoted-paired"}></div>

> <div id={"quoted-self"} />

- <div id={"listed-paired"}></div>

- <div id={"listed-self"} />

Text <br id={"inline-void"}> and <img id={"inline-image"} />

<br id={"standalone-void"}>

<span id={"standalone-paired"}></span>

<div id={"rock&amp;roll"} />
""",
        encoding="utf-8",
    )

    assert extract_anchors(document) == {
        '{"quoted-paired"}',
        "quoted-self",
        '{"listed-paired"}',
        "listed-self",
        "standalone-void",
        '{"standalone-paired"}',
        "rock&amp;roll",
    }


def test_nested_list_headings_match_rendered_anchors(tmp_path):
    document = tmp_path / "document.md"
    document.write_text(
        """- - ## Deep heading
> - - ## Deep quoted heading
- - Deep setext
    ------------
""",
        encoding="utf-8",
    )

    assert extract_anchors(document) == {"deep-heading", "deep-quoted-heading", "deep-setext"}


def test_check_file_links_treats_autodoc_namespaces_as_generated(tmp_path):
    target = tmp_path / "target.md"
    target.write_text(
        """## API reference[[api-reference]]
[[autodoc]] integrations.PeftAdapterMixin
    - load_adapter

## Bert
[[autodoc]] models.bert.BertModel

## Widget
[[autodoc]] Widget
""",
        encoding="utf-8",
    )
    source = tmp_path / "source.md"
    source.write_text(
        """[object](target.md#transformers.integrations.PeftAdapterMixin)
[parameter](target.md#transformers.integrations.PeftAdapterMixin.load_adapter.adapter_name)
[example](target.md#transformers.integrations.PeftAdapterMixin.load_adapter.example)
[shortest path](target.md#transformers.BertModel)
[module-shortened path](target.md#transformers.models.bert.BertModel)
[dotted package](target.md#acme.widgets.Widget)
[dotted package module](target.md#acme.widgets.models.bert.BertModel)
[dotted package shortened module](target.md#acme.widgets.BertModel)
[bare object](target.md#BertModel)
[class typo](target.md#BertModel.typo)
[unknown dotted package](target.md#totally.wrong.BertModel.typo)
[unknown dotted package module](target.md#transformers.bert.BertModel)
[empty segment](target.md#transformers..BertModel)
[replaced heading](target.md#api-reference)
[unrelated object](target.md#transformers.integrations.OtherMixin)
""",
        encoding="utf-8",
    )

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 15
    assert broken_links == [
        ("bare object", "target.md#BertModel", 9),
        ("class typo", "target.md#BertModel.typo", 10),
        ("empty segment", "target.md#transformers..BertModel", 13),
        ("replaced heading", "target.md#api-reference", 14),
        ("unrelated object", "target.md#transformers.integrations.OtherMixin", 15),
    ]


def test_check_links_resolves_autodoc_aliases_from_the_documented_package(tmp_path, monkeypatch):
    project = tmp_path / "fake-alias-project"
    docs = project / "docs"
    package = project / "fake_alias_pkg"
    distribution = project / "fake_alias_project-1.0.dist-info"
    (project / ".git").mkdir(parents=True)
    docs.mkdir()
    package.mkdir()
    distribution.mkdir()
    package.joinpath("__init__.py").write_text(
        "class Canonical:\n    pass\n\nPublicAlias = Canonical\n",
        encoding="utf-8",
    )
    distribution.joinpath("METADATA").write_text(
        "Metadata-Version: 2.1\nName: fake-alias-project\nVersion: 1.0\n",
        encoding="utf-8",
    )
    distribution.joinpath("top_level.txt").write_text("fake_alias_pkg\n", encoding="utf-8")
    docs.joinpath("target.md").write_text(
        "[[autodoc]] PublicAlias\n[[autodoc]] MissingObject\n",
        encoding="utf-8",
    )
    docs.joinpath("source.md").write_text(
        "[canonical](target.md#fake_alias_pkg.Canonical)\n"
        "[guessed alias](target.md#fake_alias_pkg.PublicAlias)\n"
        "[unresolved fallback](target.md#fake_alias_pkg.MissingObject)\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(project))

    result = check_links(docs, max_workers=1, show_progress=False)

    assert result.broken_links == [(docs / "source.md", "guessed alias", "target.md#fake_alias_pkg.PublicAlias", 2)]


def test_resolve_autodoc_anchors_skips_package_import_without_directives(tmp_path, monkeypatch):
    document = tmp_path / "document.md"
    document.write_text("# Heading\n", encoding="utf-8")

    def fail_import(_package_name):
        raise AssertionError("package should not be imported")

    monkeypatch.setattr("doc_builder.check_links.importlib.import_module", fail_import)

    assert _resolve_autodoc_anchors([document], "side_effectful_package") == {}


def test_check_links_parser_accepts_package_name_aliases():
    parser = check_links_command_parser()

    assert parser.parse_args(["docs", "--package-name", "fake_pkg"]).package_name == "fake_pkg"
    assert parser.parse_args(["docs", "--package_name", "fake_pkg"]).package_name == "fake_pkg"


def test_fence_length_keeps_links_anchors_and_autodoc_inside_code(tmp_path):
    target = tmp_path / "target.md"
    target.write_text("## Real\n", encoding="utf-8")
    source = tmp_path / "source.md"
    source.write_text(
        """# Source

````md
```python
[fake](missing.md)
## Fake
<a id="fake-anchor"></a>
[[autodoc]] Ghost
```
````
[real](target.md#real)
[fenced autodoc](#pkg.Ghost)
""",
        encoding="utf-8",
    )

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 2
    assert broken_links == [("fenced autodoc", "#pkg.Ghost", 12)]
    assert extract_anchors(source) == {"source"}


def test_nested_fences_hide_links_and_generated_anchors(tmp_path):
    target = tmp_path / "target.md"
    target.write_text("## Real\n", encoding="utf-8")
    source = tmp_path / "source.md"
    source.write_text(
        """> ```md
> [blockquote code](missing-blockquote.md)
> [[autodoc]] BlockquoteGhost
> ```

- item

    ```md
    [list code](missing-list.md)
    [[autodoc]] ListGhost
    ```

[real](target.md#real)
[not generated](#pkg.BlockquoteGhost)
""",
        encoding="utf-8",
    )

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 2
    assert broken_links == [("not generated", "#pkg.BlockquoteGhost", 14)]
    assert extract_anchors(source) == set()


def test_fences_can_begin_on_list_marker_lines(tmp_path):
    source = tmp_path / "source.md"
    source.write_text(
        """- ```md
  [bullet code](missing-bullet.md)
  ```

1. ```md
   [numbered code](missing-numbered.md)
   ```

[real link](missing-real.md)
""",
        encoding="utf-8",
    )

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 1
    assert broken_links == [("real link", "missing-real.md", 9)]


def test_fences_can_begin_in_nested_list_markers(tmp_path):
    source = tmp_path / "source.md"
    source.write_text(
        """- - ```md
    [nested code](missing-nested.md)
    ```

[real link](missing-real.md)
""",
        encoding="utf-8",
    )

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 1
    assert broken_links == [("real link", "missing-real.md", 5)]


def test_outdented_fence_markers_follow_container_rules(tmp_path):
    list_source = tmp_path / "list.md"
    list_source.write_text(
        """- ```md
  [list code](missing-list-code.md)
```
[after list](missing-after-list.md)
""",
        encoding="utf-8",
    )
    quote_source = tmp_path / "quote.md"
    quote_source.write_text(
        """> ```md
> [quote code](missing-quote-code.md)
```
[after quote](missing-after-quote.md)
""",
        encoding="utf-8",
    )

    list_broken, list_total = check_file_links(list_source, tmp_path)
    quote_broken, quote_total = check_file_links(quote_source, tmp_path)

    assert list_total == 0
    assert list_broken == []
    assert quote_total == 1
    assert quote_broken == [("after quote", "missing-after-quote.md", 4)]


def test_links_inside_raw_html_blocks_remain_literal(tmp_path):
    source = tmp_path / "source.md"
    source.write_text(
        """<div>
[div content](missing-div.md)
</div>

<pre>
[pre content](missing-pre.md)
</pre>

<span>
[span content](missing-span.md)
</span>

<Tip>
[component content](missing-component.md)
</Tip>

<![CDATA[
[cdata content](missing-cdata.md)
]]>

<span>[paired inline content](missing-paired-inline.md)</span>

[real link](missing-real.md)
""",
        encoding="utf-8",
    )

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 1
    assert broken_links == [("real link", "missing-real.md", 23)]


def test_raw_html_blocks_end_at_renderer_boundaries(tmp_path):
    source = tmp_path / "source.md"
    source.write_text(
        """<script></script>
[after script](missing-after-script.md)

<textarea></textarea>
[inside textarea](missing-inside-textarea.md)

- <span></span>
- [sibling item](missing-sibling.md)

<span> prefix
[inside span](missing-inside-span.md)
</span>

    <span>indented</span>
[inside indented block](missing-inside-indented.md)

[real](missing-real.md)
""",
        encoding="utf-8",
    )

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 3
    assert broken_links == [
        ("after script", "missing-after-script.md", 2),
        ("sibling item", "missing-sibling.md", 8),
        ("real", "missing-real.md", 17),
    ]


def test_raw_html_inherits_list_container_and_serializes_multiline_tags(tmp_path):
    source = tmp_path / "source.mdx"
    source.write_text(
        """- text
  <span id={"a"}></span>
- <span id={"b"} />

<span
 id={"multiline"}
></span>

<foo-bar> prefix
[after invalid tag](missing-after-invalid.md)

> <span
> id={"quoted-multiline"}
> ></span>
""",
        encoding="utf-8",
    )

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 1
    assert broken_links == [("after invalid tag", "missing-after-invalid.md", 10)]
    assert extract_anchors(source) == {'{"a"}', "b", '{"multiline"}', '{"quoted-multiline"}'}


def test_raw_html_list_context_handles_lazy_blank_and_empty_items(tmp_path):
    source = tmp_path / "source.mdx"
    source.write_text(
        """- text
<span id={"lazy"}></span>
- [lazy sibling](missing-lazy-sibling.md)

- text

  <span id={"after-blank"}></span>
- [blank sibling](missing-blank-sibling.md)

-
  <span id={"empty"}></span>
- [empty sibling](missing-empty-sibling.md)
""",
        encoding="utf-8",
    )

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 3
    assert [url for _, url, _ in broken_links] == [
        "missing-lazy-sibling.md",
        "missing-blank-sibling.md",
        "missing-empty-sibling.md",
    ]
    assert extract_anchors(source) == {'{"lazy"}', '{"after-blank"}', '{"empty"}'}


def test_raw_html_drops_list_context_after_block_interrupts(tmp_path):
    source = tmp_path / "source.md"
    source.write_text(
        """- text
# Heading
<span></span>
- [inside top-level html](missing-heading.md)

- text
***
<span></span>
- [inside thematic html](missing-thematic.md)
""",
        encoding="utf-8",
    )

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 0
    assert broken_links == []


def test_raw_html_pops_only_the_interrupted_nested_list(tmp_path):
    inside_outer = tmp_path / "inside-outer.md"
    inside_outer.write_text(
        """- - text
  # Heading
  <span></span>
  - [literal nested item](missing-literal.md)
""",
        encoding="utf-8",
    )
    outside_outer = tmp_path / "outside-outer.md"
    outside_outer.write_text(
        """- - text
  # Heading
  <span></span>
- [rendered outer sibling](missing-rendered.md)
""",
        encoding="utf-8",
    )

    inside_broken, inside_total = check_file_links(inside_outer, tmp_path)
    outside_broken, outside_total = check_file_links(outside_outer, tmp_path)

    assert inside_total == 0
    assert inside_broken == []
    assert outside_total == 1
    assert outside_broken == [("rendered outer sibling", "missing-rendered.md", 4)]


def test_raw_html_setext_candidates_remain_headings(tmp_path):
    document = tmp_path / "document.md"
    document.write_text(
        """<span>
---
<div>
===
<script></script>
## Visible
""",
        encoding="utf-8",
    )

    assert extract_anchors(document) == {"span", "div", "visible"}


def test_html_tags_with_angle_brackets_in_attributes(tmp_path):
    source = tmp_path / "source.mdx"
    source.write_text(
        """<Tip text="> [hidden](missing-hidden.md)" />
<span title="< [also hidden](missing-also-hidden.md)" id="anchor"></span>

[real](missing-real.md)
""",
        encoding="utf-8",
    )

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 1
    assert broken_links == [("real", "missing-real.md", 4)]
    assert extract_anchors(source) == {"anchor"}


def test_raw_html_blocks_hide_markdown_headings_but_keep_html_ids(tmp_path):
    document = tmp_path / "document.mdx"
    document.write_text(
        """<div id="real-div">
## Fake heading
<a id="real-child"></a>
</div>

<span>
Fake setext
------------
</span>

## Visible heading
""",
        encoding="utf-8",
    )

    assert extract_anchors(document) == {"real-div", "real-child", "visible-heading"}


def test_opaque_and_removed_html_elements_do_not_add_descendant_ids(tmp_path):
    document = tmp_path / "document.mdx"
    document.write_text(
        """<iframe id="iframe-anchor"><div id="iframe-phantom"></div></iframe>

<noscript id="noscript-phantom"><div id="noscript-child-phantom"></div></noscript>

<template id="template-phantom"><div id="template-child-phantom"></div></template>

<iframe id="nested-iframe-anchor"><iframe id="nested-iframe-phantom"></iframe><div id="after-inner-phantom"></div></iframe>

<template><template></template><div id="after-inner-template-phantom"></div></template>
""",
        encoding="utf-8",
    )

    assert extract_anchors(document) == {"iframe-anchor", "nested-iframe-anchor"}


def test_serialized_html_matches_cheerio_document_and_comment_semantics(tmp_path):
    document = tmp_path / "document.mdx"
    document.write_text(
        """<script id="script-removed">code</script>

<style id="style-removed">code</style>

<title id="title-removed">Title</title>

<body id="body-removed"><div id="body-child"></div></body>

<html id="html-removed"><head id="head-removed"><meta id="meta-removed"></head><body id="nested-body-removed"><div id="html-body-child"></div></body></html>

<script><script></script><div id="after-raw-close"></div></script>

<div><!-- <span id="embedded-comment-phantom"></span> --><span id="after-embedded-comment"></span></div>

<!-- a --><!-- <div id="second-comment-phantom"></div> --><div id="after-comments"></div>
""",
        encoding="utf-8",
    )

    assert extract_anchors(document) == {
        "body-child",
        "html-body-child",
        "after-raw-close",
        "after-embedded-comment",
        "after-comments",
    }


def test_escaped_brackets_follow_heading_text_nodes(tmp_path):
    document = tmp_path / "document.md"
    document.write_text("## a \\[foo\\]\n## a\\[bar\\]b\n", encoding="utf-8")

    assert extract_anchors(document) == {"foo", "a--bar--b"}


def test_autodoc_replaces_only_the_heading_seen_by_the_builder(tmp_path):
    document = tmp_path / "document.md"
    document.write_text(
        """## Visible comment heading
<!--
## Hidden comment heading
-->
[[autodoc]] models.bert.BertModel

## Visible tilde heading
~~~md
## Hidden tilde heading
~~~
[[autodoc]] models.gpt2.GPT2Model

## Replaced by fenced directive
```md
[[autodoc]] models.t5.T5Model
```

## !!!
```md
[[autodoc]] models.empty.EmptyModel
```
""",
        encoding="utf-8",
    )

    assert extract_anchors(document) == {"visible-comment-heading", "visible-tilde-heading"}

    source = tmp_path / "source.md"
    source.write_text(
        "[generated](document.md#transformers.T5Model)\n"
        "[generated from empty slug](document.md#transformers.EmptyModel)\n"
        "[removed](document.md#replaced-by-fenced-directive)\n",
        encoding="utf-8",
    )
    broken_links, total_links = check_file_links(source, tmp_path)
    assert total_links == 3
    assert broken_links == [("removed", "document.md#replaced-by-fenced-directive", 3)]


def test_math_headings_use_the_renderer_placeholder_anchor(tmp_path):
    target = tmp_path / "target.md"
    target.write_text("## Loss $L$ function\n", encoding="utf-8")
    source = tmp_path / "source.md"
    source.write_text(
        "[rendered](target.md#loss-katexparse0marker-function)\n[source-only slug](target.md#loss-l-function)\n",
        encoding="utf-8",
    )

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 2
    assert broken_links == [("source-only slug", "target.md#loss-l-function", 2)]


def test_autodoc_makes_all_math_counters_uncertain(tmp_path):
    target = tmp_path / "target.md"
    target.write_text(
        """## First $x$
## API
[[autodoc]] Foo
## Later $y$
""",
        encoding="utf-8",
    )
    source = tmp_path / "source.md"
    source.write_text(
        """[first exact](target.md#first-katexparse0marker)
[first wrong counter](target.md#first-katexparse999marker)
[later shifted counter](target.md#later-katexparse999marker)
""",
        encoding="utf-8",
    )

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 3
    assert broken_links == []


def test_link_destinations_support_titles_same_page_forms_and_encoded_fragments(tmp_path):
    target = tmp_path / "target.md"
    target.write_text('## Café\n<div id="rock&amp;roll"></div>\n', encoding="utf-8")
    encoded_target = tmp_path / "encoded page.md"
    encoded_target.write_text("## Encoded path\n", encoding="utf-8")
    nested_target = tmp_path / "nested_(page).md"
    nested_target.write_text("## Nested destination\n", encoding="utf-8")
    source = tmp_path / "source.md"
    source.write_text(
        """# Source
[title](target.md#café "Details")
[single quoted title](#source 'Details')
[angle](<#source>)
[query](?view=full#source)
[encoded](target.html?view=full#caf%C3%A9)
[encoded path](encoded%20page.md#encoded-path)
[entity id](target.md#rock%26roll)
[nested destination](nested_(page).md#nested-destination)
[parenthesized title](target.md#café "Details (expanded)")
[missing](target.md#missing "Helpful title")
""",
        encoding="utf-8",
    )

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 10
    assert broken_links == [("missing", 'target.md#missing "Helpful title"', 11)]


def test_unmatched_backtick_does_not_hide_a_link(tmp_path):
    source = tmp_path / "source.md"
    source.write_text(
        "Stray ` before [missing](missing.md)\n"
        "Literal ``[text span](bounding boxes)''\n"
        "Literal [parenthesized title](target.md (title))\n",
        encoding="utf-8",
    )

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 1
    assert broken_links == [("missing", "missing.md", 1)]


def test_code_spans_do_not_cross_markdown_block_boundaries(tmp_path):
    source = tmp_path / "source.md"
    source.write_text(
        """`
# Heading
[after heading](missing-after-heading.md)
`

`before

[after blank](missing-after-blank.md)
after`

1. `
2. [ordered sibling](missing-ordered-sibling.md)
`
""",
        encoding="utf-8",
    )

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 3
    assert broken_links == [
        ("after heading", "missing-after-heading.md", 3),
        ("after blank", "missing-after-blank.md", 8),
        ("ordered sibling", "missing-ordered-sibling.md", 12),
    ]


def test_multiline_code_comments_and_links_follow_markdown_structure(tmp_path):
    source = tmp_path / "source.md"
    source.write_text(
        """`<!--`
[after inline code](missing-after-comment.md)
`before
[inside multiline code](missing-code.md)
after`
[multiline
label](missing-label.md)
[multiline destination](
missing-destination.md
)
[code `]` label](not-a-link.md)
""",
        encoding="utf-8",
    )

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 3
    assert broken_links == [
        ("after inline code", "missing-after-comment.md", 2),
        ("multiline\nlabel", "missing-label.md", 6),
        ("multiline destination", "\nmissing-destination.md\n", 8),
    ]


def test_html_comment_blocks_hide_trailing_links_but_inline_comments_do_not(tmp_path):
    source = tmp_path / "source.md"
    source.write_text(
        """<!-- comment --> [hidden](missing-hidden.md)
<!-- multiline
--> [also hidden](missing-close.md)
Text <!-- inline --> [inline](missing-inline.md)
[real](missing-real.md)
""",
        encoding="utf-8",
    )

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 2
    assert broken_links == [
        ("inline", "missing-inline.md", 4),
        ("real", "missing-real.md", 5),
    ]


def test_comment_markers_in_fence_info_do_not_leak(tmp_path):
    source = tmp_path / "source.md"
    source.write_text(
        """~~~md <!--
[tilde fake](missing-tilde.md)
~~~
[after tilde](missing-after-tilde.md)

```md <!--
[backtick fake](missing-backtick.md)
````
[after backtick](missing-after-backtick.md)
""",
        encoding="utf-8",
    )

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 2
    assert broken_links == [
        ("after tilde", "missing-after-tilde.md", 4),
        ("after backtick", "missing-after-backtick.md", 9),
    ]


def test_inline_comment_state_ends_at_markdown_block_interrupts(tmp_path):
    source = tmp_path / "source.md"
    source.write_text(
        """text <!--

[after blank](missing-after-blank.md)

text <!--
~~~md
--> [inside fence](missing-inside-fence.md)
~~~
[after fence](missing-after-fence.md)

text <!--
> [quoted](missing-quoted.md)
-->

Text <span title="<!--">x</span> [attribute-safe](missing-attribute-safe.md)
[comment title](missing-title.md "<!--") [after title](missing-after-title.md)
![comment label <!--](missing-image.png) [after image](missing-after-image.md)
""",
        encoding="utf-8",
    )

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 8
    assert broken_links == [
        ("after blank", "missing-after-blank.md", 3),
        ("after fence", "missing-after-fence.md", 9),
        ("quoted", "missing-quoted.md", 12),
        ("attribute-safe", "missing-attribute-safe.md", 15),
        ("comment title", 'missing-title.md "<!--"', 16),
        ("after title", "missing-after-title.md", 16),
        ("comment label <!--", "missing-image.png", 17),
        ("after image", "missing-after-image.md", 17),
    ]


def test_inline_comments_continue_within_the_same_blockquote(tmp_path):
    source = tmp_path / "source.md"
    source.write_text(
        """> text <!--
> [hidden](missing-hidden.md)
> --> [shown](missing-shown.md)

> text
lazy <!--
> [lazy hidden](missing-lazy-hidden.md)
> --> [lazy shown](missing-lazy-shown.md)
""",
        encoding="utf-8",
    )

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 2
    assert broken_links == [
        ("shown", "missing-shown.md", 3),
        ("lazy shown", "missing-lazy-shown.md", 8),
    ]


def test_inline_comment_ends_at_an_ordered_list_sibling(tmp_path):
    source = tmp_path / "source.md"
    source.write_text(
        """1. text <!--
2. [shown](missing-shown.md)

text <!--
2. [hidden](missing-hidden.md)
-->
""",
        encoding="utf-8",
    )

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 1
    assert broken_links == [("shown", "missing-shown.md", 2)]


def test_anchor_comments_reset_and_protect_inline_syntax(tmp_path):
    document = tmp_path / "document.md"
    document.write_text(
        """text <!--

## After blank

text <!--
~~~md
code
~~~
## After fence

Text <span title="<!--">x</span>
## After attribute

[link](target.md "<!--")
## After link
""",
        encoding="utf-8",
    )

    assert extract_anchors(document) == {
        "after-blank",
        "after-fence",
        "after-attribute",
        "after-link",
    }


def test_comment_setext_heading_matches_renderer_slug(tmp_path):
    document = tmp_path / "document.md"
    document.write_text("<!-- c --> Heading\n---\n", encoding="utf-8")

    assert extract_anchors(document) == {"---c----heading"}


def test_link_scanner_respects_block_boundaries_and_html_attributes(tmp_path):
    target = tmp_path / "target file.md"
    target.write_text("## Here\n", encoding="utf-8")
    source = tmp_path / "source.md"
    source.write_text(
        """<Tip text="[attribute](missing-attribute.md)" />

Text <span title="[inline attribute](missing-inline-attribute.md)">content</span>

[blank

label](missing-blank.md)
[quote break
> label](missing-quote-break.md)
[list break
- label](missing-list-break.md)
[heading break
# label](missing-heading-break.md)
[thematic break
***
label](missing-thematic-break.md)
[underscore break
___
label](missing-underscore-break.md)
> [quoted
> label](missing-quoted.md)
- [listed
  label](missing-listed.md)
[angle destination](<target file.md#here>)
[real](missing-real.md)
""",
        encoding="utf-8",
    )

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 4
    assert [(url, line) for _, url, line in broken_links] == [
        ("missing-quoted.md", 20),
        ("missing-listed.md", 22),
        ("missing-real.md", 25),
    ]


def test_multiline_links_follow_lazy_quote_and_ordered_list_rules(tmp_path):
    source = tmp_path / "source.md"
    source.write_text(
        """> [quoted
label](missing-lazy-quote.md)

> > [nested quote
> label](missing-decreased-quote.md)

[quote increase
> label](missing-increased-quote.md)

[ordered two
2. label](missing-ordered-two.md)

[ordered one
1. label](missing-ordered-one.md)

[bullet
- label](missing-bullet.md)

> [quoted destination](
> missing-quoted-destination.md
> )
""",
        encoding="utf-8",
    )

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 4
    assert broken_links == [
        ("quoted\nlabel", "missing-lazy-quote.md", 1),
        ("nested quote\n> label", "missing-decreased-quote.md", 4),
        ("ordered two\n2. label", "missing-ordered-two.md", 10),
        ("quoted destination", "\n> missing-quoted-destination.md\n> ", 19),
    ]


def test_multiline_links_do_not_cross_list_item_boundaries(tmp_path):
    source = tmp_path / "source.md"
    source.write_text(
        """1. [first item
2. second item](missing-list-link.md)

text [ordinary
2. continuation](missing-ordinary-link.md)

1. [indented
   2. continuation](missing-indented-link.md)
""",
        encoding="utf-8",
    )

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 2
    assert broken_links == [
        ("ordinary\n2. continuation", "missing-ordinary-link.md", 4),
        ("indented\n   2. continuation", "missing-indented-link.md", 7),
    ]


def test_ordered_lists_above_one_start_at_block_boundaries(tmp_path):
    source = tmp_path / "source.md"
    source.write_text(
        """2. [first item
3. second item](missing-at-start.md)

paragraph

2. [after blank
3. second item](missing-after-blank.md)

paragraph [ordinary
2. continuation](missing-ordinary.md)
""",
        encoding="utf-8",
    )

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 1
    assert broken_links == [("ordinary\n2. continuation", "missing-ordinary.md", 9)]


def test_nested_image_links_validate_the_image_and_outer_destination(tmp_path):
    target = tmp_path / "target.md"
    target.write_text("## Target\n", encoding="utf-8")
    (tmp_path / "badge_(ok).svg").write_text("<svg></svg>\n", encoding="utf-8")
    source = tmp_path / "source.md"
    source.write_text(
        "[![badge](badge_(ok).svg)](target.md#target)\n[![missing badge](missing.svg)](target.md#target)\n",
        encoding="utf-8",
    )

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 4
    assert broken_links == [("missing badge", "missing.svg", 2)]


def test_check_links_reports_broken_fragment_links(tmp_path):
    (tmp_path / "index.md").write_text("[missing](page.md#missing)\n", encoding="utf-8")
    (tmp_path / "page.md").write_text("# Existing\n", encoding="utf-8")

    result = check_links(tmp_path, max_workers=1, show_progress=False)

    assert result.has_broken_links()
    assert result.broken_links == [(tmp_path / "index.md", "missing", "page.md#missing", 1)]


def test_find_target_file_supports_dots_in_extensionless_page_names(tmp_path):
    document = tmp_path / "t5v1.1.md"
    document.write_text("# T5v1.1\n", encoding="utf-8")

    source = tmp_path / "source.md"
    source.write_text("[T5v1.1](t5v1.1)\n", encoding="utf-8")

    broken_links, total_links = check_file_links(source, tmp_path)

    assert total_links == 1
    assert broken_links == []
