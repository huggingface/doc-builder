import sys
import unittest

import transformers

# To find the doc_builder package.
sys.path.append("src")

from doc_builder.build_doc import (
    _re_autodoc,
    _re_list_item,
    resolve_links_in_text
)


class BuildDocTester(unittest.TestCase):
    def test_re_autodoc(self):
        self.assertEqual(
            _re_autodoc.search("[[autodoc]] transformers.FlaxBertForQuestionAnswering").groups(), 
            ("transformers.FlaxBertForQuestionAnswering",)
        )
    
    def test_re_list_item(self):
        self.assertEqual(_re_list_item.search("   - forward").groups(), ("forward",))
    

    def test_resolve_links_in_text(self):
        small_mapping = {
            "transformers.BertModel": "model_doc/bert.html",
            "transformers.BertModel.forward": "model_doc/bert.html",
            "transformers.BertTokenizer": "bert.html",
        }

        self.assertEqual(
            resolve_links_in_text(
                "Link to [`BertModel`], [`BertModel.forward`] and [`BertTokenizer`] as well as [`SomeClass`].",
                transformers,
                small_mapping,
            ),
            (
                "Link to [BertModel](model_doc/bert.html#transformers.BertModel), "
                "[BertModel.forward()](model_doc/bert.html#transformers.BertModel.forward) "
                "and [BertTokenizer](bert.html#transformers.BertTokenizer) as well as `SomeClass`."
            ),
        )

        self.assertEqual(
            resolve_links_in_text(
                "Link to [`~transformers.BertModel`], [`~transformers.BertModel.forward`].",
                transformers,
                small_mapping,
            ),
            (
                "Link to [BertModel](model_doc/bert.html#transformers.BertModel), "
                "[forward()](model_doc/bert.html#transformers.BertModel.forward)."
            ),
        )

        self.assertEqual(
            resolve_links_in_text(
                "Link to [`transformers.BertModel`], [`transformers.BertModel.forward`].",
                transformers,
                small_mapping,
            ),
            (
                "Link to [transformers.BertModel](model_doc/bert.html#transformers.BertModel), "
                "[transformers.BertModel.forward()](model_doc/bert.html#transformers.BertModel.forward)."
            ),
        )