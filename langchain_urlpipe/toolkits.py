"""All four URLpipe tools, sharing one client."""

from __future__ import annotations

from typing import Any

import urlpipe
from langchain_core.tools import BaseTool, BaseToolkit
from langchain_core.utils import secret_from_env
from pydantic import ConfigDict, Field, SecretStr, model_validator
from typing_extensions import Self

from ._clients import build_client
from .tools import UrlpipeConsoleErrors, UrlpipeLighthouse, UrlpipePageMetadata, UrlpipeReadPage


class UrlpipeToolkit(BaseToolkit):
    """Give an agent every URLpipe tool at once: read a page, get its metadata,
    list its console errors and run a Lighthouse audit.

    >>> tools = UrlpipeToolkit().get_tools()  # reads URLPIPE_API_KEY

    The tools share one ``urlpipe.Client``, and the same ``api_key``,
    ``client_kwargs`` and ``async_client`` as the tools take.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    api_key: SecretStr | None = Field(
        default_factory=secret_from_env("URLPIPE_API_KEY", default=None)
    )
    client_kwargs: dict[str, Any] = Field(default_factory=dict)
    client: urlpipe.Client | None = Field(default=None, exclude=True)
    async_client: urlpipe.AsyncClient | None = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def _connect(self) -> Self:
        if self.client is None:
            self.client = build_client(self.api_key, self.client_kwargs)
        return self

    def get_tools(self) -> list[BaseTool]:
        """The four tools, in the order an agent usually needs them."""
        shared: dict[str, Any] = {
            "api_key": self.api_key,
            "client_kwargs": self.client_kwargs,
            "client": self.client,
            "async_client": self.async_client,
        }
        return [
            UrlpipeReadPage(**shared),
            UrlpipePageMetadata(**shared),
            UrlpipeConsoleErrors(**shared),
            UrlpipeLighthouse(**shared),
        ]
