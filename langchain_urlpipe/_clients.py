"""How every component here reaches URLpipe: through the official ``urlpipe``
client, configured once and shared."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any

import urlpipe
from langchain_core.tools import ToolException
from pydantic import SecretStr


def build_client(api_key: SecretStr | None, client_kwargs: Mapping[str, Any]) -> urlpipe.Client:
    """A sync client. With no ``api_key`` it reads ``URLPIPE_API_KEY`` and raises
    ``urlpipe.ConfigurationError`` if that is unset too."""
    return urlpipe.Client(_secret(api_key), **client_kwargs)


@asynccontextmanager
async def async_session(
    async_client: urlpipe.AsyncClient | None,
    api_key: SecretStr | None,
    client_kwargs: Mapping[str, Any],
) -> AsyncIterator[urlpipe.AsyncClient]:
    """The async client to use for one call.

    An ``httpx.AsyncClient`` keeps connections tied to the event loop that opened
    them, so one shared across loops fails with "Event loop is closed". Unless
    you passed your own ``async_client``, each call gets a fresh one, closed
    when the call ends.
    """
    if async_client is not None:
        yield async_client
        return
    async with urlpipe.AsyncClient(_secret(api_key), **client_kwargs) as client:
        yield client


def tool_error(error: urlpipe.UrlpipeError) -> ToolException:
    """The client's error as a ``ToolException``, so an agent reads why the call
    failed instead of the run stopping."""
    return ToolException(error.message)


def _secret(api_key: SecretStr | None) -> str | None:
    return api_key.get_secret_value() if api_key is not None else None
