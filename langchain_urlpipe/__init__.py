"""LangChain integration for URLpipe: read any web page as Markdown, get its
metadata, console errors or a Lighthouse audit, rendered in real Chrome.

Docs: https://urlpipe.dev/integrations/langchain
"""

from importlib import metadata

from langchain_urlpipe.document_loaders import UrlpipeLoader
from langchain_urlpipe.toolkits import UrlpipeToolkit
from langchain_urlpipe.tools import (
    UrlpipeConsoleErrors,
    UrlpipeLighthouse,
    UrlpipePageMetadata,
    UrlpipeReadPage,
)

try:
    __version__ = metadata.version(__package__ or "langchain-urlpipe")
except metadata.PackageNotFoundError:
    __version__ = ""
del metadata

__all__ = [
    "UrlpipeConsoleErrors",
    "UrlpipeLighthouse",
    "UrlpipeLoader",
    "UrlpipePageMetadata",
    "UrlpipeReadPage",
    "UrlpipeToolkit",
    "__version__",
]
