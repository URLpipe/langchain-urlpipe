# Changelog

## 0.1.0 — 2026-09-28

The first release.

- Tools: `UrlpipeReadPage` (`urlpipe_read_page`), `UrlpipePageMetadata` (`urlpipe_page_metadata`), `UrlpipeConsoleErrors` (`urlpipe_console_errors`) and `UrlpipeLighthouse` (`urlpipe_lighthouse`), sync and async. URLpipe errors reach the agent as the tool result.
- `UrlpipeToolkit`: all four tools sharing one client.
- `UrlpipeLoader`: one `Document` per URL as Markdown, HTML or a summary, with `lazy_load`, `alazy_load` and `continue_on_failure`.
- Built on the official `urlpipe` Python client.
