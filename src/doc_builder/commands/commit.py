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
import base64
from pathlib import Path

import requests
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportQueryError


def get_head_oid(repo_id, token, branch="main"):
    """
    Returns last commit sha from repostory `repo_id` & branch `branch`
    """
    res = requests.get(
        f"https://api.github.com/repos/{repo_id}/git/refs/heads/{branch}",
        headers={"Authorization": f"bearer {token}"},
    )
    if res.status_code == 200:
        res_json = res.json()
        head_oid = res_json["object"]["sha"]
        return head_oid
    else:
        raise Exception(f"get_head_oid failed: {res.message}")


def create_additions(path_to_built_docs):
    """
    Given `path_to_built_docs` dir, returns [FileAddition!]!: [{path: "some_path", contents: "base64_repr_contents"}, ...]
    see more here: https://docs.github.com/en/graphql/reference/input-objects#filechanges
    """
    p = Path(path_to_built_docs)
    files = [x for x in p.glob("**/*") if x.is_file()]
    additions = []

    for fpath in files:
        with open(fpath, "rb") as reader:
            content = reader.read()
            content_base64 = base64.b64encode(content)
            content_base64 = str(content_base64, "utf-8")
            additions.append({"path": str(fpath), "contents": content_base64})

    return additions


def commit_additions(additions, repo_id, head_oid, token, commit_msg):
    """
    Commits additions to a repository using Github GraphQL mutation `createCommitOnBranch`
    see more here: https://docs.github.com/en/graphql/reference/mutations#createcommitonbranch
    """
    # Select your transport with a defined url endpoint
    transport = AIOHTTPTransport(url="https://api.github.com/graphql", headers={"Authorization": f"bearer {token}"})
    # Create a GraphQL client using the defined transport
    client = Client(transport=transport, fetch_schema_from_transport=True)
    # Provide a GraphQL query
    query = gql(
        """
  mutation ($repo_id: String!, $additions: [FileAddition!]!, $head_oid: GitObjectID!, $commit_msg: String!) {
    createCommitOnBranch(
      input: {
        branch:{
          repositoryNameWithOwner: $repo_id,
          branchName: "main"
        },
        message: {
          headline: $commit_msg
        },
        fileChanges: {
          additions: $additions
        },
        expectedHeadOid: $head_oid
      }
    ) {
      clientMutationId
    }
  }
  """
    )
    # Execute the query on the transport
    params = {"additions": additions, "repo_id": repo_id, "head_oid": head_oid, "commit_msg": commit_msg}
    result = client.execute(query, variable_values=params)
    return result


def commit_command(args):
    """
    Commit file additions using Github GraphQL rather than `git`.
    Usage: doc-builder commit $args
    """
    number_of_retries = 5
    additions_str = create_additions(args.path_to_built_docs)
    while number_of_retries:
        try:
            head_oid = get_head_oid(args.doc_build_repo_id, args.token)
            commit_additions(additions_str, args.doc_build_repo_id, head_oid, args.token, args.commit_msg)
            break
        except TransportQueryError as e:
            error_msg = str(e)
            if "Expected branch to point to" in error_msg:
                number_of_retries -= 1
                print(f"Failed on try #{6-number_of_retries}, pushing again")


def commit_command_parser(subparsers=None):
    if subparsers is not None:
        parser = subparsers.add_parser("commit")
    else:
        parser = argparse.ArgumentParser("Doc Builder commit command")

    parser.add_argument(
        "path_to_built_docs",
        type=str,
        help="The path where built doc artifacts reside in",
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

    if subparsers is not None:
        parser.set_defaults(func=commit_command)
    return parser
