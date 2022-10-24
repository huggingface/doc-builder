# coding=utf-8
# Copyright 2022 The HuggingFace Team. All rights reserved.
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

import argparse
import logging
from pathlib import Path
from time import sleep, time

from huggingface_hub import CommitOperationDelete, HfApi


def delete_folder(repo_id, folder_path_in_repo, token, commit_message="Delete folder"):
    api = HfApi()
    repo_files = api.list_repo_files(repo_id)
    files_to_delete = [rf for rf in repo_files if rf.startswith(folder_path_in_repo)]
    delete_operations = [CommitOperationDelete(path_in_repo=rf) for rf in files_to_delete]
    api.create_commit(
        repo_id=repo_id,
        operations=delete_operations,
        commit_message=commit_message,
        token=token,
    )


def push_command(args):
    """
    Commit file additions and/or deletions using Github GraphQL rather than `git`.
    Usage: doc-builder push $args
    """
    if args.n_retries < 1:
        raise ValueError(f"CLI arg `n_retries` MUST be positive & non-zero; supplied value was {args.n_retries}")
    if args.is_remove:
        push_command_remove(args)
    else:
        push_command_add(args)


def push_command_add(args):
    """
    Commit file changes (additions & deletions) using Github GraphQL rather than `git`.
    Used in: build_main_documentation.yml & build_pr_documentation.yml
    """
    max_n_retries = args.n_retries + 1
    number_of_retries = args.n_retries
    n_seconds_sleep = 5

    library_name = args.library_name
    path_docs_built = Path(library_name)
    doc_version_folder = next(filter(lambda x: not x.is_file(), path_docs_built.glob("*")), None).relative_to(
        path_docs_built
    )
    doc_version_folder = str(doc_version_folder)

    folder_path = f"{library_name}/{doc_version_folder}"
    api = HfApi()

    time_start = time()
    while number_of_retries:
        try:
            delete_folder(
                args.doc_build_repo_id, folder_path, args.token, commit_message=f"Deleteions: {args.commit_msg}"
            )
            api.upload_folder(
                repo_id=args.doc_build_repo_id,
                folder_path=folder_path,
                path_in_repo=folder_path,
                commit_message=args.commit_msg,
                token=args.token,
            )
            break
        except Exception as e:
            number_of_retries -= 1
            print(f"createCommitOnBranch error occurred: {e}")
            if number_of_retries:
                print(f"Failed on try #{max_n_retries-number_of_retries}, pushing again in {n_seconds_sleep} seconds")
                sleep(n_seconds_sleep)
            else:
                raise RuntimeError("create_commit additions failed") from e

    time_end = time()
    logging.debug(f"commit_additions took {time_end-time_start:.4f} seconds or {(time_end-time_start)/60.0:.2f} mins")


def push_command_remove(args):
    """
    Commit file deletions only using Github GraphQL rather than `git`.
    Used in: delete_doc_comment.yml
    """
    max_n_retries = args.n_retries + 1
    number_of_retries = args.n_retries
    n_seconds_sleep = 5

    library_name = args.library_name
    doc_version_folder = args.doc_version
    doc_build_repo_id = args.doc_build_repo_id
    commit_msg = args.commit_msg

    folder_path = f"{library_name}/{doc_version_folder}"

    while number_of_retries:
        try:
            delete_folder(doc_build_repo_id, folder_path, args.token, commit_message=commit_msg)
            break
        except Exception as e:
            number_of_retries -= 1
            print(f"createCommitOnBranch error occurred: {e}")
            if number_of_retries:
                print(f"Failed on try #{max_n_retries-number_of_retries}, pushing again in {n_seconds_sleep} seconds")
                sleep(n_seconds_sleep)
            else:
                raise RuntimeError("create_commit additions failed") from e


def push_command_parser(subparsers=None):
    if subparsers is not None:
        parser = subparsers.add_parser("push")
    else:
        parser = argparse.ArgumentParser("Doc Builder push command")

    parser.add_argument(
        "library_name",
        type=str,
        help="The name of the library, which also acts as a path where built doc artifacts reside in",
    )
    parser.add_argument(
        "--doc_build_repo_id",
        type=str,
        help="Repo to which doc artifcats will be committed (e.g. `huggingface/doc-build-dev`)",
    )
    parser.add_argument("--token", type=str, help="Github token that has write/push premission to `doc_build_repo_id`")
    parser.add_argument(
        "--commit_msg",
        type=str,
        help="Git commit message",
        default="Github GraphQL createcommitonbranch commit",
    )
    parser.add_argument("--n_retries", type=int, help="Number of push retries in the event of conflict", default=1)
    parser.add_argument(
        "--doc_version",
        type=str,
        default=None,
        help="Version of the generated documentation.",
    )
    parser.add_argument(
        "--is_remove",
        action="store_true",
        help="Whether or not to remove entire folder ('--doc_version') from git tree",
    )

    if subparsers is not None:
        parser.set_defaults(func=push_command)
    return parser
