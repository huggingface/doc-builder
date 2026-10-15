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

import html
import json
import re
import unittest
from pathlib import Path

from doc_builder import translate_html as th

DATA = Path(__file__).parent / "data" / "translate"


def read(name):
    return (DATA / name).read_text(encoding="utf-8")


class TranslateHtmlTester(unittest.TestCase):
    def test_hydration_safety(self):
        self.assertTrue(th.is_hydration_safe(th.split_page(read("page.html"))[1]))
        # built before huggingface/doc-builder#851: stray module scripts and text-node headings
        self.assertFalse(th.is_hydration_safe(th.split_page(read("page_before_851.html"))[1]))

    def test_blocks(self):
        _, body = th.split_page(read("page.html"))
        blocks = th.find_blocks(body)
        texts = [th.visible_text(body[b.start : b.end]) for b in blocks]
        self.assertIn("Hydration check", texts)
        self.assertIn("Text of the second option.", texts)  # inactive options are in the HTML
        # code blocks and UI strings outside blocks are never prose
        self.assertFalse(any("import" in t for t in texts))
        heading = next(b for b in blocks if b.tag == "h1")
        self.assertEqual(heading.anchor, "hydration-check")
        self.assertFalse(th.is_static(body, heading))  # headings carry hydration markers
        # the docstring signature is code
        self.assertFalse(any(t.startswith("( text") for t in texts))

    def test_docstring_parameter_segments(self):
        _, body = th.split_page(read("page.html"))
        block = next(b for b in th.find_blocks(body) if "Whether to pad" in body[b.start : b.end])
        segments = th.segments(body, block)
        # the parameter name and the punctuation after its type are not prose
        self.assertEqual(segments[0], {"fixed": "padding (bool,"})
        self.assertIn({"fixed": "False ) —"}, segments)
        self.assertEqual(segments[-1], {"id": 2, "text": "Whether to pad the output."})
        edits = th.replace_text_nodes(
            block, {"0": "省略可能", "1": "デフォルトは", "2": "出力をパディングするかどうか。"}
        )
        translated = th.visible_text(th.apply_edits(body[: block.end], edits)[block.start :])
        self.assertEqual(translated, "padding (bool, 省略可能, デフォルトは False) — 出力をパディングするかどうか。")

    def test_markup_round_trip(self):
        _, body = th.split_page(read("page.html"))
        static = [b for b in th.find_blocks(body) if th.is_static(body, b)]
        self.assertTrue(static)
        for block in static:
            inner = body[block.start : block.end]
            markup, elements = th.to_markup(inner)
            th.markup_structure(markup)
            self.assertEqual(th.from_markup(markup, elements), inner)

    def test_markup_example(self):
        markup, elements = th.to_markup('See <a href="/x">the guide</a> and <code>a &lt; b</code>.')
        self.assertEqual(markup, "See <t0>the guide</t0> and <c1>a &lt; b</c1>.")
        translated = "<c1>a &lt; b</c1> と <t0>ガイド</t0> を参照してください。"
        th.check_markup(markup, translated)  # tags may move
        self.assertEqual(
            th.from_markup(translated, elements),
            '<code>a &lt; b</code> と <a href="/x">ガイド</a> を参照してください。',
        )

    def test_repeated_prefix_punctuation_is_not_doubled(self):
        body = "<li><!---->If an <code>int</code>, compute logits.</li>"
        block = th.find_blocks(body)[0]
        edits = th.replace_text_nodes(block, {"0": "Если передано значение типа", "1": ", вычислить logits."})
        self.assertEqual(
            th.visible_text(th.apply_edits(body, edits)), "Если передано значение типа int, вычислить logits."
        )

    def test_invented_tags_are_dropped(self):
        # models wrap names in code tags of their own; the tag goes, the name stays as text
        answer = th.drop_invented_tags("This uses ByteFallback.", "Isso usa <cN>ByteFallback</cN> <c7>x</c7>.")
        self.assertEqual(answer, "Isso usa ByteFallback x.")
        self.assertEqual(th.drop_invented_tags("See <t0>it</t0>", "Veja <t0>isso</t0>"), "Veja <t0>isso</t0>")
        wrapped = '<comment id="c1">حمّل مُجمِّع بيانات.</comment>'
        self.assertEqual(th.drop_invented_tags("Load a data collator.", wrapped), "حمّل مُجمِّع بيانات.")

    def test_code_also_in_prose_is_not_a_repeat(self):
        # "-100" is both code and prose in the source, so the translation may keep both
        th.check_markup("Use <c0>-100</c0> or -100 here", "<c0>-100</c0> または -100 を使います")

    def test_code_may_be_mentioned_twice(self):
        markup, elements = th.to_markup("Call the <code>Module</code> instance instead.")
        answer = "<c0>Module</c0> 인스턴스는 … 이 함수 대신 <c0>Module</c0> 인스턴스를 호출해야 합니다."
        th.check_markup(markup, answer)
        self.assertEqual(th.from_markup(answer, elements).count("<code>Module</code>"), 2)

    def test_check_markup_rejects(self):
        markup = "Use <t0><c1>Trainer</c1></t0> with <c2>bf16=True</c2>."
        for bad in [
            "Use <c1>Trainer</c1> with <c2>bf16=True</c2>.",  # dropped link
            "<t0><c1>Trainer</c1></t0> <t0>x</t0> <c2>bf16=True</c2>",  # duplicated tag
            "<t0><c1>Trainer</c1></t0> <c2>bf16=True</c2> <c2>fp16=True</c2>",  # duplicated code, changed
            "<t0><c1>Trainer</c1></t0> と <c2>fp16=True</c2>",  # changed code
            "<c1>Trainer</c1> <t0></t0> <c2>bf16=True</c2>",  # different nesting
            "<t0><c1>Trainer</c1></t0> で bf16=True <c2>bf16=True</c2>",  # code outside its tag
            "<t0><c1>Trainer</c1></t0> <b> <c2>bf16=True</c2>",  # raw markup
        ]:
            with self.assertRaises(ValueError, msg=bad):
                th.check_markup(markup, bad)

    def test_rewrite_links(self):
        body = '<a href="/docs/lib/main/en/guide#x">g</a><link href="/docs/lib/main/en/_app/a.js"><a href="/docs/other/main/en/p">o</a>'
        self.assertEqual(
            th.rewrite_links(body, "lib", "main", "ja"),
            '<a href="/docs/lib/main/ja/guide#x">g</a><link href="/docs/lib/main/en/_app/a.js"><a href="/docs/other/main/en/p">o</a>',
        )

    def test_translate_metadata(self):
        metadata, _ = th.split_page(read("page.html"))
        translated = th.translate_metadata(
            metadata, {"hydration-check": 'ハイドレーション "確認"', "options": "オプション"}
        )
        # decode the way moon-landing does
        data = json.loads(html.unescape(re.search(r'content="(\{.*\})"', translated)[1]).replace("\\\\", "\\"))
        self.assertEqual(data["title"], 'ハイドレーション "確認"')
        self.assertEqual([s["title"] for s in data["sections"]][:1], ["オプション"])
        self.assertEqual(th.page_title(translated), 'ハイドレーション "確認"')

    def test_still_english_answers_are_rejected(self):
        from doc_builder.translate_model import check_translated

        source = "Use Accelerator to automatically detect an available accelerator for inference."
        with self.assertRaises(ValueError):
            check_translated(source, "Use Accelerator to detect automatically an available accelerator for inference.")
        check_translated(
            source, "Usa Accelerator para detectar automáticamente un acelerador disponible para la inferencia."
        )
        check_translated(source, "Accelerator を使用して、推論に利用できるアクセラレータを自動的に検出します。")
