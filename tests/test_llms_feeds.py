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

import tempfile
import unittest
from pathlib import Path

import yaml

from doc_builder.translate_docs import llms_pages
from doc_builder.utils import markdown_page_description, markdown_page_title, write_llms_feeds

BASE = "https://huggingface.co/docs/lerobot/main"

TOCTREE = [
    {
        "title": "Get started",
        "sections": [
            {"local": "index", "title": "LeRobot"},
            {"local": "installation", "title": "Installation"},
        ],
    },
    {
        "title": "Policies",
        "sections": [
            {"local": "act", "title": "ACT"},
            {
                "local": "vla/index",
                "title": "VLAs [beta]",
                "sections": [{"local": "vla/pi0", "title": "π₀ (Pi0)"}],
            },
            {"local": "evo1", "title": "EVO1"},
        ],
    },
    {"local": "act", "title": "ACT again"},
    {
        "title": "API",
        "sections": [{"title": "Main classes", "sections": [{"local": "api/robots", "title": "Robots"}]}],
    },
]

PAGES = {
    "index.md": "# LeRobot\n\n![logo](logo.png)\n\n**Machine learning for real-world robotics**\n\nMore.",
    "installation.md": "# Installation\n\n> [!TIP]\n> Use conda.\n\nThis guide uses conda (e.g. miniforge). Then...",
    "act.md": "# ACT (Action Chunking with Transformers)\n\nACT is a lightweight policy. It is fast.",
    "vla/index.md": "# VLAs\n\n[Paper](https://arxiv.org) · [Code](https://github.com)\n\nVision-language-action models.",
    "vla/pi0.md": "# π₀\n\n```python\n# not a title\n```\n\nπ₀ is a VLA from Physical Intelligence.",
    "evo1.md": "# EVO1\n\nEVO1 is a VLA policy.",
    "api/robots.md": "# Robots\n\nEvery robot implements the `Robot` interface: connect, read, act.",
    "policy_evo1_README.md": "# EVO1\n\nThe EVO1 integration.",
    "policy_act_README.md": "## Paper\n\nhttps://tonyzhaozh.github.io/aloha\n\n## Citation\n\n```bibtex\n@article{x}\n```",
}


