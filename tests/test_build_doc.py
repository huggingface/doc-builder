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


import re
import unittest

import transformers
from doc_builder.build_doc import _re_autodoc, _re_list_item, generate_frontmatter_in_text, resolve_links_in_text, resolve_open_in_colab


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
<ColabDropdown hydrate-props={{
  classNames: "absolute z-10 right-0 top-0",
  options:[
    {label: "Mixed", value: "https://colab.research.google.com/github/huggingface/notebooks/blob/master/transformers_doc/quicktour.ipynb"},
    {label: "PyTorch", value: "https://colab.research.google.com/github/huggingface/notebooks/blob/master/transformers_doc/pytorch/quicktour.ipynb"},
    {label: "TensorFlow", value: "https://colab.research.google.com/github/huggingface/notebooks/blob/master/transformers_doc/tensorflow/quicktour.ipynb"},
]}} />
"""
        self.assertEqual(resolve_open_in_colab("\n[[open-in-colab]]\n", {"page": "quicktour.html"}), expected)

    def test_resolve_links_in_text(self):
        page_info = {"package_name": "transformers"}
        small_mapping = {
            "transformers.BertModel": "model_doc/bert.html",
            "transformers.BertModel.forward": "model_doc/bert.html",
            "transformers.BertTokenizer": "bert.html",
        }

        self.maxDiff = None
        self.assertEqual(
            resolve_links_in_text(
                "Link to [`BertModel`], [`BertModel.forward`] and [`BertTokenizer`] as well as [`SomeClass`].",
                transformers,
                small_mapping,
                page_info,
            ),
            (
                "Link to [BertModel](/docs/transformers/master/en/model_doc/bert.html#transformers.BertModel), "
                "[BertModel.forward()](/docs/transformers/master/en/model_doc/bert.html#transformers.BertModel.forward) "
                "and [BertTokenizer](/docs/transformers/master/en/bert.html#transformers.BertTokenizer) as well as `SomeClass`."
            ),
        )

        self.assertEqual(
            resolve_links_in_text(
                "Link to [`~transformers.BertModel`], [`~transformers.BertModel.forward`].",
                transformers,
                small_mapping,
                page_info,
            ),
            (
                "Link to [BertModel](/docs/transformers/master/en/model_doc/bert.html#transformers.BertModel), "
                "[forward()](/docs/transformers/master/en/model_doc/bert.html#transformers.BertModel.forward)."
            ),
        )

        self.assertEqual(
            resolve_links_in_text(
                "Link to [`transformers.BertModel`], [`transformers.BertModel.forward`].",
                transformers,
                small_mapping,
                page_info,
            ),
            (
                "Link to [transformers.BertModel](/docs/transformers/master/en/model_doc/bert.html#transformers.BertModel), "
                "[transformers.BertModel.forward()](/docs/transformers/master/en/model_doc/bert.html#transformers.BertModel.forward)."
            ),
        )

    def test_resolve_links_in_text_custom_version_lang(self):
        page_info = {"package_name": "transformers", "version": "v4.10.0", "language": "fr"}
        small_mapping = {
            "transformers.BertModel": "model_doc/bert.html",
            "transformers.BertModel.forward": "model_doc/bert.html",
            "transformers.BertTokenizer": "bert.html",
        }

        self.maxDiff = None
        self.assertEqual(
            resolve_links_in_text(
                "Link to [`BertModel`], [`BertModel.forward`] and [`BertTokenizer`] as well as [`SomeClass`].",
                transformers,
                small_mapping,
                page_info,
            ),
            (
                "Link to [BertModel](/docs/transformers/v4.10.0/fr/model_doc/bert.html#transformers.BertModel), "
                "[BertModel.forward()](/docs/transformers/v4.10.0/fr/model_doc/bert.html#transformers.BertModel.forward) "
                "and [BertTokenizer](/docs/transformers/v4.10.0/fr/bert.html#transformers.BertTokenizer) as well as `SomeClass`."
            ),
        )

        self.assertEqual(
            resolve_links_in_text(
                "Link to [`~transformers.BertModel`], [`~transformers.BertModel.forward`].",
                transformers,
                small_mapping,
                page_info,
            ),
            (
                "Link to [BertModel](/docs/transformers/v4.10.0/fr/model_doc/bert.html#transformers.BertModel), "
                "[forward()](/docs/transformers/v4.10.0/fr/model_doc/bert.html#transformers.BertModel.forward)."
            ),
        )

        self.assertEqual(
            resolve_links_in_text(
                "Link to [`transformers.BertModel`], [`transformers.BertModel.forward`].",
                transformers,
                small_mapping,
                page_info,
            ),
            (
                "Link to [transformers.BertModel](/docs/transformers/v4.10.0/fr/model_doc/bert.html#transformers.BertModel), "
                "[transformers.BertModel.forward()](/docs/transformers/v4.10.0/fr/model_doc/bert.html#transformers.BertModel.forward)."
            ),
        )

    def test_generate_frontmatter_in_text(self):
        # test canonical
        self.assertEqual(
            generate_frontmatter_in_text("# Bert\n## BertTokenizer\n### BertTokenizerMethod"),
            '---\nlocal: bert\nsections:\n- local: berttokenizer\n  sections:\n  - local: berttokenizermethod\n    title: BertTokenizerMethod\n  title: BertTokenizer\ntitle: Bert\n---\n<h1 id="bert">Bert</h1>\n<h2 id="berttokenizer">BertTokenizer</h2>\n<h3 id="berttokenizermethod">BertTokenizerMethod</h3>',
        )

        # test h1 having h3 children (skipping h2 level)
        self.assertEqual(
            generate_frontmatter_in_text("# Bert\n### BertTokenizerMethodA\n### BertTokenizerMethodB"),
            '---\nlocal: bert\nsections:\n- local: berttokenizermethoda\n  title: BertTokenizerMethodA\n- local: berttokenizermethodb\n  title: BertTokenizerMethodB\ntitle: Bert\n---\n<h1 id="bert">Bert</h1>\n<h3 id="berttokenizermethoda">BertTokenizerMethodA</h3>\n<h3 id="berttokenizermethodb">BertTokenizerMethodB</h3>',
        )

        # skip python comments in code blocks (because markdown `#` is same as python comment `#`)
        self.assertEqual(
            generate_frontmatter_in_text("# Bert\n```\n# python comment\n```\n## BertTokenizer"),
            '---\nlocal: bert\nsections:\n- local: berttokenizer\n  title: BertTokenizer\ntitle: Bert\n---\n<h1 id="bert">Bert</h1>\n```\n# python comment\n```\n<h2 id="berttokenizer">BertTokenizer</h2>',
        )

        # test header with multiple words
        self.assertEqual(
            generate_frontmatter_in_text("# Bert and Bart\n```\n# python comment\n```\n## BertTokenizer"),
            '---\nlocal: bert-and-bart\nsections:\n- local: berttokenizer\n  title: BertTokenizer\ntitle: Bert and Bart\n---\n<h1 id="bert-and-bart">Bert and Bart</h1>\n```\n# python comment\n```\n<h2 id="berttokenizer">BertTokenizer</h2>',
        )

        # test header with HF emoji
        self.assertEqual(
            generate_frontmatter_in_text("# SomeHeader 🤗\n```\n"),
            '---\nlocal: someheader\ntitle: SomeHeader 🤗\n---\n<h1 id="someheader">SomeHeader 🤗</h1>\n```\n',
        )

        # test headers with exisitng ids
        self.assertEqual(
            generate_frontmatter_in_text("# Bert[[id1]]\n## BertTokenizer[[id2]]\n### BertTokenizerMethod"),
            '---\nlocal: id1\nsections:\n- local: id2\n  sections:\n  - local: berttokenizermethod\n    title: BertTokenizerMethod\n  title: BertTokenizer\ntitle: Bert\n---\n<h1 id="id1">Bert</h1>\n<h2 id="id2">BertTokenizer</h2>\n<h3 id="berttokenizermethod">BertTokenizerMethod</h3>',
        )

        # test headers with numbers
        self.assertEqual(
            generate_frontmatter_in_text("# Bert 1\n## BertTokenizer 2 3\n### BertTokenizer 4 5 6 Method"),
            '---\nlocal: bert-1\nsections:\n- local: berttokenizer-2-3\n  sections:\n  - local: berttokenizer-4-5-6-method\n    title: BertTokenizer 4 5 6 Method\n  title: BertTokenizer 2 3\ntitle: Bert 1\n---\n<h1 id="bert-1">Bert 1</h1>\n<h2 id="berttokenizer-2-3">BertTokenizer 2 3</h2>\n<h3 id="berttokenizer-4-5-6-method">BertTokenizer 4 5 6 Method</h3>',
        )
