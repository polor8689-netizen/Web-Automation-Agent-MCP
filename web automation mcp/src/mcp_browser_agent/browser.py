"""Managed Playwright browser with SSRF-guarded request routing."""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from playwright.async_api import (
    Browser,
    BrowserContext,
    Error as PlaywrightError,
    Page,
    Playwright,
    Request,
    Route,
    async_playwright,
)

from mcp_browser_agent.config import Settings
from mcp_browser_agent.security import validate_url

logger = logging.getLogger(__name__)


class BrowserError(RuntimeError):
    """Raised when the managed browser cannot start or serve a page."""


def _redirect_depth(request: Request) -> int:
    depth = 0
    current: Request | None = request.redirected_from
    while current is not None:
        depth += 1
        current = current.redirected_from
    return depth


async def _abort_route(route: Route) -> None:
    try:
        await route.abort("blocked")
    except PlaywrightError as exc:
        logger.debug("Failed to abort routed request: %s", exc)


async def _guard_route(route: Route, settings: Settings) -> None:
    request = route.request
    try:
        await asyncio.to_thread(validate_url, request.url)
    except ValueError:
        logger.debug("Blocked disallowed URL: %s", request.url)
        await _abort_route(route)
        return
    if _redirect_depth(request) > settings.max_redirects:
        logger.debug(
            "Aborting request beyond the redirect limit of %d: %s",
            settings.max_redirects,
            request.url,
        )
        await _abort_route(route)
        return
    try:
        await route.continue_()
    except PlaywrightError as exc:
        logger.debug("Failed to continue routed request: %s", exc)


async def _close_context(context: BrowserContext) -> None:
    try:
        await context.close()
    except PlaywrightError as exc:
        logger.debug("Failed to close browser context cleanly: %s", exc)


class BrowserManager:
    """Own the Playwright driver and hand out guarded, short-lived pages."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    @property
    def is_running(self) -> bool:
        """Whether Chromium is currently running."""
        return self._browser is not None

    async def start(self) -> None:
        """Start the Playwright driver and launch headless Chromium."""
        if self._browser is not None:
            return
        try:
            self._playwright = await async_playwright().start()
        except PlaywrightError as exc:
            self._playwright = None
            raise BrowserError(f"Failed to start the Playwright driver: {exc}") from exc
        try:
            self._browser = await self._playwright.chromium.launch(
                headless=self._settings.headless
            )
        except PlaywrightError as exc:
            await self._quit_driver()
            raise BrowserError(f"Failed to launch Chromium: {exc}") from exc

    async def stop(self) -> None:
        """Shut down Chromium and the Playwright driver, tolerating errors."""
        await self._quit_driver()

    async def _quit_driver(self) -> None:
        browser = self._browser
        self._browser = None
        if browser is not None:
            try:
                await browser.close()
            except PlaywrightError as exc:
                logger.debug("Failed to close Chromium cleanly: %s", exc)
        playwright = self._playwright
        self._playwright = None
        if playwright is not None:
            try:
                await playwright.stop()
            except PlaywrightError as exc:
                logger.debug("Failed to stop the Playwright driver: %s", exc)

    async def new_page(self) -> tuple[BrowserContext, Page]:
        """Create a fresh browser context and page guarded by URL validation."""
        browser = self._browser
        if browser is None:
            raise BrowserError("Browser is not started; call start() first")
        try:
            context = await browser.new_context()
        except PlaywrightError as exc:
            raise BrowserError(f"Failed to create a browser context: {exc}") from exc
        guard = self._route_guard()
        try:
            timeout_ms = self._settings.http_timeout_seconds * 1000
            await context.set_default_timeout(timeout_ms)
            await context.set_default_navigation_timeout(timeout_ms)
            await context.route("**/*", guard)
        except PlaywrightError as exc:
            await _close_context(context)
            raise BrowserError(f"Failed to prepare the browser context: {exc}") from exc
        try:
            page = await context.new_page()
        except PlaywrightError as exc:
            await _close_context(context)
            raise BrowserError(f"Failed to open a new page: {exc}") from exc
        return context, page

    def _route_guard(self) -> Callable[[Route], Awaitable[None]]:
        settings = self._settings

        async def guard(route: Route) -> None:
            await _guard_route(route, settings)

        return guard
