# Copyright 2021 The HuggingFace Team. All rights reserved.
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

"""
Utilities for tracking document embeddings using a HuggingFace dataset.
This enables incremental updates - only processing documents that have changed.
"""

from datasets import Dataset, load_dataset

from .meilisearch_helper import generate_doc_id

# Dataset repository for tracking embeddings
EMBEDDINGS_TRACKER_REPO = "huggingface/doc-builder-embeddings-tracker"


def fetch_existing_doc_ids(repo_id: str = EMBEDDINGS_TRACKER_REPO) -> set[str]:
    """
    Fetch all existing document IDs from the HuggingFace dataset.
    
    Args:
        repo_id: The HuggingFace dataset repository ID
        
    Returns:
        Set of document IDs that already have embeddings
    """
    try:
        print(f"Fetching existing document IDs from {repo_id}...")
        dataset = load_dataset(repo_id, split="train")
        existing_ids = set(dataset["id"])
        print(f"Found {len(existing_ids)} existing document IDs")
        return existing_ids
    except Exception as e:
        print(f"Warning: Could not fetch existing IDs from {repo_id}: {e}")
        print("Assuming no existing documents - will process all chunks")
        return set()


def filter_new_chunks(chunks: list, existing_ids: set[str]) -> tuple[list, list]:
    """
    Filter chunks to only include those that don't already have embeddings.
    
    Args:
        chunks: List of Chunk objects
        existing_ids: Set of document IDs that already exist
        
    Returns:
        Tuple of (new_chunks, existing_chunks)
    """
    new_chunks = []
    existing_chunks = []
    
    for chunk in chunks:
        doc_id = generate_doc_id(chunk.package_name, chunk.page, chunk.text)
        if doc_id in existing_ids:
            existing_chunks.append(chunk)
        else:
            new_chunks.append(chunk)
    
    return new_chunks, existing_chunks


def update_tracker_dataset(
    new_embeddings: list,
    existing_ids: set[str],
    hf_token: str,
    repo_id: str = EMBEDDINGS_TRACKER_REPO,
):
    """
    Update the tracker dataset with new document IDs.
    
    Args:
        new_embeddings: List of Embedding objects that were just added
        existing_ids: Set of existing document IDs
        hf_token: HuggingFace token for pushing
        repo_id: The HuggingFace dataset repository ID
    """
    from .meilisearch_helper import generate_doc_id
    
    # Create entries for new documents
    new_entries = []
    for e in new_embeddings:
        doc_id = generate_doc_id(e.library, e.page, e.text)
        new_entries.append({
            "id": doc_id,
            "library": e.library,
            "source_page_url": e.source_page_url,
        })
    
    if not new_entries:
        print("No new entries to add to tracker dataset")
        return
    
    # Combine with existing entries
    all_entries = []
    
    # Try to load existing dataset
    try:
        existing_dataset = load_dataset(repo_id, split="train")
        for i in range(len(existing_dataset)):
            all_entries.append({
                "id": existing_dataset[i]["id"],
                "library": existing_dataset[i]["library"],
                "source_page_url": existing_dataset[i].get("source_page_url", ""),
            })
    except Exception:
        print("Creating new tracker dataset")
    
    # Add new entries
    all_entries.extend(new_entries)
    
    # Deduplicate by ID
    seen_ids = set()
    unique_entries = []
    for entry in all_entries:
        if entry["id"] not in seen_ids:
            seen_ids.add(entry["id"])
            unique_entries.append(entry)
    
    # Create and push dataset
    dataset = Dataset.from_list(unique_entries)
    print(f"Pushing updated tracker dataset with {len(dataset)} entries...")
    dataset.push_to_hub(repo_id, token=hf_token, private=False)
    print(f"Successfully updated tracker dataset at {repo_id}")


def get_chunk_ids(chunks: list) -> list[str]:
    """
    Generate document IDs for a list of chunks without computing embeddings.
    
    Args:
        chunks: List of Chunk objects
        
    Returns:
        List of document IDs
    """
    return [
        generate_doc_id(chunk.package_name, chunk.page, chunk.text)
        for chunk in chunks
    ]
