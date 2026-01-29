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
EMBEDDINGS_TRACKER_REPO = "hf-doc-build/doc-builder-embeddings-tracker"


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


def find_stale_ids(chunks: list, existing_ids: set[str], existing_dataset=None) -> set[str]:
    """
    Find document IDs that are stale (page was updated or deleted).

    Handles two cases:
    1. Page updated: content hash changes, old ID should be removed
    2. Page deleted: all IDs for that page should be removed

    Args:
        chunks: List of current Chunk objects
        existing_ids: Set of document IDs that exist in the tracker
        existing_dataset: Optional dataset with library info for detecting deleted pages

    Returns:
        Set of stale document IDs that should be removed
    """
    from .meilisearch_helper import sanitize_for_id

    # Build a mapping of (library, page) -> set of current IDs
    current_ids_by_page: dict[tuple[str, str], set[str]] = {}
    for chunk in chunks:
        doc_id = generate_doc_id(chunk.package_name, chunk.page, chunk.text)
        key = (chunk.package_name, chunk.page)
        if key not in current_ids_by_page:
            current_ids_by_page[key] = set()
        current_ids_by_page[key].add(doc_id)

    # Build set of all current IDs
    all_current_ids = set()
    for ids in current_ids_by_page.values():
        all_current_ids.update(ids)

    # Build set of current prefixes (library-page combinations)
    current_prefixes = set()
    for library, page in current_ids_by_page.keys():
        prefix = f"{sanitize_for_id(library)}-{sanitize_for_id(page)}"
        current_prefixes.add(prefix)

    # Find stale IDs
    stale_ids = set()
    for existing_id in existing_ids:
        # Skip if this ID is still current
        if existing_id in all_current_ids:
            continue

        # Parse the existing ID to extract prefix (library-page)
        # Format: {library}-{page}-{hash}
        # The hash is always 8 characters at the end
        parts = existing_id.rsplit("-", 1)
        if len(parts) != 2 or len(parts[1]) != 8:
            continue

        prefix = parts[0]  # library-page part

        # Check if this prefix still exists in current pages
        if prefix in current_prefixes:
            # Page still exists but content changed (updated page)
            stale_ids.add(existing_id)
        else:
            # Check if this is a page from a library we're currently processing
            # We only want to delete pages from libraries that are in our current chunks
            # to avoid deleting pages from libraries we didn't process
            current_libraries = {sanitize_for_id(lib) for lib, _ in current_ids_by_page.keys()}

            # Extract library from prefix (everything before the first underscore after library name)
            # This is tricky because both library and page can have underscores
            # We need to check if any current library is a prefix of this ID's prefix
            for lib in current_libraries:
                if prefix.startswith(f"{lib}-"):
                    # This is a deleted page from a library we're processing
                    stale_ids.add(existing_id)
                    break

    return stale_ids


def update_tracker_dataset(
    new_embeddings: list,
    existing_ids: set[str],
    hf_token: str,
    stale_ids: set[str] | None = None,
    repo_id: str = EMBEDDINGS_TRACKER_REPO,
):
    """
    Update the tracker dataset: add new document IDs and remove stale ones.

    Args:
        new_embeddings: List of Embedding objects that were just added
        existing_ids: Set of existing document IDs
        hf_token: HuggingFace token for pushing
        stale_ids: Set of document IDs to remove (updated pages)
        repo_id: The HuggingFace dataset repository ID
    """
    from .meilisearch_helper import generate_doc_id

    if stale_ids is None:
        stale_ids = set()

    # Create entries for new documents
    new_entries = []
    for e in new_embeddings:
        doc_id = generate_doc_id(e.library, e.page, e.text)
        new_entries.append(
            {
                "id": doc_id,
                "library": e.library,
                "source_page_url": e.source_page_url,
            }
        )

    if not new_entries and not stale_ids:
        print("No changes to tracker dataset")
        return

    # Combine with existing entries (excluding stale ones)
    all_entries = []

    # Try to load existing dataset
    try:
        existing_dataset = load_dataset(repo_id, split="train")
        for i in range(len(existing_dataset)):
            entry_id = existing_dataset[i]["id"]
            # Skip stale IDs
            if entry_id in stale_ids:
                continue
            all_entries.append(
                {
                    "id": entry_id,
                    "library": existing_dataset[i]["library"],
                    "source_page_url": existing_dataset[i].get("source_page_url", ""),
                }
            )
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
    if stale_ids:
        print(f"  (removed {len(stale_ids)} stale entries)")
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
    return [generate_doc_id(chunk.package_name, chunk.page, chunk.text) for chunk in chunks]
