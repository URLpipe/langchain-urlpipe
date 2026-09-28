"""Against the real API. Skipped unless ``URLPIPE_API_KEY`` is set; spends a
few credits the first time (repeats within 7 days are served from cache)."""

from __future__ import annotations

import os
from typing import Any

import pytest
from langchain_core.tools import BaseTool
from langchain_tests.integration_tests import ToolsIntegrationTests

from langchain_urlpipe import UrlpipeLoader, UrlpipeReadPage

pytestmark = pytest.mark.skipif(
    not os.environ.get("URLPIPE_API_KEY"), reason="set URLPIPE_API_KEY to run live tests"
)

PAGE = "https://example.com"


class TestUrlpipeReadPageLive(ToolsIntegrationTests):
    @property
    def tool_constructor(self) -> type[BaseTool]:
        return UrlpipeReadPage

    @property
    def tool_invoke_params_example(self) -> dict[str, Any]:
        return {"url": PAGE}


def test_read_page_returns_markdown() -> None:
    assert "Example Domain" in UrlpipeReadPage().invoke({"url": PAGE})


def test_loader_loads_the_page() -> None:
    [document] = UrlpipeLoader([PAGE]).load()

    assert "Example Domain" in document.page_content
    assert document.metadata["source"] == PAGE
