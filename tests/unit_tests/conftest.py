"""A real local HTTP server standing in for the URLpipe API: it answers each
request with the next queued reply and records what it was sent."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

API_KEY = "test_key_123"

META_HEADERS = {
    "X-Result-Token": "tok_123",
    "X-Cache": "miss",
    "X-Quota-Cost": "1",
    "X-Quota-Limit": "1000",
    "X-Quota-Remaining": "943",
}


@dataclass
class Recorded:
    method: str
    path: str
    headers: dict[str, str]
    body: bytes

    @property
    def json(self) -> Any:
        return json.loads(self.body)


@dataclass
class Reply:
    status: int
    body: Any
    headers: dict[str, str] = field(default_factory=dict)
    content_type: str | None = None


class StubServer:
    def __init__(self) -> None:
        self.replies: list[Reply] = []
        self.routes: dict[str, Reply] = {}
        self.requests: list[Recorded] = []
        self._lock = threading.Lock()
        stub = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args: Any) -> None:
                pass

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                recorded = Recorded(
                    self.command,
                    self.path,
                    {k.lower(): v for k, v in self.headers.items()},
                    body,
                )
                with stub._lock:
                    stub.requests.append(recorded)
                    reply = stub._reply_for(recorded)
                payload, content_type = _encode(reply)
                self.send_response(reply.status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(payload)))
                for name, value in reply.headers.items():
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(payload)

            do_GET = do_POST

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def _reply_for(self, request: Recorded) -> Reply:
        """A reply routed by the requested page's URL wins over the queue, so
        concurrent requests get the right answer whatever order they arrive in."""
        try:
            page = request.json.get("url")
        except ValueError:
            page = None
        if page in self.routes:
            return self.routes[page]
        if self.replies:
            return self.replies.pop(0)
        return Reply(599, {"error": "no reply queued"})

    def reply(
        self,
        status: int = 200,
        body: Any = "",
        headers: dict[str, str] | None = None,
        content_type: str | None = None,
        *,
        for_url: str | None = None,
    ) -> StubServer:
        reply = Reply(status, body, {**META_HEADERS, **(headers or {})}, content_type)
        if for_url is None:
            self.replies.append(reply)
        else:
            self.routes[for_url] = reply
        return self

    def reset(self) -> None:
        self.replies.clear()
        self.routes.clear()
        self.requests.clear()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def _encode(reply: Reply) -> tuple[bytes, str]:
    if isinstance(reply.body, str):
        return reply.body.encode(), reply.content_type or "text/plain; charset=utf-8"
    return json.dumps(reply.body).encode(), reply.content_type or "application/json"


@pytest.fixture(scope="session")
def _server() -> Iterator[StubServer]:
    server = StubServer()
    yield server
    server.close()


@pytest.fixture
def server(_server: StubServer) -> Iterator[StubServer]:
    _server.reset()
    yield _server
    _server.reset()


@pytest.fixture
def connection(server: StubServer) -> dict[str, Any]:
    """Construction arguments that point a tool or loader at the stub server."""
    return {"api_key": API_KEY, "client_kwargs": {"base_url": server.url, "max_retries": 0}}
