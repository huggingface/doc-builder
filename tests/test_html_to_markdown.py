# Copyright 2026 The HuggingFace Team. All rights reserved.
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

from doc_builder.html_to_markdown import html_to_markdown


class TabsTester(unittest.TestCase):
    def test_hfoptions_keep_their_labels(self):
        # Regression: the `>` inside the id cut the tag short, leaving `= 2.10 only)">` on the page, and
        # nothing said which command belonged to which tab.
        content = (
            "Create a virtual environment:\n\n"
            '<hfoptions id="create_venv">\n'
            '<hfoption id="conda">\n'
            "```bash\nconda create -y -n lerobot python=3.12\n```\n"
            "</hfoption>\n"
            '<hfoption id="uv (PyTorch >= 2.10 only)">\n'
            "```bash\nuv venv --python 3.12\n```\n"
            "</hfoption>\n"
            "</hfoptions>\n\n"
            "Then activate it.\n"
        )
        self.assertEqual(
            html_to_markdown(content),
            "Create a virtual environment:\n\n"
            "**Option: conda**\n\n"
            "```bash\nconda create -y -n lerobot python=3.12\n```\n\n"
            "**Option: uv (PyTorch >= 2.10 only)**\n\n"
            "```bash\nuv venv --python 3.12\n```\n\n"
            "Then activate it.\n",
        )

    def test_hfoption_content_is_dedented_markdown(self):
        content = (
            "<hfoptions id='os'>\n<hfoption id='Linux'>\n\n"
            "    Install it with:\n\n    - apt\n    - snap\n\n"
            "</hfoption>\n</hfoptions>\n"
        )
        self.assertEqual(html_to_markdown(content), "**Option: Linux**\n\nInstall it with:\n\n- apt\n- snap\n")

    def test_frameworkcontent_keeps_framework_labels(self):
        content = "<frameworkcontent>\n<pt>\nPyTorch way.\n</pt>\n<tf>\nTensorFlow way.\n</tf>\n</frameworkcontent>\n"
        self.assertEqual(
            html_to_markdown(content),
            "**Option: PyTorch**\n\nPyTorch way.\n\n**Option: TensorFlow**\n\nTensorFlow way.\n",
        )


