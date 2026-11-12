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

"""
Fast paths for github.com links, which github.com rate-limits hard.

A fast path can only confirm that a URL exists. The checker requests any URL
the fast paths do not confirm from github.com as usual, so only a real
github.com response can mark a link broken. This module never has to know
GitHub's redirect rules for renamed repos, renamed branches or transferred
issues.

1. With a token (GITHUB_TOKEN or GH_TOKEN), one GraphQL query resolves up to
   100 URLs. It never confirms a private repo, which the token can see but
   readers cannot. It also never confirms a renamed or transferred repo.
   GraphQL follows the rename, but github.com does not redirect every page of
   the old name, and issue pages answer 404.
2. Without a token, or for URLs GraphQL did not confirm, git's `info/refs`
   endpoint checks repository roots and raw.githubusercontent.com checks files.
   Neither shares github.com's page rate limit.
"""

import asyncio
import os
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import quote, unquote, urlsplit

import httpx

GITHUB_HOSTS = frozenset({"github.com", "www.github.com"})
GRAPHQL_URL = "https://api.github.com/graphql"
GIT_BASE_URL = "https://github.com"
RAW_BASE_URL = "https://raw.githubusercontent.com"
GRAPHQL_BATCH_SIZE = 100
# GitHub discourages many concurrent GraphQL requests (secondary rate limits).
GRAPHQL_CONCURRENCY = 4
# info/refs and raw.githubusercontent.com showed no rate limiting at 32 concurrent requests.
TOKEN_FREE_CONCURRENCY = 32


@dataclass(frozen=True)
class GithubTarget:
    """What a github.com URL points at."""

    kind: str  # "owner", "repo", "blob", "tree" or "issue"
    owner: str
    repo: str = ""
    ref: str = ""
    path: str = ""
    number: int = 0


def github_token() -> str | None:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or None


def github_target(url: str) -> GithubTarget | None:
    """Parse a github.com URL into a shape the fast paths understand, or None."""
    parts = urlsplit(url)
    if parts.netloc not in GITHUB_HOSTS or parts.query:
        return None
    segments = [unquote(segment) for segment in parts.path.split("/") if segment]
    if len(segments) == 1:
        return GithubTarget("owner", segments[0])
    if len(segments) < 2:
        return None
    owner, repo = segments[0], segments[1].removesuffix(".git")
    if len(segments) == 2:
        return GithubTarget("repo", owner, repo)
    kind, rest = segments[2], segments[3:]
    if kind == "blob" and len(rest) >= 2:
        return GithubTarget("blob", owner, repo, ref=rest[0], path="/".join(rest[1:]))
    if kind == "tree" and rest:
        return GithubTarget("tree", owner, repo, ref=rest[0], path="/".join(rest[1:]))
    # graphql_query inlines the number as a GraphQL Int. It must fit in 32 bits,
    # or the whole batch fails to parse.
    if kind in ("issues", "pull") and len(rest) == 1 and rest[0].isdigit() and int(rest[0]) < 2**31:
        return GithubTarget("issue", owner, repo, number=int(rest[0]))
    return None


def _graphql_field(index: int, target: GithubTarget) -> tuple[str, dict[str, str]]:
    """Return one aliased GraphQL field and its variables.

    Paths and refs go in as variables, not inline literals, so they need no
    GraphQL string escaping.
    """
    alias = f"u{index}"
    if target.kind == "owner":
        return f"{alias}: repositoryOwner(login: $o{index}) {{ login }}", {f"o{index}": target.owner}
    variables = {f"o{index}": target.owner, f"n{index}": target.repo}
    if target.kind == "repo":
        inner = "nameWithOwner isPrivate"
    elif target.kind in ("blob", "tree"):
        inner = f"nameWithOwner isPrivate object(expression: $e{index}) {{ __typename }}"
        variables[f"e{index}"] = f"{target.ref}:{target.path}"
    else:
        inner = f"nameWithOwner isPrivate issueOrPullRequest(number: {target.number}) {{ __typename }}"
    return f"{alias}: repository(owner: $o{index}, name: $n{index}) {{ {inner} }}", variables


