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

import json
import re
from collections import Counter

import httpx
import pytest

from doc_builder.external_links import check_external_urls
from doc_builder.github_links import GithubTarget, github_target, graphql_query

# A tiny fake GitHub.
REPOS = {
    ("org", "public"): {"private": False, "objects": {"main:README.md": "Blob", "main:docs": "Tree"}, "issues": {7}},
    ("org", "secret"): {"private": True, "objects": {"main:README.md": "Blob"}, "issues": set()},
}
# GraphQL resolves an old name to the new repo, github.com only redirects some pages.
RENAMES = {("old-org", "public"): ("org", "public")}
OWNERS = {"org"}
# What github.com serves to anonymous readers. It also knows pages the fast
# paths do not, such as a renamed branch it redirects.
PUBLIC_PAGES = {
    "/org",
    "/org/public",
    "/org/public/blob/main/README.md",
    "/org/public/tree/main/docs",
    "/org/public/issues/7",
    "/org/public/blob/master/README.md",
    "/org/public/releases",
}


class FakeGithub:
    def __init__(self, graphql_status: int = 200):
        self.graphql_status = graphql_status
        self.requests = Counter()
        self.pages: set[str] = set()

    def __call__(self, request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        if host == "api.github.com":
            self.requests["graphql"] += 1
            return self.graphql(json.loads(request.content))
        if host == "raw.githubusercontent.com":
            self.requests["raw"] += 1
            owner, repo, ref, *rest = path.strip("/").split("/")
            repo_data = REPOS.get((owner, repo))
            found = repo_data and not repo_data["private"] and repo_data["objects"].get(f"{ref}:{'/'.join(rest)}")
            return httpx.Response(200 if found == "Blob" else 404)
        assert host == "github.com"
        if path.endswith(".git/info/refs"):
            self.requests["info/refs"] += 1
            owner, repo = path.strip("/").removesuffix(".git/info/refs").split("/")
            repo_data = REPOS.get((owner, repo))
            return httpx.Response(200 if repo_data and not repo_data["private"] else 401)
        self.pages.add(path)
        return httpx.Response(200 if path in PUBLIC_PAGES else 404)

    def graphql(self, body: dict) -> httpx.Response:
        if self.graphql_status != 200:
            return httpx.Response(self.graphql_status, json={"message": "Bad credentials"})
        variables, data = body["variables"], {}
        for field in re.split(r" (?=u\d+: )", body["query"]):
            alias = re.search(r"u(\d+): ", field)
            if alias is None:  # the "query(...) {" header
                continue
            index = alias.group(1)
            if "repositoryOwner(" in field:
                data[f"u{index}"] = {"login": variables[f"o{index}"]} if variables[f"o{index}"] in OWNERS else None
                continue
            name = (variables[f"o{index}"], variables[f"n{index}"])
            name = RENAMES.get(name, name)
            repo_data = REPOS.get(name)
            if repo_data is None:
                data[f"u{index}"] = None
                continue
            value = {"nameWithOwner": "/".join(name), "isPrivate": repo_data["private"]}
            if f"$e{index}" in field:
                kind = repo_data["objects"].get(variables[f"e{index}"])
                value["object"] = {"__typename": kind} if kind else None
            if number := re.search(r"issueOrPullRequest\(number: (\d+)\)", field):
                value["issueOrPullRequest"] = (
                    {"__typename": "Issue"} if int(number[1]) in repo_data["issues"] else None
                )
            data[f"u{index}"] = value
        return httpx.Response(200, json={"data": data})


URLS = {
    "https://github.com/org": "ok",
    "https://github.com/org/public": "ok",
    "https://github.com/org/public/blob/main/README.md": "ok",
    "https://github.com/org/public/tree/main/docs": "ok",
    "https://github.com/org/public/issues/7": "ok",
    # GraphQL and raw do not follow branch renames, github.com does.
    "https://github.com/org/public/blob/master/README.md": "ok",
    # Shapes with no fast path go straight to github.com.
    "https://github.com/org/public/releases": "ok",
    "https://github.com/org/public/blob/main/MISSING.md": "broken",
    "https://github.com/org/public/issues/8": "broken",
    "https://github.com/org/gone": "broken",
    # The token can see this private repo, readers cannot.
    "https://github.com/org/secret": "broken",
    "https://github.com/org/secret/blob/main/README.md": "broken",
    # github.com does not redirect issue pages of a renamed repo.
    "https://github.com/old-org/public/issues/7": "broken",
}


def check(fake: FakeGithub) -> dict[str, str]:
    statuses = check_external_urls(URLS, transport=httpx.MockTransport(fake), retries=0)
    return {url: status.outcome for url, status in statuses.items()}


def test_github_target():
    assert github_target("https://github.com/org") == GithubTarget("owner", "org")
    assert github_target("https://github.com/org/repo.git") == GithubTarget("repo", "org", "repo")
    assert github_target("https://github.com/org/repo/blob/main/My%20Dir/a.py") == GithubTarget(
        "blob", "org", "repo", ref="main", path="My Dir/a.py"
    )
    assert github_target("https://github.com/org/repo/tree/main") == GithubTarget("tree", "org", "repo", ref="main")
    assert github_target("https://github.com/org/repo/pull/3") == GithubTarget("issue", "org", "repo", number=3)
    assert github_target("https://github.com/org/repo/pull/3/files") is None
    assert github_target("https://github.com/org/repo/releases") is None
    assert github_target("https://github.com/org/repo/issues?q=bug") is None
    assert github_target("https://gitlab.com/org/repo") is None


def test_graphql_query_passes_values_as_variables():
    body = graphql_query([GithubTarget("blob", "org", "repo", ref="main", path='a "quoted" path.py')])
    assert '"quoted"' not in body["query"]
    assert body["variables"] == {"o0": "org", "n0": "repo", "e0": 'main:a "quoted" path.py'}


def test_github_links_with_token(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    fake = FakeGithub()
    assert check(fake) == URLS
    assert fake.requests["graphql"] == 1
    # Only what GraphQL could not confirm reaches github.com pages.
    assert fake.pages == {
        "/org/public/blob/master/README.md",
        "/org/public/releases",
        "/org/public/blob/main/MISSING.md",
        "/org/public/issues/8",
        "/org/gone",
        "/org/secret",
        "/org/secret/blob/main/README.md",
        "/old-org/public/issues/7",
    }


def test_github_links_without_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    fake = FakeGithub()
    assert check(fake) == URLS
    assert fake.requests["graphql"] == 0
    assert fake.requests["info/refs"] == 3
    assert fake.requests["raw"] == 4


def test_github_links_with_rejected_token(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "expired-token")
    fake = FakeGithub(graphql_status=401)
    assert check(fake) == URLS
    assert fake.requests["info/refs"] == 3


@pytest.mark.parametrize("env_var", ["GITHUB_TOKEN", "GH_TOKEN"])
def test_github_token_env_vars(monkeypatch, env_var):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setenv(env_var, "test-token")
    fake = FakeGithub()
    check(fake)
    assert fake.requests["graphql"] == 1
