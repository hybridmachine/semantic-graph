"""SQLAlchemy ORM models for the semantic-graph storage layer.

Two-database architecture:
- ``projects.db`` (shared metadata): Project, ProcessingJob
- Per-project ``graph.db``: Node, Edge, FileManifestEntry
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(UTC)


def _new_uuid() -> uuid.UUID:
    """Generate a new UUID v4."""
    return uuid.uuid4()


# ---------------------------------------------------------------------------
# Declarative bases — separate metadata per database
# ---------------------------------------------------------------------------


class ProjectsBase(DeclarativeBase):
    """Base for models stored in the shared ``projects.db``."""


class GraphBase(DeclarativeBase):
    """Base for models stored in each per-project ``graph.db``."""


# Convenience alias used by tests / fixtures that create all tables in one
# in-memory database.
Base = ProjectsBase


# ---------------------------------------------------------------------------
# Shared mixins
# ---------------------------------------------------------------------------


class UUIDMixin:
    """Mixin providing a UUID primary key with auto-generated default."""

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=_new_uuid,
    )


class TimestampMixin:
    """Mixin providing ``created_at`` and ``updated_at`` columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )


# ---------------------------------------------------------------------------
# projects.db models
# ---------------------------------------------------------------------------


class Project(UUIDMixin, TimestampMixin, ProjectsBase):
    """Project configuration and metadata stored in ``projects.db``."""

    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    root_path: Mapped[str] = mapped_column(String(1024), nullable=False)

    # File scanning configuration
    include_patterns: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSON), default=list, nullable=False
    )
    exclude_patterns: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSON), default=list, nullable=False
    )
    respect_gitignore: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    max_file_size_bytes: Mapped[int] = mapped_column(
        Integer,
        default=10_485_760,
        nullable=False,  # 10 MB
    )
    follow_symlinks: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # LLM configuration
    llm_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    llm_parameters: Mapped[dict[str, Any] | None] = mapped_column(
        MutableDict.as_mutable(JSON), nullable=True
    )

    # Lifecycle
    status: Mapped[str] = mapped_column(String(50), default="idle", nullable=False)

    def __repr__(self) -> str:
        return f"<Project id={self.id!r} name={self.name!r}>"


class ProcessingJob(UUIDMixin, ProjectsBase):
    """Tracks file processing jobs per project in ``projects.db``."""

    __tablename__ = "processing_jobs"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    files_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    files_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors: Mapped[list[dict[str, Any]]] = mapped_column(
        MutableList.as_mutable(JSON), default=list, nullable=False
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<ProcessingJob id={self.id!r} project_id={self.project_id!r}"
            f" type={self.type!r} status={self.status!r}>"
        )


# ---------------------------------------------------------------------------
# Per-project graph.db models
# ---------------------------------------------------------------------------


class Node(UUIDMixin, TimestampMixin, GraphBase):
    """A semantic node in the graph, stored in the per-project ``graph.db``."""

    __tablename__ = "nodes"

    project_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    abstraction_level: Mapped[str] = mapped_column(String(20), nullable=False)
    source_file: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    content_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        MutableDict.as_mutable(JSON),
        default=dict,
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<Node id={self.id!r} name={self.name!r}"
            f" type={self.type!r} level={self.abstraction_level!r}>"
        )


class Edge(UUIDMixin, GraphBase):
    """A relationship between two nodes, stored in the per-project ``graph.db``."""

    __tablename__ = "edges"

    project_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("nodes.id"), nullable=False, index=True
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("nodes.id"), nullable=False, index=True
    )
    relationship_type: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        MutableDict.as_mutable(JSON),
        default=dict,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<Edge id={self.id!r} type={self.relationship_type!r}"
            f" src={self.source_node_id!r} tgt={self.target_node_id!r}>"
        )


class FileManifestEntry(UUIDMixin, GraphBase):
    """Records file-level processing state in the per-project ``graph.db``."""

    __tablename__ = "file_manifest"
    __table_args__ = (
        UniqueConstraint("project_id", "relative_path", name="uq_file_manifest_path"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    relative_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    modified_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    extractor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    skip_reason: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    last_processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<FileManifestEntry id={self.id!r}"
            f" path={self.relative_path!r} status={self.status!r}>"
        )
