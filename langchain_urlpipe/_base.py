"""What every URLpipe tool shares: the API key, the client, the arguments and
turning client errors into ``ToolException``."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

import urlpipe
from langchain_core.callbacks import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from langchain_core.tools import BaseTool, ToolException
from langchain_core.utils import secret_from_env
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from typing_extensions import Self

from ._clients import async_session, build_client, tool_error

MAX_AGE_DESCRIPTION = (
    "How fresh a stored copy must be: seconds (3600) or a duration such as "
    "'1 hour' or '3 days'. Leave it out to accept a copy up to 7 days old; 0 "
    "always loads the page fresh. A stored copy costs no credits."
)


class UrlpipeInput(BaseModel):
    """The arguments every URLpipe tool takes."""

    url: str = Field(description="The full URL of the page, including https://.")
    max_age: int | str | None = Field(default=None, description=MAX_AGE_DESCRIPTION)


class UrlpipeBaseTool(BaseTool):
    """Base class for the URLpipe tools.

    Args:
        api_key: a URLpipe project API key. Defaults to ``URLPIPE_API_KEY``.
        client_kwargs: passed to ``urlpipe.Client`` and ``urlpipe.AsyncClient``:
            ``base_url``, ``timeout``, ``max_retries``, ``wait_timeout``.
        client: a ready ``urlpipe.Client`` to use instead of building one.
        async_client: a ``urlpipe.AsyncClient`` for async calls. Without it each
            async call opens its own, so the tool works from any event loop.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    args_schema: type[BaseModel] = UrlpipeInput

    api_key: SecretStr | None = Field(
        default_factory=secret_from_env("URLPIPE_API_KEY", default=None)
    )
    client_kwargs: dict[str, Any] = Field(default_factory=dict)
    client: urlpipe.Client | None = Field(default=None, exclude=True)
    async_client: urlpipe.AsyncClient | None = Field(default=None, exclude=True)

    handle_tool_error: bool | str | Callable[[ToolException], Any] | None = True
    """URLpipe errors come back to the agent as the tool's output (the API's own
    explanation, such as why a page could not be loaded) instead of stopping
    the run. Set ``False`` to have ``ToolException`` raised."""

    operation: ClassVar[str]

    @model_validator(mode="after")
    def _connect(self) -> Self:
        if self.client is None:
            self.client = build_client(self.api_key, self.client_kwargs)
        return self

    def _run(
        self,
        url: str,
        max_age: int | str | None = None,
        run_manager: CallbackManagerForToolRun | None = None,
        **options: Any,
    ) -> Any:
        assert self.client is not None
        try:
            response = getattr(self.client, self.operation)(
                url, max_age=max_age, **self._arguments(options)
            )
        except urlpipe.UrlpipeError as error:
            raise tool_error(error) from error
        return self._output(response)

    async def _arun(
        self,
        url: str,
        max_age: int | str | None = None,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
        **options: Any,
    ) -> Any:
        try:
            async with async_session(self.async_client, self.api_key, self.client_kwargs) as client:
                response = await getattr(client, self.operation)(
                    url, max_age=max_age, **self._arguments(options)
                )
        except urlpipe.UrlpipeError as error:
            raise tool_error(error) from error
        return self._output(response)

    def _output(self, response: urlpipe.Response[Any]) -> Any:
        if response.data is None:
            raise ToolException(
                f"URLpipe is still working on this page. Its result token is {response.token}."
            )
        return self._render(response.data)

    def _arguments(self, options: dict[str, Any]) -> dict[str, Any]:
        """The tool's own arguments as the client method takes them."""
        return options

    def _render(self, data: Any) -> Any:
        """Shape the operation's result for the model."""
        return data
