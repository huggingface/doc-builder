import re

from .convert_rst_to_mdx import parse_rst_docstring

def convert_md_to_mdx(md_text):
    """
    Convert a document written in md to mdx.
    """
    return '''<script>
import Tip from "./Tip.svelte";
import Youtube from "./Youtube.svelte";	
import Docstring from "./Docstring.svelte";	
import CodeBlock from "./CodeBlock.svelte";	
import CodeBlockFw from "./CodeBlockFw.svelte";	
import IconCopyLink from "./IconCopyLink.svelte";	
export let fw: "pt" | "tf"
</script>\n'''+convert_special_chars(md_text)


def convert_special_chars(text):
    """
    Converts { and < that have special meanings in MDX.
    """
    text = text.replace("{", "&amp;lcub;")
    # We don't want to replace those by the HTML code, so we temporarily set them at LTHTML
    text = re.sub(r"<(img|br|hr)", r"LTHTML\1", text) # html void elements with no closing counterpart
    _re_lt_html = re.compile(r"<(\S+)([^>]*>)(((?!</\1>).)*)<(/\1>)", re.DOTALL)
    while _re_lt_html.search(text):
        text = _re_lt_html.sub(r"LTHTML\1\2\3LTHTML\5", text)
    text = re.sub(r"(^|[^<])<([^(<|!)]|$)", r"\1&amp;lt;\2", text)
    text = text.replace("LTHTML", "<")
    return text


def convert_md_docstring_to_mdx(docstring):
    """
    Convert a docstring written in Markdown to mdx.
    """
    text = parse_rst_docstring(docstring)
    return convert_special_chars(text)
