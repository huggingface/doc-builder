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

from doc_builder.build_doc import _re_autodoc, _re_list_item, resolve_open_in_colab


class BuildDocTester(unittest.TestCase):
    def test_re_autodoc(self):
        self.assertEqual(
            _re_autodoc.search("[[autodoc]] transformers.FlaxBertForQuestionAnswering").groups(),
            ("transformers.FlaxBertForQuestionAnswering",),
        )

    def test_re_list_item(self):
        self.assertEqual(_re_list_item.search("   - forward").groups(), ("forward",))

    def test_resolve_open_in_colab(self):
        # Test with heading - should place component before the heading
        input_with_heading = "[[open-in-colab]]\n\n# Quick tour\n\nSome content here."
        expected_with_heading = """<DocNotebookDropdown
  containerStyle="float: right; margin-left: 10px; display: inline-flex; position: relative; z-index: 10;"
  options={[
    {label: "Mixed", value: "https://colab.research.google.com/github/huggingface/notebooks/blob/main/transformers_doc/en/quicktour.ipynb"},
    {label: "PyTorch", value: "https://colab.research.google.com/github/huggingface/notebooks/blob/main/transformers_doc/en/pytorch/quicktour.ipynb"},
    {label: "TensorFlow", value: "https://colab.research.google.com/github/huggingface/notebooks/blob/main/transformers_doc/en/tensorflow/quicktour.ipynb"},
    {label: "Mixed", value: "https://studiolab.sagemaker.aws/import/github/huggingface/notebooks/blob/main/transformers_doc/en/quicktour.ipynb"},
    {label: "PyTorch", value: "https://studiolab.sagemaker.aws/import/github/huggingface/notebooks/blob/main/transformers_doc/en/pytorch/quicktour.ipynb"},
    {label: "TensorFlow", value: "https://studiolab.sagemaker.aws/import/github/huggingface/notebooks/blob/main/transformers_doc/en/tensorflow/quicktour.ipynb"},
]} />

# Quick tour

Some content here."""
        self.assertEqual(
            resolve_open_in_colab(input_with_heading, {"package_name": "transformers", "page": "quicktour.html"}),
            expected_with_heading,
        )

        # Test with CopyLLMTxtMenu present - should place component after CopyLLMTxtMenu
        # (so CopyLLMTxtMenu appears rightmost when floated)
        input_with_copy_menu = '[[open-in-colab]]\n\n<CopyLLMTxtMenu containerStyle="float: right;"></CopyLLMTxtMenu>\n\n# Quick tour\n\nContent.'
        expected_with_copy_menu = """<CopyLLMTxtMenu containerStyle="float: right;"></CopyLLMTxtMenu>

<DocNotebookDropdown
  containerStyle="float: right; margin-left: 10px; display: inline-flex; position: relative; z-index: 10;"
  options={[
    {label: "Mixed", value: "https://colab.research.google.com/github/huggingface/notebooks/blob/main/transformers_doc/en/quicktour.ipynb"},
    {label: "PyTorch", value: "https://colab.research.google.com/github/huggingface/notebooks/blob/main/transformers_doc/en/pytorch/quicktour.ipynb"},
    {label: "TensorFlow", value: "https://colab.research.google.com/github/huggingface/notebooks/blob/main/transformers_doc/en/tensorflow/quicktour.ipynb"},
    {label: "Mixed", value: "https://studiolab.sagemaker.aws/import/github/huggingface/notebooks/blob/main/transformers_doc/en/quicktour.ipynb"},
    {label: "PyTorch", value: "https://studiolab.sagemaker.aws/import/github/huggingface/notebooks/blob/main/transformers_doc/en/pytorch/quicktour.ipynb"},
    {label: "TensorFlow", value: "https://studiolab.sagemaker.aws/import/github/huggingface/notebooks/blob/main/transformers_doc/en/tensorflow/quicktour.ipynb"},
]} />

# Quick tour

Content."""
        self.assertEqual(
            resolve_open_in_colab(input_with_copy_menu, {"package_name": "transformers", "page": "quicktour.html"}),
            expected_with_copy_menu,
        )