class LlmsFeedsTester(unittest.TestCase):
    def write(self, toctree=TOCTREE, pages=PAGES):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        output_dir = Path(tmp.name) / "lerobot" / "main" / "en"
        output_dir.mkdir(parents=True)
        if toctree is not None:
            (output_dir / "_toctree.yml").write_text(yaml.safe_dump(toctree, allow_unicode=True), encoding="utf-8")
        written = write_llms_feeds(output_dir, list(pages.items()), package_name="lerobot", version="main")
        return output_dir, written

    def test_llms_txt_follows_the_table_of_contents(self):
        output_dir, written = self.write()
        llms = (output_dir / "llms.txt").read_text(encoding="utf-8")
        sections = {
            "get-started": "Get started",
            "policies": "Policies",
            "api": "API",
            "optional": "Optional",
        }
        self.assertEqual(written, ["llms.txt", "llms-full.txt"] + [f"llms-full/{slug}.txt" for slug in sections])
        header, index = llms.split("\n## Get started\n")
        self.assertTrue(header.startswith("# LeRobot\n\n> Machine learning for real-world robotics\n"))
        for slug, title in sections.items():
            self.assertRegex(header, rf"- \[{title}\]\({BASE}/llms-full/{slug}\.txt\): \d pages?, \d+ KB")
        self.assertEqual(
            index.strip().split("\n"),
            [
                f"- [LeRobot]({BASE}/index.md): Machine learning for real-world robotics",
                # callouts and abbreviations are not where a description stops
                f"- [Installation]({BASE}/installation.md): This guide uses conda (e.g. miniforge).",
                "",
                "## Policies",
                "",
                # sidebar titles; a page listed twice is listed once
                f"- [ACT]({BASE}/act.md): ACT is a lightweight policy.",
                f"- [EVO1]({BASE}/evo1.md): EVO1 is a VLA policy.",
                "",
                "### VLAs [beta]",
                "",
                # a group's own page comes first; a line of links isn't a description
                f"- [VLAs \\[beta\\]]({BASE}/vla/index.md): Vision-language-action models.",
                f"- [π₀ (Pi0)]({BASE}/vla/pi0.md): π₀ is a VLA from Physical Intelligence.",
                "",
                "## API",
                "",
                "### Main classes",
                "",
                f"- [Robots]({BASE}/api/robots.md): Every robot implements the `Robot` interface: connect, read, act.",
                "",
                "## Optional",
                "",
                # pages outside the sidebar: their H1 (never a `##`), told apart from a listed page of the same name
                f"- [Policy act README]({BASE}/policy_act_README.md)",
                f"- [EVO1 (policy_evo1_README)]({BASE}/policy_evo1_README.md): The EVO1 integration.",
            ],
        )

    def test_full_text(self):
        output_dir, _ = self.write()
        llms = (output_dir / "llms.txt").read_text(encoding="utf-8")
        full = (output_dir / "llms-full.txt").read_text(encoding="utf-8")
        self.assertTrue(full.startswith(llms.rstrip("\n")))
        self.assertIn(f"### ACT\n{BASE}/act.md\n\n# ACT (Action Chunking with Transformers)\n", full)
        self.assertLess(full.index("vla/pi0.md\n\n"), full.index("api/robots.md\n\n"))

        policies = (output_dir / "llms-full" / "policies.txt").read_text(encoding="utf-8")
        self.assertTrue(policies.startswith(f"# LeRobot: Policies\n\n## Policies\n\n- [ACT]({BASE}/act.md)"))
        self.assertIn("EVO1 is a VLA policy.", policies)
        self.assertNotIn("Every robot implements", policies)

    def test_without_table_of_contents(self):
        output_dir, written = self.write(toctree=None, pages={"b.md": "# B\n\nBee.", "a.md": "# A\n\nAy."})
        self.assertEqual(written, ["llms.txt", "llms-full.txt", "llms-full/docs.txt"])
        llms = (output_dir / "llms.txt").read_text(encoding="utf-8")
        self.assertIn(f"## Docs\n\n- [B]({BASE}/b.md): Bee.\n- [A]({BASE}/a.md): Ay.\n", llms)

    def test_translated_llms_txt_is_parsed(self):
        # the translation job reads the English llms.txt back: the pages it lists, in order
        output_dir, _ = self.write()
        llms = (output_dir / "llms.txt").read_text(encoding="utf-8")
        order, base = llms_pages(llms, list(PAGES))
        self.assertEqual(base, BASE)
        self.assertEqual(order[:4], ["index.md", "installation.md", "act.md", "evo1.md"])
        self.assertEqual(set(order), set(PAGES))


class PageTitleAndDescriptionTester(unittest.TestCase):
    def test_title(self):
        self.assertEqual(markdown_page_title("# Robots[[robots]]\n\nText"), "Robots")
        self.assertEqual(markdown_page_title("```py\n# comment\n```\n\n# **Real** title"), "Real title")
        self.assertIsNone(markdown_page_title("## Paper\n\nhttps://example.com"))

    def test_description(self):
        self.assertEqual(markdown_page_description("# T\n\n- a list\n\n| a | b |\n\nFinally. More."), "Finally.")
        self.assertEqual(markdown_page_description("# T\n\n**Option: conda**\n\nUse [conda](x)."), "Use conda.")
        self.assertEqual(markdown_page_description("# 标题\n\n这是第一句。这是第二句。"), "这是第一句。")
        self.assertEqual(markdown_page_description("# T\n\nhttps://example.com\n"), "")
        long = markdown_page_description("# T\n\n" + "word " * 100)
        self.assertTrue(long.endswith("…") and len(long) <= 201)


if __name__ == "__main__":
    unittest.main()
