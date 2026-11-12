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
Fast external link checking.

A single asyncio event loop requests every unique URL (without its fragment)
once. Each host gets its own concurrency limit.
"""

import asyncio
import email.utils
import math
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import timezone
from urllib.parse import urlsplit, urlunsplit

import httpx

from doc_builder import github_links

DEFAULT_IGNORE_PATTERNS = (
    r"^https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])([:/]|$)",
    r"^https?://([^/]+\.)?example\.(com|org|net)([:/]|$)",
)

_HUB_HOSTS = frozenset({"huggingface.co", "hf.co"})
# First path segments of Hub pages that are not repos. No user or org can take these names.
_HUB_NON_REPO_PATHS = frozenset(
    {"api", "blog", "collections", "docs", "join", "learn", "login", "models", "new", "new-dataset", "new-space"}
    | {"notifications", "organizations", "papers", "posts", "pricing", "settings", "tasks"}
)
# Hub sections that answer 401 to anonymous readers even though the page exists.
_HUB_SIGN_IN_PATHS = frozenset({"new", "new-dataset", "new-space", "notifications", "settings"})
DEFAULT_PER_HOST_CONCURRENCY = 8
# Hub pages take about 300 ms each to render and showed no 429s at 32
# concurrent HEADs, which halves the Hub's share of a Transformers run.
HOST_CONCURRENCY = dict.fromkeys(_HUB_HOSTS, 32)
_USER_AGENT = "Mozilla/5.0 (compatible; hf-doc-builder link checker)"
_MAX_RETRY_AFTER = 30.0


@dataclass(frozen=True)
class ExternalLinkStatus:
    """Outcome of checking one URL."""

    url: str
    # "ok": the page exists. "broken": the server says it does not exist.
    # "unreachable": the check could not tell (timeout, rate limit, bot wall...).
    outcome: str
    detail: str


def normalize_external_url(url: str) -> str | None:
    """Return the URL to request, or None when it is not an http(s) URL."""
    if url.startswith("//"):
        url = "https:" + url
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
        return None
    # The fragment is never sent to the server, so drop it to deduplicate.
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


def _classify(status_code: int | None, error: Exception | None) -> str:
    """Map a final HTTP status or transport error to "ok", "broken" or "unreachable"."""
    if status_code is not None and 200 <= status_code < 300:
        return "ok"
    # Only fail when the server itself says the page is gone. Bot walls (401/403),
    # leftover rate limits (429), server errors and timeouts say nothing about the link.
    if status_code in (404, 410):
        return "broken"
    return "unreachable"


def _retry_after_seconds(response: httpx.Response, attempt: int) -> float:
    """Seconds to wait before retrying, from Retry-After (seconds or HTTP date) or exponential backoff."""
    value = response.headers.get("retry-after", "")
    try:
        delay = float(value)
    except ValueError:
        try:
            when = email.utils.parsedate_to_datetime(value)
            delay = when.replace(tzinfo=when.tzinfo or timezone.utc).timestamp() - time.time()
        except (TypeError, ValueError):
            delay = math.nan
    if math.isnan(delay):
        delay = 2.0**attempt
    return max(0.0, min(delay, _MAX_RETRY_AFTER))


def _hub_repo_api_url(url: str) -> str | None:
    """Return the Hub API URL of the repo a page belongs to, or None for non-repo pages."""
    segments = [segment for segment in urlsplit(url).path.split("/") if segment]
    kind = "models"
    if segments and segments[0] in ("datasets", "spaces"):
        kind, segments = segments[0], segments[1:]
    elif not segments or segments[0] in _HUB_NON_REPO_PATHS:
        return None
    if len(segments) < 2:
        return None
    return f"https://huggingface.co/api/{kind}/{segments[0]}/{segments[1]}"


async def _hub_401(client: httpx.AsyncClient, url: str) -> tuple[str, str]:
    """Explain an anonymous 401 from the Hub.

    The Hub answers 401 for pages that do not exist or are private (repos,
    papers, collections), and also for pages that need a signed-in reader, such
    as gated repo files and /settings/tokens. For a repo page, the repo API tells
    them apart. It answers 200 for a gated repo and 401 for a missing or private one.
    """
    segments = urlsplit(url).path.split("/")
    if len(segments) > 1 and segments[1] in _HUB_SIGN_IN_PATHS:
        return "unreachable", "HTTP 401, needs sign-in"
    api_url = _hub_repo_api_url(url)
    if api_url is None:
        return "broken", "HTTP 401, not found or private"
    try:
        api_status = (await client.head(api_url)).status_code
    except httpx.HTTPError:
        return "unreachable", "HTTP 401"
    if api_status in (401, 404):
        return "broken", "HTTP 401, repo not found or private"
    if api_status == 200:
        return "unreachable", "HTTP 401, gated repo"
    return "unreachable", "HTTP 401"


class _HostLimiter:
    """One semaphore per host, created on first use.

    With `per_host` unset, hosts use DEFAULT_PER_HOST_CONCURRENCY, or their
    HOST_CONCURRENCY entry. A `per_host` value applies to every host.
    """

    def __init__(self, per_host: int | None = None):
        self.per_host = per_host
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    def __call__(self, url: str) -> asyncio.Semaphore:
        host = urlsplit(url).netloc
        if host not in self._semaphores:
            limit = self.per_host or HOST_CONCURRENCY.get(host, DEFAULT_PER_HOST_CONCURRENCY)
            self._semaphores[host] = asyncio.Semaphore(limit)
        return self._semaphores[host]


async def _check_one(
    client: httpx.AsyncClient,
    limiter: _HostLimiter,
    url: str,
    retries: int,
) -> ExternalLinkStatus:
    status_code = None
    error = None
    async with limiter(url):
        for attempt in range(retries + 1):
            try:
                response = await client.head(url)
                status_code = response.status_code
                # Many servers answer HEAD with an error while GET works, so
                # confirm any failure with a GET. Streaming the GET reads only
                # the status line and headers, never the body.
                if status_code >= 400 and status_code != 429:
                    async with client.stream("GET", url) as response:
                        status_code = response.status_code
                error = None
            # A malformed host raises UnicodeError (IDNA) rather than an httpx error.
            except (httpx.HTTPError, UnicodeError) as e:
                status_code, error = None, e
            if attempt == retries:
                break
            # Retry when the server asks for it. The host slot stays held while
            # waiting, so the other queued URLs do not hit a rate-limited host.
            if status_code is not None and (status_code == 429 or status_code >= 500):
                await asyncio.sleep(_retry_after_seconds(response, attempt))
                continue
            # Also retry a dropped connection, such as a keep-alive connection the
            # server already closed. Do not retry timeouts, TLS or DNS errors.
            # Each attempt costs a full timeout, and they rarely clear up in seconds.
            if isinstance(error, (httpx.ReadError, httpx.WriteError, httpx.RemoteProtocolError)):
                continue
            break

    if status_code == 401 and urlsplit(url).netloc in _HUB_HOSTS:
        outcome, detail = await _hub_401(client, url)
        return ExternalLinkStatus(url=url, outcome=outcome, detail=detail)
    if error is not None:
        detail = f"{type(error).__name__}: {error}" if str(error) else type(error).__name__
    else:
        detail = f"HTTP {status_code}"
    return ExternalLinkStatus(url=url, outcome=_classify(status_code, error), detail=detail)


async def _check_all(
    urls: list[str],
    *,
    max_concurrency: int,
    per_host_concurrency: int | None,
    timeout: float,
    retries: int,
    on_done: Callable[[ExternalLinkStatus], None] | None,
    transport: httpx.AsyncBaseTransport | None,
) -> dict[str, ExternalLinkStatus]:
    limits = httpx.Limits(max_connections=max_concurrency, max_keepalive_connections=max_concurrency)
    limiter = _HostLimiter(per_host_concurrency)
    results: dict[str, ExternalLinkStatus] = {}

    async with httpx.AsyncClient(
        follow_redirects=True,
        # The semaphores already bound the work, so waiting for a free connection
        # has no timeout. That wait says nothing about the link.
        timeout=httpx.Timeout(timeout, connect=min(timeout, 10.0), pool=None),
        limits=limits,
        headers={"User-Agent": _USER_AGENT, "Accept": "*/*"},
        transport=transport,
    ) as client:

        def finish(status: ExternalLinkStatus) -> None:
            results[status.url] = status
            if on_done is not None:
                on_done(status)

        async def run(url: str) -> None:
            finish(await _check_one(client, limiter, url, retries))

        # The GitHub fast paths can only confirm that a URL exists. Every URL they
        # do not confirm gets a normal request, so only a real github.com response
        # can mark a link broken.
        github = [url for url in urls if github_links.github_target(url) is not None]

        async def run_github() -> None:
            confirmed = await github_links.confirmed(client, github)
            for url in confirmed:
                finish(ExternalLinkStatus(url, "ok", "GitHub fast path"))
            await asyncio.gather(*(run(url) for url in github if url not in confirmed))

        github_set = set(github)
        await asyncio.gather(run_github(), *(run(url) for url in urls if url not in github_set))
    return results


def check_external_urls(
    urls: Iterable[str],
    *,
    max_concurrency: int = 128,
    per_host_concurrency: int | None = None,
    timeout: float = 15.0,
    retries: int = 2,
    ignore_patterns: Iterable[str] = (),
    on_done: Callable[[ExternalLinkStatus], None] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, ExternalLinkStatus]:
    """
    Check URLs over the network and return their status, keyed by normalized URL.

    The result leaves out URLs that are not http(s) or that match an ignore
    pattern. Each normalized URL gets one request. github.com URLs go through the
    fast paths in `doc_builder.github_links` first, and setting GITHUB_TOKEN or
    GH_TOKEN turns on the GraphQL one. Tests pass `transport` to replace the network.
    """
    ignore = [re.compile(pattern) for pattern in (*DEFAULT_IGNORE_PATTERNS, *ignore_patterns)]
    unique = {
        normalized
        for url in urls
        if (normalized := normalize_external_url(url)) is not None and not any(p.search(normalized) for p in ignore)
    }
    if not unique:
        return {}
    return asyncio.run(
        _check_all(
            sorted(unique),
            max_concurrency=max_concurrency,
            per_host_concurrency=per_host_concurrency,
            timeout=timeout,
            retries=retries,
            on_done=on_done,
            transport=transport,
        )
    )
