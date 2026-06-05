"""Application configuration via pydantic-settings."""

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
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    data_dir: str = Field(default="~/.semantic-graph")


settings = Settings()
