import hashlib
import sys
from datetime import datetime
from functools import wraps
from time import sleep
from typing import Callable, Optional, Tuple

from meilisearch.client import Client, TaskInfo


# References:
# https://www.meilisearch.com/docs/learn/experimental/vector_search
# https://github.com/meilisearch/meilisearch-python/blob/d5a0babe50b4ce5789892845db98b30d4db72203/tests/index/test_index_search_meilisearch.py#L491-L493
# https://github.com/meilisearch/meilisearch-python/blob/d5a0babe50b4ce5789892845db98b30d4db72203/tests/conftest.py#L132-L146

VECTOR_NAME = "embeddings"
VECTOR_DIM = 768  # dim of https://huggingface.co/BAAI/bge-base-en-v1.5

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
            sleep(20)

    return wrapped_meilisearch_function


def wait_for_all_addition_tasks(client: Client, index_name: str):
    """
    Wait for all document addition/update tasks to finish for a specific index
    """
    print(f"Waiting for all addition tasks on index '{index_name}' to finish...")

    # Keep checking until there are no more tasks to process
    while True:
        # Get processing tasks for the specific index
        task_params = {
            "indexUids": [index_name],
            "types": ["documentAdditionOrUpdate"],
            "statuses": ["enqueued", "processing"],
        }

        processing_tasks = client.get_tasks(task_params)

        if len(processing_tasks.results) == 0:
            break

        print(f"Found {len(processing_tasks.results)} tasks still processing on index '{index_name}', waiting...")
        # Wait for one minute before retrying
        sleep(60)

    # Get all failed tasks for the specific index
    failed_task_ids = []
    from_task = None

    while True:
        failed_params = {"indexUids": [index_name], "types": ["documentAdditionOrUpdate"], "statuses": ["failed"]}

        # Only add 'from' parameter if from_task is not None and is a valid integer
        if from_task is not None and isinstance(from_task, int):
            failed_params["from"] = from_task

        try:
            failed_tasks = client.get_tasks(failed_params)
        except Exception as e:
            print(f"Error getting failed tasks: {e}")
            break

        if len(failed_tasks.results) > 0:
            failed_task_ids.extend([task.task_uid for task in failed_tasks.results])

        # Check if there are more results to fetch
        # Handle the 'next' attribute more carefully
        if hasattr(failed_tasks, "next") and failed_tasks.next is not None:
            # Ensure next is an integer before using it
            if isinstance(failed_tasks.next, int):
                from_task = failed_tasks.next
            else:
                print(f"Warning: 'next' field is not an integer: {failed_tasks.next}")
                break
        else:
            break

    if failed_task_ids:
        print(f"Failed addition task IDs on index '{index_name}': {failed_task_ids}")

    print(f"Finished waiting for addition tasks on index '{index_name}' to finish.")


@wait_for_task_completion
def create_embedding_db(client: Client, index_name: str):
    index = client.index(index_name)
    task_info = index.update_embedders({VECTOR_NAME: {"source": "userProvided", "dimensions": VECTOR_DIM}})
    return client, task_info


@wait_for_task_completion
def update_db_settings(client: Client, index_name: str):
    index = client.index(index_name)
    task_info = index.update_settings(
        {
            "searchableAttributes": ["heading1", "heading2", "heading3", "heading4", "heading5", "text"],
            "filterableAttributes": ["product"],
        }
    )
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
            "source_page_url": e.source_page_url,
            "source_page_title": e.source_page_title,
            "product": e.library,
            "heading1": e.heading1,
            "heading2": e.heading2,
            "heading3": e.heading3,
            "heading4": e.heading4,
            "heading5": e.heading5,
            "_vectors": {VECTOR_NAME: e.embedding},
        }
        for e in embeddings
    ]
    task_info = index.add_documents(payload_data)
    return client, task_info


def swap_indexes(
    client: Client,
    index1_name: str,
    index2_name: str,
    temp_index_name: Optional[str] = None,
):
    """
    Swap indexes and wait for all addition tasks to complete on the temporary index first

    Args:
        client: MeiliSearch client
        index1_name: First index name
        index2_name: Second index name
        temp_index_name: Name of the temporary index to wait for additions on. If None, defaults to index2_name
    """
    # Determine which index is the temporary one
    temp_index = temp_index_name if temp_index_name is not None else index2_name

    # Wait for all addition tasks on the temporary index to complete before swapping
    wait_for_all_addition_tasks(client, temp_index)

    print(f"Starting index swap between '{index1_name}' and '{index2_name}'...")

    # Perform the swap
    task_info = client.swap_indexes([{"indexes": [index1_name, index2_name]}])

    # Wait for the swap task itself to complete
    task_id = task_info.task_uid
    while True:
        task = client.get_task(task_id)
        if task.status == "failed":
            error_message = task.error.get("message") if task.error else "Unknown error"
            error_type = task.error.get("type") if task.error else "Unknown"
            error_link = task.error.get("link") if task.error else "No additional information"
            raise Exception(
                f"Swap task {task_id} failed with error type '{error_type}': {error_message}. More info: {error_link}"
            )
        if task.status == "succeeded":
            break
        sleep(60 * 2)  # wait for 2 minutes

    print(f"Index swap between '{index1_name}' and '{index2_name}' completed successfully.")

    return task


# see https://www.meilisearch.com/docs/learn/core_concepts/documents#upload
MEILISEARCH_PAYLOAD_MAX_MB = 95


def get_meili_chunks(obj_list):
    # Convert max_chunk_size_mb to bytes
    max_chunk_size_bytes = MEILISEARCH_PAYLOAD_MAX_MB * 1024 * 1024

    chunks = []
    current_chunk = []
    current_chunk_size = 0

    for obj in obj_list:
        obj_size = sys.getsizeof(obj)

        if current_chunk_size + obj_size > max_chunk_size_bytes:
            # If adding this object exceeds the chunk size, start a new chunk
            chunks.append(current_chunk)
            current_chunk = [obj]
            current_chunk_size = obj_size
        else:
            # Add the object to the current chunk
            current_chunk.append(obj)
            current_chunk_size += obj_size

    # Don't forget to add the last chunk if it contains any objects
    if current_chunk:
        chunks.append(current_chunk)

    return chunks
