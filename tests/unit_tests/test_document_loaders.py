from __future__ import annotations

import asyncio
import logging
from typing import Any

import pytest
import urlpipe
from langchain_core.documents import Document

from langchain_urlpipe import UrlpipeLoader

from .conftest import StubServer

A = "https://example.com/a"
B = "https://example.com/b"


def _aload(loader: UrlpipeLoader) -> list[Document]:
    async def collect() -> list[Document]:
        return [document async for document in loader.alazy_load()]

    return asyncio.run(collect())


def test_lazy_load_yields_one_document_per_url(server: StubServer, connection: dict[str, Any]) -> None:
    server.reply(body="# A", content_type="text/markdown", headers={"X-Result-Token": "tok_a"})
    server.reply(body="# B", content_type="text/markdown", headers={"X-Cache": "hit"})
    loader = UrlpipeLoader([A, B], **connection)

    documents = loader.lazy_load()
    first = next(documents)

    assert first == Document(
        page_content="# A",
        metadata={"source": A, "operation": "markdown", "token": "tok_a", "cache": "miss"},
    )
    assert len(server.requests) == 1
    assert next(documents).metadata["cache"] == "hit"
    assert [request.json for request in server.requests] == [
        {"url": A, "sync": True},
        {"url": B, "sync": True},
    ]


def test_options_are_sent_with_every_page(server: StubServer, connection: dict[str, Any]) -> None:
    server.reply(body="<html></html>", content_type="text/html")
    options = {"block_cookie_banners": True, "remove_selectors": [".promo"]}

    [document] = UrlpipeLoader(
        A, operation="html", max_age=3600, page_options=options, **connection
    ).load()

    assert document.page_content == "<html></html>"
    assert document.metadata["operation"] == "html"
    assert server.requests[0].path == "/html"
    assert server.requests[0].json == {
        "url": A,
        "sync": True,
        "max_age": 3600,
        "page_options": options,
    }


def test_summarize_puts_the_summary_in_the_document(server: StubServer, connection: dict[str, Any]) -> None:
    server.reply(body="A pricing page with three plans.", content_type="text/markdown")

    [document] = UrlpipeLoader([A], "summarize", **connection).load()

    assert document.page_content == "A pricing page with three plans."
    assert server.requests[0].path == "/summarize"


def test_alazy_load_keeps_the_order_of_urls(server: StubServer, connection: dict[str, Any]) -> None:
    server.reply(body="# A", content_type="text/markdown", for_url=A)
    server.reply(body="# B", content_type="text/markdown", for_url=B)

    documents = _aload(UrlpipeLoader([A, B], **connection))

    assert [(d.metadata["source"], d.page_content) for d in documents] == [(A, "# A"), (B, "# B")]


def test_aload_works_across_event_loops(server: StubServer, connection: dict[str, Any]) -> None:
    server.reply(body="# A", content_type="text/markdown", for_url=A)
    loader = UrlpipeLoader([A], **connection)

    assert asyncio.run(loader.aload())[0].page_content == "# A"
    assert asyncio.run(loader.aload())[0].page_content == "# A"


def test_a_failed_url_raises_by_default(server: StubServer, connection: dict[str, Any]) -> None:
    server.reply(422, {"error": "The page could not be reached."})

    with pytest.raises(urlpipe.AnalysisFailedError, match="could not be reached"):
        UrlpipeLoader([A, B], **connection).load()


def test_a_failed_url_raises_from_alazy_load(server: StubServer, connection: dict[str, Any]) -> None:
    server.reply(422, {"error": "The page could not be reached."}, for_url=A)
    server.reply(body="# B", content_type="text/markdown", for_url=B)

    with pytest.raises(urlpipe.AnalysisFailedError):
        _aload(UrlpipeLoader([A, B], **connection))


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_continue_on_failure_logs_and_skips(
    server: StubServer, connection: dict[str, Any], caplog: pytest.LogCaptureFixture, mode: str
) -> None:
    server.reply(422, {"error": "The page could not be reached."}, for_url=A)
    server.reply(body="# B", content_type="text/markdown", for_url=B)
    loader = UrlpipeLoader([A, B], continue_on_failure=True, **connection)

    with caplog.at_level(logging.WARNING, logger="langchain_urlpipe.document_loaders"):
        documents = loader.load() if mode == "sync" else _aload(loader)

    assert [d.metadata["source"] for d in documents] == [B]
    assert f"Skipping {A}: The page could not be reached." in caplog.text


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"operation": "screenshot"}, "operation must be one of markdown, html, summarize"),
        ({"max_concurrency": 0}, "max_concurrency must be 1 or more"),
    ],
)
def test_bad_arguments_are_refused(connection: dict[str, Any], kwargs: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        UrlpipeLoader([A], **connection, **kwargs)
