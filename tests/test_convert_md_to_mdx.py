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


import contextlib
import io
import unittest
from pathlib import Path

from doc_builder.convert_md_to_mdx import (
    clean_runnable_blocks,
    convert_img_links,
    convert_include,
    convert_literalinclude,
    convert_md_to_mdx,
    escape_img_alt_description,
    process_md,
    strip_md_extension_from_internal_links,
)


class ConvertMdToMdxTester(unittest.TestCase):
    def test_convert_md_to_mdx(self):
        page_info = {"package_name": "transformers", "version": "v4.10.0", "language": "fr"}
        md_text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit"
        expected_conversion = """<script lang="ts">
import {onMount} from "svelte";
import Tip from "$lib/Tip.svelte";
import CopyLLMTxtMenu from "$lib/CopyLLMTxtMenu.svelte";
import Youtube from "$lib/Youtube.svelte";
import Docstring from "$lib/Docstring.svelte";
import CodeBlock from "$lib/CodeBlock.svelte";
import CodeBlockFw from "$lib/CodeBlockFw.svelte";
import DocNotebookDropdown from "$lib/DocNotebookDropdown.svelte";
import CourseFloatingBanner from "$lib/CourseFloatingBanner.svelte";
import IconCopyLink from "$lib/IconCopyLink.svelte";
import IconInfo from "$lib/IconInfo.svelte";
import IconLightbulb from "$lib/IconLightbulb.svelte";
import IconMessageSquareWarning from "$lib/IconMessageSquareWarning.svelte";
import IconTriangleAlert from "$lib/IconTriangleAlert.svelte";
import IconOctagonAlert from "$lib/IconOctagonAlert.svelte";
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
import InferenceSnippet from "$lib/InferenceSnippet/InferenceSnippet.svelte";
import MermaidChart from "$lib/MermaidChart.svelte";
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

    def test_add_copy_menu_when_existing_float_right_block(self):
        page_info = {"package_name": "transformers", "version": "main", "language": "en"}
        md_text = """<div style="float: right;">\n existing block\n</div>\n\n# Heading"""
        result = convert_md_to_mdx(md_text, page_info)
        expected_body = """<CopyLLMTxtMenu containerStyle="float: right; margin-left: 10px; display: inline-flex; position: relative; z-index: 10;"></CopyLLMTxtMenu>

<div style="float: right;">
 existing block
</div>

# Heading"""
        self.assertIn(expected_body, result)

    def test_add_copy_menu_skips_when_already_present(self):
        page_info = {"package_name": "transformers", "version": "main", "language": "en"}
        md_text = """<CopyLLMTxtMenu containerStyle="float: right; margin-left: 10px; display: inline-flex; position: relative; z-index: 10;"></CopyLLMTxtMenu>\n\n# Heading"""
        result = convert_md_to_mdx(md_text, page_info)
        self.assertEqual(result.count("<CopyLLMTxtMenu"), 1)

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

    def test_strip_md_extension_from_internal_links(self):
        # Test relative links with .md extension
        text = "[Overview](./overview.md)"
        expected = "[Overview](./overview)"
        self.assertEqual(strip_md_extension_from_internal_links(text), expected)

        # Test relative links with parent directory
        text = "[Section](../other/section.md)"
        expected = "[Section](../other/section)"
        self.assertEqual(strip_md_extension_from_internal_links(text), expected)

        # Test links without extension (should remain unchanged)
        text = "[Overview](./overview)"
        expected = "[Overview](./overview)"
        self.assertEqual(strip_md_extension_from_internal_links(text), expected)

        # Test external links (should remain unchanged)
        text = "[HuggingFace](https://huggingface.co)"
        expected = "[HuggingFace](https://huggingface.co)"
        self.assertEqual(strip_md_extension_from_internal_links(text), expected)

        # Test anchor-only links (should remain unchanged)
        text = "[Section](#section)"
        expected = "[Section](#section)"
        self.assertEqual(strip_md_extension_from_internal_links(text), expected)

        # Test links with anchors
        text = "[Overview](./overview.md#section)"
        expected = "[Overview](./overview#section)"
        self.assertEqual(strip_md_extension_from_internal_links(text), expected)

        # Test links with query parameters
        text = "[Overview](./overview.md?param=value)"
        expected = "[Overview](./overview?param=value)"
        self.assertEqual(strip_md_extension_from_internal_links(text), expected)

        # Test absolute paths (should remain unchanged)
        text = "[Docs](/docs/transformers/main)"
        expected = "[Docs](/docs/transformers/main)"
        self.assertEqual(strip_md_extension_from_internal_links(text), expected)

        # Test multiple links in same text
        text = "Check [Overview](./overview.md) and [Guide](./guide.md#intro) for more info."
        expected = "Check [Overview](./overview) and [Guide](./guide#intro) for more info."
        self.assertEqual(strip_md_extension_from_internal_links(text), expected)

        # Test mixed internal and external links
        text = "See [Local](./local.md) and [External](https://example.com/page.md)"
        expected = "See [Local](./local) and [External](https://example.com/page.md)"
        self.assertEqual(strip_md_extension_from_internal_links(text), expected)

    def test_clean_runnable_blocks_strips_annotation(self):
        text = """```py runnable:test_clean
from transformers import pipeline
pipe = pipeline("sentiment-analysis")
print(pipe("I love this!"))
```"""
        expected = """```py
from transformers import pipeline
pipe = pipeline("sentiment-analysis")
print(pipe("I love this!"))
```"""
        self.assertEqual(clean_runnable_blocks(text), expected)

    def test_clean_runnable_blocks_python_fence(self):
        text = """```python runnable:test_python
x = 1
print(x)
```"""
        expected = """```python
x = 1
print(x)
```"""
        self.assertEqual(clean_runnable_blocks(text), expected)

    def test_clean_runnable_blocks_warns_on_bare_assert(self):
        text = """```py runnable:test_warn
x = 1
assert x == 1
print(x)
```"""
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = clean_runnable_blocks(
                text, page_info={"path": Path("docs/source/en/example.md"), "emit_warning": True}
            )

        self.assertIn("assert x == 1", result)
        warning = stderr.getvalue()
        self.assertIn("Bare assert found in runnable:test_warn", warning)
        self.assertIn("ignore-bare-assert", warning)
        self.assertRegex(warning, r"docs[\\/]source[\\/]en[\\/]example\.md(?::3|,line=3)")

    def test_clean_runnable_blocks_does_not_warn_by_default(self):
        text = """```py runnable:test_warn_default
x = 1
assert x == 1
print(x)
```"""
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = clean_runnable_blocks(text, page_info={"path": Path("docs/source/en/example.md")})

        self.assertIn("assert x == 1", result)
        self.assertEqual(stderr.getvalue(), "")

    def test_clean_runnable_blocks_can_silence_assert_warning(self):
        text = """```py runnable:test_silence
x = 1
assert x == 1  # doc-builder: ignore-bare-assert
print(x)
```"""
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = clean_runnable_blocks(
                text, page_info={"path": Path("docs/source/en/example.md"), "emit_warning": True}
            )

        self.assertIn("assert x == 1", result)
        self.assertNotIn("ignore-bare-assert", result)
        self.assertEqual(stderr.getvalue(), "")

    def test_clean_runnable_blocks_hide_assert_is_removed_without_warning(self):
        text = """```py runnable:test_hide_assert
x = 1
assert x == 1  # doc-builder: hide
print(x)
```"""
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = clean_runnable_blocks(
                text, page_info={"path": Path("docs/source/en/example.md"), "emit_warning": True}
            )

        self.assertNotIn("assert x == 1", result)
        self.assertEqual(stderr.getvalue(), "")

    def test_clean_runnable_blocks_leaves_normal_blocks(self):
        text = """```py
x = 1  # doc-builder: hide
print(x)
```"""
        # Normal blocks without runnable: should be untouched
        self.assertEqual(clean_runnable_blocks(text), text)

    def test_clean_runnable_blocks_backticks_in_string(self):
        """Triple backticks inside a string literal should not close the block early."""
        text = '''```py runnable:test_backticks
x = """```
not a fence
```"""
print(x)
```'''
        expected = '''```py
x = """```
not a fence
```"""
print(x)
```'''
        self.assertEqual(clean_runnable_blocks(text), expected)

    def test_clean_runnable_blocks_hide_single_line(self):
        """A line marked with # doc-builder: hide is removed."""
        text = """```py runnable:test_hide
from transformers import pipeline
pipe = pipeline("sentiment-analysis")
result = pipe("test")  # doc-builder: hide
print(pipe("I love this!"))
```"""
        expected = """```py
from transformers import pipeline
pipe = pipeline("sentiment-analysis")
print(pipe("I love this!"))
```"""
        self.assertEqual(clean_runnable_blocks(text), expected)

    def test_clean_runnable_blocks_hide_multiline_parens(self):
        """A multi-line statement marked with # doc-builder: hide is fully removed."""
        text = """```py runnable:test_hide_multi
result = compute()

EXPECTED_OUTPUT = (  # doc-builder: hide
    "first value"
    + "second value"
)

print(result)
```"""
        expected = """```py
result = compute()

print(result)
```"""
        self.assertEqual(clean_runnable_blocks(text), expected)

    def test_clean_runnable_blocks_hide_multiline_brackets(self):
        """Multi-line list with # doc-builder: hide tracked via bracket depth."""
        text = """```py runnable:test_hide_brackets
x = do_work()
expected = [  # doc-builder: hide
    1,
    2,
    3,
]
print(x)
```"""
        expected = """```py
x = do_work()
print(x)
```"""
        self.assertEqual(clean_runnable_blocks(text), expected)

    def test_clean_runnable_blocks_hide_for_loop(self):
        """A for-loop marked with # doc-builder: hide is removed with its body."""
        text = """```py runnable:test_hide_for
inputs = prepare()

for key in inputs:  # doc-builder: hide
    do_something(inputs[key])

outputs = model.generate(**inputs)
```"""
        expected = """```py
inputs = prepare()

outputs = model.generate(**inputs)
```"""
        self.assertEqual(clean_runnable_blocks(text), expected)

    def test_clean_runnable_blocks_hide_collapses_blank_lines(self):
        text = """```py runnable:test_blanks
x = 1

y = 2  # doc-builder: hide

z = 3
```"""
        expected = """```py
x = 1

z = 3
```"""
        self.assertEqual(clean_runnable_blocks(text), expected)

    def test_clean_runnable_blocks_glmasr_batched(self):
        """Real-world test from huggingface/transformers PR #44277 - test_batched block with # doc-builder: hide."""
        text = """```py runnable:test_batched
import torch
from transformers import AutoProcessor, GlmAsrForConditionalGeneration

checkpoint_name = "zai-org/GLM-ASR-Nano-2512"
processor = AutoProcessor.from_pretrained(checkpoint_name)

conversation = [
    [
        {
            "role": "user",
            "content": [
                {
                    "type": "audio",
                    "url": "https://huggingface.co/datasets/eustlb/audio-samples/resolve/main/bcn_weather.mp3",
                },
                {"type": "text", "text": "Please transcribe this audio into text"},
            ],
        },
    ],
    [
        {
            "role": "user",
            "content": [
                {
                    "type": "audio",
                    "url": "https://huggingface.co/datasets/eustlb/audio-samples/resolve/main/obama2.mp3",
                },
                {"type": "text", "text": "Please transcribe this audio into text"},
            ],
        },
    ],
]

model = GlmAsrForConditionalGeneration.from_pretrained(checkpoint_name, device_map="auto", dtype="auto")

inputs = processor.apply_chat_template(
    conversation, tokenize=True, add_generation_prompt=True, return_dict=True
).to(model.device, dtype=model.dtype)

inputs_transcription = processor.apply_transcription_request(  # doc-builder: hide
    [
        "https://huggingface.co/datasets/eustlb/audio-samples/resolve/main/bcn_weather.mp3",
        "https://huggingface.co/datasets/eustlb/audio-samples/resolve/main/obama2.mp3",
    ],
).to(model.device, dtype=model.dtype)

for key in inputs:  # doc-builder: hide
    assert torch.equal(inputs[key], inputs_transcription[key])

outputs = model.generate(**inputs, do_sample=False, max_new_tokens=500)

decoded_outputs = processor.batch_decode(
    outputs[:, inputs.input_ids.shape[1] :], skip_special_tokens=True
)

EXPECTED_OUTPUT = [  # doc-builder: hide
    "Yesterday it was thirty five degrees in Barcelona, but today the temperature will go down to minus twenty degrees.",
    "This week, I traveled to Chicago to deliver my final farewell address to the nation.",
]
assert decoded_outputs == EXPECTED_OUTPUT  # doc-builder: hide
```"""
        expected = """```py
import torch
from transformers import AutoProcessor, GlmAsrForConditionalGeneration

checkpoint_name = "zai-org/GLM-ASR-Nano-2512"
processor = AutoProcessor.from_pretrained(checkpoint_name)

conversation = [
    [
        {
            "role": "user",
            "content": [
                {
                    "type": "audio",
                    "url": "https://huggingface.co/datasets/eustlb/audio-samples/resolve/main/bcn_weather.mp3",
                },
                {"type": "text", "text": "Please transcribe this audio into text"},
            ],
        },
    ],
    [
        {
            "role": "user",
            "content": [
                {
                    "type": "audio",
                    "url": "https://huggingface.co/datasets/eustlb/audio-samples/resolve/main/obama2.mp3",
                },
                {"type": "text", "text": "Please transcribe this audio into text"},
            ],
        },
    ],
]

model = GlmAsrForConditionalGeneration.from_pretrained(checkpoint_name, device_map="auto", dtype="auto")

inputs = processor.apply_chat_template(
    conversation, tokenize=True, add_generation_prompt=True, return_dict=True
).to(model.device, dtype=model.dtype)

outputs = model.generate(**inputs, do_sample=False, max_new_tokens=500)

decoded_outputs = processor.batch_decode(
    outputs[:, inputs.input_ids.shape[1] :], skip_special_tokens=True
)
```"""
        self.assertEqual(clean_runnable_blocks(text), expected)

    def test_clean_runnable_blocks_glmasr_basic(self):
        """Real-world test from huggingface/transformers PR #44277 — test_basic block (no asserts)."""
        text = """```py runnable:test_basic
from transformers import AutoModelForSeq2SeqLM, AutoProcessor

processor = AutoProcessor.from_pretrained("zai-org/GLM-ASR-Nano-2512")
model = AutoModelForSeq2SeqLM.from_pretrained("zai-org/GLM-ASR-Nano-2512", device_map="auto", dtype="auto")

inputs = processor.apply_transcription_request(
    "https://huggingface.co/datasets/hf-internal-testing/dummy-audio-samples/resolve/main/bcn_weather.mp3"
)

inputs = inputs.to(model.device, dtype=model.dtype)
outputs = model.generate(**inputs, do_sample=False, max_new_tokens=500)

decoded_outputs = processor.batch_decode(outputs[:, inputs.input_ids.shape[1] :], skip_special_tokens=True)
print(decoded_outputs)
```"""
        expected = """```py
from transformers import AutoModelForSeq2SeqLM, AutoProcessor

processor = AutoProcessor.from_pretrained("zai-org/GLM-ASR-Nano-2512")
model = AutoModelForSeq2SeqLM.from_pretrained("zai-org/GLM-ASR-Nano-2512", device_map="auto", dtype="auto")

inputs = processor.apply_transcription_request(
    "https://huggingface.co/datasets/hf-internal-testing/dummy-audio-samples/resolve/main/bcn_weather.mp3"
)

inputs = inputs.to(model.device, dtype=model.dtype)
outputs = model.generate(**inputs, do_sample=False, max_new_tokens=500)

decoded_outputs = processor.batch_decode(outputs[:, inputs.input_ids.shape[1] :], skip_special_tokens=True)
print(decoded_outputs)
```"""
        self.assertEqual(clean_runnable_blocks(text), expected)
