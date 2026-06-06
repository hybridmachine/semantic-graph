"""Repository for the FileManifestEntry model."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from semantic_graph.storage.models import FileManifestEntry
from semantic_graph.storage.repositories.base import BaseRepository


class FileManifestEntryRepository(BaseRepository[FileManifestEntry]):
    """CRUD operations for :class:`FileManifestEntry`."""

    def __init__(self) -> None:
        super().__init__(FileManifestEntry)

    def list_by_project(
        self, session: Session, project_id: uuid.UUID
    ) -> list[FileManifestEntry]:
        """Return all manifest entries for *project_id*."""
        stmt = select(FileManifestEntry).filter_by(project_id=project_id)
        return list(session.scalars(stmt))

    def get_by_path(
        self, session: Session, project_id: uuid.UUID, relative_path: str
    ) -> FileManifestEntry | None:
        """Return the manifest entry for a given path, or *None*."""
        stmt = select(FileManifestEntry).filter_by(
            project_id=project_id, relative_path=relative_path
        )
        return session.scalars(stmt).one_or_none()
