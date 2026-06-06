"""Generic base repository with CRUD operations."""

from __future__ import annotations

import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy.orm import DeclarativeBase, Session

M = TypeVar("M", bound=DeclarativeBase)


class BaseRepository(Generic[M]):
    """Generic CRUD repository for a SQLAlchemy model.

    Parameters
    ----------
    model_class:
        The SQLAlchemy ORM class this repository manages.
    """

    def __init__(self, model_class: type[M]) -> None:
        self._model_class = model_class

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create(self, session: Session, **kwargs: Any) -> M:
        """Create and persist a new entity.

        Returns the newly created ORM instance (already flushed to the
        session but not yet committed).
        """
        instance = self._model_class(**kwargs)
        session.add(instance)
        session.flush()
        return instance

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_by_id(self, session: Session, entity_id: uuid.UUID) -> M | None:
        """Return the entity with the given primary key, or *None*."""
        return session.get(self._model_class, entity_id)

    def list_all(
        self,
        session: Session,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[M]:
        """Return all entities, optionally paginated."""
        from sqlalchemy import select

        stmt = select(self._model_class).offset(offset).limit(limit)
        return list(session.scalars(stmt))

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, session: Session, instance: M) -> M:
        """Merge changes on *instance* into the session and flush.

        The caller should modify the ORM object attributes directly, then
        call this method to persist the changes.
        """
        merged = session.merge(instance)
        session.flush()
        return merged

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete(self, session: Session, instance: M) -> None:
        """Remove *instance* from the database."""
        session.delete(instance)
        session.flush()