class HtmlBlocksTester(unittest.TestCase):
    def test_cards_keep_their_links(self):
        # Regression: the cards of a landing page became plain text, without their URLs, and their
        # indented lines turned into code blocks.
        content = (
            '<div class="grid grid-cols-1 md:grid-cols-3 gap-4 my-6">\n'
            '  <div class="border rounded-lg p-4 shadow">\n'
            '    <div class="text-lg font-semibold mb-2">🔧 I have a robot</div>\n'
            '    <p class="text-sm">\n'
            "      LeRobot supports a wide range of arms. Popular picks:\n"
            "    </p>\n"
            '    <ul class="list-disc pl-5">\n'
            "      <li>\n"
            '        <a href="./so101">SO-101</a> - our flagship, low-cost arm\n'
            "      </li>\n"
            '      <li><a href="./lekiwi">LeKiwi</a> - a mobile base</li>\n'
            "    </ul>\n"
            "  </div>\n"
            "  <a\n"
            '    class="!no-underline border rounded-lg p-4"\n'
            '    href="./cheat-sheet"\n'
            "  >\n"
            '    <div class="font-semibold mb-1">📋 Cheat Sheet</div>\n'
            "    <p>Every LeRobot CLI command, copy-paste ready.</p>\n"
            "  </a>\n"
            "</div>\n"
        )
        self.assertEqual(
            html_to_markdown(content),
            "🔧 I have a robot\n\n"
            "LeRobot supports a wide range of arms. Popular picks:\n\n"
            "- [SO-101](./so101) - our flagship, low-cost arm\n"
            "- [LeKiwi](./lekiwi) - a mobile base\n\n"
            "[📋 Cheat Sheet](./cheat-sheet)\n\n"
            "Every LeRobot CLI command, copy-paste ready.\n",
        )

    def test_table(self):
        content = (
            "Intro.\n"
            '<table width="100%">\n'
            '  <colgroup><col width="30%" /></colgroup>\n'
            "  <thead><tr><th>Project</th><th>Description</th></tr></thead>\n"
            "  <tbody>\n"
            "    <tr>\n"
            '      <td><a href="https://github.com/a/b">b</a> ⚠️</td>\n'
            "      <td>Uses <code>x | y</code>,<br />and more.</td>\n"
            "    </tr>\n"
            "  </tbody>\n"
            "</table>\n"
            "After.\n"
        )
        self.assertEqual(
            html_to_markdown(content),
            "Intro.\n\n"
            "| Project | Description |\n"
            "| --- | --- |\n"
            "| [b](https://github.com/a/b) ⚠️ | Uses `x \\| y`, and more. |\n\n"
            "After.\n",
        )

    def test_images_links_and_media(self):
        content = (
            '<div align="center">\n'
            '  <a href="https://discord.gg/x"><img alt="Discord" src="https://img.shields.io/discord.svg"></a>\n'
            "  <img\n"
            '    src="https://example.com/a b.png"\n'
            '    style="height:300px;"\n'
            "  />\n"
            '  <img class="hidden dark:block" src="https://example.com/dark.png" alt="dark copy"/>\n'
            "</div>\n\n"
            '<video controls><source src="https://example.com/v.mp4" type="video/mp4" /></video>\n'
        )
        self.assertEqual(
            html_to_markdown(content),
            "[![Discord](https://img.shields.io/discord.svg)](https://discord.gg/x) ![](https://example.com/a%20b.png)"
            "\n\n[Video](https://example.com/v.mp4)\n",
        )

    def test_links_side_by_side_become_a_list(self):
        content = (
            '<div class="group">\n<div class="font-semibold">Repositories</div>\n'
            '<a class="hover:x" href="./getting-started">Getting Started</a>\n'
            '<a class="hover:x" href="./settings">Settings</a>\n</div>\n'
        )
        self.assertEqual(
            html_to_markdown(content),
            "Repositories\n\n- [Getting Started](./getting-started)\n- [Settings](./settings)\n",
        )

    def test_details_and_markdown_between_html_lines(self):
        content = (
            "<details>\n<summary><strong>Troubleshooting</strong></summary>\n\n"
            "## The camera is black\n\n"
            "- Check the cable\n- Restart\n\n"
            "</details>\n"
        )
        self.assertEqual(
            html_to_markdown(content),
            "**Troubleshooting**\n\n## The camera is black\n\n- Check the cable\n- Restart\n",
        )

    def test_markdown_after_an_html_line(self):
        # the HTML block ends with its last element: the Markdown that follows stays Markdown
        content = '<img src="a.png" alt="A">\n## Heading\n\n- item\n'
        self.assertEqual(html_to_markdown(content), "![A](a.png)\n## Heading\n\n- item\n")

    def test_entities(self):
        content = "<p>Use the &lt;img&gt; tag &amp; the&nbsp;alt attribute.</p>\n"
        self.assertEqual(html_to_markdown(content), "Use the &lt;img&gt; tag & the alt attribute.\n")


class InlineAndCodeTester(unittest.TestCase):
    def test_inline_html_in_markdown(self):
        content = (
            '> This is part of the <a href="https://hf.co/enterprise" target="_blank">Team & Enterprise</a> plans.\n\n'
            "Press <kbd>Ctrl</kbd>+<kbd>C</kbd>, it's <strong>fast</strong>.\n\n"
            "| a | b |\n| --- | --- |\n| one<br>two | x |\n"
        )
        self.assertEqual(
            html_to_markdown(content),
            "> This is part of the [Team & Enterprise](https://hf.co/enterprise) plans.\n\n"
            "Press `Ctrl`+`C`, it's **fast**.\n\n"
            "| a | b |\n| --- | --- |\n| one two | x |\n",
        )

    def test_code_and_placeholders_are_kept(self):
        content = (
            "Replace <user>/<repo>, see <https://hf.co/docs>, and set `<YOUR_TOKEN>` (a `--sim.task=<task>\n"
            "--docker=true` flag).\n\n"
            "```html\n<div class='x'>\n  <a href='y'>z</a>\n\n\n</div>\n```\n"
        )
        self.assertEqual(html_to_markdown(content), content)

    def test_tips_become_callouts(self):
        content = (
            "<Tip>\n  Run it locally:\n\n  ```bash\n  lerobot-eval\n  ```\n</Tip>\n\n"
            "<Tip warning={true}>\n\nInstalling it **replaces** LIBERO.\n\n</Tip>\n"
        )
        self.assertEqual(
            html_to_markdown(content),
            "> [!TIP]\n> Run it locally:\n>\n> ```bash\n> lerobot-eval\n> ```\n\n"
            "> [!WARNING]\n> Installing it **replaces** LIBERO.\n",
        )

    def test_components_are_removed(self):
        content = (
            '<EditOnGithub source="https://github.com/x"/>\n\n'
            '<ExampleCodeBlock anchor="x">\n\n```py\nprint(1)\n```\n\n</ExampleCodeBlock>\n'
        )
        self.assertEqual(html_to_markdown(content), "```py\nprint(1)\n```\n")


if __name__ == "__main__":
    unittest.main()
