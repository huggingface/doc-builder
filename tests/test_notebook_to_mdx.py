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

from doc_builder.commands.notebook_to_mdx import notebook_to_mdx, text_output_to_pre


class NotebookToMdxTester(unittest.TestCase):
    def test_text_output_to_pre_escapes_tag_like_text(self):
        # Tag-like text in an output (CLI help placeholders, object reprs) must be escaped,
        # otherwise it reaches the Svelte compiler as raw markup and fails the doc build.
        result = text_output_to_pre("--model-id <MODEL_ID>\nSee <https://hf.co/models>")
        self.assertEqual(result, "<pre>\n--model-id &lt;MODEL_ID&gt;\nSee &lt;https://hf.co/models&gt;\n</pre>")

        result = text_output_to_pre("<transformers.trainer.Trainer object at 0x7f0000000000>")
        self.assertNotIn("<transformers", result)
        self.assertIn("&lt;transformers.trainer.Trainer object at 0x7f0000000000&gt;", result)

    def test_text_output_to_pre_strips_ansi_sequences(self):
        # Color codes and cursor-control sequences (as emitted by CLI tools and progress bars).
        result = text_output_to_pre("\x1b[1m\x1b[4mOptions:\x1b[0m\n\x1b[?25l⠋ loading\x1b[?25h done")
        self.assertEqual(result, "<pre>\nOptions:\n⠋ loading done\n</pre>")

    def test_notebook_to_mdx_escapes_stream_output(self):
        notebook = {
            "cells": [
                {
                    "cell_type": "code",
                    "source": "!text-generation-launcher -h",
                    "outputs": [
                        {
                            "output_type": "stream",
                            "name": "stdout",
                            "text": "\x1b[1mUsage:\x1b[0m --model-id <MODEL_ID>",
                        }
                    ],
                }
            ]
        }
        mdx = notebook_to_mdx(notebook, max_len=119)
        self.assertIn("<pre>\nUsage: --model-id &lt;MODEL_ID&gt;\n</pre>", mdx)
        self.assertNotIn("<MODEL_ID>", mdx)
        self.assertNotIn("\x1b", mdx)
