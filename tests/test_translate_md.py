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

import re
import unittest

from doc_builder import translate_md as tm
from doc_builder.translate_model import TranslationFailed

PAGE = """# Llama[[llama]]

[Llama](https://huggingface.co/papers/2302.13971) is a family of models.
It is hard-wrapped.

> [!TIP]
> Set `use_kernels=True` in [from_pretrained()](/docs/transformers/main/en/main_classes/model#from_pretrained) to
> use kernels.

```python
>>> from transformers import LlamaConfig
# a comment, not prose
```

- load a pretrained model
- run inference with [Pipeline](/docs/transformers/main/en/main_classes/pipelines)

| **Class** | **Description** |
|---|---|
| [PreTrainedConfig](/docs/transformers/main/en/main_classes/configuration) | A file that specifies attributes. |

**Parameters:**

vocab_size (`int`, *optional*, defaults to `32000`) : Vocabulary size of the model.
"""


def fake_translate(markup):
    """Prefix the prose of each piece with "訳", keeping tags and code."""
    parts = re.split(r"(<c(\d+)>.*?</c\2>|</?t\d+/?>)", markup)
    out = []
    for i in range(0, len(parts), 3):
        out.append("訳" + parts[i] if parts[i].strip() else parts[i])
        if i + 1 < len(parts):
            out.append(parts[i + 1])
    return "".join(out)


class TranslateMdTester(unittest.TestCase):
    def test_units(self):
        units = [p for p in tm.parse(PAGE) if isinstance(p, tm.Unit)]
        texts = [u.text for u in units]
        self.assertEqual(units[0].prefix, "# ")
        self.assertEqual(units[0].suffix, "[[llama]]\n")
        self.assertIn(
            "[Llama](https://huggingface.co/papers/2302.13971) is a family of models. It is hard-wrapped.", texts
        )
        self.assertIn("load a pretrained model", texts)
        self.assertIn("A file that specifies attributes.", texts)
        # code, admonition markers and table separators are never units
        self.assertFalse(any("import" in t or "[!TIP]" in t or "---" in t for t in texts))
        parameter = next(u for u in units if "Vocabulary" in u.text)
        self.assertEqual(parameter.prefix, "vocab_size ")  # the parameter name is not prose

    def test_unit_markup_round_trip(self):
        for unit in tm.parse(PAGE):
            if isinstance(unit, tm.Unit):
                markup, elements = tm.to_markup(unit.text)
                self.assertEqual(tm.from_markup(markup, elements), unit.text)

    def test_markup(self):
        markup, _ = tm.to_markup("Set `use_kernels=True` in [from_pretrained()](/x#y) or *optional* **bold** up_proj.")
        self.assertEqual(
            markup,
            "Set <c0>use_kernels=True</c0> in <t1>from_pretrained()</t1> or <t2>optional</t2> <t3>bold</t3> up_proj.",
        )

    def test_translate(self):
        md, units, failed = tm.translate_md(PAGE, fake_translate, "transformers", "main", "ja", workers=1)
        self.assertEqual(failed, 0)
        self.assertTrue(md.startswith("# 訳Llama[[llama]]\n"))
        # code blocks and URLs are byte for byte the English ones; page links move to the translation
        self.assertIn("```python\n>>> from transformers import LlamaConfig\n# a comment, not prose\n```", md)
        self.assertIn("(https://huggingface.co/papers/2302.13971)", md)
        self.assertIn("](/docs/transformers/main/ja/main_classes/pipelines)", md)
        self.assertNotIn("/main/en/", md)
        self.assertIn("> [!TIP]\n> 訳Set `use_kernels=True`", md)
        self.assertIn("|---|---|", md)
        self.assertIn("**訳Parameters:**", md)
        self.assertIn("vocab_size ", md)  # the parameter name is untouched
        self.assertIn("*訳optional*", md)
        self.assertTrue(md.endswith("\n") and not md.endswith("\n\n"))

    def test_code_in_quotes_and_lists_is_kept(self):
        md = "> [!TIP]\n> Run this:\n>\n> ```shell\n> transformers chat Qwen\n> ```\n\n- install it\n\n    ```bash\n    pip install x\n    ```\n"
        out, _, _ = tm.translate_md(md, fake_translate, "transformers", "main", "ja", workers=1)
        self.assertIn("> ```shell\n> transformers chat Qwen\n> ```\n", out)
        self.assertIn("    ```bash\n    pip install x\n    ```\n", out)
        self.assertIn("> 訳Run this:", out)

    def test_failed_unit_stays_english(self):
        def flaky(markup):
            if "Vocabulary" in markup:
                raise TranslationFailed("invalid")
            return fake_translate(markup)

        md, units, failed = tm.translate_md(PAGE, flaky, "transformers", "main", "ja", workers=1)
        self.assertEqual(failed, 1)
        self.assertIn(": Vocabulary size of the model.", md)
