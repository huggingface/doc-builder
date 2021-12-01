import re

from .convert_rst_to_mdx import parse_rst_docstring

def convert_md_to_mdx(md_text, page_info):
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
</script>\n'''+process_md(md_text, page_info)


def convert_special_chars(text):
    """
    Convert { and < that have special meanings in MDX.
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


def convert_img_links(text, page_info):
    """
    Convert image links to correct URL paths.
    """
    if "package_name" not in page_info:
        raise ValueError("`page_info` must contain at least the package_name.")
    package_name = page_info["package_name"]
    version = page_info.get("version", "master")
    language = page_info.get("language", "en")

    _re_img_link = re.compile(r"(src=\"|\()/imgs/")
    while _re_img_link.search(text):
        text = _re_img_link.sub(r"\1/docs/%s/%s/%s/imgs/" % (package_name, version, language), text)
    return text


def convert_md_docstring_to_mdx(docstring, page_info):
    """
    Convert a docstring written in Markdown to mdx.
    """
    text = parse_rst_docstring(docstring)
    return process_md(text, page_info)


def process_md(text, page_info):
    """
    Processes markdown by:
        1. Converting special characters
        2. Converting image links
    """
    text = convert_special_chars(text)
    text = convert_img_links(text, page_info)
    return text
