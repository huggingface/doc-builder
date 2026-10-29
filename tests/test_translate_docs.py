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
from doc_builder.translate_docs import BLOCKS_VERSION, MAX_TRIES, RunStats, Store, translate_library, translate_page
from doc_builder.translate_model import Translator
from doc_builder.utils import write_llms_feeds

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
        shutil.copy(DATA / "page.md", en / "guides" / "old.md")
        shutil.copy(DATA / "_toctree.yml", en / "_toctree.yml")
        self.write_llms(version, ["index.md", "guides/old.md"])
        (en / "_app").mkdir()
        (en / "_app" / "chunk.js").write_text("// asset")

    def write_llms(self, version, pages):
        # the English feeds, as `doc-builder build` writes them: they list the pages of the build
        md = (DATA / "page.md").read_text(encoding="utf-8")
        write_llms_feeds(self.source_dir / LIB / version / "en", [(p, md) for p in pages], package_name=LIB)

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

    def test_llms_feeds_are_rebuilt_from_the_translation(self):
        self.run_job()
        english = (self.source_dir / LIB / "main" / "en" / "llms.txt").read_text(encoding="utf-8")
        self.assertIn(f"- [Hydration check](https://huggingface.co/docs/{LIB}/main/index.md)", english)
        llms = self.ja("main", "llms.txt").read_text(encoding="utf-8")
        # translated title, and the URL of the translated Markdown
        self.assertIn(f"- [訳Hydration check](https://huggingface.co/docs/{LIB}/main/ja/index.md)", llms)
        full = self.ja("main", "llms-full.txt").read_text(encoding="utf-8")
        self.assertTrue(full.startswith(llms.rstrip("\n")))
        self.assertIn("訳Text of the second option.", full)

    def test_pages_from_an_older_block_detection_are_processed_again(self):
        self.run_job()
        tracker_path = self.target_dir / ".translation" / LIB / "ja" / "tracker.json"
        tracker = self.tracker()
        for entry in tracker["versions"]["main"]["files"].values():
            entry.pop("blocks", None)
        tracker_path.write_text(json.dumps(tracker))
        model = self.run_job()
        self.assertEqual(self.stats.pages, 2)  # the two HTML pages, not their Markdown
        self.assertEqual(model.calls, 0)  # every block comes from the cache
        self.assertEqual(self.tracker()["versions"]["main"]["files"]["index.html"]["blocks"], BLOCKS_VERSION)

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

    def test_page_left_over_from_an_earlier_build_is_removed(self):
        self.run_job()
        self.assertTrue(self.ja("main", "guides/old.html").exists())
        # a new build no longer has the page, but its files stay in the English bucket
        self.write_llms("main", ["index.md"])
        self.run_job()
        self.assertFalse(self.ja("main", "guides/old.html").exists())
        self.assertFalse(self.ja("main", "guides/old.md").exists())
        self.assertNotIn("guides/old.html", self.tracker()["versions"]["main"]["files"])
        self.assertEqual(self.stats.waiting, [])

    def human_translation(self, version, language):
        """A translation built into the same bucket by the library's own docs build (with its own JS)."""
        folder = self.target_dir / LIB / version / language
        (folder / "_app").mkdir(parents=True)
        (folder / "_app" / "chunk.js").write_text("// asset")
        (folder / "index.html").write_text("human translation", encoding="utf-8")
        (folder / "only-human.html").write_text("human translation", encoding="utf-8")
        return folder

    @mock.patch.dict(translate_docs_module.TRANSLATED_DOCS, {LIB: ["ja", "ko"]})
    def test_first_translation_of_main_deletes_the_docs_build_translations(self):
        en, ja, ko, cn = (self.human_translation("main", lang) for lang in ("en", "ja", "ko", "cn"))
        release = self.human_translation("v1.0.0", "cn")
        # a machine translation of a language that isn't configured (a manual run)
        (self.target_dir / LIB / "main" / "de").mkdir()
        (self.target_dir / LIB / "main" / "de" / "index.html").write_text("translation", encoding="utf-8")
        self.run_job()
        self.assertIn("訳Text of the second option.", (ja / "index.html").read_text(encoding="utf-8"))
        self.assertFalse((ja / "only-human.html").exists())
        self.assertFalse((ja / "_app").exists())
        self.assertFalse(cn.exists())
        # left alone: English, the job of another configured language, other versions, and translations
        for kept in (en, ko, release):
            self.assertEqual((kept / "index.html").read_text(encoding="utf-8"), "human translation")
        self.assertTrue((self.target_dir / LIB / "main" / "de" / "index.html").exists())
        # only the first translation
        cn = self.human_translation("main", "cn")
        self.run_job()
        self.assertTrue((cn / "index.html").exists())

    def test_release_built_by_the_docs_build_is_left_alone(self):
        self.run_job()
        self.add_version("v1.1.0")
        self.write_versions(["main", "v1.1.0", "v1.0.0"])
        human = self.human_translation("v1.1.0", "ja")
        self.assertEqual(self.run_job().calls, 0)
        self.assertEqual((human / "index.html").read_text(encoding="utf-8"), "human translation")
        self.assertFalse(self.ja("v1.1.0", "guides/old.html").exists())

    def test_language_taken_over_by_the_docs_build_is_left_alone(self):
        self.run_job()
        # the library starts building this language itself
        (self.target_dir / LIB / "main" / "ja" / "_app").mkdir()
        (self.target_dir / LIB / "main" / "ja" / "_app" / "chunk.js").write_text("// asset")
        self.ja("main", "index.html").write_text("human translation", encoding="utf-8")
        en = self.source_dir / LIB / "main" / "en" / "index.html"
        en.write_text(en.read_text(encoding="utf-8").replace("Text of the first option.", "Edited."), encoding="utf-8")
        self.assertEqual(self.run_job().calls, 0)
        self.assertEqual(self.ja("main", "index.html").read_text(encoding="utf-8"), "human translation")

    def test_only_files_the_job_wrote_are_deleted(self):
        self.run_job()
        other = self.ja("main", "notes.html")
        other.write_text("written by someone else", encoding="utf-8")
        self.run_job()
        self.assertTrue(other.exists())

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

    def test_block_that_keeps_failing_waits_for_an_english_change(self):
        fail = "Text of the second option."
        calls = [self.run_job(FakeModel(fail_on=fail)).calls for _ in range(MAX_TRIES + 1)]
        self.assertTrue(all(calls[:MAX_TRIES]))
        self.assertEqual(calls[MAX_TRIES], 0)  # given up: the block stays English
        self.assertEqual(self.tracker()["versions"]["main"]["files"]["index.html"]["tries"], MAX_TRIES)
        en = self.source_dir / LIB / "main" / "en" / "index.html"
        en.write_text(
            en.read_text(encoding="utf-8").replace("Text of the first option.", "Edited first option."),
            encoding="utf-8",
        )
        self.run_job()
        self.assertIn("訳Text of the second option.", self.ja("main", "index.html").read_text(encoding="utf-8"))

    def test_release_is_frozen_once_its_failing_blocks_are_given_up(self):
        fail = "Text of the second option."
        self.run_job(FakeModel(fail_on=fail))
        self.add_version("v1.1.0")
        self.write_versions(["main", "v1.1.0", "v1.0.0"])
        for _ in range(MAX_TRIES - 1):
            self.run_job(FakeModel(fail_on=fail))
        self.assertFalse(self.tracker()["versions"]["v1.1.0"]["frozen"])
        self.run_job(FakeModel(fail_on=fail))
        self.assertTrue(self.tracker()["versions"]["v1.1.0"]["frozen"])

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
        # the sidebar is there too; the page that isn't translated yet keeps its English title
        toctree = yaml.safe_load(self.ja("main", "_toctree.yml").read_text(encoding="utf-8"))
        self.assertEqual(toctree[0]["title"], "訳Get started")
        self.assertEqual(toctree[0]["sections"][0], {"local": "index", "title": "Hydration check"})
        self.run_job()
        toctree = yaml.safe_load(self.ja("main", "_toctree.yml").read_text(encoding="utf-8"))
        self.assertEqual(toctree[0]["sections"][0], {"local": "index", "title": "訳Hydration check"})

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
        self.assertEqual(self.stats.english_blocks, 4)  # once per page and Markdown file that has the block
        self.assertEqual(
            {page for page, _, _ in self.stats.incomplete},
            {f"{LIB}/main/ja/{p}" for p in ["index.html", "guides/old.html", "index.md", "guides/old.md"]},
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
