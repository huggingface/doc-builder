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

from types import SimpleNamespace

import pytest

from doc_builder.build_embeddings import Chunk, chunks_to_documents
from doc_builder.commands import embeddings as embeddings_command
from doc_builder.process_hf_docs import (
    HF_BLOG_API_URL,
    fetch_blog_chunks,
    markdown_file_to_url,
    process_all_libraries,
    process_api_html_file,
    process_markdown_file,
    should_embed_chunk,
)


def make_chunk(package_name: str, page: str, text: str = "Searchable text") -> Chunk:
    return Chunk(
        text=text,
        source_page_url=f"https://huggingface.co/{page}",
        source_page_title="Page title",
        package_name=package_name,
        headings=["# Page title"],
        page=page,
    )


@pytest.mark.parametrize(
    ("package_name", "page", "expected"),
    [
        ("transformers", "model_doc/bert", False),
        ("transformers", "model_doc/bert.mdx", False),
        ("transformers", "main_classes/trainer", True),
        ("diffusers", "api/models/autoencoder_kl", False),
        ("diffusers", "api/pipelines/stable_diffusion/pipeline", False),
        ("diffusers", "api/schedulers/ddim", True),
        ("course", "chapter1/1", False),
        ("llm-course", "chapter1/1", False),
        ("agents-course", "unit0/introduction", False),
        ("cookbook", "notebooks/example", False),
        ("blog", "/blog/search-post", False),
        ("datasets", "about_dataset_features", True),
    ],
)
def test_should_embed_chunk_policy(package_name, page, expected):
    assert should_embed_chunk(make_chunk(package_name, page)) is expected


def test_course_uses_public_product_name_and_learn_url(tmp_path):
    page = tmp_path / "chapter1" / "lesson.md"
    page.parent.mkdir()
    page.write_text("# Lesson\n\nCourse content.", encoding="utf-8")

    assert markdown_file_to_url(page, "course", tmp_path) == (
        "https://huggingface.co/learn/llm-course/en/chapter1/lesson"
    )

    chunks = process_markdown_file(page, "course", tmp_path)

    assert chunks
    assert {chunk.package_name for chunk in chunks} == {"llm-course"}
    assert {chunk.page for chunk in chunks} == {"chapter1/lesson"}
    assert all(
        chunk.source_page_url.startswith("https://huggingface.co/learn/llm-course/en/chapter1/lesson")
        for chunk in chunks
    )


def test_api_page_becomes_one_vectorless_record_per_docstring(tmp_path):
    page = tmp_path / "model_doc" / "bert.md"
    page.parent.mkdir()
    page.write_text("# BERT", encoding="utf-8")
    page.with_suffix(".html").write_text(
        """
        <div class="docstring">
          <div>
            <span id="transformers.BertModel"><h3>transformers.BertModel</h3></span>
            <p>(config, add_pooling_layer=True)</p>
            <div class="docstring-details"><p>Returns a tensor.</p></div>
          </div>
          <p>The bare BERT model transformer.</p>
        </div>
        """,
        encoding="utf-8",
    )

    chunks = process_api_html_file(page, "transformers", tmp_path)

    assert len(chunks) == 1
    assert chunks[0].text == "transformers.BertModel\n\nThe bare BERT model transformer."
    assert chunks[0].source_page_url.endswith("/docs/transformers/model_doc/bert#transformers.BertModel")
    assert chunks[0].source_page_title == "transformers.BertModel"
    assert chunks[0].headings == ["# transformers.BertModel"]
    assert chunks[0].page == "model_doc/bert#transformers.BertModel"
    assert should_embed_chunk(chunks[0]) is False


