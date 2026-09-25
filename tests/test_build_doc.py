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

import importlib
import os
import tempfile
import unittest

from doc_builder.build_doc import (
    _re_autodoc,
    _re_list_item,
    build_doc,
    build_mdx_files,
    check_toc_integrity,
    resolve_links,
    resolve_open_in_colab,
)


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

    def test_broken_autodoc_does_not_abort_other_pages(self):
        """
        Regression: a broken [[autodoc]] on one page must not prevent other pages from
        being written or from contributing their anchors.  The error must be aggregated
        and returned, not raised immediately.

        Asserts all three things specified in the PR review:
          1. Other pages are still written to output_dir.
          2. Links to a good page still resolve.
          3. TOC validation accepts the known failed page.
          4. The broken page's error is collected and returned in all_errors (not raised).
        """
        page_info = {
            "version": "main",
            "version_tag": "main",
            "language": "en",
            "package_name": "doc_builder",
            "repo_owner": "huggingface",
            "repo_name": "doc-builder",
            "emit_warning": False,
        }

        with tempfile.TemporaryDirectory() as doc_folder, tempfile.TemporaryDirectory() as output_dir:
            # Good page: valid autodoc that supplies an anchor for the links page.
            good_md = os.path.join(doc_folder, "good_page.md")
            with open(good_md, "w", encoding="utf-8") as f:
                f.write("# Good page\n\n[[autodoc]] doc_builder.build_doc\n")

            links_md = os.path.join(doc_folder, "links.md")
            with open(links_md, "w", encoding="utf-8") as f:
                f.write("# Links\n\nSee [`~doc_builder.build_doc`].\n")

            # Broken page: references a non-existent object via [[autodoc]].
            broken_md = os.path.join(doc_folder, "broken_page.md")
            with open(broken_md, "w", encoding="utf-8") as f:
                f.write("# Broken page\n\n[[autodoc]] does_not_exist.FakeClass\n")

            with open(os.path.join(doc_folder, "_toctree.yml"), "w", encoding="utf-8") as f:
                f.write(
                    "- title: Documentation\n"
                    "  sections:\n"
                    "    - local: good_page\n"
                    "      title: Good page\n"
                    "    - local: links\n"
                    "      title: Links\n"
                    "    - local: broken_page\n"
                    "      title: Broken page\n"
                )

            package = importlib.import_module("doc_builder")
            anchor_mapping, _src_mapping, all_errors, failed_files = build_mdx_files(
                package, doc_folder, output_dir, page_info, version_tag_suffix="src/"
            )

            # 1. The good page must be written to output_dir.
            good_output = os.path.join(output_dir, "good_page.mdx")
            self.assertTrue(
                os.path.isfile(good_output),
                "good_page.mdx was not written — broken autodoc aborted the whole build.",
            )

            # 2. Link resolution uses the anchors from the successfully built page.
            self.assertNotIn(
                "good_page",
                failed_files,
                "good_page ended up in failed_files even though it has no autodoc errors.",
            )
            resolve_links(output_dir, package, anchor_mapping, page_info)
            with open(os.path.join(output_dir, "links.mdx"), encoding="utf-8") as f:
                links_content = f.read()
            self.assertIn("[build_doc()](/docs/doc_builder/main/en/good_page#doc_builder.build_doc)", links_content)

            # 3. The failed page is still listed in the source TOC but is intentionally
            #    excluded from the missing-output check.
            check_toc_integrity(doc_folder, output_dir, known_failed_files=set(failed_files))

            # 4. The broken page's error must be collected — not silently dropped, not raised.
            self.assertTrue(
                len(all_errors) > 0,
                "No errors were collected — broken [[autodoc]] was silently ignored.",
            )
            self.assertIn(
                "broken_page",
                failed_files,
                "broken_page was not recorded in failed_files.",
            )
            # Sanity-check the error message identifies the file so it's diagnosable.
            self.assertTrue(
                any("broken_page" in err for err in all_errors),
                "The collected error doesn't mention broken_page — hard to diagnose later.",
            )

            # The public build function must resolve links before it reports the
            # aggregated conversion error. This verifies the intended ordering.
            with tempfile.TemporaryDirectory() as full_build_output:
                with self.assertRaisesRegex(ValueError, "broken_page"):
                    build_doc(
                        "doc_builder",
                        doc_folder,
                        full_build_output,
                        is_python_module=True,
                        clean=False,
                    )
                with open(os.path.join(full_build_output, "links.mdx"), encoding="utf-8") as f:
                    self.assertIn(
                        "[build_doc()](/docs/doc_builder/main/en/good_page#doc_builder.build_doc)", f.read()
                    )
