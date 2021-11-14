import sys
import unittest

# To find the doc_builder package.
sys.path.append("src")

from doc_builder.convert_md_to_mdx import convert_md_to_mdx

class ConvertMdToMdxTester(unittest.TestCase):
    def test_convert_md_to_mdx(self):
        md_text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit"
        mdx_text = convert_md_to_mdx(md_text)
        self.assertEqual(mdx_text, '<script>\nimport Tip from "./Tip.svelte";\nimport Youtube from "./Youtube.svelte";\t\nimport Docstring from "./Docstring.svelte";\t\nimport CodeBlock from "./CodeBlock.svelte";\t\nexport let fw: "pt" | "tf"\n</script>\nLorem ipsum dolor sit amet, consectetur adipiscing elit')
