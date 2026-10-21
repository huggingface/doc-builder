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

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from doc_builder import translate_docs as translate_docs_module
from doc_builder import translate_html as th
from doc_builder.translate_docs import RunStats, Store, translate_library, translate_page
from doc_builder.translate_model import Translator

DATA = Path(__file__).parent / "data" / "translate"
LIB = "hydrationlib"


class FakeModel:
    """Prefixes every piece of prose with "訳"; keeps tags and code. Counts calls."""

    def __init__(self, fail_on=None):
        self.calls = 0
        self.fail_on = fail_on

    def __call__(self, messages, temperature=0, response_format=None):
        self.calls += 1
        system, user = messages[0]["content"], messages[1]["content"].split("\n\n", 1)[1]
        if self.fail_on and self.fail_on in user:
            return "not a valid answer <"
        if "light markup" in system:
            # translate text outside code tags, keep every tag in place
            parts = re.split(r"(<c(\d+)>.*?</c\2>|</?t\d+/?>)", user)
            out = []
            for i in range(0, len(parts), 3):
                text = parts[i]
                out.append("訳" + text if text.strip() else text)
                if i + 1 < len(parts):
                    out.append(parts[i + 1])
            return "".join(out)
        segments = json.loads(user)
        return json.dumps({str(s["id"]): "訳" + s["text"] for s in segments if "id" in s}, ensure_ascii=False)


