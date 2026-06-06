"""Repository for the Edge model."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from semantic_graph.storage.models import Edge
from semantic_graph.storage.repositories.base import BaseRepository


class EdgeRepository(BaseRepository[Edge]):
    """CRUD operations for :class:`Edge`."""

    def __init__(self) -> None:
        super().__init__(Edge)

    def list_by_project(self, session: Session, project_id: uuid.UUID) -> list[Edge]:
        """Return all edges belonging to *project_id*."""
        return list(session.query(Edge).filter(Edge.project_id == project_id).all())

    def list_by_source_node(self, session: Session, node_id: uuid.UUID) -> list[Edge]:
        """Return all edges where *node_id* is the source."""
        return list(session.query(Edge).filter(Edge.source_node_id == node_id).all())

    def list_by_target_node(self, session: Session, node_id: uuid.UUID) -> list[Edge]:
        """Return all edges where *node_id* is the target."""
        return list(session.query(Edge).filter(Edge.target_node_id == node_id).all())
