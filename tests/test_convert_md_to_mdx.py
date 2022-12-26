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
from pathlib import Path

from doc_builder.convert_md_to_mdx import (
    convert_img_links,
    convert_literalinclude,
    convert_md_to_mdx,
    convert_special_chars,
    process_md,
)


class ConvertMdToMdxTester(unittest.TestCase):
    def test_convert_md_to_mdx(self):
        page_info = {"package_name": "transformers", "version": "v4.10.0", "language": "fr"}
        md_text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit"
        expected_conversion = """<script lang="ts">
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
Lorem ipsum dolor sit amet, consectetur adipiscing elit"""
        self.assertEqual(convert_md_to_mdx(md_text, page_info), expected_conversion)

    def test_convert_special_chars(self):
        self.assertEqual(convert_special_chars("{ lala }"), "&amp;lcub; lala }")
        self.assertEqual(convert_special_chars("< blo"), "&amp;lt; blo")
        self.assertEqual(convert_special_chars("<source></source>"), "<source></source>")
        self.assertEqual(convert_special_chars("<Youtube id='my_vid' />"), "<Youtube id='my_vid' />")

        longer_test = """<script lang="ts">
import Tip from "$lib/Tip.svelte";
import Youtube from "$lib/Youtube.svelte";
import Docstring from "$lib/Docstring.svelte";
import CodeBlock from "$lib/CodeBlock.svelte";
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

        video_code = '<video src="someSrc">'
        self.assertEqual(convert_special_chars(video_code), video_code)

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

    def test_convert_literalinclude(self):
        path = Path(__file__).resolve()
        page_info = {"path": path}
        # test canonical
        text = """<literalinclude>
{"path": "./data/convert_literalinclude_dummy.txt",
"language": "python",
"start-after": "START python_import",
"end-before": "END python_import"}
</literalinclude>"""
        # test entire file
        text = """<literalinclude>
{"path": "./data/convert_literalinclude_dummy.txt",
"language": "python"}
</literalinclude>"""
        expected_conversion = '''```python
# START python_import_answer
import scipy as sp
# END python_import_answer

# START python_import
import numpy as np
import pandas as pd
# END python_import

# START node_import
import fs
# END node_import"""
```'''
        self.assertEqual(convert_literalinclude(text, page_info), expected_conversion)
        # test without language
        text = """<literalinclude>
{"path": "./data/convert_literalinclude_dummy.txt",
"start-after": "START python_import",
"end-before": "END python_import"}
</literalinclude>"""
        expected_conversion = """```
import numpy as np
import pandas as pd
```"""
        self.assertEqual(convert_literalinclude(text, page_info), expected_conversion)
        # test with indent
        text = """Some text
    <literalinclude>
{"path": "./data/convert_literalinclude_dummy.txt",
"start-after": "START python_import",
"end-before": "END python_import"}
</literalinclude>"""
        expected_conversion = """Some text
    ```
    import numpy as np
    import pandas as pd
    ```"""
        self.assertEqual(convert_literalinclude(text, page_info), expected_conversion)
        # test with dedent
        text = """Some text
    <literalinclude>
{"path": "./data/convert_literalinclude_dummy.txt",
"start-after": "START python_import",
"end-before": "END python_import",
"dedent": 7}
</literalinclude>"""
        expected_conversion = """Some text
    ```
    numpy as np
    pandas as pd
    ```"""
        self.assertEqual(convert_literalinclude(text, page_info), expected_conversion)
        # test tag rstrip
        text = """<literalinclude>
{"path": "./data/convert_literalinclude_dummy.txt",
"start-after": "START node_import",
"end-before": "END node_import"}
</literalinclude>"""
        expected_conversion = """```
import fs
```"""
        self.assertEqual(convert_literalinclude(text, page_info), expected_conversion)
