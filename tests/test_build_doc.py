import sys
import unittest

import transformers

# To find the doc_builder package.
sys.path.append("src")

from doc_builder.build_doc import (
    _re_autodoc,
    _re_list_item,
    resolve_links_in_text,
    generate_frontmatter_in_text
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
            "---\nlocal: bert\nsections:\n- local: berttokenizer\n  sections:\n  - local: berttokenizermethod\n    title: BertTokenizerMethod\n  title: BertTokenizer\ntitle: Bert\n---\n# [Bert](#bert)\n## [BertTokenizer](#berttokenizer)\n### [BertTokenizerMethod](#berttokenizermethod)"
        )
        
        # test h1 having h3 children (skipping h2 level)
        self.assertEqual(
            generate_frontmatter_in_text("# Bert\n### BertTokenizerMethodA\n### BertTokenizerMethodB"),
            "---\nlocal: bert\nsections:\n- local: berttokenizermethoda\n  title: BertTokenizerMethodA\n- local: berttokenizermethodb\n  title: BertTokenizerMethodB\ntitle: Bert\n---\n# [Bert](#bert)\n### [BertTokenizerMethodA](#berttokenizermethoda)\n### [BertTokenizerMethodB](#berttokenizermethodb)"
        )
        
        # skip python comments in code blocks (because markdown `#` is same as python comment `#`)
        self.assertEqual(
            generate_frontmatter_in_text("# Bert\n```\n# python comment\n```\n## BertTokenizer"),
            "---\nlocal: bert\nsections:\n- local: berttokenizer\n  title: BertTokenizer\ntitle: Bert\n---\n# [Bert](#bert)\n```\n# python comment\n```\n## [BertTokenizer](#berttokenizer)"
        )
