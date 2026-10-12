"""URLpipe tools: read a page, get its metadata, read data off it into your own
fields, detect what it is built with, list its console errors and run a
Lighthouse audit, each rendered in real Chrome."""

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


class UrlpipeExtractField(BaseModel):
    """One value to read off the page."""

    name: str = Field(
        description="The key this value has in the result: letters, digits and underscores."
    )
    type: Literal[
        "string", "number", "integer", "boolean", "date", "datetime", "url", "email", "object", "array"
    ] = Field(default="string", description="The type of the value.")
    description: str | None = Field(
        default=None,
        description=(
            "Which value is meant, in plain words, such as 'the current price, "
            "without the currency'. Up to 300 characters."
        ),
    )
    fields: list[dict[str, Any]] | None = Field(
        default=None,
        description="For type 'object': its own fields, each written like this one.",
    )
    items: dict[str, Any] | None = Field(
        default=None,
        description=(
            "For type 'array': what each item is, such as {'type': 'string'} or "
            "{'type': 'object', 'fields': [{'name': 'color', 'type': 'string'}]}."
        ),
    )


class UrlpipeExtractDataInput(UrlpipeInput):
    """The arguments of :class:`UrlpipeExtractData`."""

    fields: list[UrlpipeExtractField] = Field(
        min_length=1,
        description=(
            "The values to read off the page, up to 50 counting nested ones. The "
            "result has exactly these names, in this order."
        ),
    )
    instructions: str | None = Field(
        default=None,
        description=(
            "Guidance that applies to every field, such as 'prices in euros' or "
            "'the first product only'. Up to 1,000 characters."
        ),
    )


class UrlpipeExtractData(UrlpipeBaseTool):
    """Data read off a page with AI, as a dict with the fields you name.

    >>> tool = UrlpipeExtractData()  # reads URLPIPE_API_KEY
    >>> tool.invoke({
    ...     "url": "https://example.com/shoe",
    ...     "fields": [{"name": "name"}, {"name": "price", "type": "number"}],
    ... })
    {'name': 'Trail Shoe', 'price': 89.5}
    """

    name: str = "urlpipe_extract_data"
    description: str = (
        "Read specific values off a web page into the fields you name, as JSON: a "
        "product's name and price, an article's author and date, a list of job "
        "postings with their titles and locations. The page is loaded in a real "
        "Chrome browser and read after its JavaScript has run. The result has "
        "exactly your fields, in your order; a value the page does not give is "
        "null, never guessed. Costs 24 credits, so use it when you need the same "
        "fields as data, for instance across many pages; to read or reason about "
        "one page, urlpipe_read_page costs 1."
    )
    args_schema: type[BaseModel] = UrlpipeExtractDataInput
    operation: ClassVar[str] = "extract"

    def _arguments(self, options: dict[str, Any]) -> dict[str, Any]:
        fields = [
            field.model_dump(exclude_none=True) if isinstance(field, BaseModel) else dict(field)
            for field in options["fields"]
        ]
        arguments: dict[str, Any] = {"fields": fields}
        if options.get("instructions"):
            arguments["instructions"] = options["instructions"]
        return arguments

    def _render(self, data: Any) -> Any:
        return dict(data)


class UrlpipeTechnologies(UrlpipeBaseTool):
    """What a site is built with, compacted: each technology's name, version,
    categories and how certain the detection is."""

    name: str = "urlpipe_technologies"
    description: str = (
        "Detect what a website is built with: its CMS or shop platform, JavaScript "
        "frameworks, analytics, tag managers, CDN and web server, with versions "
        "where the page shows them. Returns each technology's name, version, "
        "categories and a confidence from 0 to 100, most certain first. Use it to "
        "profile a site or check which tools it runs. Costs 1 credit."
    )
    operation: ClassVar[str] = "technologies"

    def _render(self, data: Any) -> Any:
        return compact_technologies(data)


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


def compact_technologies(result: Mapping[str, Any]) -> dict[str, Any]:
    """Keep what a model needs from a technologies result: what each one is,
    not how it was detected."""
    return {
        "final_url": result.get("final_url"),
        "technologies": [
            {
                "name": technology.get("name"),
                "version": technology.get("version"),
                "categories": [
                    category.get("name") for category in technology.get("categories") or []
                ],
                "confidence": technology.get("confidence"),
            }
            for technology in result.get("technologies") or []
        ],
    }


def _percent(score: Any) -> int | None:
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        return None
    return round(score * 100)
