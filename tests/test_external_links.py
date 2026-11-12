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

import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest

from doc_builder import external_links
from doc_builder.check_links import check_links
from doc_builder.external_links import _classify, check_external_urls, normalize_external_url


class _Handler(BaseHTTPRequestHandler):
    requests: Counter = Counter()
    lock = threading.Lock()

    def log_message(self, *args):
        pass

    def _respond(self):
        with self.lock:
            self.requests[(self.command, self.path)] += 1
            count = self.requests[(self.command, self.path)]
        path = self.path
        if path == "/ok":
            status = 200
        elif path == "/head-not-allowed":
            status = 405 if self.command == "HEAD" else 200
        elif path == "/missing":
            status = 404
        elif path == "/forbidden":
            status = 403
        elif path == "/rate-limited-once":
            status = 429 if count == 1 else 200
        elif path == "/redirect":
            self.send_response(301)
            self.send_header("Location", "/ok")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        else:
            status = 404
        self.send_response(status)
        if status == 429:
            self.send_header("Retry-After", "0")
        body = b"x" * 100
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command == "GET":
            self.wfile.write(body)

    do_GET = _respond
    do_HEAD = _respond


class _Server(ThreadingHTTPServer):
    # The default backlog of 5 refuses connections when the checker opens more at once.
    request_queue_size = 128


