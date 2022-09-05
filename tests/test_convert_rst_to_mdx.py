# coding=utf-8
# Copyright 2021 The HuggingFace Team. All rights reserved.
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


import unittest

from doc_builder.convert_rst_to_mdx import (
    _re_anchor_section,
    _re_args,
    _re_block,
    _re_block_info,
    _re_doc_with_description,
    _re_double_backquotes,
    _re_example,
    _re_func_class,
    _re_ignore_line_table,
    _re_ignore_line_table1,
    _re_links,
    _re_math,
    _re_obj,
    _re_prefix_links,
    _re_ref_with_description,
    _re_returns,
    _re_rst_option,
    _re_sep_line_table,
    _re_simple_doc,
    _re_simple_ref,
    _re_single_backquotes,
    apply_min_indent,
    convert_rst_blocks,
    convert_rst_formatting,
    convert_rst_links,
    convert_special_chars,
    find_indent,
    is_empty_line,
    parse_options,
    parse_rst_docstring,
    process_titles,
    remove_indent,
    split_arg_line,
    split_pt_tf_code_blocks,
    split_raise_line,
    split_return_line,
)


class ConvertRstToMdxTester(unittest.TestCase):
    def test_re_obj(self):
        self.assertEqual(_re_obj.search("There is an :obj:`object`.").groups(), ("object",))
        self.assertIsNone(_re_obj.search("There is no :obj:`object."))

    def test_re_math(self):
        self.assertEqual(_re_math.search("There is a :math:`formula`.").groups(), ("formula",))
        self.assertIsNone(_re_math.search("There is no :math:`formula."))

    def test_re_single_backquotes(self):
        self.assertEqual(_re_single_backquotes.search("There is some `code`.").groups(), (" ", "code", "."))
        self.assertIsNone(_re_single_backquotes.search("This is double ``code``."))
        self.assertEqual(_re_single_backquotes.search("`code` at the beginning.").groups(), ("", "code", " "))
        self.assertEqual(_re_single_backquotes.search("At the end there is some `code`").groups(), (" ", "code", ""))

    def test_re_double_backquotes(self):
        self.assertEqual(_re_double_backquotes.search("There is some ``code``.").groups(), (" ", "code", "."))
        self.assertIsNone(_re_double_backquotes.search("This is single `code`."))
        self.assertIsNone(_re_double_backquotes.search("This is triple ```code```."))
        self.assertEqual(_re_double_backquotes.search("``code`` at the beginning.").groups(), ("", "code", " "))
        self.assertEqual(_re_double_backquotes.search("At the end there is some ``code``").groups(), (" ", "code", ""))

    def test_re_func_class(self):
        self.assertEqual(_re_func_class.search("There is a :class:`class`.").groups(), ("class",))
        self.assertEqual(_re_func_class.search("There is a :func:`function`.").groups(), ("function",))
        self.assertEqual(_re_func_class.search("There is a :meth:`method`.").groups(), ("method",))
        self.assertIsNone(_re_func_class.search("There is no :obj:`object`."))

    def test_re_links(self):
        self.assertEqual(_re_links.search("This is a regular `link <url>`_").groups(), ("link", "url"))
        self.assertEqual(_re_links.search("This is a regular `link <url>`__").groups(), ("link", "url"))

    def test_re_prefix_links(self):
        self.assertEqual(
            _re_prefix_links.search("This is a regular :prefix_link:`link <url>`").groups(),
            ("link", "url"),
        )

    def test_re_simple_doc(self):
        self.assertEqual(_re_simple_doc.search("This is a link to an inner page :doc:`page`.").groups(), ("page",))

    def test_re_doc_with_description(self):
        self.assertEqual(
            _re_doc_with_description.search("This is a link to an inner page :doc:`page name <page ref>`.").groups(),
            ("page name", "page ref"),
        )

    def test_re_simple_ref(self):
        self.assertEqual(
            _re_simple_ref.search("This is a link to an inner section :ref:`section`.").groups(), ("section",)
        )

    def test_re_ref_with_description(self):
        self.assertEqual(
            _re_ref_with_description.search(
                "This is a link to an inner section :ref:`section name <section ref>`."
            ).groups(),
            ("section name", "section ref"),
        )

    def test_re_example(self):
        self.assertEqual(_re_example.search("  Example::").groups(), ("Example",))
        self.assertEqual(_re_example.search("  Generation example::").groups(), ("Generation example",))
        self.assertIsNone(_re_example.search("  Return:"))

    def test_re_block(self):
        self.assertEqual(_re_block.search("  .. note::").groups(), ("note",))
        self.assertEqual(_re_block.search("  .. code-example::").groups(), ("code-example",))

    def test_re_block_info(self):
        self.assertEqual(_re_block_info.search("  .. note:: python").groups(), ("python",))
        self.assertEqual(_re_block_info.search("  .. code-example:: python").groups(), ("python",))

    def test_re_rst_option(self):
        self.assertEqual(_re_rst_option.search("    :size: 123").groups(), ("size", " 123"))
        self.assertEqual(_re_rst_option.search("    :members: func1, func2,").groups(), ("members", " func1, func2,"))
        self.assertEqual(
            _re_rst_option.search(
                "    :special-members: __call__, batch_decode, decode, encode, push_to_hub"
            ).groups(),
            ("special-members", " __call__, batch_decode, decode, encode, push_to_hub"),
        )

    def test_re_args(self):
        self.assertIsNotNone(_re_args.search("  Args:"))
        self.assertIsNotNone(_re_args.search("  Arg:"))
        self.assertIsNone(_re_args.search("  Arg: lala"))

        self.assertIsNotNone(_re_args.search("  Arguments:"))
        self.assertIsNotNone(_re_args.search("  Argument:"))
        self.assertIsNone(_re_args.search("  Argument: lala"))

        self.assertIsNotNone(_re_args.search("  Params:"))
        self.assertIsNotNone(_re_args.search("  Param:"))
        self.assertIsNone(_re_args.search("  Param: lala"))

        self.assertIsNotNone(_re_args.search("  Parameters:"))
        self.assertIsNotNone(_re_args.search("  Parameter:"))
        self.assertIsNone(_re_args.search("  Parameter: lala"))

        self.assertIsNotNone(_re_args.search("  Attributes:"))
        self.assertIsNotNone(_re_args.search("  Attribute:"))
        self.assertIsNone(_re_args.search("  Attribute: lala"))

    def test_re_returns(self):
        self.assertIsNotNone(_re_returns.search("  Returns:"))
        self.assertIsNotNone(_re_returns.search("  Return:"))
        self.assertIsNone(_re_returns.search("  Return: lala"))

    def test_re_ignore_line_table(self):
        self.assertIsNotNone(_re_ignore_line_table.search("+--- + --- +"))

    def test_re_ignore_line_table1(self):
        self.assertIsNotNone(_re_ignore_line_table1.search("| +--- + --- +"))

    def test_re_sep_line_table(self):
        self.assertIsNotNone(_re_sep_line_table.search("+=== +===+ === +"))

    def test_re_anchor_table(self):
        self.assertEqual(_re_anchor_section.search(".. _reference:").groups(), ("reference",))

    def test_convert_rst_formatting(self):
        test_text_1 = """
This text comports a bit of everything: `italics`, *italics*, some ``code``. There is some already converted **bold** and
some references to :obj:`objects`, :class:`~transformers.classes`, :meth:`methods` and :func:`funcs`. Also, we can find
a :math:`formula`."""
        expected_converted_1 = """
This text comports a bit of everything: *italics*, *italics*, some `code`. There is some already converted **bold** and
some references to `objects`, [`~transformers.classes`], [`methods`] and [`funcs`]. Also, we can find
a \\\\(formula\\\\)."""
        self.assertEqual(convert_rst_formatting(test_text_1), expected_converted_1)

        test_text_2 = """
  This contains some ``code on
  two lines``.
"""
        expected_converted_2 = "\n  This contains some `code on two lines`.\n"
        self.assertEqual(convert_rst_formatting(test_text_2), expected_converted_2)

        test_text_3 = """
This contains some ``code on
two lines.`` with more ``on the second line``.
"""
        expected_converted_3 = "\nThis contains some `code on two lines.` with more `on the second line`.\n"
        self.assertEqual(convert_rst_formatting(test_text_3), expected_converted_3)

        test_text_4 = """
This contains some ``code on
two lines.`` with more ``on the
third line``.
"""
        expected_converted_4 = "\nThis contains some `code on two lines.` with more `on the third line`.\n"
        self.assertEqual(convert_rst_formatting(test_text_4), expected_converted_4)

    def test_convert_rst_links(self):
        page_info = {"package_name": "transformers"}
        self.assertEqual(
            convert_rst_links("This is a regular `link <url>`_", page_info), "This is a regular [link](url)"
        )
        self.assertEqual(
            convert_rst_links("This is a regular `link <url>`__", page_info), "This is a regular [link](url)"
        )

        self.assertEqual(
            convert_rst_links("This is a prefixed :prefix_link:`link <url>`", page_info),
            "This is a prefixed [link](https://github.com/huggingface/transformers/tree/main/url)",
        )
        self.assertEqual(
            convert_rst_links("This is a prefixed :prefix_link:`link <url>`", page_info),
            "This is a prefixed [link](https://github.com/huggingface/transformers/tree/main/url)",
        )

        self.assertEqual(
            convert_rst_links("This is a link to an inner page :doc:`page`.", page_info),
            "This is a link to an inner page [page](/docs/transformers/main/en/page).",
        )
        self.assertEqual(
            convert_rst_links("This is a link to an inner page :doc:`page name <page ref>`.", page_info),
            "This is a link to an inner page [page name](/docs/transformers/main/en/page ref).",
        )

        self.assertEqual(
            convert_rst_links("This is a link to an inner section :ref:`section`.", page_info),
            "This is a link to an inner section [section](#section).",
        )
        self.assertEqual(
            convert_rst_links("This is a link to an inner section :ref:`section name <section ref>`.", page_info),
            "This is a link to an inner section [section name](#section ref).",
        )

        page_info["page"] = "model_doc/bert.html"
        self.assertEqual(
            convert_rst_links("This is a link to an inner section :ref:`section`.", page_info),
            "This is a link to an inner section [section](/docs/transformers/main/en/model_doc/bert#section).",
        )
        self.assertEqual(
            convert_rst_links("This is a link to an inner section :ref:`section name <section ref>`.", page_info),
            "This is a link to an inner section [section name](/docs/transformers/main/en/model_doc/bert#section ref).",
        )

    def test_convert_rst_links_with_version_and_lang(self):
        page_info = {"package_name": "transformers", "version": "v4.10.0", "language": "fr"}

        self.assertEqual(
            convert_rst_links("This is a link to an inner page :doc:`page`.", page_info),
            "This is a link to an inner page [page](/docs/transformers/v4.10.0/fr/page).",
        )
        self.assertEqual(
            convert_rst_links("This is a link to an inner page :doc:`page name <page ref>`.", page_info),
            "This is a link to an inner page [page name](/docs/transformers/v4.10.0/fr/page ref).",
        )

        self.assertEqual(
            convert_rst_links("This is a link to an inner section :ref:`section`.", page_info),
            "This is a link to an inner section [section](#section).",
        )
        self.assertEqual(
            convert_rst_links("This is a link to an inner section :ref:`section name <section ref>`.", page_info),
            "This is a link to an inner section [section name](#section ref).",
        )

        page_info["page"] = "model_doc/bert.html"
        self.assertEqual(
            convert_rst_links("This is a link to an inner section :ref:`section`.", page_info),
            "This is a link to an inner section [section](/docs/transformers/v4.10.0/fr/model_doc/bert#section).",
        )
        self.assertEqual(
            convert_rst_links("This is a link to an inner section :ref:`section name <section ref>`.", page_info),
            "This is a link to an inner section [section name](/docs/transformers/v4.10.0/fr/model_doc/bert#section ref).",
        )
        self.assertEqual(
            convert_rst_links("`What are input IDs? <../glossary.html#input-ids>`__", page_info),
            "[What are input IDs?](../glossary#input-ids)",
        )

    def test_is_empty_line(self):
        self.assertTrue(is_empty_line(""))
        self.assertTrue(is_empty_line("  "))
        self.assertFalse(is_empty_line("a"))
        self.assertFalse(is_empty_line("  a"))

    def test_find_indent(self):
        self.assertEqual(find_indent(""), 0)
        self.assertEqual(find_indent("a"), 0)
        self.assertEqual(find_indent("   "), 3)
        self.assertEqual(find_indent("   a"), 3)

    def test_convert_special_chars(self):
        self.assertEqual(convert_special_chars("{ lala }"), "&amp;lcub; lala }")
        self.assertEqual(convert_special_chars("< blo"), "&amp;lt; blo")
        self.assertEqual(convert_special_chars("<source></source>"), "<source></source>")
        self.assertEqual(convert_special_chars("<Youtube id='my_vid' />"), "<Youtube id='my_vid' />")

        longer_test = """<script lang="ts">
import Tip from "$lib/Tip.svelte";
import Youtube from "$lib/Youtube.svelte";
import Docstring from "$lib/Docstring.svelte";
import CodeBlock from "$lib/CodeBlock.svelte";
export let fw: "pt" | "tf"
</script>"""
        self.assertEqual(convert_special_chars(longer_test), longer_test)

        nested_test = """<blockquote>
   sometext
   <blockquote>
        sometext
   </blockquote>
</blockquote>"""
        self.assertEqual(convert_special_chars(nested_test), nested_test)

        html_code = '<a href="Some URl">some_text</a>'
        self.assertEqual(convert_special_chars(html_code), html_code)

        inner_less = """<blockquote>
   sometext 4 &amp;lt; 5
</blockquote>"""
        self.assertEqual(convert_special_chars(inner_less), inner_less)

        img_code = '<img src="someSrc">'
        self.assertEqual(convert_special_chars(img_code), img_code)

    def test_parse_options(self):
        self.assertEqual(
            parse_options("    :size: 123\n    :members: func1, func2,\n        func3"),
            {"size": "123", "members": "func1, func2, func3"},
        )
        self.assertEqual(parse_options("    :size: 123\n    :members:"), {"size": "123", "members": ""})

    def test_convert_rst_blocks(self):
        page_info = {"package_name": "transformers", "version": "v4.10.0", "language": "fr"}

        original_rst = """
text
text

..

    comment

.. code-block:: python

    print(1 + 1)

Example::
    example code

.. note::
    This is a note.

.. autoclass:: transformers.AdamW
    :members:

.. autoclass:: transformers.PreTrainedTokenizer
    :special-members: __call__, batch_decode, decode, encode, push_to_hub
    :members:

.. autoclass:: transformers.BertTokenizer
    :members: build_inputs_with_special_tokens, get_special_tokens_mask,
        create_token_type_ids_from_sequences, save_vocabulary

.. autofunction:: transformers.create_optimizer

.. image:: /imgs/warmup_cosine_schedule.png
    :target: /imgs/warmup_cosine_schedule.png
    :alt: Alternative text

.. math::

    formula
"""

        expected_conversion = """
text
text

<!--comment
-->

```python
print(1 + 1)
```

<exampletitle>Example:</exampletitle>

<example>```python
example code
```
</example>
<Tip>

This is a note.

</Tip>

[[autodoc]] transformers.AdamW
    - all

[[autodoc]] transformers.PreTrainedTokenizer
    - __call__
    - batch_decode
    - decode
    - encode
    - push_to_hub
    - all

[[autodoc]] transformers.BertTokenizer
    - build_inputs_with_special_tokens
    - get_special_tokens_mask
    - create_token_type_ids_from_sequences
    - save_vocabulary

[[autodoc]] transformers.create_optimizer

<img alt="Alternative text" src="/docs/transformers/v4.10.0/fr/imgs/warmup_cosine_schedule.png"/>

$$formula$$
"""

        self.assertEqual(convert_rst_blocks(original_rst, page_info), expected_conversion)

        rst_with_indent = """
    This is inside a docstring, so we have some indent.

    .. note::
        There is a note in the middle.

    We should keep the indent for the note.
"""
        expected_conversion = """
    This is inside a docstring, so we have some indent.

    <Tip>

    There is a note in the middle.

    </Tip>

    We should keep the indent for the note.
"""
        self.assertEqual(convert_rst_blocks(rst_with_indent, page_info), expected_conversion)

    def test_split_return_line(self):
        self.assertEqual(
            split_return_line("A :obj:`str` or a :obj:`bool`: the result"),
            ("A :obj:`str` or a :obj:`bool`", " the result"),
        )
        self.assertEqual(
            split_return_line("A :obj:`str` or a :obj:`bool` the result"),
            (None, "A :obj:`str` or a :obj:`bool` the result"),
        )
        self.assertEqual(split_return_line("A :obj:`str` or a :obj:`bool`:"), ("A :obj:`str` or a :obj:`bool`", ""))
        self.assertEqual(
            split_return_line("    :obj:`str` or :obj:`bool`: some result:"),
            ("    :obj:`str` or :obj:`bool`", " some result:"),
        )
        self.assertEqual(split_return_line(":class:`IterableDataset`"), (":class:`IterableDataset`", ""))
        self.assertEqual(split_return_line("`int`"), ("`int`", ""))

    def test_split_raise_line(self):
        self.assertEqual(split_raise_line("SomeError some error"), ("SomeError", "some error"))
        self.assertEqual(split_raise_line("SomeError: some error"), ("SomeError", "some error"))
        self.assertEqual(
            split_raise_line("[SomeError](https:://someurl): some error"),
            ("[SomeError](https:://someurl)", "some error"),
        )
        self.assertEqual(
            split_raise_line(
                "[`HTTPError`](https://2.python-requests.org/en/master/api/#requests.HTTPError) if credentials are invalid"
            ),
            (
                "[`HTTPError`](https://2.python-requests.org/en/master/api/#requests.HTTPError)",
                "if credentials are invalid",
            ),
        )

    def test_split_arg_line(self):
        self.assertEqual(split_arg_line("   x (:obj:`int`): an int"), ("   x (:obj:`int`)", " an int"))
        self.assertEqual(split_arg_line("   x (:obj:`int`)"), ("   x (:obj:`int`)", ""))

    def test_parse_rst_docsting(self):
        # test canonical
        rst_docstring = """
docstring

Args:
    a (:obj:`str` or :obj:`bool`): some parameter
    b (:obj:`str` or :obj:`bool`):
        Another parameter with the description below

Raises:
    `pa.ArrowInvalidError`: if the arrow data casting fails
    TypeError: if the target type is not supported according, e.g.
        - point1
        - point2
    [`HTTPError`](https://2.python-requests.org/en/master/api/#requests.HTTPError) if credentials are invalid
    [`HTTPError`](https://2.python-requests.org/en/master/api/#requests.HTTPError) if connection got lost

Returns:
    :obj:`str` or :obj:`bool`: some result

Example::

    print(a + b)

End of the arg section.
"""
        expected_conversion = """
docstring

<parameters>

- **a** (:obj:`str` or :obj:`bool`) -- some parameter
- **b** (:obj:`str` or :obj:`bool`) --
        Another parameter with the description below

</parameters>

<raises>

- ``pa.ArrowInvalidError`` -- if the arrow data casting fails
- ``TypeError`` -- if the target type is not supported according, e.g.
        - point1
        - point2
- [`HTTPError`](https://2.python-requests.org/en/master/api/#requests.HTTPError) -- if credentials are invalid
- [`HTTPError`](https://2.python-requests.org/en/master/api/#requests.HTTPError) -- if connection got lost

</raises>

<raisederrors>``pa.ArrowInvalidError`` or ``TypeError`` or ``HTTPError``</raisederrors>

<returns>

 some result

</returns>

<returntype>    :obj:`str` or :obj:`bool`</returntype>

Example::

    print(a + b)

End of the arg section.
"""
        self.assertEqual(parse_rst_docstring(rst_docstring), expected_conversion)

        # test yields
        rst_docstring = """
docstring

Args:
    a (:obj:`str` or :obj:`bool`): some parameter
    b (:obj:`str` or :obj:`bool`):
        Another parameter with the description below

Yields:
    :obj:`str` or :obj:`bool`: some result
"""
        expected_conversion = """
docstring

<parameters>

- **a** (:obj:`str` or :obj:`bool`) -- some parameter
- **b** (:obj:`str` or :obj:`bool`) --
        Another parameter with the description below

</parameters>

<yields>

 some result

</yields>

<yieldtype>    :obj:`str` or :obj:`bool`</yieldtype>
"""

        self.assertEqual(parse_rst_docstring(rst_docstring), expected_conversion)

        # test multiple parameter blocks
        rst_docstring = """Args:
    a (:obj:`str` or :obj:`bool`): some parameter
    b (:obj:`str` or :obj:`bool`):
        Another parameter with the description below

Parameters:
    a (:obj:`str` or :obj:`bool`): some parameter
    b (:obj:`str` or :obj:`bool`):
        Another parameter with the description below
"""
        expected_conversion = """



<parameters>- **a** (:obj:`str` or :obj:`bool`) -- some parameter
- **b** (:obj:`str` or :obj:`bool`) --
        Another parameter with the description below
- **a** (:obj:`str` or :obj:`bool`) -- some parameter
- **b** (:obj:`str` or :obj:`bool`) --
        Another parameter with the description below</parameters>
"""
        self.assertEqual(parse_rst_docstring(rst_docstring), expected_conversion)

    def test_remove_indent(self):
        example1 = """
    Lala
    Loulou

    - This is a list.
      This item is long.
    - This is the second item.
        - This list is nested
        - With two items.
        Now we are at the nested level

    - We return to the previous level.

    Now we are out of the list.
"""
        expected1 = """
Lala
Loulou

- This is a list.
  This item is long.
- This is the second item.
  - This list is nested
  - With two items.
  Now we are at the nested level

- We return to the previous level.

Now we are out of the list.
"""

        example1b = """
    Lala
    Loulou

    - This is a list.
      This item is long.
    - This is the second item.
          - This list is nested
          - With two items.
        Now we are at the nested level

    - We return to the previous level.

    Now we are out of the list.
"""
        expected1b = """
Lala
Loulou

- This is a list.
  This item is long.
- This is the second item.
  - This list is nested
  - With two items.
  Now we are at the nested level

- We return to the previous level.

Now we are out of the list.
"""

        example2 = """
[[autodoc]] transformers.BertModel
    - forward

  [[autodoc]] transformers.function

[[autodoc]] transformers.BertTokenizer
    - __call__
    - all
"""
        expected2 = """
[[autodoc]] transformers.BertModel
    - forward

[[autodoc]] transformers.function

[[autodoc]] transformers.BertTokenizer
    - __call__
    - all
"""

        example3 = """
  Lala

  ```python
  def function(x):
      return x
  ```

  Loulou
"""
        expected3 = """
Lala

```python
def function(x):
    return x
```

Loulou
"""
        self.assertEqual(remove_indent(example1), expected1)
        self.assertEqual(remove_indent(example1b), expected1b)
        self.assertEqual(remove_indent(example2), expected2)
        self.assertEqual(remove_indent(example3), expected3)

    def test_process_titles(self):
        self.assertListEqual(
            process_titles(["Title 1", "=======", "text", "", "section", "--------"]),
            ["# Title 1", "text", "", "## section"],
        )

    def test_split_pt_tf_code_blocks(self):
        content = """
bla

```py
common_code
## PYTORCH CODE
pytorch_code
## TENSORFLOW CODE
tf_code
```

bli
"""

        expected = """
bla

<frameworkcontent>
<pt>
```py
common_code
pytorch_code
```
</pt>
<tf>
```py
common_code
tf_code
```
</tf>
</frameworkcontent>

bli
"""

        self.assertEqual(split_pt_tf_code_blocks(content), expected)

    def test_apply_min_indent(self):
        self.assertEqual(apply_min_indent("aaa\n  bb\n\n    ccc\ndd", 4), "    aaa\n      bb\n\n        ccc\n    dd")
