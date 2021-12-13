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

from doc_builder.convert_md_to_mdx import convert_img_links, convert_md_to_mdx, convert_special_chars, process_md


class ConvertMdToMdxTester(unittest.TestCase):
    def test_convert_md_to_mdx(self):
        page_info = {"package_name": "transformers", "version": "v4.10.0", "language": "fr"}
        md_text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit"
        expected_conversion = '<script>\nimport Tip from "./Tip.svelte";\nimport Youtube from "./Youtube.svelte";\nimport Docstring from "./Docstring.svelte";\nimport CodeBlock from "./CodeBlock.svelte";\nimport CodeBlockFw from "./CodeBlockFw.svelte";\nimport ColabDropdown from "./ColabDropdown.svelte";\nimport IconCopyLink from "./IconCopyLink.svelte";\nimport FrameworkSwitch from "./FrameworkSwitch.svelte";\nexport let fw: "pt" | "tf"\n</script>\nLorem ipsum dolor sit amet, consectetur adipiscing elit'
        self.assertEqual(convert_md_to_mdx(md_text, page_info), expected_conversion)

    def test_convert_special_chars(self):
        self.assertEqual(convert_special_chars("{ lala }"), "&amp;lcub; lala }")
        self.assertEqual(convert_special_chars("< blo"), "&amp;lt; blo")
        self.assertEqual(convert_special_chars("<source></source>"), "<source></source>")
        self.assertEqual(convert_special_chars("<Youtube id='my_vid' />"), "<Youtube id='my_vid' />")
        self.assertEqual(convert_special_chars("<FrameworkSwitch />"), "<FrameworkSwitch />")

        longer_test = """<script>
import Tip from "./Tip.svelte";
import Youtube from "./Youtube.svelte";
import Docstring from "./Docstring.svelte";
import CodeBlock from "./CodeBlock.svelte";
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

        comment = "<!-- comment -->"
        self.assertEqual(convert_special_chars(comment), comment)

    def test_convert_img_links(self):
        page_info = {"package_name": "transformers", "version": "v4.10.0", "language": "fr"}

        img_md = "[img](/imgs/img.gif)"
        self.assertEqual(convert_img_links(img_md, page_info), "[img](/docs/transformers/v4.10.0/fr/imgs/img.gif)")

        img_html = '<img src="/imgs/img.gif"/>'
        self.assertEqual(
            convert_img_links(img_html, page_info), '<img src="/docs/transformers/v4.10.0/fr/imgs/img.gif"/>'
        )

    def test_process_md(self):
        page_info = {"package_name": "transformers", "version": "v4.10.0", "language": "fr"}

        text = """[img](/imgs/img.gif)
{}
<>"""
        expected_conversion = """[img](/docs/transformers/v4.10.0/fr/imgs/img.gif)
&amp;lcub;}
&amp;lt;>"""
        self.assertEqual(process_md(text, page_info), expected_conversion)
