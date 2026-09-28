from __future__ import annotations

import asyncio
from typing import Any

from langchain_urlpipe import UrlpipeToolkit

from .conftest import StubServer


def test_the_toolkit_gives_all_four_tools_one_client(connection: dict[str, Any]) -> None:
    toolkit = UrlpipeToolkit(**connection)

    tools = toolkit.get_tools()

    assert [tool.name for tool in tools] == [
        "urlpipe_read_page",
        "urlpipe_page_metadata",
        "urlpipe_console_errors",
        "urlpipe_lighthouse",
    ]
    assert all(tool.client is toolkit.client for tool in tools)  # type: ignore[attr-defined]


def test_toolkit_tools_reach_the_api(server: StubServer, connection: dict[str, Any]) -> None:
    server.reply(body="# Hi", content_type="text/markdown").reply(body=[])
    read_page, _, console_errors, _ = UrlpipeToolkit(**connection).get_tools()

    assert read_page.invoke({"url": "https://example.com"}) == "# Hi"
    assert asyncio.run(console_errors.ainvoke({"url": "https://example.com"})) == (
        "The page logged no errors, warnings or exceptions."
    )
    assert [request.path for request in server.requests] == ["/markdown", "/console"]