def _graphql_confirms(target: GithubTarget, data: dict | None) -> bool:
    if data is None:
        return False
    if target.kind == "owner":
        return True
    if data.get("isPrivate"):
        return False
    if str(data.get("nameWithOwner", "")).lower() != f"{target.owner}/{target.repo}".lower():
        return False
    if target.kind == "repo":
        return True
    if target.kind in ("blob", "tree"):
        found = data.get("object")
        return found is not None and found.get("__typename") == ("Blob" if target.kind == "blob" else "Tree")
    return data.get("issueOrPullRequest") is not None


def graphql_query(targets: list[GithubTarget]) -> dict:
    """Build one GraphQL request body that resolves every target."""
    fields, variables = [], {}
    for index, target in enumerate(targets):
        field, field_variables = _graphql_field(index, target)
        fields.append(field)
        variables.update(field_variables)
    declarations = ", ".join(f"${name}: String!" for name in variables)
    query = f"query({declarations}) {{ {' '.join(fields)} }}" if declarations else f"query {{ {' '.join(fields)} }}"
    return {"query": query, "variables": variables}


async def confirmed(client: httpx.AsyncClient, urls: Iterable[str]) -> set[str]:
    """Return the URLs a fast path confirmed exist. It never raises.

    URLs with no fast path are never in the result. GraphQL runs first when a
    token is set, then the token-free check covers what GraphQL did not confirm.
    """
    targets = {url: target for url in urls if (target := github_target(url)) is not None}
    found: set[str] = set()
    token = github_token()
    if token:
        items = list(targets.items())
        semaphore = asyncio.Semaphore(GRAPHQL_CONCURRENCY)
        batches = [items[start : start + GRAPHQL_BATCH_SIZE] for start in range(0, len(items), GRAPHQL_BATCH_SIZE)]
        answers = await asyncio.gather(
            *(_graphql_confirmed(client, token, [target for _, target in batch], semaphore) for batch in batches)
        )
        for batch, oks in zip(batches, answers, strict=True):
            found.update(url for (url, _), ok in zip(batch, oks, strict=True) if ok)

    rest = [(url, target) for url, target in targets.items() if url not in found]
    semaphore = asyncio.Semaphore(TOKEN_FREE_CONCURRENCY)
    oks = await asyncio.gather(*(_token_free_confirmed(client, target, semaphore) for _, target in rest))
    found.update(url for (url, _), ok in zip(rest, oks, strict=True) if ok)
    return found


async def _graphql_confirmed(
    client: httpx.AsyncClient, token: str, targets: list[GithubTarget], semaphore: asyncio.Semaphore
) -> list[bool]:
    """Return, for each target, whether GraphQL confirmed it exists. It never raises."""
    try:
        async with semaphore:
            response = await client.post(
                GRAPHQL_URL, json=graphql_query(targets), headers={"Authorization": f"bearer {token}"}
            )
        # Missing objects come back as null data next to an "errors" list, which is
        # expected. Anything else unusual (bad token, rate limit) confirms nothing.
        data = (response.json().get("data") or {}) if response.status_code == 200 else {}
    except (httpx.HTTPError, ValueError):
        data = {}
    return [_graphql_confirms(target, data.get(f"u{index}")) for index, target in enumerate(targets)]


def _token_free_url(target: GithubTarget) -> tuple[str, str] | None:
    owner, repo = quote(target.owner), quote(target.repo)
    if target.kind == "repo":
        # This endpoint rejects HEAD with a 405, so it needs a GET. The stream
        # never reads the body, which lists every ref in the repo.
        return "GET", f"{GIT_BASE_URL}/{owner}/{repo}.git/info/refs?service=git-upload-pack"
    if target.kind == "blob":
        # raw.githubusercontent.com resolves refs that contain slashes the same way github.com does.
        return "HEAD", f"{RAW_BASE_URL}/{owner}/{repo}/{quote(target.ref + '/' + target.path)}"
    return None


async def _token_free_confirmed(client: httpx.AsyncClient, target: GithubTarget, semaphore: asyncio.Semaphore) -> bool:
    """Check a repo root or file without a token. It never raises."""
    request = _token_free_url(target)
    if request is None:
        return False
    method, url = request
    try:
        async with semaphore, client.stream(method, url) as response:
            return response.status_code == 200
    except httpx.HTTPError:
        return False
