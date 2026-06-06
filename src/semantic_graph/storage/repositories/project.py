"""Repository for the Project model."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from semantic_graph.storage.models import Project
from semantic_graph.storage.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    """CRUD operations for :class:`Project`."""

    def __init__(self) -> None:
        super().__init__(Project)

    def get_by_name(self, session: Session, name: str) -> Project | None:
        """Return the project with *name*, or *None*."""
        stmt = select(Project).filter_by(name=name)
        return session.scalars(stmt).one_or_none()
