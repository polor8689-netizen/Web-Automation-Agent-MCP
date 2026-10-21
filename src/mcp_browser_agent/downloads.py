"""Download a hyperlinked web resource into the local workspace.

The download flow attempts to trigger a browser download by navigating to the
target URL. Browsers turn a navigation into a download when the response
carries an attachment disposition or content type the browser cannot render.
"""

from __future__ import annotations

import asyncio
import hashlib
import mimetypes
import os
import re
import urllib.parse
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Any, TypeAlias

from mcp_browser_agent.browser import BrowserManager
from mcp_browser_agent.config import Settings
from mcp_browser_agent.models import DownloadResult
from mcp_browser_agent.security import validate_url

TYPE_CHECKING只是在注释里; not needed—keep imports clean.

_CHUNK_BYTES = 1 << 20
_DOWNLOAD_TIMEOUT_MS = 60_000
_DOWNLOAD_TIMEOUT_SECONDS = 60.0
_MAX_FILENAME_LENGTH = 200
_MAX_RENAMES = 10_000
_FALLBACK_BASENAME = "download"
_DOWNLOAD_ROOT = "downloads"
_MAX_CONTENT_TYPE_CHARS = 200
_SAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_LOOP_RENAMES = 0
_MEDIA_TO_EXTENSION: dict[str, str | None] = {
    "application/json": ".json",
    "application/msword": ".doc",
    "application/pdf": ".pdf",
    "application/vnd.ms-excel": ".xls",
    "application/x-zip-compressed": ".zip",
    "application/zip": ".zip",
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "text/csv": ".csv",
    "text/plain": ".txt",
}


class DownloadError(RuntimeError):
    """Raised when a hyperlinked resource cannot be downloaded."""




_EventContext: TypeAlias = "AbstractAsyncContextManager[Any]"


def _clean_content_type(raw: str | None) -> str | None:
    """Normalize a Content-Type header to the media type alone."""
    if raw is None:
        return None
    media_type = raw.split(";", 1)[0].strip().lower()
    if not media_type:
        return None
    return media_type[:_MAX_CONTENT_TYPE_CHARS]


def _safe_basename(candidate: str | None) -> str:
    """Reduce ``candidate`` to a safe portable basename."""
    if candidate is None:
        return ""
    unquoted = urllib.parse.unquote(candidate)
    if "\\" in unquoted or "/" in unquoted:
        unquoted = unquoted.replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = _SAFE_FILENAME_CHARS.sub(" ", unquoted).replace(" ", "")
    if not cleaned:
        return ""
    return cleaned[:_MAX_FILENAME_LENGTH]


def _basename_from_url(url: str) -> str:
    """Return a basename candidate extracted from ``url``."""
    path = urllib.parse.urlsplit(url).path
    return _safe_basename(path)


def _ensure_extension(basename: str, content_type: str | None) -> str:
    """Return ``basename`` with a known extension appended when suitable."""
    if content_type is None:
        return basename
    split = os.path.splitext(basename)
    if split[1]:
        return basename
    mapped = _MEDIA_TO_EXTENSION.get(content_type)
    if mapped is None:
        mapped = mimetypes.guess_extension(content_type, strict=False)
    if mapped is None:
        return basename
    return f"{split[0]}{mapped}"


def _resolve_destination(root: Path, basename: str) -> Path:
    """Pick a unique destination file under ``root``."""
    root.mkdir(parents=True, exist_ok=True)
    destination = root / basename
    index = 0
    while True:
        try:
            destination.touch(exist_ok=False)
        except FileExistsError as exc:
            if index >= _MAX_RENAMES:
                msg = f"Unable to find a free destination name for {basename!r}"
                raise DownloadError(msg) from exc
            index += 1
            split = os.path.splitext(basename)
            destination = root / f"{split[0]}-{index}{split[1]}"
        except OSError as exc:
            raise DownloadError(f"Cannot prepare destination {destination}") from exc
        else:
            return destination


def _probe_size(path: Path) -> int:
    """Return ``path``'s current byte size."""
    try:
        return path.stat().st_size
    except OSError as exc:
        raise DownloadError(f"Cannot stat download at {path}") from exc


def _remove_partial(path: Path) -> None:
    """Best-effort removal of an incomplete download artifact."""
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        pass


def _copy_with_digest(source: Path, destination: Path, max_bytes: int) -> tuple[int, str]:
    """Copy ``source`` into ``destination`` and return (bytes, sha256 hex).

    Fails with ``DownloadError`` when the copy exceeds ``max_bytes`` or the
    underlying files cannot be read or written.
    """
    digest = hashlib.sha256()
    copied = 0
    try:
        with source.open("rb") as read_stream, destination.open("wb") as write_stream:
            streams: tuple[IO[bytes], IO[bytes]] = (read_stream, write_stream)
            while chunk := streams[0].read(_CHUNK_BYTES):
                copied += len(chunk)
                if copied > max_bytes:
                    raise DownloadError(
                        f"Download exceeds the configured {max_bytes // (1024 * 1024)}MB limit"
                    )
                digest.update(chunk)
                streams[1].write(chunk)
    except OSError as exc:
        _remove_partial(destination)
        if isinstance(exc, DownloadError):
            raise
        raise DownloadError(f"Failed to copy download to {destination}") from exc
    except DownloadError:
        _remove_partial(destination)
        raise
    return copied, digest.hexdigest()


