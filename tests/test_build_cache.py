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

from doc_builder.build_cache import PageCache, hash_kit_tree, page_cache_key, rewrite_cached_html


class BuildCacheTester(unittest.TestCase):
    def test_page_cache_key_is_stable(self):
        key1 = page_cache_key("# Hello", "kithash", "accelerate", "main", "en")
        key2 = page_cache_key("# Hello", "kithash", "accelerate", "main", "en")
        self.assertEqual(key1, key2)
        self.assertNotEqual(key1, page_cache_key("# Hello!", "kithash", "accelerate", "main", "en"))
        self.assertNotEqual(key1, page_cache_key("# Hello", "otherkit", "accelerate", "main", "en"))
        self.assertNotEqual(key1, page_cache_key("# Hello", "kithash", "accelerate", "main", "fr"))

    def test_page_cache_key_is_version_normalized(self):
        # resolved internal links embed the built version; identical content built for
        # different versions must share a key
        main_mdx = "See [Trainer](/docs/transformers/main/en/main_classes/trainer#transformers.Trainer)"
        pr_mdx = "See [Trainer](/docs/transformers/pr_123/en/main_classes/trainer#transformers.Trainer)"
        key_main = page_cache_key(main_mdx, "kithash", "transformers", "main", "en")
        key_pr = page_cache_key(pr_mdx, "kithash", "transformers", "pr_123", "en")
        self.assertEqual(key_main, key_pr)

    def test_rewrite_cached_html(self):
        html = (
            '<link href="/docs/transformers/main/en/_app/immutable/entry/start.abc.js" rel="modulepreload">'
            '<a href="/docs/transformers/main/en/quicktour">quicktour</a>'
            '<script>base: "/docs/transformers/main/en/page"</script>'
        )
        rewritten = rewrite_cached_html(html, "transformers", "main", "pr_123", "en")
        # asset URLs stay pinned to the source version (still hosted there)
        self.assertIn("/docs/transformers/main/en/_app/immutable/entry/start.abc.js", rewritten)
        # page URLs move to the target version
        self.assertIn('href="/docs/transformers/pr_123/en/quicktour"', rewritten)
        self.assertIn('base: "/docs/transformers/pr_123/en/page"', rewritten)
        self.assertNotIn('href="/docs/transformers/main/en/quicktour"', rewritten)
        # same-version rewrite is a no-op
        self.assertEqual(rewrite_cached_html(html, "transformers", "main", "main", "en"), html)

    def test_hash_kit_tree_ignores_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            kit = Path(tmp)
            (kit / "src").mkdir()
            (kit / "src" / "app.css").write_text("body {}")
            base_hash = hash_kit_tree(kit)
            (kit / "node_modules").mkdir()
            (kit / "node_modules" / "dep.js").write_text("x")
            (kit / ".svelte-kit").mkdir()
            (kit / ".svelte-kit" / "gen.js").write_text("y")
            self.assertEqual(hash_kit_tree(kit), base_hash)
            (kit / "src" / "app.css").write_text("body { color: red }")
            self.assertNotEqual(hash_kit_tree(kit), base_hash)

    def test_local_cache_roundtrip(self):
        with tempfile.TemporaryDirectory() as cache_dir, tempfile.TemporaryDirectory() as build_dir:
            html = Path(build_dir) / "quicktour.html"
            html.write_text('<a href="/docs/accelerate/main/en/index">home</a>', encoding="utf-8")
            key = page_cache_key("mdx content", "kithash", "accelerate", "main", "en")

            writer = PageCache(cache_dir, package="accelerate", version="main", language="en", write=True)
            self.assertEqual(writer.load_manifest(), {})
            writer.store_pages({"quicktour.mdx": (key, html)}, manifest={}, reused={})

            reader = PageCache(cache_dir, package="accelerate", version="main", language="en")
            manifest = reader.load_manifest()
            self.assertIn("quicktour.mdx", manifest)

            # matching key -> hit, byte-identical
            fetched = reader.fetch_pages({"quicktour.mdx": key}, manifest)
            self.assertEqual(set(fetched), {"quicktour.mdx"})
            self.assertEqual(fetched["quicktour.mdx"].html_path.read_text(encoding="utf-8"), html.read_text())

            # changed content -> miss
            other_key = page_cache_key("changed mdx", "kithash", "accelerate", "main", "en")
            self.assertEqual(reader.fetch_pages({"quicktour.mdx": other_key}, manifest), {})

            # cross-version hit -> page urls rewritten
            pr_reader = PageCache(cache_dir, package="accelerate", version="pr_5", language="en")
            fetched = pr_reader.fetch_pages({"quicktour.mdx": key}, manifest)
            self.assertEqual(set(fetched), {"quicktour.mdx"})
            self.assertIn(
                "/docs/accelerate/pr_5/en/index", fetched["quicktour.mdx"].html_path.read_text(encoding="utf-8")
            )

    def test_write_disabled_does_not_store(self):
        with tempfile.TemporaryDirectory() as cache_dir, tempfile.TemporaryDirectory() as build_dir:
            html = Path(build_dir) / "index.html"
            html.write_text("<p>hi</p>", encoding="utf-8")
            key = page_cache_key("mdx", "kithash", "accelerate", "main", "en")
            cache = PageCache(cache_dir, package="accelerate", version="main", language="en", write=False)
            cache.store_pages({"index.mdx": (key, html)}, manifest={}, reused={})
            self.assertEqual(cache.load_manifest(), {})
