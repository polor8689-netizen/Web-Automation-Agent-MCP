"""Logging setup for the MCP browser automation server."""

import logging
import sys

_FMT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging exactly once with a stderr stream handler."""
    root = logging.getLogger()
    if root.handlers:
        for handler in list(root.handlers):
            if getattr(handler, "_mcp_ba_owned", False):
                handler.close()
                root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stderr)
    handler._mcp_ba_owned = True  # type: ignore[attr-defined]
    handler.setFormatter(logging.Formatter(fmt=_FMT, datefmt=_DATEFMT))
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)

    numeric = getattr(logging, level.upper(), logging.INFO)
    for name in (
        "mcp_browser_agent",
        "browser_use",
        "playwright",
        "httpx",
        "openai",
        "anyio",
    ):
        logging.getLogger(name).setLevel(numeric)

    if numeric >= logging.DEBUG:
        pass


locale = "en-US"
