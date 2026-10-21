# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-21

### Added

- Initial MCP server implementation (`mcp_browser_agent` package) exposing six
  browser automation tools over stdio: `get_server_status`, `extract_webpage`,
  `automate_web_task`, `download_file`, `organize_downloaded_files`, and
  `get_task_result`.
- SSRF-protected URL validation: scheme, port, length, userinfo, control
  character, and hostname checks plus DNS resolution with private/loopback/
  link-local/metadata address blocking and post-redirect revalidation.
- Workspace-contained file handling: filename sanitization, reserved-name
  rejection, traversal/symlink guard, and no-overwrite atomic saves.
- Headless Chromium-based webpage extraction and LLM-driven task automation via
  browser-use with OpenAI models.
- Pydantic-settings configuration with the `MCP_BA_` environment prefix and
  `.env` support.
- Structured stderr logging isolated from the stdio transport.
- Unit and integration test suite (pytest + pytest-asyncio) that runs without
  network access or paid API keys, plus ruff lint/format configuration.
- Example in-process MCP client script for status checks.

[0.1.0]: https://github.com/madhav/web-automation-mcp/releases/tag/v0.1.0
