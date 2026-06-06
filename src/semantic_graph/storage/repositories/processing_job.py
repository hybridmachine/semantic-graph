"""Repository for the ProcessingJob model."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from semantic_graph.storage.models import ProcessingJob
from semantic_graph.storage.repositories.base import BaseRepository


class ProcessingJobRepository(BaseRepository[ProcessingJob]):
    """CRUD operations for :class:`ProcessingJob`."""

    def __init__(self) -> None:
        super().__init__(ProcessingJob)

    def list_by_project(
        self, session: Session, project_id: uuid.UUID
    ) -> list[ProcessingJob]:
        """Return all processing jobs for *project_id*."""
        stmt = select(ProcessingJob).filter_by(project_id=project_id)
        return list(session.scalars(stmt))
