"""Page extraction primitives for the MCP browser-automation server."""

from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Any

from .browser import BrowserError, BrowserManager, _close_context
from .config import Settings
from .models import ExtractedContent
from .security import validate_url

logger = logging.getLogger(__name__)

MAX_TEXT_CHARS = 200_000
MAX_LINKS = 1_000
MAX_IMAGES = 500
MAX_TABLES = 50


def _build_extract_script() -> str:
    template = """
() => {
    const MAX_TEXT = __MAX_TEXT__;
    const MAX_LINKS = __MAX_LINKS__;
    const MAX_IMAGES = __MAX_IMAGES__;
    const MAX_TABLES = __MAX_TABLES__;
    const collect = (selector, attribute, cap) => {
        const values = new Set();
        for (const node of document.querySelectorAll(selector)) {
            const raw = node.getAttribute(attribute) || "";
            if (!raw) {
                continue;
            }
            let resolved;
            try {
                resolved = new URL(raw, location.href).toString();
            } catch (error) {
                continue;
            }
            if (resolved.startsWith("http://") || resolved.startsWith("https://")) {
                values.add(resolved);
            }
            if (values.size >= cap) {
                break;
            }
        }
        return Array.from(values);
    };
    const body = document.body;
    const text = body ? String(body.innerText).slice(0, MAX_TEXT) : "";
    const links = collect("a[href]", "href", MAX_LINKS);
    const images = collect("img[src]", "src", MAX_IMAGES);
    const tables = [];
    for (const table of document.querySelectorAll("table")) {
        if (tables.length >= MAX_TABLES) {
            break;
        }
        const rows = [];
        for (const row of table.querySelectorAll("tr")) {
            if (rows.length >= MAX_TABLES) {
                break;
            }
            const cells = [];
            for (const cell of row.querySelectorAll("th, td")) {
                if (cells.length >= MAX_TABLES) {
                    break;
                }
                cells.push(String(cell.textContent || ""));
            }
            rows.push(cells);
        }
        tables.push(rows);
    }
    return {
        title: document.title || "",
        text: text,
        links: links,
        images: images,
        tables: tables,
    };
}
"""
    replacements = {
        "__MAX_TEXT__": str(MAX_TEXT_CHARS),
        "__MAX_LINKS__": str(MAX_LINKS),
        "__MAX_IMAGES__": str(MAX_IMAGES),
        "__MAX_TABLES__": str(MAX_TABLES),
    }
    script = template
    for token, value in replacements.items():
        script = script.replace(token, value)
    return script.strip()


EXTRACT_SCRIPT = _build_extract_script()


class ExtractionError(RuntimeError):
    """Raised when a webpage cannot be fetched or parsed."""


def _string_list(value: Any, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    collected: list[str] = []
    for item in value:
        if isinstance(item, str):
            collected.append(item)
        if len(collected) >= limit:
            break
    return collected


def _table_rows(value: Any) -> list[list[list[str]]]:
    if not isinstance(value, list):
        return []
    tables: list[list[list[str]]] = []
    for table in value:
        if not isinstance(table, list):
            continue
        rows: list[list[str]] = []
        for row in table:
            if not isinstance(row, list):
                continue
            cells: list[str] = []
            for cell in row:
                if isinstance(cell, str):
                    cells.append(cell)
            rows.append(cells)
        tables.append(rows)
        if len(tables) >= MAX_TABLES:
            break
    return tables


async def extract_webpage(
    browser_manager: BrowserManager,
    url: str,
    settings: Settings,
) -> ExtractedContent:
    """Fetch and parse a webpage using a Playwright page."""
    try:
        cleaned_url = await asyncio.to_thread(validate_url, url)
    except ValueError as exc:
        raise ExtractionError(str(exc)) from exc

    try:
        page, context = await browser_manager.new_page()
    except BrowserError as exc:
        raise ExtractionError(str(exc)) from exc

    try:
        try:
            await page.goto(cleaned_url, wait_until="domcontentloaded")
        except Exception as exc:
            raise ExtractionError(f"Navigation failed: {exc}") from exc
        final_url = page.url
        try:
            await asyncio.to_thread(validate_url, final_url)
        except ValueError as exc:
            raise ExtractionError(f"Redirected to a disallowed URL: {exc}") from exc
        payload = await page.evaluate(EXTRACT_SCRIPT)
        if not isinstance(payload, dict):
            raise ExtractionError("Unexpected page data type")
    finally:
        await _close_context(context)

    links = _string_list(payload.get("links"), MAX_LINKS)
    images = _string_list(payload.get("images"), MAX_IMAGES)
    tables = _table_rows(payload.get("tables"))
    title = payload.get("title")
    text = payload.get("text")

    logger.debug(
        "Extracted %d links and %d images from %s",
        len(links),
        len(images),
        final_url,
    )
    return ExtractedContent(
        url=final_url,
        title=title if isinstance(title, str) and title else None,
        content=text if isinstance(text, str) else None,
        links=links,
        images=images,
        tables=tables,
        fetched_at=datetime.datetime.now(datetime.UTC),
        error=None,
    )
