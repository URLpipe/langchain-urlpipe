"""URLpipe tools: read a page, get its metadata, list its console errors and
run a Lighthouse audit, each rendered in real Chrome."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field

from ._base import UrlpipeBaseTool, UrlpipeInput


class UrlpipeReadPage(UrlpipeBaseTool):
    """The page's main content as Markdown, after its JavaScript ran.

    >>> tool = UrlpipeReadPage()  # reads URLPIPE_API_KEY
    >>> tool.invoke({"url": "https://example.com"})
    '# Example Domain\\n\\nThis domain is for use in ...'
    """

    name: str = "urlpipe_read_page"
    description: str = (
        "Read a web page and get its main content as Markdown. The page is loaded "
        "in a real Chrome browser and read after its JavaScript has run, so sites "
        "built with JavaScript (single-page apps, most modern docs and shops) come "
        "back complete, where a plain HTTP fetch would return an empty shell. This "
        "is the tool to use whenever you need to read, quote or reason about what "
        "a page says. Costs 1 credit; asking again for the same page within 7 days "
        "is free."
    )
    operation: ClassVar[str] = "markdown"

    def _render(self, data: Any) -> Any:
        text = str(data)
        return text if text.strip() else "The page has no readable text content."


class UrlpipePageMetadata(UrlpipeBaseTool):
    """A page's metadata as a dict, with the same keys for every page: title,
    description, site name, language, authors, dates, share image, icons, feeds
    and more."""

    name: str = "urlpipe_page_metadata"
    description: str = (
        "Get a web page's metadata as JSON, with the same keys for every page: "
        "title, description, site_name, language, authors (name and link), "
        "published_at, modified_at, image (url and size), favicon_url, feeds, "
        "keywords, canonical_url and more; null where the page declares nothing. "
        "Use it to cite, date or preview a link, or to find a site's feed, without "
        "reading the whole page. Costs 1 credit; when you need the content itself, "
        "use urlpipe_read_page instead."
    )
    operation: ClassVar[str] = "meta"

    def _render(self, data: Any) -> Any:
        return dict(data)


class UrlpipeConsoleErrors(UrlpipeBaseTool):
    """The errors, warnings and uncaught exceptions a page logs while it loads."""

    name: str = "urlpipe_console_errors"
    description: str = (
        "List the JavaScript errors, warnings and uncaught exceptions a web page "
        "logs to the browser console while it loads in real Chrome. Use it to find "
        "out why a page is broken or blank, or to check a site for front-end "
        "errors. Returns one line per entry, marked [error], [warning] or "
        "[exception]. Costs 1 credit."
    )
    operation: ClassVar[str] = "console"

    def _render(self, data: Any) -> Any:
        if not data:
            return "The page logged no errors, warnings or exceptions."
        return "\n".join(f"[{entry.get('type')}] {entry.get('text')}" for entry in data)


class UrlpipeLighthouseInput(UrlpipeInput):
    """The arguments of :class:`UrlpipeLighthouse`."""

    device: Literal["mobile", "desktop"] = Field(
        default="mobile",
        description=(
            "The device to emulate: 'mobile' (a phone on slow 4G with a throttled "
            "CPU, the stricter test) or 'desktop'."
        ),
    )


class UrlpipeLighthouse(UrlpipeBaseTool):
    """A Lighthouse audit, compacted: category scores from 0 to 100 and each key
    metric's displayed value and score."""

    name: str = "urlpipe_lighthouse"
    description: str = (
        "Run a Google Lighthouse audit on a web page and get its scores from 0 to "
        "100 for performance, accessibility, best practices and SEO, plus the key "
        "lab metrics such as First Contentful Paint, Largest Contentful Paint, "
        "Cumulative Layout Shift and Total Blocking Time. Use it to judge how fast "
        "and well built a page is, or to compare mobile and desktop. Costs 2 credits."
    )
    args_schema: type[BaseModel] = UrlpipeLighthouseInput
    operation: ClassVar[str] = "lighthouse"

    def _render(self, data: Any) -> Any:
        return compact_lighthouse(data)


def compact_lighthouse(report: Mapping[str, Any]) -> dict[str, Any]:
    """Keep what a model needs from a Lighthouse report: scores as 0-100
    integers, metrics as their displayed value and score."""
    categories = report.get("categories") or {}
    metrics = report.get("metrics") or {}
    return {
        "url": report.get("url"),
        "device": report.get("device"),
        "scores": {
            name: _percent(category.get("score"))
            for name, category in categories.items()
            if category is not None
        },
        "metrics": {
            name: {"value": metric.get("displayValue"), "score": _percent(metric.get("score"))}
            for name, metric in metrics.items()
            if metric is not None
        },
    }


def _percent(score: Any) -> int | None:
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        return None
    return round(score * 100)
