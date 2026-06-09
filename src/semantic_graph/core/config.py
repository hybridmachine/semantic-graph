"""Application configuration via pydantic-settings."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SEMANTIC_GRAPH_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    app_name: str = Field(default="semantic-graph")
    debug: bool = Field(default=False)
    # Defaults to loopback for local security (NFR-24); override to 0.0.0.0
    # when running in Docker or on a LAN (e.g. via SEMANTIC_GRAPH_API_HOST).
    api_host: str = Field(default="127.0.0.1")
    api_port: int = Field(default=8000)
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".semantic-graph")
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Allowed CORS origins (NFR-24: defaults to localhost only)",
    )


settings = Settings()
