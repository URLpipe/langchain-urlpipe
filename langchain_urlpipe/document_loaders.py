"""Load web pages as LangChain Documents, rendered in real Chrome first."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Iterator, Mapping, Sequence
from typing import Any, Literal, get_args

import urlpipe
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document
from pydantic import SecretStr

from ._clients import async_session, build_client

logger = logging.getLogger(__name__)

LoaderOperation = Literal["markdown", "html", "summarize"]


class UrlpipeLoader(BaseLoader):
    """One ``Document`` per URL, with the page as Markdown (or its rendered HTML,
    or an AI summary). Pages load in real Chrome, so JavaScript-built sites come
    back complete.

    >>> loader = UrlpipeLoader(["https://example.com"])  # reads URLPIPE_API_KEY
    >>> docs = loader.load()
    >>> docs[0].metadata
    {'source': 'https://example.com', 'operation': 'markdown', 'token': '…', 'cache': 'miss'}

    Args:
        urls: one URL or several.
        operation: ``"markdown"`` (1 credit a page), ``"html"`` (the HTML after
            JavaScript ran, 1 credit) or ``"summarize"`` (an AI summary in
            Markdown, 17 credits).
        api_key: a URLpipe project API key. Defaults to ``URLPIPE_API_KEY``.
        max_age: how fresh a stored copy must be, in seconds or as a duration
            such as ``"1 hour"``. ``0`` always loads the page fresh.
        page_options: passed to the API unchanged: ``wait_for_selector``,
            ``scroll_to_bottom``, ``delay``, ``block_ads``,
            ``block_cookie_banners``, ``block_popups``, ``remove_selectors``.
        continue_on_failure: log and skip a URL that fails instead of raising
            its ``urlpipe.UrlpipeError``.
        max_concurrency: how many pages :meth:`alazy_load` loads at once.
        client_kwargs: passed to ``urlpipe.Client`` and ``urlpipe.AsyncClient``.
        client: a ready ``urlpipe.Client`` to use instead of building one.
        async_client: a ready ``urlpipe.AsyncClient`` for the async methods.
    """

    def __init__(
        self,
        urls: str | Sequence[str],
        operation: LoaderOperation = "markdown",
        api_key: str | None = None,
        max_age: int | str | None = None,
        page_options: Mapping[str, Any] | None = None,
        *,
        continue_on_failure: bool = False,
        max_concurrency: int = 3,
        client_kwargs: Mapping[str, Any] | None = None,
        client: urlpipe.Client | None = None,
        async_client: urlpipe.AsyncClient | None = None,
    ) -> None:
        if operation not in get_args(LoaderOperation):
            raise ValueError(
                f"operation must be one of {', '.join(get_args(LoaderOperation))}; "
                f"got {operation!r}."
            )
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be 1 or more.")
        self.urls = [urls] if isinstance(urls, str) else list(urls)
        self.operation = operation
        self.max_age = max_age
        self.page_options = page_options
        self.continue_on_failure = continue_on_failure
        self.max_concurrency = max_concurrency
        self._api_key = SecretStr(api_key) if api_key is not None else None
        self._client_kwargs = dict(client_kwargs or {})
        self._client = client if client is not None else build_client(
            self._api_key, self._client_kwargs
        )
        self._async_client = async_client

    def lazy_load(self) -> Iterator[Document]:
        """Load the pages one after another, yielding each as it arrives."""
        for url in self.urls:
            try:
                response = getattr(self._client, self.operation)(url, **self._options())
            except urlpipe.UrlpipeError as error:
                self._skip_or_raise(url, error)
                continue
            yield self._document(url, response)

    async def alazy_load(self) -> AsyncIterator[Document]:
        """Load up to ``max_concurrency`` pages at once, yielding them in the
        order of ``urls``."""
        async with async_session(self._async_client, self._api_key, self._client_kwargs) as client:
            semaphore = asyncio.Semaphore(self.max_concurrency)

            async def fetch(url: str) -> Document | None:
                async with semaphore:
                    try:
                        response = await getattr(client, self.operation)(url, **self._options())
                    except urlpipe.UrlpipeError as error:
                        self._skip_or_raise(url, error)
                        return None
                return self._document(url, response)

            tasks = [asyncio.ensure_future(fetch(url)) for url in self.urls]
            try:
                for task in tasks:
                    document = await task
                    if document is not None:
                        yield document
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

    def _options(self) -> dict[str, Any]:
        return {"max_age": self.max_age, "page_options": self.page_options}

    def _document(self, url: str, response: urlpipe.Response[Any]) -> Document:
        return Document(
            page_content=response.data or "",
            metadata={
                "source": url,
                "operation": self.operation,
                "token": response.token,
                "cache": response.meta.cache,
            },
        )

    def _skip_or_raise(self, url: str, error: urlpipe.UrlpipeError) -> None:
        if not self.continue_on_failure:
            raise error
        logger.warning("Skipping %s: %s", url, error)
