"""LangChain's standard unit tests for every tool (``langchain-tests``)."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool
from langchain_tests.unit_tests import ToolsUnitTests

from langchain_urlpipe import (
    UrlpipeConsoleErrors,
    UrlpipeLighthouse,
    UrlpipePageMetadata,
    UrlpipeReadPage,
)


class _Standard(ToolsUnitTests):
    tool_class: type[BaseTool]

    @property
    def tool_constructor(self) -> type[BaseTool]:
        return self.tool_class

    @property
    def tool_constructor_params(self) -> dict[str, Any]:
        return {"api_key": "test_key_123"}

    @property
    def tool_invoke_params_example(self) -> dict[str, Any]:
        return {"url": "https://example.com", "max_age": "1 hour"}

    @property
    def init_from_env_params(self) -> tuple[dict[str, str], dict[str, Any], dict[str, Any]]:
        return {"URLPIPE_API_KEY": "env_key"}, {}, {"api_key": "env_key"}


class TestUrlpipeReadPage(_Standard):
    tool_class = UrlpipeReadPage


class TestUrlpipePageMetadata(_Standard):
    tool_class = UrlpipePageMetadata


class TestUrlpipeConsoleErrors(_Standard):
    tool_class = UrlpipeConsoleErrors


class TestUrlpipeLighthouse(_Standard):
    tool_class = UrlpipeLighthouse

    @property
    def tool_invoke_params_example(self) -> dict[str, Any]:
        return {"url": "https://example.com", "device": "desktop"}
