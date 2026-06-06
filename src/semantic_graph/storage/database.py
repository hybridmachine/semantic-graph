"""Database session management for the two-database architecture.

``projects.db`` (shared metadata) and per-project ``graph.db`` files.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from semantic_graph.storage.models import GraphBase, ProjectsBase


def _stamp_if_configured(engine: Engine, db: str) -> None:
    """Stamp *engine*'s database with the current Alembic head revision.

    This prevents future ``alembic upgrade head`` runs from attempting
    to create tables that already exist.  A missing or misconfigured
    Alembic installation is silently ignored — stamping is a best-effort
    convenience for development setups.
    """
    try:
        from alembic import command
        from alembic.config import Config
    except ImportError:
        return

    # Locate the project root by walking up from this file.
    candidate = Path(__file__).resolve().parent
    for _ in range(6):
        if (candidate / "alembic.ini").exists():
            break
        candidate = candidate.parent

    alembic_ini = candidate / "alembic.ini"
    if not alembic_ini.exists():
        return

    try:
        cfg = Config(str(alembic_ini))
        # Point Alembic at the engine's actual database URL.
        cfg.set_main_option("sqlalchemy.url", str(engine.url))
        # Select the correct target database branch.
        cfg.cmd_opts = type("_CmdOptions", (), {"x": [f"db={db}"]})()
        command.stamp(cfg, "head")
    except Exception:
        # Best-effort — failures here should not prevent startup.
        pass


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
    """Enable foreign-key enforcement for SQLite connections.

    SQLite does not enforce foreign-key constraints by default;
    this pragma must be enabled on every new connection.

    The listener is registered globally, so it fires for *all* engines
    in the process.  It only acts on SQLite connections; non-SQLite
    backends are left untouched.
    """
    # Only SQLite connections need this pragma.
    driver = getattr(dbapi_connection, "__class__", None)
    if driver is None or "sqlite" not in driver.__module__:
        return

    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


class DatabaseManager:
    """Manages connections to ``projects.db`` and per-project ``graph.db`` files.

    On initialisation, creates the shared ``projects.db`` (if missing) and
    installs its tables.  Per-project databases are created lazily on first
    access.
    """

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # ------------------------------------------------------------------
        # Shared projects database
        # ------------------------------------------------------------------
        projects_db_path = self.data_dir / "projects.db"
        self._projects_engine: Engine = create_engine(
            f"sqlite:///{projects_db_path}", echo=False
        )
        self._projects_session_factory = sessionmaker(bind=self._projects_engine)

        # Install tables on first creation, then stamp the database so
        # future Alembic migrations don't try to recreate existing tables.
        ProjectsBase.metadata.create_all(self._projects_engine)
        _stamp_if_configured(self._projects_engine, "projects")

        # ------------------------------------------------------------------
        # Per-project engine / session cache
        # ------------------------------------------------------------------
        self._project_engines: dict[uuid.UUID, Engine] = {}
        self._project_session_factories: dict[uuid.UUID, sessionmaker[Session]] = {}

    # ------------------------------------------------------------------
    # Shared projects.db helpers
    # ------------------------------------------------------------------

    @contextmanager
    def projects_session(self) -> Generator[Session, None, None]:
        """Yield a transactional session for ``projects.db``."""
        session: Session = self._projects_session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Per-project graph.db helpers
    # ------------------------------------------------------------------

    def get_project_db_path(self, project_id: uuid.UUID) -> Path:
        """Return the filesystem path for a project's ``graph.db``."""
        return self.data_dir / "projects" / str(project_id) / "graph.db"

    def get_project_engine(self, project_id: uuid.UUID) -> Engine:
        """Return (possibly creating) the engine for a project's ``graph.db``.

        On first access the database directory and file are created and the
        schema tables are installed.
        """
        if project_id not in self._project_engines:
            db_path = self.get_project_db_path(project_id)
            db_path.parent.mkdir(parents=True, exist_ok=True)

            engine = create_engine(f"sqlite:///{db_path}", echo=False)
            GraphBase.metadata.create_all(engine)
            _stamp_if_configured(engine, "graph")

            self._project_engines[project_id] = engine
            self._project_session_factories[project_id] = sessionmaker(bind=engine)
        return self._project_engines[project_id]

    @contextmanager
    def project_session(self, project_id: uuid.UUID) -> Generator[Session, None, None]:
        """Yield a transactional session for a project's ``graph.db``."""
        # Ensure the engine (and therefore the DB) exists before handing
        # out a session.
        self.get_project_engine(project_id)
        session: Session = self._project_session_factories[project_id]()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def dispose(self) -> None:
        """Dispose of all engine connection pools."""
        self._projects_engine.dispose()
        for engine in self._project_engines.values():
            engine.dispose()
