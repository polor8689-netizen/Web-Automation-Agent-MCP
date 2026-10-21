# mcp-browser-agent

An MCP (Model Context Protocol) server that exposes browser automation, webpage
extraction, and file download/organization tools for MCP-compatible clients.

## Features

- **get_server_status** — report runtime, configuration, and playwright health.
- **extract_webpage** — load a URL in an isolated headless browser and return
  title, visible text, and links.
- **automate_web_task** — run a natural-language browsing task with an LLM-driven
  agent.
- **download_file** — fetch a file via HTTP with SSRF guards and save it into the
  workspace.
- **organize_downloaded_files** — classify downloads by content type and move
  them into category folders.
- **get_task_result** — retrieve the result of an asynchronous automation task.

Built with [FastMCP](https://gofastmcp.com/), [browser-use](https://browser-use.com/),
and [Playwright](https://playwright.dev/python/).

## Requirements

- Python 3.11+
- OpenAI API key (for `automate_web_task`; other tools work without one)
- Playwright Chromium (installed automatically, see below)

## Installation

```bash
python -m venv .venv
.\.venv\Scripts\pip install -e ".[dev]"   # Windows
.\.venv\Scripts\playwright install chromium
```

## Configuration

Copy `.env.example` to `.env` and set at least `MCP_BA_OPENAI_API_KEY`:

```
MCP_BA_OPENAI_API_KEY=sk-...
MCP_BA_LLM_MODEL=gpt-4o-mini
MCP_BA_HEADLESS=true
MCP_BA_WORKSPACE_DIR=workspace
```

All settings use the `MCP_BA_` prefix; see `.env.example` for the full list.

## Usage

Run the server over stdio:

```bash
.\.venv\Scripts\mcp-browser-agent
```

Add it to an MCP client (e.g. Claude Desktop, `claude_code`, or any MCP
launcher) with a stdio transport pointing at the command above.

An example in-process client is available:

```bash
.\.venv\Scripts\python examples\mcp_client_status.py
```

## Security model

- **SSRF protection** — only `http`/`https` URLs are accepted; localhost, loopback,
  private, link-local, and cloud-metadata addresses (including IPv4-mapped,
  6to4, and Teredo IPv6 forms) are rejected, and hostnames are DNS-resolved and
  re-checked after redirects.
- **Filesystem containment** — downloaded files are restricted to the workspace
  directory; path traversal (`..`), symlink escapes, and Windows reserved names
  are rejected; filenames are sanitized and never overwritten.
- **Browser isolation** — every task runs in a fresh browser context with no
  access to existing profiles or cookies. Page content is treated as untrusted
  data; prompt-injection text found on pages is never followed.

## Development

```bash
.\.venv\Scripts\pip install -e ".[dev]"
.\.venv\Scripts\pytest
.\.venv\Scripts\ruff check .
.\.venv\Scripts\ruff format .
```

See `CHANGELOG.md` for version history.

## License

MIT — see `LICENSE`.
