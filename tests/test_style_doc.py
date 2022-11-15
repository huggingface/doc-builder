# coding=utf-8
# Copyright 2022 The HuggingFace Team. All rights reserved.
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

import re
import unittest

from doc_builder.style_doc import (
    _re_code,
    _re_docstyle_ignore,
    _re_list,
    _re_tip,
    format_code_example,
    format_text,
    parse_code_example,
    style_docstring,
)


class BuildDocTester(unittest.TestCase):
    def test_re_code(self):
        self.assertEqual(_re_code.search("```").groups(), ("", ""))
        self.assertEqual(_re_code.search("```python").groups(), ("", "python"))
        self.assertEqual(_re_code.search("    ```").groups(), ("    ", ""))
        self.assertEqual(_re_code.search("    ```python").groups(), ("    ", "python"))

    def test_re_docstyle_ignore(self):
        self.assertIsNotNone(_re_docstyle_ignore.search("# docstyle-ignore"))
        self.assertIsNotNone(_re_docstyle_ignore.search("   #   docstyle-ignore"))

    def test_re_list(self):
        self.assertEqual(_re_list.search("  - normal list").groups(), ("  - ",))
        self.assertEqual(_re_list.search("* star list").groups(), ("* ",))
        self.assertEqual(_re_list.search("    1. digit list").groups(), ("    1. ",))

    def test_re_tip(self):
        self.assertIsNotNone(_re_tip.search("<Tip>"))
        self.assertIsNotNone(_re_tip.search("    <Tip>"))

        self.assertIsNotNone(_re_tip.search("</Tip>"))
        self.assertIsNotNone(_re_tip.search("    </Tip>"))

        self.assertIsNotNone(_re_tip.search("<Tip warning={true}>"))
        self.assertIsNotNone(_re_tip.search("    <Tip warning={true}>"))

    def test_parse_code_example(self):
        # One code sample, no output
        self.assertEqual(parse_code_example(["code line 1", "code line 2"]), (["code line 1\ncode line 2"], []))
        self.assertEqual(
            parse_code_example([">>> code line 1", ">>> code line 2"]), (["code line 1\ncode line 2"], [])
        )
        self.assertEqual(
            parse_code_example([">>> code line 1", "... code line 2"]), (["code line 1\ncode line 2"], [])
        )

        # One code sample, one output
        self.assertEqual(
            parse_code_example([">>> code line 1", ">>> code line 2", "output"]),
            (["code line 1\ncode line 2"], ["output"]),
        )
        self.assertEqual(
            parse_code_example([">>> code line 1", "... code line 2", "output"]),
            (["code line 1\ncode line 2"], ["output"]),
        )

        # Two code samples, one output
        self.assertEqual(
            parse_code_example([">>> code sample 1", "output 1", ">>> code sample 2"]),
            (["code sample 1", "code sample 2"], ["output 1"]),
        )
        self.assertEqual(
            parse_code_example([">>> code sample 1", "... sample 1 other line", "output 1", ">>> code sample 2"]),
            (["code sample 1\nsample 1 other line", "code sample 2"], ["output 1"]),
        )

        # Two code samples, two outputs
        self.assertEqual(
            parse_code_example([">>> code sample 1", "output 1", ">>> code sample 2", "output 2"]),
            (["code sample 1", "code sample 2"], ["output 1", "output 2"]),
        )
        self.assertEqual(
            parse_code_example(
                [">>> code sample 1", "...     indented code", "output 1", ">>> code sample 2", "output 2"]
            ),
            (["code sample 1\n    indented code", "code sample 2"], ["output 1", "output 2"]),
        )

    def test_format_code_example(self):
        no_output_code = "from transformers import AutoModel\nmodel = AutoModel('bert-base-cased')"
        expected_result = 'from transformers import AutoModel\n\nmodel = AutoModel("bert-base-cased")'
        self.assertEqual(format_code_example(no_output_code, max_len=119), (expected_result, ""))

        no_output_code = ">>> from transformers import AutoModel\n>>> model = AutoModel('bert-base-cased')"
        expected_result = '>>> from transformers import AutoModel\n\n>>> model = AutoModel("bert-base-cased")'
        self.assertEqual(format_code_example(no_output_code, max_len=119), (expected_result, ""))

        no_output_code_with_indent = (
            "    >>> from transformers import AutoModel\n    >>> model = AutoModel('bert-base-cased')"
        )
        expected_result = '    >>> from transformers import AutoModel\n\n    >>> model = AutoModel("bert-base-cased")'
        self.assertEqual(format_code_example(no_output_code_with_indent, max_len=119), (expected_result, ""))

        no_output_code_with_error = "from transformers import AutoModel\nmodel = AutoModel('bert-base-cased'"
        result, error = format_code_example(no_output_code_with_error, max_len=119)
        self.assertEqual(result, no_output_code_with_error)
        self.assertIn("Error message:\nCannot parse", error)

        code_with_output = ">>> from transformers import AutoModel\n>>> model = AutoModel('bert-base-cased')\noutput"
        expected_result = '>>> from transformers import AutoModel\n\n>>> model = AutoModel("bert-base-cased")\noutput'
        self.assertEqual(format_code_example(code_with_output, max_len=119), (expected_result, ""))

    def test_format_text(self):
        text = "This is an example text   that will \nbe used in\n  these examples. "
        clean_text = re.sub("\s+", " ", text).strip()
        for max_len in [20, 30, 50, 100]:
            formatted_text = format_text(text, max_len=max_len)
            # Nothing was lost
            self.assertEqual(clean_text, formatted_text.replace("\n", " "))
            for line in formatted_text.split("\n"):
                self.assertTrue(len(line) <= max_len)

            formatted_text = format_text(text, max_len=max_len, min_indent=4)
            # Nothing was lost
            clean_formatted_text = "\n".join([l[4:] for l in formatted_text.split("\n")])
            self.assertEqual(clean_text, clean_formatted_text.replace("\n", " "))
            for line in formatted_text.split("\n"):
                self.assertTrue(line.startswith("    "))
                self.assertTrue(len(line) <= max_len)

            formatted_text = format_text(text, max_len=max_len, prefix="- ", min_indent=4)
            # Nothing was lost
            clean_formatted_text = "\n".join([l[4:] for l in formatted_text.split("\n")])
            self.assertEqual(clean_text, clean_formatted_text.replace("\n", " "))
            for i, line in enumerate(formatted_text.split("\n")):
                self.assertTrue(line.startswith("    " if i > 0 else "  - "))
                self.assertTrue(len(line) <= max_len)

    def test_format_docstring_empty_line(self):
        test_docstring = """Function description

Params:

    x (`int`): This is x.
    y (`float`): this is y.
"""
        expected_result = """Function description

Params:
    x (`int`): This is x.
    y (`float`): this is y.
"""

        self.assertEqual(style_docstring(test_docstring, 119)[0], expected_result)

    def test_format_docstring_handle_params_without_empty_line_after_description(self):
        test_docstring = """Function description
Params:
    x (`int`): This is x.
    y (`float`): this is y.
"""
        expected_result = """Function description

Params:
    x (`int`): This is x.
    y (`float`): this is y.
"""

        self.assertEqual(style_docstring(test_docstring, 119)[0], expected_result)
