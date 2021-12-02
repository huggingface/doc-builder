import sys
import unittest

# To find the doc_builder package.
sys.path.append("src")

from doc_builder.convert_md_to_mdx import convert_md_to_mdx, convert_special_chars, convert_img_links, process_md

class ConvertMdToMdxTester(unittest.TestCase):
    def test_convert_md_to_mdx(self):
        page_info = {"package_name": "transformers", "version": "v4.10.0", "language": "fr"}
        md_text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit"
        expected_conversion = '<script>\nimport Tip from "./Tip.svelte";\nimport Youtube from "./Youtube.svelte";\t\nimport Docstring from "./Docstring.svelte";\t\nimport CodeBlock from "./CodeBlock.svelte";\t\nimport CodeBlockFw from "./CodeBlockFw.svelte";\t\nimport IconCopyLink from "./IconCopyLink.svelte";\t\nexport let fw: "pt" | "tf"\n</script>\nLorem ipsum dolor sit amet, consectetur adipiscing elit'
        self.assertEqual(convert_md_to_mdx(md_text, page_info), expected_conversion)

    def test_convert_special_chars(self):
        self.assertEqual(convert_special_chars("{ lala }"), "&amp;lcub; lala }")
        self.assertEqual(convert_special_chars("< blo"), "&amp;lt; blo")
        self.assertEqual(convert_special_chars("<source></source>"), "<source></source>")

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

        comment = '<!-- comment -->'
        self.assertEqual(convert_special_chars(comment), comment)

    def test_convert_img_links(self):
        page_info = {"package_name": "transformers", "version": "v4.10.0", "language": "fr"}

        img_md = "[img](/imgs/img.gif)"
        self.assertEqual(convert_img_links(img_md, page_info), '[img](/docs/transformers/v4.10.0/fr/imgs/img.gif)')

        img_html = '<img src="/imgs/img.gif"/>'
        self.assertEqual(convert_img_links(img_html, page_info), '<img src="/docs/transformers/v4.10.0/fr/imgs/img.gif"/>')

    def test_process_md(self):
        page_info = {"package_name": "transformers", "version": "v4.10.0", "language": "fr"}

        text = """[img](/imgs/img.gif)
{}
<>"""
        expected_conversion = """[img](/docs/transformers/v4.10.0/fr/imgs/img.gif)
&amp;lcub;}
&amp;lt;>"""
        self.assertEqual(process_md(text, page_info), expected_conversion)

