# langchain-urlpipe

Let your LangChain agents read any web page, JavaScript sites included, and load pages into your RAG pipeline as clean Markdown.

[URLpipe](https://urlpipe.dev) renders each page in real Chrome before it answers, so a single-page app or a docs site built with JavaScript comes back with its content, where a plain HTTP fetch gets an empty shell. This package gives you six LangChain tools, a toolkit and a document loader, built on the official [`urlpipe`](https://pypi.org/project/urlpipe/) Python client.

## Install

```sh
pip install langchain-urlpipe
```

Python 3.10 or later.

## Set up your API key

Create a project at [urlpipe.dev](https://urlpipe.dev) and copy its API key. The Free plan gives you 1,000 credits a month, no card needed.

```sh
export URLPIPE_API_KEY=your_project_key
```

Every tool, the toolkit and the loader read `URLPIPE_API_KEY`, or take `api_key="…"` directly.

## Tools

| Tool | Name the model sees | What it returns | Credits |
|---|---|---|---|
| `UrlpipeReadPage` | `urlpipe_read_page` | the page's main content as Markdown | 1 |
| `UrlpipePageMetadata` | `urlpipe_page_metadata` | title, description, site name, language, authors, dates, share image, icons, feeds and more — the same keys for every page | 1 |
| `UrlpipeExtractData` | `urlpipe_extract_data` | the values you name, read off the page with AI: a dict with exactly your fields, `None` where the page gives no value | 24 |
| `UrlpipeTechnologies` | `urlpipe_technologies` | what the site is built with — CMS, frameworks, analytics, CDN — with versions and a confidence | 1 |
| `UrlpipeConsoleErrors` | `urlpipe_console_errors` | the errors, warnings and uncaught exceptions the page logs | 1 |
| `UrlpipeLighthouse` | `urlpipe_lighthouse` | Lighthouse scores (0–100) and key metrics, on `mobile` or `desktop` | 2 |

Each takes a `url` and an optional `max_age`: how fresh a stored copy must be, in seconds or as a duration such as `"1 hour"`. Asking for the same page again within 7 days is served from storage and costs nothing; `max_age=0` always loads it fresh.

```python
from langchain_urlpipe import UrlpipeReadPage, UrlpipeLighthouse

UrlpipeReadPage().invoke({"url": "https://example.com"})
# '# Example Domain\n\nThis domain is for use in …'

UrlpipeLighthouse().invoke({"url": "https://example.com", "device": "desktop"})
# {'url': 'https://example.com', 'device': 'desktop',
#  'scores': {'performance': 100, 'accessibility': 88, 'best-practices': 100, 'seo': 90},
#  'metrics': {'first-contentful-paint': {'value': '0.3 s', 'score': 100}, …}}
```

`UrlpipeExtractData` also takes the `fields` to fill, each with a `name`, a `type` (`string` unless you say otherwise) and a `description` of which value is meant, and optional `instructions` for all of them:

```python
from langchain_urlpipe import UrlpipeExtractData

UrlpipeExtractData().invoke({
    "url": "https://example.com/shoe",
    "fields": [
        {"name": "name"},
        {"name": "price", "type": "number", "description": "The current price, without the currency"},
        {"name": "sizes", "type": "array", "items": {"type": "string"}},
    ],
    "instructions": "Prices in euros.",
})
# {'name': 'Trail Shoe', 'price': 89.5, 'sizes': ['40', '41', '42']}
```

### In an agent

```python
from langchain.agents import create_agent
from langchain_urlpipe import UrlpipeReadPage, UrlpipePageMetadata

agent = create_agent(
    "anthropic:claude-sonnet-5",
    tools=[UrlpipeReadPage(), UrlpipePageMetadata()],
    system_prompt="You answer questions about web pages. Read a page before you describe it.",
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "What plans does https://urlpipe.dev/pricing list?"}]}
)
print(result["messages"][-1].content)
```

Or bind the tools to any chat model that supports tool calling:

```python
from langchain.chat_models import init_chat_model
from langchain_urlpipe import UrlpipeReadPage

read_page = UrlpipeReadPage()
model = init_chat_model("openai:gpt-4.1-mini").bind_tools([read_page])

message = model.invoke("Summarise https://example.com in one sentence.")
for call in message.tool_calls:
    print(read_page.invoke(call))  # a ToolMessage with the page's Markdown
```

When URLpipe cannot load a page, or your credits run out, the tool returns the API's explanation to the model as the tool result (a `ToolMessage` with `status="error"`), so the agent can try another page or tell you why. Pass `handle_tool_error=False` to have a `ToolException` raised instead.

## Toolkit

`UrlpipeToolkit` hands an agent all six tools at once, sharing one client:

```python
from langchain.agents import create_agent
from langchain_urlpipe import UrlpipeToolkit

tools = UrlpipeToolkit().get_tools()
agent = create_agent("anthropic:claude-sonnet-5", tools=tools)

agent.invoke(
    {"messages": [{"role": "user", "content": "Why is https://example.com slow on mobile?"}]}
)
```

## Document loader

`UrlpipeLoader` turns a list of URLs into `Document`s, one per page, with the page as Markdown:

```python
from langchain_urlpipe import UrlpipeLoader

loader = UrlpipeLoader(
    ["https://urlpipe.dev/docs", "https://urlpipe.dev/pricing"],
    page_options={"block_cookie_banners": True},
)
docs = loader.load()

docs[0].metadata
# {'source': 'https://urlpipe.dev/docs', 'operation': 'markdown', 'token': '…', 'cache': 'miss'}
```

- `operation="markdown"` (the default, 1 credit a page), `"html"` for the HTML after JavaScript ran (1 credit), or `"summarize"` for an AI summary in Markdown (17 credits).
- `max_age` and `page_options` (`wait_for_selector`, `scroll_to_bottom`, `delay`, `block_ads`, `block_cookie_banners`, `block_popups`, `remove_selectors`) go with every page.
- `continue_on_failure=True` logs and skips a page that fails instead of raising its `urlpipe.UrlpipeError`.
- `lazy_load()` yields pages one at a time as they arrive; `alazy_load()` and `aload()` load up to `max_concurrency` pages at once (3 by default) and keep the order of your URLs.

### For RAG

Markdown keeps the page's headings, so you can split on them and keep each chunk's section as metadata:

```python
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_urlpipe import UrlpipeLoader

docs = UrlpipeLoader(["https://urlpipe.dev/docs"]).load()

by_heading = MarkdownHeaderTextSplitter(
    headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")]
)
sized = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)

chunks = []
for doc in docs:
    for section in by_heading.split_text(doc.page_content):
        section.metadata.update(doc.metadata)  # keep source, token, cache
        chunks.extend(sized.split_documents([section]))

# add `chunks` to any vector store
```

`langchain-text-splitters` is a separate install: `pip install langchain-text-splitters`.

## Configuration

The tools, the toolkit and the loader take the same connection arguments:

```python
UrlpipeReadPage(
    api_key="…",                                     # default: URLPIPE_API_KEY
    client_kwargs={"timeout": 120, "max_retries": 3},  # passed to urlpipe.Client
)
```

`client_kwargs` accepts `base_url`, `timeout`, `max_retries` and `wait_timeout`, as documented for the [`urlpipe` client](https://pypi.org/project/urlpipe/). To reuse a client you already have, or send requests through your own `httpx` client, pass `client=urlpipe.Client(…)` and `async_client=urlpipe.AsyncClient(…)`. Without `async_client`, each async call opens its own connection, so the tools work from any event loop.

## Links

- The LangChain integration on urlpipe.dev: https://urlpipe.dev/integrations/langchain
- API docs: https://urlpipe.dev/docs
- MCP server, for using URLpipe from AI assistants: https://github.com/URLpipe/mcp

## License

MIT © Aliat Partner S.L.