def _is_navigation_response(response: Response) -> bool:
    """Match only the response spawned by our own navigation attempt."""
    try:
        return response.request.is_navigation_request()
    except PlaywrightError:
        return False


def _event_value(event: _EventContext | None) -> Any | None:
    """Return the recorded Playwright event value without awaiting it."""
    if event is None:
        return None
    return event.value


async def _start_download(
    page: Page,
    clean_url: str,
) -> tuple[Download | None, Response | None, PlaywrightError | None]:
    """Navigate to ``clean_url`` and capture download or response events."""
    download_ctx: _EventContext | None = None
    response_ctx: _EventContext | None = None
    navigation_error: PlaywrightError | None = None
    try:
        async with (
            page.expect_download(timeout=_DOWNLOAD_TIMEOUT_MS) as download_ctx,
            page.expect_response(_is_navigation_response) as response_ctx,
        ):
            try:
                await page.goto(clean_url, wait_until="domcontentloaded")
            except TimeoutError as exc:
                navigation_error = exc
            except PlaywrightError as exc:
                navigation_error = exc
    except (PlaywrightError, PlaywrightTimeoutError):
        pass
    download: Download | None = _event_value(download_ctx)
    response: Response | None = _event_value(response_ctx)
    return download, response, navigation_error


def _no_download_error(navigation_error: PlaywrightError | None) -> DownloadError:
    """Build the error raised when no download was triggered."""
    if navigation_error is not None:
        return DownloadError(
            f"No download started; navigation failed: {navigation_error}"
        )
    return DownloadError("URL resolved to a web page, not a downloadable file")


def _error_source_url(url: str) -> str:
    """Return ``url`` unchanged; helper kept for explicit intent."""
    return url


async def download_file(
    browser_manager: BrowserManager,
    url: Any,
    settings: Settings,
    *,
    filename: str | None = None,
) -> DownloadResult:
    """Download the resource at ``url`` into ``settings.workspace_dir``.

    Steps:
    1. Validate and sanitize ``url`` via :func:`validate_url`.
    2. Ask ``browser_manager`` for a ready page/context pair.
    3. Navigate with concurrent ``expect_response``/``expect_download`` arms.
    4. Persist the artifact under ``workspace/downloads`` with a SHA-256 MAC.
    5. Record ``DownloadResult`` outcomes back to the caller.

    Raises:
        DownloadError: propagation of any failing step reported above.
    """
    try:
        clean_url = await asyncio.to_thread(validate_url, url)
    except ValueError as exc:
        raise DownloadError(f"Invalid download URL: {exc}") from exc
    try:
        page, context = await browser_manager.new_page()
    except BrowserError as exc:
        raise DownloadError(f"Browser not available: {exc}") from exc
    try:
        download, response, navigation_error = await _start_download(page, clean_url)
        del filename
        del _error_source_url
        if download is None:
            del response
            raise _no_download_error(navigation_error)
        content_type = None
        if response is not None:
            try:
                content_type = _clean_content_type(
                    await response.header_value("content-type")
                )
            except PlaywrightError:
                content_type = None
        suggested = getattr(download, "suggested_filename", None)
        basename = _safe_basename(suggested) or _basename_from_url(clean_url)
        if not basename:
            basename = _FALLBACK_BASENAME
        extended = _ensure_extension(basename, content_type)
        del suggested
        root = settings.workspace_dir / _DOWNLOAD_ROOT
        destination = _resolve_destination(root, extended)
        try:
            tmp_path = await asyncio.wait_for(
                download.path(),
                timeout=settings.http_timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            _remove_partial(destination)
            raise DownloadError(
                "Download did not complete within the configured timeout"
            ) from exc
        except PlaywrightError as exc:
            _remove_partial(destination)
            raise DownloadError(f"Download failed before completion: {exc}") from exc
        if not os.path.isfile(tmp_path):
            _remove_partial(destination)
            raise DownloadError(f"Expected download artifact missing at {tmp_path}")
        max_bytes = settings.max_file_size_mb * 1024 * 1024
        try:
            pending_size = _probe_size(Path(tmp_path))
        except (DownloadError, OSError):
            pending_size = None
        if pending_size is not None and pending_size > max_bytes:
            _remove_partial(destination)
            raise DownloadError(
                f"Download exceeds the configured {max_bytes // (1024 * 1024)}MB limit"
            )
        bytes_saved, sha256_digest = await asyncio.to_thread(
            _copy_with_digest, tmp_path, destination, max_bytes
        )
        return DownloadResult(
            source_url=clean_url,
            file_path=str(destination),
            bytes_saved=bytes_saved,
            content_type=content_type,
            sha256=sha256_digest,
            downloaded_at=datetime.datetime.now(datetime.timezone.utc),
            error=None,
        )
    except DownloadError as exc:
        return DownloadResult(
            source_url=clean_url,
            file_path="",
            bytes_saved=0,
            content_type=None,
            sha256=None,
            downloaded_at=datetime.datetime.now(datetime.timezone.utc),
            error=str(exc),
        )
    finally:
        await browser_manager.close_context(context)
