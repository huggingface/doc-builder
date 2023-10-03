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
        expected = """
<DocNotebookDropdown
  classNames="absolute z-10 right-0 top-0"
  options={[
    {label: "Mixed", value: "https://colab.research.google.com/github/huggingface/notebooks/blob/main/transformers_doc/en/quicktour.ipynb"},
    {label: "PyTorch", value: "https://colab.research.google.com/github/huggingface/notebooks/blob/main/transformers_doc/en/pytorch/quicktour.ipynb"},
    {label: "TensorFlow", value: "https://colab.research.google.com/github/huggingface/notebooks/blob/main/transformers_doc/en/tensorflow/quicktour.ipynb"},
    {label: "Mixed", value: "https://studiolab.sagemaker.aws/import/github/huggingface/notebooks/blob/main/transformers_doc/en/quicktour.ipynb"},
    {label: "PyTorch", value: "https://studiolab.sagemaker.aws/import/github/huggingface/notebooks/blob/main/transformers_doc/en/pytorch/quicktour.ipynb"},
    {label: "TensorFlow", value: "https://studiolab.sagemaker.aws/import/github/huggingface/notebooks/blob/main/transformers_doc/en/tensorflow/quicktour.ipynb"},
]} />
"""
        self.assertEqual(
            resolve_open_in_colab("\n[[open-in-colab]]\n", {"package_name": "transformers", "page": "quicktour.html"}),
            expected,
        )
