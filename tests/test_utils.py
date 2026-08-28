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


import tempfile
import unittest
from pathlib import Path

import yaml

from doc_builder.utils import (
    is_doc_builder_repo,
    strip_html_from_markdown,
    sveltify_file_route,
    update_versions_file,
)


class UtilsTester(unittest.TestCase):
    def test_update_versions_file(self):
        repo_folder = Path(__file__).parent.parent
        # test canonical
        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(f"{tmp_dir}/_versions.yml", "w") as tmp_yml:
                versions = [{"version": "main"}, {"version": "v4.2.3"}, {"version": "v4.2.1"}]
                yaml.dump(versions, tmp_yml)
            update_versions_file(tmp_dir, "v4.2.2", repo_folder)
            with open(f"{tmp_dir}/_versions.yml") as tmp_yml:
                yml_str = tmp_yml.read()
                expected_yml = "- version: main\n- version: v4.2.3\n- version: v4.2.2\n- version: v4.2.1\n"
                self.assertEqual(yml_str, expected_yml)

        # test yml with main version only
        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(f"{tmp_dir}/_versions.yml", "w") as tmp_yml:
                versions = [{"version": "main"}]
                yaml.dump(versions, tmp_yml)
            update_versions_file(tmp_dir, "v4.2.2", repo_folder)
            with open(f"{tmp_dir}/_versions.yml") as tmp_yml:
                yml_str = tmp_yml.read()
                expected_yml = "- version: main\n- version: v4.2.2\n"
                self.assertEqual(yml_str, expected_yml)

        # test yml without main version
        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(f"{tmp_dir}/_versions.yml", "w") as tmp_yml:
                versions = [{"version": "v4.2.2"}]
                yaml.dump(versions, tmp_yml)

            self.assertRaises(ValueError, update_versions_file, tmp_dir, "v4.2.2", repo_folder)

        # test inserting duplicate version into yml
        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(f"{tmp_dir}/_versions.yml", "w") as tmp_yml:
                versions = [{"version": "main"}]
                yaml.dump(versions, tmp_yml)
            update_versions_file(tmp_dir, "v4.2.2", repo_folder)
            update_versions_file(tmp_dir, "v4.2.2", repo_folder)  # inserting duplicate version
            with open(f"{tmp_dir}/_versions.yml") as tmp_yml:
                yml_str = tmp_yml.read()
                expected_yml = "- version: main\n- version: v4.2.2\n"
                self.assertEqual(yml_str, expected_yml)

    def test_sveltify_file_route(self):
        mdx_file_path = "guide.mdx"
        svelte_file_path = sveltify_file_route(mdx_file_path)
        expected_path = "guide/+page.svelte"
        self.assertEqual(svelte_file_path, expected_path)

        mdx_file_path = "xyz/abc/guide.mdx"
        svelte_file_path = sveltify_file_route(mdx_file_path)
        expected_path = "xyz/abc/guide/+page.svelte"
        self.assertEqual(svelte_file_path, expected_path)

        mdx_file_path = "/xyz/abc/guide.mdx"
        svelte_file_path = sveltify_file_route(mdx_file_path)
        expected_path = "/xyz/abc/guide/+page.svelte"
        self.assertEqual(svelte_file_path, expected_path)

    def test_strip_html_preserves_angle_brackets_in_code(self):
        # Placeholders inside fenced code must survive (regression: <YOUR_TOKEN> was being stripped).
        content = (
            "Some prose.\n\n"
            "```python\n"
            "%env LOCATION eastus\n"
            "%env SUBSCRIPTION_ID <YOUR_SUBSCRIPTION_ID>\n"
            "%env RESOURCE_GROUP <YOUR_RESOURCE_GROUP>\n"
            "```\n"
        )
        result = strip_html_from_markdown(content)
        self.assertIn("<YOUR_SUBSCRIPTION_ID>", result)
        self.assertIn("<YOUR_RESOURCE_GROUP>", result)

    def test_strip_html_does_not_swallow_code_between_lt_and_gt(self):
        # A stray `<` in a code block (e.g. `if idx < n:`) must not eat content
        # up to the next `>` further down (regression that nuked entire snippets).
        content = (
            "Intro paragraph.\n\n"
            "```python\n"
            "for idx, ax in enumerate(axes):\n"
            "    if idx < n:\n"
            "        ax.imshow(pil_masks[idx])\n"
            "    else:\n"
            "        ax.imshow(np.zeros(mask_size))\n"
            "\n"
            "return np.array(mask_img) > 0\n"
            "```\n\n"
            "Trailing paragraph.\n"
        )
        result = strip_html_from_markdown(content)
        self.assertIn("if idx < n:", result)
        self.assertIn("ax.imshow(pil_masks[idx])", result)
        self.assertIn("return np.array(mask_img) > 0", result)
        self.assertIn("Trailing paragraph.", result)

    def test_strip_html_still_removes_real_tags(self):
        content = 'Before <Tip>warning</Tip> after.\n\n<div class="x">inside</div>\n'
        result = strip_html_from_markdown(content)
        self.assertNotIn("<Tip>", result)
        self.assertNotIn("</Tip>", result)
        self.assertNotIn("<div", result)
        self.assertIn("warning", result)
        self.assertIn("inside", result)

    def test_strip_html_from_markdown_docstring_component(self):
        # Regression: method names, anchors, signatures and the section labels were
        # dropped from the `.md` export because the old parser looked for the legacy
        # `<docstring>` markup instead of the `<Docstring ...>` props.
        content = (
            '<div class="docstring border-l-2">\n\n'
            '<Docstring name={"class huggingface_hub.HfApi"} anchor={"huggingface_hub.HfApi"} '
            'source={"https://github.com/huggingface/huggingface_hub/blob/main/src/huggingface_hub/hf_api.py#L2226"} '
            'parameters={[{"name": "endpoint", "val": ": str | None = None"}]}>\n'
            "<paramsdesc>- **endpoint** (`str`, *optional*) --\n"
            "  Endpoint of the Hub.</paramsdesc></Docstring>\n"
            "Client to interact with the Hugging Face Hub via HTTP.\n\n"
            '<div class="docstring border-l-2">\n\n'
            '<Docstring name={"merge_pull_request"} anchor={"huggingface_hub.HfApi.merge_pull_request"} '
            'parameters={[{"name": "repo_id", "val": ": str"}, {"name": "discussion_num", "val": ": int"}]}>\n'
            "<paramsdesc>- **repo_id** (`str`) --\n"
            "  A namespace and a repo name separated\n"
            "  by a `/`.\n"
            "- **discussion_num** (`int`) --\n"
            "  The number of the Pull Request.</paramsdesc>"
            "<rettype>[DiscussionStatusChange](https://hf.co/docs#DiscussionStatusChange)</rettype>"
            "<retdesc>the status change event</retdesc></Docstring>\n"
            "Merges a Pull Request.\n\n"
            "</div></div>\n"
        )
        result = strip_html_from_markdown(content)

        # Class: heading with anchor, signature and parameters
        self.assertIn("#### huggingface_hub.HfApi[[huggingface_hub.HfApi]]", result)
        self.assertIn("huggingface_hub.HfApi(endpoint: str | None = None)", result)
        self.assertIn(
            "[Source](https://github.com/huggingface/huggingface_hub/blob/main/src/huggingface_hub/hf_api.py#L2226)",
            result,
        )
        # Method: heading with anchor, signature, and both section labels
        self.assertIn("#### merge_pull_request[[huggingface_hub.HfApi.merge_pull_request]]", result)
        self.assertIn("merge_pull_request(repo_id: str, discussion_num: int)", result)
        self.assertEqual(result.count("**Parameters:**"), 2)
        # A resolved doc link as return type keeps its markdown (no backtick wrapping)
        self.assertIn("**Returns:** [DiscussionStatusChange](https://hf.co/docs#DiscussionStatusChange)", result)
        # The description must not be glued to the last section of the docstring block
        self.assertIn("the status change event\n\nMerges a Pull Request.", result)
        # No leftover component markup
        self.assertNotIn("<Docstring", result)
        self.assertNotIn("paramsdesc", result)

    def test_strip_html_from_markdown_docstring_getset_descriptor(self):
        # Properties have no parameters and no anchor: heading only, no empty signature.
        content = (
            '<div class="docstring border-l-2">\n\n'
            '<Docstring name={"content"} anchor={"None"} parameters={[]} isGetSetDescriptor={true}>\n'
            "</Docstring>\n"
            "Get the content of this `AddedToken`\n\n"
            "</div>\n"
        )
        result = strip_html_from_markdown(content)
        self.assertIn("#### content", result)
        self.assertNotIn("[[None]]", result)
        self.assertNotIn("content()", result)
        self.assertIn("Get the content of this `AddedToken`", result)

        # ... whereas a parameterless method keeps its (empty) signature
        content = '<Docstring name={"dummy.reset"} anchor={"dummy.reset"} parameters={[]}>\n</Docstring>\nResets it.\n'
        self.assertIn("dummy.reset()", strip_html_from_markdown(content))

    def test_strip_html_from_markdown_docstring_props_with_angle_brackets(self):
        # `>` inside the props JSON must not truncate the opening tag.
        content = (
            '<Docstring name={"dummy.func"} anchor={"dummy.func"} '
            'parameters={[{"name": "cb", "val": ": Callable[[int], int] = <factory>"}]}>\n'
            "<rettype>`int`</rettype></Docstring>\n"
            "Does something.\n"
        )
        result = strip_html_from_markdown(content)
        self.assertIn("#### dummy.func[[dummy.func]]", result)
        self.assertIn("dummy.func(cb: Callable[[int], int] = <factory>)", result)
        self.assertIn("**Returns:** `int`", result)
        self.assertIn("Does something.", result)

    def test_is_doc_builder_repo(self):
        # the actual repo, which `locate_kit_folder` relies on to find the `kit` folder
        self.assertTrue(is_doc_builder_repo(Path(__file__).parent.parent))

        with tempfile.TemporaryDirectory() as tmp_dir:
            # no pyproject.toml at all
            self.assertFalse(is_doc_builder_repo(tmp_dir))

            # a pyproject.toml belonging to another project
            (Path(tmp_dir) / "pyproject.toml").write_text('[project]\nname = "something-else"\n', encoding="utf-8")
            self.assertFalse(is_doc_builder_repo(tmp_dir))

            # the name is matched regardless of quoting and spacing
            for line in ('name = "hf-doc-builder"', "name='hf-doc-builder'", "name=  'hf-doc-builder'"):
                (Path(tmp_dir) / "pyproject.toml").write_text(f"[project]\n{line}\n", encoding="utf-8")
                self.assertTrue(is_doc_builder_repo(tmp_dir), line)
