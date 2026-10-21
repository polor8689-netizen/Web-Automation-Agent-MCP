"""Pydantic models shared by MCP tools and the task orchestrator."""

import datetime
import sys
from typing import Literal

from pydantic import BaseModel, Field


class ServerStatus(BaseModel):
    """Baseline health and capability report from get_server_status."""

    server_name: str = "mcp-browser-agent"
    version: str
    status: Literal["ok", "degraded"] = "ok"
    python_version: str = Field(default_factory=lambda: sys.version.split()[0])
    platform: str = Field(default_factory=lambda: sys.platform)
    uptime_seconds: float = 0.0
    llm_configured: bool = False
    browser_available: bool = False
    settings_summary: dict[str, str] = Field(default_factory=dict)
    started_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


class ExtractedContent(BaseModel):
    """Structured extraction produced from a single web page."""

    url: str
    title: str | None = None
    content: str | None = None
    links: list[str] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)
    tables: list[list[list[str]]] = Field(default_factory=list)
    fetched_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    error: str | None = None


class TaskStatus(BaseModel):
    """State of one automation task."""

    task_id: str
    status: Literal["queued", "running", "completed", "failed"] = "queued"
    target_url: str
    instruction: str
    started_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    finished_at: datetime.datetime | None = None
    pages_visited: int = 0
    error: str | None = None


class DownloadResult(BaseModel):
    """Outcome of one file download."""

    source_url: str
    file_path: str
    bytes_saved: int = 0
    content_type: str | None = None
    sha256: str | None = None
    downloaded_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    error: str | None = None


class OrganizedFiles(BaseModel):
    """Classification of downloaded files organized into category folders."""

    categorized: dict[str, list[str]] = Field(default_factory=dict)
    total_files: int = 0
    moved_count: int = 0
    skipped_count: int = 0
    errors: list[str] = Field(default_factory=list)


class TaskResult(BaseModel):
    """Full result envelope for one automation task."""

    task_id: str
    status: Literal["completed", "failed", "running", "queued"] = "queued"
    answer: str | None = None
    pages_visited: int = 0
    action_summary: list[str] = Field(default_factory=list)
    error: str | None = None
    duration_seconds: float = 0.0
