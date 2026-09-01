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

from doc_builder.build_embeddings import Chunk, chunks_to_documents
from doc_builder.meilisearch_helper import VECTOR_NAME, add_embeddings_to_db


class FakeIndex:
    def __init__(self):
        self.payload = None

    def add_documents(self, payload):
        self.payload = payload
        return SimpleNamespace(task_uid=7)

    def get_task(self, task_uid):
        assert task_uid == 7
        return SimpleNamespace(status="succeeded")


class FakeClient:
    def __init__(self):
        self.index_instance = FakeIndex()

    def index(self, index_name):
        assert index_name == "test-index"
        return self.index_instance


def make_chunk(text: str) -> Chunk:
    return Chunk(
        text=text,
        source_page_url=f"https://huggingface.co/docs/test/{text}",
        source_page_title=text,
        package_name="test",
        headings=[f"# {text}"],
        page=text,
    )


def test_add_embeddings_to_db_omits_vectors_only_for_none():
    chunks = [make_chunk("vectorized"), make_chunk("vectorless"), make_chunk("empty-vector")]
    documents = chunks_to_documents(chunks, [[0.1, 0.2], None, []])
    client = FakeClient()

    add_embeddings_to_db(client, "test-index", documents)

    payload_by_text = {document["text"]: document for document in client.index_instance.payload}
    assert payload_by_text["vectorized"]["_vectors"] == {VECTOR_NAME: [0.1, 0.2]}
    assert "_vectors" not in payload_by_text["vectorless"]
    assert payload_by_text["empty-vector"]["_vectors"] == {VECTOR_NAME: []}
    assert all(document["product"] == "test" for document in payload_by_text.values())