def test_process_all_libraries_keeps_courses_and_adds_blog(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "doc_builder.process_hf_docs.fetch_library_directories",
        lambda: [{"path": "course"}, {"path": "datasets"}],
    )
    processed_libraries = []

    def fake_process_library(library_name, *args, **kwargs):
        processed_libraries.append(library_name)
        return []

    monkeypatch.setattr("doc_builder.process_hf_docs.process_library", fake_process_library)
    monkeypatch.setattr("doc_builder.process_hf_docs.fetch_blog_chunks", lambda: [make_chunk("blog", "/blog/post")])

    results = process_all_libraries(output_dir=tmp_path)

    assert processed_libraries == ["course", "datasets"]
    assert results["blog"][0].package_name == "blog"


def test_process_all_libraries_can_target_blog_without_fetching_dataset(monkeypatch, tmp_path):
    def fail_dataset_fetch():
        pytest.fail("The doc-build dataset should not be fetched for a blog-only run")

    monkeypatch.setattr("doc_builder.process_hf_docs.fetch_library_directories", fail_dataset_fetch)
    monkeypatch.setattr("doc_builder.process_hf_docs.fetch_blog_chunks", lambda: [make_chunk("blog", "/blog/post")])

    results = process_all_libraries(output_dir=tmp_path, libraries=["blog"])

    assert list(results) == ["blog"]


def test_process_all_libraries_maps_llm_course_to_dataset_name(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "doc_builder.process_hf_docs.fetch_library_directories",
        lambda: [{"path": "course"}, {"path": "datasets"}],
    )
    processed_libraries = []

    def fake_process_library(library_name, *args, **kwargs):
        processed_libraries.append(library_name)
        return []

    monkeypatch.setattr("doc_builder.process_hf_docs.process_library", fake_process_library)

    results = process_all_libraries(output_dir=tmp_path, libraries=["llm-course"])

    assert processed_libraries == ["course"]
    assert list(results) == ["course"]


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def test_fetch_blog_chunks_paginates_and_uses_only_all_blogs(monkeypatch):
    pages = {
        0: {
            "numTotalItems": 3,
            "numItemsPerPage": 2,
            "allBlogs": [
                {
                    "title": "First post",
                    "url": "/blog/first-post",
                    "summary": "This body must not be indexed.",
                    "canonical": True,
                },
                {
                    "title": "Namespaced post",
                    "url": "/blog/acme/namespaced-post",
                    "canonical": False,
                },
            ],
            "communityBlogPosts": [{"title": "Ignored community post", "url": "/blog/user/ignored"}],
        },
        1: {
            "allBlogs": [{"title": "Last post", "url": "/blog/last-post"}],
            "communityBlogPosts": [{"title": "Also ignored", "url": "/blog/user/also-ignored"}],
        },
    }
    calls = []

    def fake_get(url, *, params, timeout, follow_redirects):
        calls.append((url, params, timeout, follow_redirects))
        return FakeResponse(pages[params["p"]])

    monkeypatch.setattr("doc_builder.process_hf_docs.httpx.get", fake_get)

    chunks = fetch_blog_chunks()

    assert calls == [
        (HF_BLOG_API_URL, {"p": 0}, 60, True),
        (HF_BLOG_API_URL, {"p": 1}, 60, True),
    ]
    assert [chunk.text for chunk in chunks] == ["First post", "Namespaced post", "Last post"]
    assert [chunk.source_page_url for chunk in chunks] == [
        "https://huggingface.co/blog/first-post",
        "https://huggingface.co/blog/acme/namespaced-post",
        "https://huggingface.co/blog/last-post",
    ]
    assert all(chunk.package_name == "blog" for chunk in chunks)
    assert all(chunk.text == chunk.source_page_title for chunk in chunks)
    assert all(chunk.headings == [f"# {chunk.text}"] for chunk in chunks)
    assert "Ignored community post" not in {chunk.text for chunk in chunks}
    assert "This body must not be indexed." not in {chunk.text for chunk in chunks}


