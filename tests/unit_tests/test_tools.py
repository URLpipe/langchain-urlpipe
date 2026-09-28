"""Each tool against the stub server, through ``invoke`` and ``ainvoke``."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

import pytest
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, ToolException

from langchain_urlpipe import (
    UrlpipeConsoleErrors,
    UrlpipeLighthouse,
    UrlpipePageMetadata,
    UrlpipeReadPage,
)

from .conftest import API_KEY, StubServer

PAGE = "https://example.com/pricing"

LIGHTHOUSE_REPORT = {
    "url": PAGE,
    "fetchTime": "2026-01-01T00:00:00.000Z",
    "device": "desktop",
    "categories": {
        "performance": {"score": 0.95, "title": "Performance"},
        "accessibility": {"score": 0.884, "title": "Accessibility"},
        "best-practices": {"score": 0.92, "title": "Best Practices"},
        "seo": {"score": 0.9, "title": "SEO"},
        "pwa": None,
    },
    "metrics": {
        "first-contentful-paint": {
            "score": 0.95,
            "displayValue": "1.2 s",
            "numericValue": 1200,
            "numericUnit": "millisecond",
        },
        "total-blocking-time": None,
    },
}


@pytest.fixture(params=["sync", "async"])
def call(request: pytest.FixtureRequest) -> Callable[[BaseTool, Any], Any]:
    """Invoke a tool through ``invoke`` or through ``ainvoke``."""

    def run(tool: BaseTool, tool_input: Any) -> Any:
        if request.param == "sync":
            return tool.invoke(tool_input)
        return asyncio.run(tool.ainvoke(tool_input))

    return run


def test_read_page_returns_the_markdown(server: StubServer, connection: dict[str, Any], call: Any) -> None:
    server.reply(body="# Pricing\n\nPlans from $0.", content_type="text/markdown")

    result = call(UrlpipeReadPage(**connection), {"url": PAGE})

    assert result == "# Pricing\n\nPlans from $0."
    request = server.requests[0]
    assert request.method == "POST"
    assert request.path == "/markdown"
    assert request.json == {"url": PAGE, "sync": True}
    assert request.headers["authorization"] == f"Bearer {API_KEY}"
    assert request.headers["user-agent"].startswith("langchain-urlpipe/")
    assert " urlpipe-python/" in request.headers["user-agent"]


def test_max_age_is_sent_as_given(server: StubServer, connection: dict[str, Any], call: Any) -> None:
    server.reply(body="# Pricing", content_type="text/markdown")

    call(UrlpipeReadPage(**connection), {"url": PAGE, "max_age": "1 hour"})

    assert server.requests[0].json == {"url": PAGE, "sync": True, "max_age": "1 hour"}


def test_read_page_says_when_a_page_has_no_text(
    server: StubServer, connection: dict[str, Any], call: Any
) -> None:
    server.reply(body="  \n", content_type="text/markdown")

    result = call(UrlpipeReadPage(**connection), {"url": PAGE})

    assert result == "The page has no readable text content."


def test_page_metadata_returns_a_dict(server: StubServer, connection: dict[str, Any], call: Any) -> None:
    meta = {"title": "Pricing", "language": "en", "feed_url": "https://example.com/feed.xml"}
    server.reply(body=meta)

    result = call(UrlpipePageMetadata(**connection), {"url": PAGE, "max_age": 0})

    assert result == meta
    assert server.requests[0].path == "/meta"
    assert server.requests[0].json == {"url": PAGE, "sync": True, "max_age": 0}


def test_console_errors_are_one_line_each(server: StubServer, connection: dict[str, Any], call: Any) -> None:
    server.reply(
        body=[
            {"type": "error", "text": "Failed to load resource: 404"},
            {"type": "exception", "text": "TypeError: x is undefined"},
        ]
    )

    result = call(UrlpipeConsoleErrors(**connection), {"url": PAGE})

    assert result == "[error] Failed to load resource: 404\n[exception] TypeError: x is undefined"
    assert server.requests[0].path == "/console"


def test_a_clean_console_says_so(server: StubServer, connection: dict[str, Any], call: Any) -> None:
    server.reply(body=[])

    result = call(UrlpipeConsoleErrors(**connection), {"url": PAGE})

    assert result == "The page logged no errors, warnings or exceptions."


def test_lighthouse_returns_compact_scores(server: StubServer, connection: dict[str, Any], call: Any) -> None:
    server.reply(body=LIGHTHOUSE_REPORT)

    result = call(UrlpipeLighthouse(**connection), {"url": PAGE, "device": "desktop"})

    assert result == {
        "url": PAGE,
        "device": "desktop",
        "scores": {"performance": 95, "accessibility": 88, "best-practices": 92, "seo": 90},
        "metrics": {"first-contentful-paint": {"value": "1.2 s", "score": 95}},
    }
    assert server.requests[0].path == "/lighthouse"
    assert server.requests[0].json == {"url": PAGE, "sync": True, "device": "desktop"}


def test_a_tool_call_gets_json_content(server: StubServer, connection: dict[str, Any], call: Any) -> None:
    server.reply(body={"title": "Pricing"})
    tool_call = {
        "name": "urlpipe_page_metadata",
        "args": {"url": PAGE},
        "id": "call_1",
        "type": "tool_call",
    }

    message = call(UrlpipePageMetadata(**connection), tool_call)

    assert isinstance(message, ToolMessage)
    assert json.loads(message.content) == {"title": "Pricing"}  # type: ignore[arg-type]


def test_an_api_error_reaches_the_agent(server: StubServer, connection: dict[str, Any], call: Any) -> None:
    server.reply(422, {"error": "The page took too long to load."})
    tool_call = {"name": "urlpipe_read_page", "args": {"url": PAGE}, "id": "c", "type": "tool_call"}

    message = call(UrlpipeReadPage(**connection), tool_call)

    assert isinstance(message, ToolMessage)
    assert message.status == "error"
    assert message.content == "The page took too long to load."


def test_errors_raise_tool_exception_when_not_handled(
    server: StubServer, connection: dict[str, Any], call: Any
) -> None:
    server.reply(401, {"error": "unauthorized"})
    tool = UrlpipeReadPage(**connection, handle_tool_error=False)

    with pytest.raises(ToolException, match="API key is missing or does not match"):
        call(tool, {"url": PAGE})


def test_a_missing_api_key_fails_at_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("URLPIPE_API_KEY", raising=False)
    import urlpipe

    with pytest.raises(urlpipe.ConfigurationError, match="URLPIPE_API_KEY"):
        UrlpipeReadPage()


def test_the_api_key_is_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, server: StubServer
) -> None:
    monkeypatch.setenv("URLPIPE_API_KEY", "env_key")
    server.reply(body="# Hi", content_type="text/markdown")

    UrlpipeReadPage(client_kwargs={"base_url": server.url}).invoke({"url": PAGE})

    assert server.requests[0].headers["authorization"] == "Bearer env_key"
