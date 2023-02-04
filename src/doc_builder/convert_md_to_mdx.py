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


import json
import re
import tempfile

from .convert_rst_to_mdx import parse_rst_docstring, remove_indent


_re_doctest_flags = re.compile("^(>>>.*\S)(\s+)# doctest:\s+\+[A-Z_]+\s*$", flags=re.MULTILINE)


def convert_md_to_mdx(md_text, page_info):
    """
    Convert a document written in md to mdx.
    """
    return """<script lang="ts">
import {onMount} from "svelte";
import Tip from "$lib/Tip.svelte";
import Youtube from "$lib/Youtube.svelte";
import Docstring from "$lib/Docstring.svelte";
import CodeBlock from "$lib/CodeBlock.svelte";
import CodeBlockFw from "$lib/CodeBlockFw.svelte";
import DocNotebookDropdown from "$lib/DocNotebookDropdown.svelte";
import CourseFloatingBanner from "$lib/CourseFloatingBanner.svelte";
import IconCopyLink from "$lib/IconCopyLink.svelte";
import FrameworkContent from "$lib/FrameworkContent.svelte";
import Markdown from "$lib/Markdown.svelte";
import Question from "$lib/Question.svelte";
import FrameworkSwitchCourse from "$lib/FrameworkSwitchCourse.svelte";
import InferenceApi from "$lib/InferenceApi.svelte";
import TokenizersLanguageContent from "$lib/TokenizersLanguageContent.svelte";
import ExampleCodeBlock from "$lib/ExampleCodeBlock.svelte";
import Added from "$lib/Added.svelte";
import Changed from "$lib/Changed.svelte";
import Deprecated from "$lib/Deprecated.svelte";
import PipelineIcon from "$lib/PipelineIcon.svelte";
import PipelineTag from "$lib/PipelineTag.svelte";
let fw: "pt" | "tf" = "pt";
onMount(() => {
    const urlParams = new URLSearchParams(window.location.search);
    fw = urlParams.get("fw") || "pt";
});
</script>
<svelte:head>
  <meta name="hf:doc:metadata" content={JSON.stringify(metadata)} >
</svelte:head>
""" + process_md(
        md_text, page_info
    )


def convert_special_chars(text):
    """
    Convert { and < that have special meanings in MDX.
    """
    _re_lcub_svelte = re.compile(
        r"<(Question|Tip|Added|Changed|Deprecated|DocNotebookDropdown|CourseFloatingBanner|FrameworkSwitch|audio|PipelineIcon|PipelineTag)(((?!<(Question|Tip|Added|Changed|Deprecated|DocNotebookDropdown|CourseFloatingBanner|FrameworkSwitch|audio|PipelineIcon|PipelineTag)).)*)>|&amp;lcub;(#if|:else}|/if})",
        re.DOTALL,
    )
    text = text.replace("{", "&amp;lcub;")
    # We don't want to escape `{` that are part of svelte syntax
    text = _re_lcub_svelte.sub(lambda match: match[0].replace("&amp;lcub;", "{"), text)
    # We don't want to replace those by the HTML code, so we temporarily set them at LTHTML
    text = re.sub(
        r"<(img|video|br|hr|Youtube|Question|DocNotebookDropdown|CourseFloatingBanner|FrameworkSwitch|audio|PipelineIcon|PipelineTag)",
        r"LTHTML\1",
        text,
    )  # html void elements with no closing counterpart
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
    version = page_info.get("version", "main")
    language = page_info.get("language", "en")

    _re_img_link = re.compile(r"(src=\"|\()/imgs/")
    while _re_img_link.search(text):
        text = _re_img_link.sub(rf"\1/docs/{package_name}/{version}/{language}/imgs/", text)
    return text


def clean_doctest_syntax(text):
    """
    Clean the doctest artifacts in a given content.
    """
    text = text.replace(">>> # ===PT-TF-SPLIT===", "===PT-TF-SPLIT===")
    text = _re_doctest_flags.sub(r"\1", text)
    return text


_re_literalinclude = re.compile(r"([ \t]*)<literalinclude>(((?!<literalinclude>).)*)<\/literalinclude>", re.DOTALL)


def convert_literalinclude_helper(match, page_info):
    """
    Convert a literalinclude regex match into markdown code blocks by opening a file and
    copying specified start-end section into markdown code block.
    """
    literalinclude_info = json.loads(match[2].strip())
    indent = match[1]
    if tempfile.gettempdir() in str(page_info["path"]):
        return "\n`Please restart doc-builder preview commands to see literalinclude rendered`\n"
    file = page_info["path"].parent / literalinclude_info["path"]
    with open(file, "r", encoding="utf-8-sig") as reader:
        lines = reader.readlines()
    literalinclude = lines  # defaults to entire file
    if "start-after" in literalinclude_info or "end-before" in literalinclude_info:
        start_after, end_before = -1, -1
        for idx, line in enumerate(lines):
            line = line.strip()
            line = re.sub(r"\W+$", "", line)
            if line.endswith(literalinclude_info["start-after"]):
                start_after = idx + 1
            if line.endswith(literalinclude_info["end-before"]):
                end_before = idx
        if start_after == -1 or end_before == -1:
            raise ValueError(f"The following 'literalinclude' does NOT exist:\n{match[0]}")
        literalinclude = lines[start_after:end_before]
    literalinclude = [indent + line[literalinclude_info.get("dedent", 0) :] for line in literalinclude]
    literalinclude = "".join(literalinclude)
    return f"""{indent}```{literalinclude_info.get('language', '')}\n{literalinclude.rstrip()}\n{indent}```"""


def convert_literalinclude(text, page_info):
    """
    Convert a literalinclude into markdown code blocks.
    """
    text = _re_literalinclude.sub(lambda m: convert_literalinclude_helper(m, page_info), text)
    return text


def convert_md_docstring_to_mdx(docstring, page_info):
    """
    Convert a docstring written in Markdown to mdx.
    """
    text = parse_rst_docstring(docstring)
    text = remove_indent(text)
    return process_md(text, page_info)


def process_md(text, page_info):
    """
    Processes markdown by:
        1. Converting literalinclude
        2. Converting special characters
        3. Converting image links
    """
    text = convert_literalinclude(text, page_info)
    text = convert_special_chars(text)
    text = clean_doctest_syntax(text)
    text = convert_img_links(text, page_info)
    return text