def test_fetch_blog_chunks_rejects_incomplete_results(monkeypatch):
    response = FakeResponse(
        {
            "numTotalItems": 2,
            "numItemsPerPage": 2,
            "allBlogs": [{"title": "Only post", "url": "/blog/only-post"}],
            "communityBlogPosts": [{"title": "Not a replacement", "url": "/blog/user/community"}],
        }
    )
    monkeypatch.setattr("doc_builder.process_hf_docs.httpx.get", lambda *args, **kwargs: response)

    with pytest.raises(ValueError, match="returned 1 unique allBlogs items, expected 2"):
        fetch_blog_chunks()


def test_chunks_to_documents_uses_none_for_vectorless_chunks():
    chunk = make_chunk("blog", "blog/vectorless", text="Open R1: Update #4")._replace(
        source_page_title="Open R1: Update #4",
        headings=["# Open R1: Update #4"],
    )

    documents = chunks_to_documents([chunk])

    assert len(documents) == 1
    assert documents[0].embedding is None
    assert documents[0].library == "blog"
    assert documents[0].heading1 == "Open R1: Update #4"
    assert documents[0].source_page_url == chunk.source_page_url


def test_chunks_to_search_documents_embeds_only_eligible_chunks(monkeypatch):
    regular_chunk = make_chunk("datasets", "about_dataset_features", text="Regular docs")
    api_chunk = make_chunk("transformers", "model_doc/bert", text="API docs")
    course_chunk = make_chunk("llm-course", "chapter1/1", text="Course docs")
    inference_calls = []

    def fake_inference(chunks, hf_ie_url, hf_ie_token, is_python_module):
        inference_calls.append((chunks, hf_ie_url, hf_ie_token, is_python_module))
        return chunks_to_documents(chunks, [[0.1, 0.2]])

    monkeypatch.setattr(embeddings_command, "call_embedding_inference", fake_inference)

    documents = embeddings_command._chunks_to_search_documents(
        [regular_chunk, api_chunk, course_chunk], "https://inference.test", "token"
    )

    assert inference_calls == [([regular_chunk], "https://inference.test", "token", False)]
    documents_by_text = {document.text: document for document in documents}
    assert documents_by_text["Regular docs"].embedding == [0.1, 0.2]
    assert documents_by_text["API docs"].embedding is None
    assert documents_by_text["Course docs"].embedding is None


def test_chunks_to_search_documents_skips_inference_when_every_chunk_is_vectorless(monkeypatch):
    chunks = [
        make_chunk("blog", "/blog/post", text="Blog title"),
        make_chunk("diffusers", "api/models/autoencoder_kl", text="API docs"),
    ]

    def fail_inference(*args, **kwargs):
        pytest.fail("Embedding inference should not be called for full-text-only chunks")

    monkeypatch.setattr(embeddings_command, "call_embedding_inference", fail_inference)

    documents = embeddings_command._chunks_to_search_documents(chunks, None, None)

    assert [document.text for document in documents] == ["Blog title", "API docs"]
    assert all(document.embedding is None for document in documents)


def test_incremental_course_scope_uses_public_product_prefix(monkeypatch):
    existing_ids = {"llm-course-old-page-a1b2c3d4", "course-legacy-page-a1b2c3d4", "datasets-page-a1b2c3d4"}
    deleted_batches = []
    saved_trackers = []

    monkeypatch.setattr("doc_builder.embeddings_tracker.load_tracker", lambda token: existing_ids)
    monkeypatch.setattr(
        "doc_builder.embeddings_tracker.save_tracker", lambda ids, token: saved_trackers.append((ids, token))
    )
    monkeypatch.setattr(
        "doc_builder.meilisearch_helper.delete_documents_from_db",
        lambda client, index, ids: deleted_batches.append(ids),
    )
    monkeypatch.setattr("meilisearch.Client", lambda *args: object())

    embeddings_command._run_incremental(
        SimpleNamespace(libraries=["course"], hf_token=None),
        [],
        None,
        None,
        "meili-key",
        "https://meili.test",
        5000,
    )

    assert deleted_batches == [["llm-course-old-page-a1b2c3d4"]]
    assert saved_trackers == [
        ({"course-legacy-page-a1b2c3d4", "datasets-page-a1b2c3d4"}, None),
    ]
