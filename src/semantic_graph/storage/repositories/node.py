"""Repository for the Node model."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from semantic_graph.storage.models import Node
from semantic_graph.storage.repositories.base import BaseRepository


class NodeRepository(BaseRepository[Node]):
    """CRUD operations for :class:`Node`."""

    def __init__(self) -> None:
        super().__init__(Node)

    def list_by_project(self, session: Session, project_id: uuid.UUID) -> list[Node]:
        """Return all nodes belonging to *project_id*."""
        stmt = select(Node).filter_by(project_id=project_id)
        return list(session.scalars(stmt))
