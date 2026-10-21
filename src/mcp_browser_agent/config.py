"""Application settings with environment overrides and test-safe construction."""

from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the MCP browser automation server."""

    model_config = SettingsConfigDict(
        env_prefix="MCP_BA_",
        env_file=None,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    openai_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.0
    headless: bool = True
    workspace_dir: Path = Path("workspace")
    log_level: str = "INFO"
    http_timeout_seconds: int = Field(default=30, ge=1)
    max_redirects: int = Field(default=10, ge=0)
    task_timeout_seconds: int = Field(default=600, ge=1)
    max_pages_per_task: int = Field(default=20, ge=1)
    max_file_size_mb: int = Field(default=200, ge=1)
    max_concurrent_tasks: int = Field(default=3, ge=1)
    max_url_length: int = Field(default=2048, ge=16)
    save_conversation_path: Path | None = None

    @field_validator("openai_api_key", "save_conversation_path", mode="before")
    @classmethod
    def _empty_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        upper = value.strip().upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}")
        return upper

    @field_validator("llm_temperature")
    @classmethod
    def _validate_temperature(cls, value: float) -> float:
        if not 0.0 <= value <= 2.0:
            raise ValueError("llm_temperature must be between 0.0 and 2.0")
        return value

    @model_validator(mode="after")
    def _workspace_not_optional(self) -> Self:
        if not str(self.workspace_dir).strip():
            raise ValueError("workspace_dir must not be empty")
        return self

    def workspace_root(self) -> Path:
        """Return the absolute workspace root."""
        return Path(self.workspace_dir).resolve()

    def downloads_dir(self) -> Path:
        """Return the absolute downloads directory."""
        return self.workspace_root() / "downloads"

    def results_dir(self) -> Path:
        """Return the absolute task results directory."""
        return self.workspace_root() / "results"

    def ensure_workspace(self) -> Path:
        """Create the workspace tree if missing and return the root."""
        root = self.workspace_root()
        root.mkdir(parents=True, exist_ok=True)
        self.downloads_dir().mkdir(parents=True, exist_ok=True)
        self.results_dir().mkdir(parents=True, exist_ok=True)
        return root

    @property
    def llm_configured(self) -> bool:
        """Whether an OpenAI API key is present."""
        return self.openai_api_key is not None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load process-wide settings from the environment."""
    return Settings()
