"""Repository for the FileManifestEntry model."""

from __future__ import annotations

import uuid

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
        return list(
            session.query(FileManifestEntry)
            .filter(FileManifestEntry.project_id == project_id)
            .all()
        )

    def get_by_path(
        self, session: Session, project_id: uuid.UUID, relative_path: str
    ) -> FileManifestEntry | None:
        """Return the manifest entry for a given path, or *None*."""
        return (
            session.query(FileManifestEntry)
            .filter(
                FileManifestEntry.project_id == project_id,
                FileManifestEntry.relative_path == relative_path,
            )
            .one_or_none()
        )
