"""FastMCP server assembly for the browser automation agent."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from fastmcp import FastMCP

from mcp_browser_agent.config import Settings, get_settings
from mcp_browser_agent.logging_config import configure_logging
from mcp_browser_agent.models import ServerStatus

__version__ = "0.1.0"
_SERVER_STARTED_AT = time.monotonic()


def _check_playwright_installed() -> bool:
    """Return True when Chromium from Playwright is present on disk."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            return Path(p.chromium.executable_path).exists()
    except Exception:
        return False


def create_server(settings: Settings) -> FastMCP[None]:
    """Build the FastMCP server with tools wired from settings."""
    configure_logging(settings.log_level)

    server: FastMCP[None] = FastMCP(
        name="mcp-browser-agent",
        version=__version__,
        instructions=(
            "Tools for extracting structured web content, running browser "
            "automation tasks, and downloading files with SSRF protection."
        ),
    )

    @server.tool()
    async def get_server_status() -> ServerStatus:
        """Report server version, environment, capabilities, and settings."""
        return ServerStatus(
            version=__version__,
            uptime_seconds=time.monotonic() - _SERVER_STARTED_AT,
            llm_configured=settings.llm_configured,
            browser_available=_check_playwright_installed(),
            settings_summary={
                "headless": str(settings.headless),
                "llm_model": settings.llm_model,
                "max_concurrent_tasks": str(settings.max_concurrent_tasks),
                "http_timeout_seconds": str(settings.http_timeout_seconds),
                "task_timeout_seconds": str(settings.task_timeout_seconds),
                "max_pages_per_task": str(settings.max_pages_per_task),
                "max_file_size_mb": str(settings.max_file_size_mb),
                "workspace_dir": str(settings.workspace_root()),
            },
        )

    return server


def main() -> None:
    """Load settings, build the server, and run it over stdio transport."""
    settings = get_settings()
    settings.ensure_workspace()
    server = create_server(settings)

    server.run()


__all__ = ["create_server", "get_server_status", "main"]
