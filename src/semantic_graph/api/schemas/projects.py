"""Pydantic schemas for project management endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ProjectCreate(BaseModel):
    """Payload for ``POST /api/v1/projects``."""

    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    root_path: str = Field(
        ..., min_length=1, max_length=1024, description="Absolute path to scan"
    )
    include_patterns: list[str] = Field(
        default_factory=lambda: ["*"],
        description="Glob patterns for files to include",
    )
    exclude_patterns: list[str] = Field(
        default_factory=list,
        description="Glob patterns for files to exclude",
    )
    respect_gitignore: bool = Field(
        default=True,
        description="Whether to respect .gitignore",
    )
    max_file_size_bytes: int = Field(
        default=10_485_760,
        ge=1,
        description="Maximum file size in bytes (default 10 MB)",
    )
    follow_symlinks: bool = Field(
        default=False,
        description="Whether to follow symlinks",
    )
    llm_provider: str | None = Field(
        default=None, max_length=100, description="LLM provider name"
    )
    llm_model: str | None = Field(
        default=None, max_length=255, description="LLM model name"
    )
    llm_parameters: dict[str, Any] | None = Field(
        default=None, description="LLM provider-specific parameters"
    )

    @field_validator("root_path")
    @classmethod
    def _root_path_must_be_absolute(cls, v: str) -> str:
        if not v.startswith("/"):
            raise ValueError("root_path must be an absolute path")
        return v


class ProjectUpdate(BaseModel):
    """Payload for ``PUT /api/v1/projects/{id}``.  All fields optional."""

    name: str | None = Field(
        default=None, min_length=1, max_length=255, description="Project name"
    )
    root_path: str | None = Field(
        default=None, min_length=1, max_length=1024, description="Absolute path"
    )
    include_patterns: list[str] | None = Field(
        default=None, description="Glob patterns for files to include"
    )
    exclude_patterns: list[str] | None = Field(
        default=None, description="Glob patterns for files to exclude"
    )
    respect_gitignore: bool | None = Field(
        default=None, description="Whether to respect .gitignore"
    )
    max_file_size_bytes: int | None = Field(
        default=None, ge=1, description="Maximum file size in bytes"
    )
    follow_symlinks: bool | None = Field(
        default=None, description="Whether to follow symlinks"
    )
    llm_provider: str | None = Field(
        default=None, max_length=100, description="LLM provider name"
    )
    llm_model: str | None = Field(
        default=None, max_length=255, description="LLM model name"
    )
    llm_parameters: dict[str, Any] | None = Field(
        default=None, description="LLM provider-specific parameters"
    )
    status: str | None = Field(
        default=None, max_length=50, description="Project lifecycle status"
    )

    @field_validator("root_path")
    @classmethod
    def _root_path_must_be_absolute(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith("/"):
            raise ValueError("root_path must be an absolute path")
        return v


class ScanTrigger(BaseModel):
    """Payload for ``POST /api/v1/projects/{id}/scan``."""

    mode: str = Field(
        default="incremental",
        pattern=r"^(incremental|full)$",
        description="Scan mode: 'incremental' or 'full'",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ProjectSummary(BaseModel):
    """Summary view returned in list responses."""

    id: uuid.UUID
    name: str
    root_path: str
    status: str
    node_count: int = 0
    edge_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectDetail(BaseModel):
    """Full project details."""

    id: uuid.UUID
    name: str
    root_path: str
    status: str
    include_patterns: list[str]
    exclude_patterns: list[str]
    respect_gitignore: bool
    max_file_size_bytes: int
    follow_symlinks: bool
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_parameters: dict[str, Any] | None = None
    node_count: int = 0
    edge_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    """Paginated list of projects."""

    items: list[ProjectSummary]
    total: int
    offset: int
    limit: int


class FileManifestEntrySummary(BaseModel):
    """Summary view of a file manifest entry."""

    id: uuid.UUID
    relative_path: str
    content_hash: str
    size_bytes: int
    status: str
    skip_reason: str | None = None
    last_processed_at: datetime | None = None

    model_config = {"from_attributes": True}


class FileManifestListResponse(BaseModel):
    """Paginated list of file manifest entries."""

    items: list[FileManifestEntrySummary]
    total: int
    offset: int
    limit: int
