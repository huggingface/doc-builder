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
    convert_include,
    convert_literalinclude,
    convert_md_to_mdx,
    escape_img_alt_description,
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
import Heading from "$lib/Heading.svelte";
import HfOptions from "$lib/HfOptions.svelte";
import HfOption from "$lib/HfOption.svelte";
import EditOnGithub from "$lib/EditOnGithub.svelte";
let fw: "pt" | "tf" = "pt";
onMount(() => {
    const urlParams = new URLSearchParams(window.location.search);
    fw = urlParams.get("fw") || "pt";
});
</script>
<svelte:head>
  <meta name="hf:doc:metadata" content={metadata} >
</svelte:head>

<!--HF DOCBUILD BODY START-->

HF_DOC_BODY_START

Lorem ipsum dolor sit amet, consectetur adipiscing elit

<!--HF DOCBUILD BODY END-->

HF_DOC_BODY_END

"""
        self.assertEqual(convert_md_to_mdx(md_text, page_info), expected_conversion)

    def test_convert_img_links(self):
        page_info = {"package_name": "transformers", "version": "v4.10.0", "language": "fr"}

        img_md = "[img](/imgs/img.gif)"
        self.assertEqual(convert_img_links(img_md, page_info), "[img](/docs/transformers/v4.10.0/fr/imgs/img.gif)")

        img_html = '<img src="/imgs/img.gif"/>'
        self.assertEqual(
            convert_img_links(img_html, page_info), '<img src="/docs/transformers/v4.10.0/fr/imgs/img.gif"/>'
        )

    def test_escape_img_alt_description(self):
        multiple_imgs_md = """![Animation exploring `model_args.pipeline_tag`](imgsrc)

### Some heading

<img src="somesrc" alt="Animation exploring `model_args.pipeline_tag`">

![Animation exploring `model_args.pipeline_tag`](imgsrc)

<img src="somesrc" alt='Animation exploring `model_args.pipeline_tag`'>

<img src="somesrc">

![Animation exploring model_args.pipeline_tag](imgsrc)"""
        expected_conversion = """![Animation exploring 'model_args.pipeline_tag'](imgsrc)

### Some heading

<img src="somesrc" alt="Animation exploring 'model_args.pipeline_tag'">

![Animation exploring 'model_args.pipeline_tag'](imgsrc)

<img src="somesrc" alt='Animation exploring 'model_args.pipeline_tag''>

<img src="somesrc">

![Animation exploring model_args.pipeline_tag](imgsrc)"""
        self.assertEqual(escape_img_alt_description(multiple_imgs_md), expected_conversion)

    def test_process_md(self):
        page_info = {"package_name": "transformers", "version": "v4.10.0", "language": "fr"}

        text = """[img](/imgs/img.gif)
{}
<>"""
        expected_conversion = """[img](/docs/transformers/v4.10.0/fr/imgs/img.gif)
{}
<>"""
        self.assertEqual(process_md(text, page_info), expected_conversion)

    def test_convert_include(self):
        path = Path(__file__).resolve()
        page_info = {"path": path}

        # canonical test:
        # <include>
        # {
        #     "path": "./data/convert_include_dummy.txt",
        #     "start-after": "START header_1",
        #     "end-before": "END header_1"
        # }
        # </include>

        # test entire file
        text = """<include>
{"path": "./data/convert_include_dummy.txt"}
</include>"""
        expected_conversion = """<!-- START header_1 -->
# This is the first header
Other text 1
<!-- END header_1 -->

<!-- START header_2 -->
# This is the second header
Other text 2
<!-- END header_2 -->

<!-- START header_3 -->
# This is the third header
Other text 3
<!-- END header_3 -->"""
        self.assertEqual(convert_include(text, page_info), expected_conversion)

        # test with indent
        text = """Some text
    <include>
{"path": "./data/convert_include_dummy.txt",
"start-after": "START header_1",
"end-before": "END header_1"}
</include>"""
        expected_conversion = """Some text
    # This is the first header
    Other text 1"""
        self.assertEqual(convert_include(text, page_info), expected_conversion)

        # test with dedent
        text = """Some text
    <include>
{"path": "./data/convert_include_dummy.txt",
"start-after": "START header_1",
"end-before": "END header_1",
"dedent": 10}
</include>"""
        expected_conversion = """Some text
    the first header
     1"""
        self.assertEqual(convert_include(text, page_info), expected_conversion)

    def test_convert_literalinclude(self):
        path = Path(__file__).resolve()
        page_info = {"path": path}

        # canonical test:
        # <literalinclude>
        # {
        #     "path": "./data/convert_literalinclude_dummy.txt",
        #     "language": "python",
        #     "start-after": "START python_import",
        #     "end-before": "END python_import"
        # }
        # </literalinclude>

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