@pytest.fixture
def server(monkeypatch):
    # The local test server lives on localhost, which is ignored by default.
    monkeypatch.setattr(external_links, "DEFAULT_IGNORE_PATTERNS", ())
    _Handler.requests = Counter()
    httpd = _Server(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_normalize_external_url():
    assert normalize_external_url("https://Example.com/a?b=1#frag") == "https://example.com/a?b=1"
    assert normalize_external_url("//example.com/a") == "https://example.com/a"
    assert normalize_external_url("mailto:docs@example.com") is None
    assert normalize_external_url("ftp://example.com/file") is None


def test_classify():
    assert _classify(200, None) == "ok"
    assert _classify(404, None) == "broken"
    assert _classify(410, None) == "broken"
    assert _classify(403, None) == "unreachable"
    assert _classify(429, None) == "unreachable"
    assert _classify(401, None) == "unreachable"
    assert _classify(None, TimeoutError()) == "unreachable"


def test_retry_after_seconds():
    def wait(value, attempt=0):
        return external_links._retry_after_seconds(httpx.Response(429, headers={"retry-after": value}), attempt)

    assert wait("3") == 3
    assert wait("3600") == 30  # capped
    assert wait("-5") == 0
    assert wait("Wed, 21 Oct 2015 07:28:00 GMT") == 0  # in the past
    assert wait("soon", attempt=2) == 4  # unparseable, so exponential backoff
    assert wait("nan", attempt=1) == 2


def test_hub_401(monkeypatch):
    # The Hub answers 401 to anonymous readers for missing or private repos, and
    # for pages that need sign-in. Its repo API tells them apart.
    api = {"/api/models/meta-llama/gated": 200, "/api/datasets/org/gone": 401}

    def handler(request):
        if request.url.path.startswith("/api/"):
            return httpx.Response(api.get(request.url.path, 401))
        return httpx.Response(401)

    statuses = check_external_urls(
        [
            "https://huggingface.co/meta-llama/gated/blob/main/config.json",
            "https://huggingface.co/datasets/org/gone",
            "https://huggingface.co/org/missing",
            "https://huggingface.co/settings/tokens",
            "https://huggingface.co/papers/2104.09864.pdf",
        ],
        transport=httpx.MockTransport(handler),
    )
    assert {url: (s.outcome, s.detail) for url, s in statuses.items()} == {
        "https://huggingface.co/meta-llama/gated/blob/main/config.json": ("unreachable", "HTTP 401, gated repo"),
        "https://huggingface.co/datasets/org/gone": ("broken", "HTTP 401, repo not found or private"),
        "https://huggingface.co/org/missing": ("broken", "HTTP 401, repo not found or private"),
        "https://huggingface.co/settings/tokens": ("unreachable", "HTTP 401, needs sign-in"),
        "https://huggingface.co/papers/2104.09864.pdf": ("broken", "HTTP 401, not found or private"),
    }


def test_errors_never_abort_the_run():
    def handler(request):
        if request.url.host == "a..b.com":
            # What the socket's DNS lookup raises for an empty label, instead of an httpx error.
            "a..b.com".encode("idna")
        return httpx.Response(200)

    statuses = check_external_urls(["https://a..b.com/", "https://ok.test/"], transport=httpx.MockTransport(handler))
    assert statuses["https://a..b.com/"].outcome == "unreachable"
    assert statuses["https://ok.test/"].outcome == "ok"


def test_dropped_connections_are_retried_but_timeouts_are_not():
    attempts = Counter()

    def handler(request):
        attempts[request.url.host] += 1
        if request.url.host == "dropped.test" and attempts["dropped.test"] == 1:
            raise httpx.RemoteProtocolError("Server disconnected without sending a response.")
        if request.url.host == "slow.test":
            raise httpx.ReadTimeout("timed out")
        return httpx.Response(200)

    statuses = check_external_urls(
        ["https://dropped.test/", "https://slow.test/"], transport=httpx.MockTransport(handler)
    )
    assert statuses["https://dropped.test/"].outcome == "ok"
    assert statuses["https://slow.test/"].outcome == "unreachable"
    assert attempts["slow.test"] == 1


def test_check_external_urls_outcomes(server):
    statuses = check_external_urls(
        [
            f"{server}/ok",
            f"{server}/ok#section",
            f"{server}/head-not-allowed",
            f"{server}/missing",
            f"{server}/forbidden",
            f"{server}/rate-limited-once",
            f"{server}/redirect",
        ],
        retries=1,
    )
    outcomes = {url.removeprefix(server): status.outcome for url, status in statuses.items()}
    assert outcomes == {
        "/ok": "ok",
        "/head-not-allowed": "ok",
        "/missing": "broken",
        "/forbidden": "unreachable",
        "/rate-limited-once": "ok",
        "/redirect": "ok",
    }
    # "/ok" and "/ok#section" are the same request.
    assert _Handler.requests[("HEAD", "/ok")] == 2  # once directly, once through the redirect


def test_check_external_urls_ignores(server, monkeypatch):
    statuses = check_external_urls([f"{server}/ok", f"{server}/missing"], ignore_patterns=[r"/missing$"])
    assert list(statuses) == [f"{server}/ok"]


def test_check_links_reports_external_links(tmp_path, server):
    (tmp_path / "index.md").write_text(
        f"""# Index

[fine]({server}/ok)
[gone]({server}/missing)
[gone again]({server}/missing#part)
[blocked]({server}/forbidden)
[mail](mailto:docs@example.com)
""",
        encoding="utf-8",
    )

    without_external = check_links(tmp_path, max_workers=1, show_progress=False)
    assert not without_external.has_broken_links()
    assert _Handler.requests == Counter()

    result = check_links(tmp_path, max_workers=1, show_progress=False, check_external=True)
    assert [(link_url, line) for _, _, link_url, line in result.broken_links] == [
        (f"{server}/missing (HTTP 404)", 4),
        (f"{server}/missing#part (HTTP 404)", 5),
    ]
    assert [(link_url, line, detail) for _, _, link_url, line, detail in result.unreachable_links] == [
        (f"{server}/forbidden", 6, "HTTP 403")
    ]
    assert result.external_urls_checked == 3
    # The missing page is requested once even though it is linked twice.
    assert _Handler.requests[("HEAD", "/missing")] == 1
    assert "Could not verify 1 external link(s)" in result.get_summary()


def test_host_limiter():
    limiter = external_links._HostLimiter()
    assert limiter("https://huggingface.co/papers/1")._value == 32
    assert limiter("https://github.com/org")._value == 8
    assert limiter("https://huggingface.co/docs") is limiter("https://huggingface.co/blog")
    # An explicit limit applies to every host, the Hub included.
    assert external_links._HostLimiter(4)("https://huggingface.co/docs")._value == 4