class TranslateDocsTester(unittest.TestCase):
    def setUp(self):
        # the fake model's "訳" + English is not a real translation; that check has its own test
        patcher = mock.patch("doc_builder.translate_model.check_translated")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tmp = Path(tempfile.mkdtemp())
        self.source_dir = self.tmp / "source"
        self.target_dir = self.tmp / "target"
        self.add_version("main")
        self.write_versions(["main", "v1.0.0"])
        self.add_version("v1.0.0")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def add_version(self, version):
        en = self.source_dir / LIB / version / "en"
        (en / "guides").mkdir(parents=True)
        page = (DATA / "page.html").read_text(encoding="utf-8").replace(f"/{LIB}/main/en/", f"/{LIB}/{version}/en/")
        (en / "index.html").write_text(page, encoding="utf-8")
        (en / "guides" / "old.html").write_text(page, encoding="utf-8")
        shutil.copy(DATA / "page.md", en / "index.md")
        shutil.copy(DATA / "_toctree.yml", en / "_toctree.yml")
        (en / "_app").mkdir()
        (en / "_app" / "chunk.js").write_text("// asset")

    def write_versions(self, versions):
        (self.source_dir / LIB / "_versions.yml").write_text(yaml.safe_dump([{"version": v} for v in versions]))

    def run_job(self, model=None, target=None, **kwargs):
        model = model or FakeModel()
        self.stats = translate_library(
            Store(str(self.source_dir)),
            target or Store(str(self.target_dir)),
            LIB,
            "ja",
            complete=model,
            workers=2,
            **kwargs,
        )
        return model

    def ja(self, version, path):
        return self.target_dir / LIB / version / "ja" / path

    def tracker(self):
        return json.loads((self.target_dir / ".translation" / LIB / "ja" / "tracker.json").read_text())

    def test_first_run(self):
        self.run_job()
        page = self.ja("main", "index.html").read_text(encoding="utf-8")
        source = (self.source_dir / LIB / "main" / "en" / "index.html").read_text(encoding="utf-8")
        # only text changed: the page hydrates against the same JS
        self.assertEqual(
            re.findall(th.TAG_RE, th.split_page(page)[1]), re.findall(th.TAG_RE, th.split_page(source)[1])
        )
        self.assertIn("訳Text of the second option.", page)
        self.assertEqual(th.page_title(th.split_page(page)[0]), "訳Hydration check")
        # the sidebar title of a page is the page's translated title
        toctree = yaml.safe_load(self.ja("main", "_toctree.yml").read_text(encoding="utf-8"))
        self.assertEqual(toctree[0]["title"], "訳Get started")
        self.assertEqual(toctree[0]["sections"][0], {"local": "index", "title": "訳Hydration check"})
        # Markdown is translated next to the page; code stays as is; assets are not copied
        md = self.ja("main", "index.md").read_text(encoding="utf-8")
        self.assertTrue(md.startswith("# 訳Hydration check"))
        self.assertIn("訳Text of the second option.", md)
        self.assertIn("```python\nhydrationlib.tokenize(", md)
        self.assertFalse(self.ja("main", "_app").exists())
        # releases that existed before translation started are not backfilled
        self.assertFalse(self.ja("v1.0.0", "index.html").exists())
        self.assertEqual(self.tracker()["baseline_versions"], ["v1.0.0"])

    def test_unchanged_run_calls_no_model(self):
        self.run_job()
        before = self.ja("main", "index.html").read_bytes()
        self.assertEqual(self.run_job().calls, 0)
        self.assertEqual(self.ja("main", "index.html").read_bytes(), before)

    def test_edited_paragraph_only_translates_that_paragraph(self):
        self.run_job()
        en = self.source_dir / LIB / "main" / "en" / "index.html"
        # an edited paragraph plus a new asset hash, as after a doc-builder update
        en.write_text(
            en.read_text(encoding="utf-8")
            .replace("Text of the first option.", "Edited first option.")
            .replace("_app/immutable", "_app/immutable2"),
            encoding="utf-8",
        )
        self.assertEqual(self.run_job().calls, 1)
        page = self.ja("main", "index.html").read_text(encoding="utf-8")
        self.assertIn("訳Edited first option.", page)
        self.assertIn("_app/immutable2", page)

    def test_deleted_page_is_removed(self):
        self.run_job()
        self.assertTrue(self.ja("main", "guides/old.html").exists())
        (self.source_dir / LIB / "main" / "en" / "guides" / "old.html").unlink()
        self.run_job()
        self.assertFalse(self.ja("main", "guides/old.html").exists())
        self.assertNotIn("guides/old.html", self.tracker()["versions"]["main"]["files"])

    def test_new_release_is_translated_once(self):
        self.run_job()
        self.add_version("v1.1.0")
        self.write_versions(["main", "v1.1.0", "v1.0.0"])
        self.run_job()
        self.assertTrue(self.ja("v1.1.0", "index.html").exists())
        self.assertTrue(self.tracker()["versions"]["v1.1.0"]["frozen"])
        self.assertIn(
            'href="/docs/hydrationlib/v1.1.0/en/_app', self.ja("v1.1.0", "index.html").read_text(encoding="utf-8")
        )
        # frozen: later changes to the release are ignored
        en = self.source_dir / LIB / "v1.1.0" / "en" / "index.html"
        en.write_text(
            en.read_text(encoding="utf-8").replace("Text of the first option.", "Changed."), encoding="utf-8"
        )
        self.assertEqual(self.run_job().calls, 0)

    def test_failed_block_stays_english_and_is_retried(self):
        self.run_job(FakeModel(fail_on="Text of the second option."))
        page = self.ja("main", "index.html").read_text(encoding="utf-8")
        self.assertIn(">Text of the second option.<", page)
        self.assertFalse(self.tracker()["versions"]["main"]["files"]["index.html"]["complete"])
        model = self.run_job()
        self.assertEqual(model.calls, 1)  # only the failed block; the rest comes from the cache
        self.assertIn("訳Text of the second option.", self.ja("main", "index.html").read_text(encoding="utf-8"))
        self.assertTrue(self.tracker()["versions"]["main"]["files"]["index.html"]["complete"])

    def test_finished_pages_are_kept_when_the_run_fails(self):
        real = translate_docs_module.translate_page
        calls = []

        def second_page_fails(*args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                raise RuntimeError("rate limited for too long")
            return real(*args, **kwargs)

        with mock.patch.object(translate_docs_module, "translate_page", second_page_fails):
            with self.assertRaises(RuntimeError):
                self.run_job()
        # the first page was published and recorded, so the next run resumes after it
        self.assertTrue(self.ja("main", "guides/old.html").exists())
        self.assertIn("guides/old.html", self.tracker()["versions"]["main"]["files"])

    def test_page_built_before_hydration_fix_is_skipped(self):
        shutil.copy(DATA / "page_before_851.html", self.source_dir / LIB / "main" / "en" / "index.html")
        self.run_job()
        self.assertFalse(self.ja("main", "index.html").exists())
        entry = self.tracker()["versions"]["main"]["files"]["index.html"]
        self.assertFalse(entry["complete"])
        self.assertEqual(self.stats.waiting, [f"{LIB}/main/ja/index.html"])

    def test_page_is_recorded_only_after_its_upload(self):
        class FailingUpload(Store):
            def write(self, files):
                if any(p.endswith(".html") for p in files):
                    raise OSError("upload interrupted")
                super().write(files)

        with self.assertRaises(OSError):
            self.run_job(target=FailingUpload(str(self.target_dir)))
        # the tracker was saved, but without pages that never reached the bucket
        self.assertNotIn("index.html", self.tracker()["versions"]["main"]["files"])
        self.run_job()
        self.assertTrue(self.ja("main", "index.html").exists())

    def test_incomplete_pages_are_reported(self):
        self.run_job(FakeModel(fail_on="Text of the second option."))
        self.assertEqual(self.stats.english_blocks, 3)  # once per page and Markdown file that has the block
        self.assertEqual(
            {page for page, _, _ in self.stats.incomplete},
            {f"{LIB}/main/ja/index.html", f"{LIB}/main/ja/guides/old.html", f"{LIB}/main/ja/index.md"},
        )
        self.assertEqual(self.tracker()["versions"]["main"]["files"]["index.html"]["english_blocks"], 1)
        self.assertFalse(self.stats.failed())  # a few English blocks: published, retried, warned
        self.assertTrue(RunStats(blocks=10, english_blocks=2).failed())  # systematic failure: the run fails

    def test_nested_blocks_are_translated_once(self):
        metadata = th.split_page((DATA / "page.html").read_text(encoding="utf-8"))[0]
        body = "<ul><li>install the library\n<ul><li>run the <code>pip</code> installation</li></ul></li></ul>"
        model = FakeModel()
        html, (blocks, failed), _ = translate_page(
            metadata + "\n" + body, Translator("ja", {}, complete=model), LIB, "main", "ja", workers=1
        )
        self.assertEqual((blocks, failed, model.calls), (2, 0, 2))
        self.assertEqual(
            th.split_page(html)[1],
            "<ul><li>訳install the library\n<ul><li>訳run the <code>pip</code>訳 installation</li></ul></li></ul>",
        )
