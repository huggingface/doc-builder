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

from doc_builder.convert_to_notebook import (
    _re_copyright,
    _re_header,
    _re_math_delimiter,
    _re_python_code,
    _re_youtube,
    expand_links,
    parse_input_output,
    split_frameworks,
)


class ConvertToNotebookTester(unittest.TestCase):
    def test_re_math_delimiter(self):
        self.assertEqual(_re_math_delimiter.search("\\\\(lala\\\\)").groups()[0], "lala")
        self.assertListEqual(_re_math_delimiter.findall("\\\\(lala\\\\)xx\\\\(loulou\\\\)"), ["lala", "loulou"])

    def test_re_copyright(self):
        self.assertIsNotNone(
            _re_copyright.search("<!--Copyright 2021 Hugging Face\n more more more\n--> rest of text")
        )

    def test_re_youtube(self):
        self.assertEqual(_re_youtube.search('<Youtube id="tiZFewofSLM"/>').groups()[0], "tiZFewofSLM")

    def test_re_header(self):
        self.assertIsNotNone(_re_header.search("# Title"))
        self.assertIsNotNone(_re_header.search("### Subesection"))
        self.assertIsNone(_re_header.search("Title"))

    def test_re_python(self):
        self.assertIsNotNone(_re_python_code.search("```py"))
        self.assertIsNotNone(_re_python_code.search("```python"))
        self.assertIsNone(_re_python_code.search("```bash"))
        self.assertIsNone(_re_python_code.search("```"))

    def test_parse_inputs_output(self):
        expected = "from transformers import pipeline\n\nclassifier = pipeline('sentiment-analysis')"
        doctest_lines_no_output = [
            ">>> from transformers import pipeline",
            "",
            ">>> classifier = pipeline('sentiment-analysis')",
        ]
        doctest_lines_with_output = [
            ">>> from transformers import pipeline",
            "",
            ">>> classifier = pipeline('sentiment-analysis')",
            "output",
        ]
        regular_lines = ["from transformers import pipeline", "", "classifier = pipeline('sentiment-analysis')"]

        self.assertListEqual(parse_input_output(regular_lines), [(expected, None)])
        self.assertListEqual(parse_input_output(doctest_lines_no_output), [(expected, None)])
        self.assertListEqual(parse_input_output(doctest_lines_with_output), [(expected, "output")])

    def test_parse_inputs_output_multiple_outputs(self):
        expected_1 = "from transformers import pipeline"
        expected_2 = "classifier = pipeline('sentiment-analysis')"

        doctest_lines_with_output = [
            ">>> from transformers import pipeline",
            "output 1",
            ">>> classifier = pipeline('sentiment-analysis')",
            "output 2",
        ]

        self.assertListEqual(
            parse_input_output(doctest_lines_with_output), [(expected_1, "output 1"), (expected_2, "output 2")]
        )

        doctest_lines_with_one_output = [
            ">>> from transformers import pipeline",
            "output 1",
            ">>> classifier = pipeline('sentiment-analysis')",
        ]

        self.assertListEqual(
            parse_input_output(doctest_lines_with_one_output), [(expected_1, "output 1"), (expected_2, None)]
        )

    def test_split_framewors(self):
        test_content = """
Intro
```py
common_code_sample
```
Content
<frameworkcontent>
<pt>
```py
pt_sample
```
</pt>
<tf>
```py
tf_sample
```
</tf>
</frameworkcontent>
End
"""
        mixed_content = """
Intro
```py
common_code_sample
```
Content
```py
pt_sample
```
```py
tf_sample
```
End
"""
        pt_content = """
Intro
```py
common_code_sample
```
Content
```py
pt_sample
```
End
"""
        tf_content = """
Intro
```py
common_code_sample
```
Content
```py
tf_sample
```
End
"""
        for expected, obtained in zip([mixed_content, pt_content, tf_content], split_frameworks(test_content)):
            self.assertEqual(expected, obtained)

    def test_expand_links(self):
        page_info = {"package_name": "transformers", "page": "quicktour.html"}
        self.assertEqual(
            expand_links("Checkout the [task summary](task-summary)", page_info),
            "Checkout the [task summary](https://huggingface.co/docs/transformers/main/en/task-summary)",
        )
        self.assertEqual(
            expand_links("Checkout the [`Trainer`](/docs/transformers/main/en/trainer#Trainer)", page_info),
            "Checkout the [`Trainer`](https://huggingface.co/docs/transformers/main/en/trainer#Trainer)",
        )

        page_info = {"package_name": "datasets", "page": "quicktour.html", "version": "stable", "language": "fr"}
        self.assertEqual(
            expand_links("Checkout the [task summary](task-summary)", page_info),
            "Checkout the [task summary](https://huggingface.co/docs/datasets/stable/fr/task-summary)",
        )

        page_info = {"package_name": "transformers", "page": "data/quicktour.html"}
        self.assertEqual(
            expand_links("Checkout the [task summary](task-summary)", page_info),
            "Checkout the [task summary](https://huggingface.co/docs/transformers/main/en/data/task-summary)",
        )
