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
from doc_builder.meilisearch_helper import (
    VECTOR_NAME,
    add_embeddings_to_db,
    delete_documents_from_db,
    generate_doc_id,
    update_all_documents,
)


class FakeIndex:
    def __init__(self, task_status="succeeded"):
        self.payload = None
        self.deleted = None
        self.task_status = task_status

    def delete_documents(self, ids):
        self.deleted = ids
        return SimpleNamespace(task_uid=7)

    def add_documents(self, payload):
        self.payload = payload
        return SimpleNamespace(task_uid=7)

    def get_task(self, task_uid):
        assert task_uid == 7
        return SimpleNamespace(status=self.task_status, error={"message": "boom", "type": "internal", "link": ""})


class FakeClient:
    def __init__(self, task_status="succeeded"):
        self.index_instance = FakeIndex(task_status)

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


def test_add_embeddings_to_db_marks_none_as_vectorless():
    chunks = [make_chunk("vectorized"), make_chunk("vectorless"), make_chunk("empty-vector")]
    documents = chunks_to_documents(chunks, [[0.1, 0.2], None, []])
    client = FakeClient()

    add_embeddings_to_db(client, "test-index", documents)

    payload_by_text = {document["text"]: document for document in client.index_instance.payload}
    assert payload_by_text["vectorized"]["_vectors"] == {VECTOR_NAME: [0.1, 0.2]}
    assert payload_by_text["vectorless"]["_vectors"] == {VECTOR_NAME: None}
    assert payload_by_text["empty-vector"]["_vectors"] == {VECTOR_NAME: []}
    assert all(document["product"] == "test" for document in payload_by_text.values())
    assert all(document["text_plain"] == document["text"] for document in payload_by_text.values())


def test_add_embeddings_to_db_ids_only_depend_on_text():
    chunk = make_chunk("**bold**")._replace(headings=["# Heading[[anchor]]"])
    client = FakeClient()

    add_embeddings_to_db(client, "test-index", chunks_to_documents([chunk]))

    [document] = client.index_instance.payload
    assert document["id"] == generate_doc_id("test", "**bold**", "**bold**")
    assert (document["text_plain"], document["heading1"]) == ("bold", "Heading")


class FakeMigrationIndex:
    def __init__(self, documents):
        self.documents = documents
        self.updates = []

    def get_documents(self, params):
        page = self.documents[params["offset"] : params["offset"] + params["limit"]]
        results = [SimpleNamespace(**{k: v for k, v in doc.items() if k in params["fields"]}) for doc in page]
        return SimpleNamespace(results=results)

    def update_documents(self, documents):
        self.updates.append(documents)
        return SimpleNamespace(task_uid=len(self.updates))


class FakeMigrationClient:
    def __init__(self, documents, pending_task_checks=0):
        self.index_instance = FakeMigrationIndex(documents)
        self.waited = []
        self.pending_task_checks = pending_task_checks

    def get_tasks(self, params):
        assert params == {"indexUids": ["test-index"], "statuses": ["enqueued", "processing"]}
        assert not self.index_instance.updates, "pending tasks must be waited for before any write"
        self.pending_task_checks -= 1
        return SimpleNamespace(results=[SimpleNamespace(uid=1)] if self.pending_task_checks >= 0 else [])

    def index(self, index_name):
        assert index_name == "test-index"
        return self.index_instance

    def wait_for_task(self, task_uid, **kwargs):
        self.waited.append(task_uid)
        return SimpleNamespace(status="succeeded", error=None)


def test_update_all_documents_writes_only_changed_fields_in_batches():
    documents = [{"id": f"doc-{i}", "text": "**x**" if i % 2 else "x", "heading1": "h"} for i in range(5)]
    client = FakeMigrationClient(documents)

    def transform(doc):
        assert set(doc) == {"id", "text", "text_plain"}
        return {"text_plain": "x"} if doc["text"] != "x" else None

    updated = update_all_documents(client, "test-index", ["text", "text_plain"], transform, batch_size=2)

    assert updated == 2
    assert client.index_instance.updates == [
        [{"id": "doc-1", "text_plain": "x"}],
        [{"id": "doc-3", "text_plain": "x"}],
    ]
    assert client.waited == [1, 2]


def test_update_all_documents_dry_run_does_not_write():
    client = FakeMigrationClient([{"id": "doc", "text": "**x**"}])

    updated = update_all_documents(client, "test-index", ["text"], lambda doc: {"text_plain": "x"}, dry_run=True)

    assert updated == 1
    assert client.index_instance.updates == []


def test_update_all_documents_waits_for_pending_index_tasks_before_scanning(monkeypatch):
    sleeps = []
    monkeypatch.setattr("doc_builder.meilisearch_helper.sleep", sleeps.append)
    client = FakeMigrationClient([{"id": "doc", "text": "**x**"}], pending_task_checks=2)

    update_all_documents(client, "test-index", ["text"], lambda doc: {"text_plain": "x"})

    assert len(sleeps) == 2
    assert client.index_instance.updates == [[{"id": "doc", "text_plain": "x"}]]


def test_delete_documents_from_db_waits_for_the_deletion():
    client = FakeClient()

    delete_documents_from_db(client, "test-index", ["doc-1"])

    assert client.index_instance.deleted == ["doc-1"]


def test_delete_documents_from_db_raises_when_the_deletion_fails():
    with pytest.raises(Exception, match="boom"):
        delete_documents_from_db(FakeClient(task_status="failed"), "test-index", ["doc-1"])
