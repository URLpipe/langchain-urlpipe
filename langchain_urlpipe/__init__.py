"""LangChain integration for URLpipe: read any web page as Markdown, get its
metadata, data in your own fields, its technologies, console errors or a
Lighthouse audit, rendered in real Chrome.

Docs: https://urlpipe.dev/integrations/langchain
"""

from importlib import metadata

from langchain_urlpipe.document_loaders import UrlpipeLoader
from langchain_urlpipe.toolkits import UrlpipeToolkit
from langchain_urlpipe.tools import (
    UrlpipeConsoleErrors,
    UrlpipeExtractData,
    UrlpipeLighthouse,
    UrlpipePageMetadata,
    UrlpipeReadPage,
    UrlpipeTechnologies,
)

try:
    __version__ = metadata.version(__package__ or "langchain-urlpipe")
except metadata.PackageNotFoundError:
    __version__ = ""
del metadata

__all__ = [
    "UrlpipeConsoleErrors",
    "UrlpipeExtractData",
    "UrlpipeLighthouse",
    "UrlpipeLoader",
    "UrlpipePageMetadata",
    "UrlpipeReadPage",
    "UrlpipeTechnologies",
    "UrlpipeToolkit",
    "__version__",
]
