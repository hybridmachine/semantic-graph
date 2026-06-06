"""Repository for the Project model."""

from __future__ import annotations

from sqlalchemy.orm import Session

from semantic_graph.storage.models import Project
from semantic_graph.storage.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    """CRUD operations for :class:`Project`."""

    def __init__(self) -> None:
        super().__init__(Project)

    def get_by_name(self, session: Session, name: str) -> Project | None:
        """Return the project with *name*, or *None*."""
        return session.query(Project).filter(Project.name == name).one_or_none()
