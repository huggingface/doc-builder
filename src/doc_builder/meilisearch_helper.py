import hashlib
from functools import wraps
from time import sleep
from typing import Callable, Tuple

from meilisearch.client import Client, TaskInfo


# References:
# https://www.meilisearch.com/docs/learn/experimental/vector_search
# https://github.com/meilisearch/meilisearch-python/blob/d5a0babe50b4ce5789892845db98b30d4db72203/tests/index/test_index_search_meilisearch.py#L491-L493
# https://github.com/meilisearch/meilisearch-python/blob/d5a0babe50b4ce5789892845db98b30d4db72203/tests/conftest.py#L132-L146

VECOR_NAME = "docs-embed"
VECOR_DIM = 768

MeilisearchFunc = Callable[..., Tuple[Client, TaskInfo]]


def wait_for_task_completion(func: MeilisearchFunc) -> MeilisearchFunc:
    """
    Decorator to wait for MeiliSearch task completion
    A function that is being decorated should return (Client, TaskInfo)
    """

    @wraps(func)
    def wrapped_meilisearch_function(*args, **kwargs):
        # Extract the Client and Task info from the function's return value
        client, task = func(*args, **kwargs)
        index_id = args[1]  # Adjust this index based on where it actually appears in your arguments
        task_id = task.task_uid

        while True:
            # task failed
            if task.status == "failed":
                # Optionally, retrieve more detailed error information if available
                error_message = task.error.get("message") if task.error else "Unknown error"
                error_type = task.error.get("type") if task.error else "Unknown"
                error_link = task.error.get("link") if task.error else "No additional information"

                # Raise an exception with the error details
                raise Exception(
                    f"Task {task_id} failed with error type '{error_type}': {error_message}. More info: {error_link}"
                )
            task = client.index(index_id).get_task(task_id)  # Use the Index object's uid
            # task succeeded
            if task.status == "succeeded":
                return task
            # task processing
            sleep(1)

    return wrapped_meilisearch_function


@wait_for_task_completion
def create_embedding_db(client: Client, index_name: str):
    index = client.index(index_name)
    task_info = index.update_embedders({VECOR_NAME: {"source": "userProvided", "dimensions": VECOR_DIM}})
    return client, task_info


@wait_for_task_completion
def delete_embedding_db(client: Client, index_name: str):
    index = client.index(index_name)
    task_info = index.delete()
    return client, task_info


def hash_text_sha1(text):
    hash_object = hashlib.sha1()
    # Encode the text to bytes and update the hash object
    hash_object.update(text.encode("utf-8"))
    # Get the hexadecimal digest of the hash
    hex_dig = hash_object.hexdigest()
    return hex_dig


@wait_for_task_completion
def add_embeddings_to_db(client: Client, index_name: str, embeddings):
    index = client.index(index_name)
    payload_data = [
        {
            "id": hash_text_sha1(e.text),
            "text": e.text,
            "source": e.source,
            "library": e.package_name,
            "_vectors": {VECOR_NAME: e.embedding},
        }
        for e in embeddings
    ]
    task_info = index.add_documents(payload_data)
    return client, task_info
