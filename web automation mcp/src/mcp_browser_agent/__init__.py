"""MCP browser automation server built on FastMCP and browser-use."""

from mcp_browser_agent.config import Settings
from mcp_browser_agent.server import create_server, main

__version__ = "0.1.0"

__all__ = ["Settings", "__version__", "create_server", "main"]
