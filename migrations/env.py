"""Alembic environment configuration.

Two-database architecture
-------------------------
- ``projects.db`` (shared metadata) — managed by Alembic.
- Per-project ``graph.db`` — managed at runtime by
  ``GraphBase.metadata.create_all(engine)`` inside
  :class:`~semantic_graph.storage.database.DatabaseManager`.

By default ``alembic upgrade head`` targets ``projects.db``.  To generate
or run migrations against the graph schema, use::

    alembic -x db=graph revision --autogenerate -m "..."
    alembic -x db=graph upgrade head

The URL is built by expanding ``~`` to the user home directory and
creating any missing parent directories.
"""

from __future__ import annotations

from logging.config import fileConfig
from pathlib import Path
from typing import Literal

from alembic import context
from sqlalchemy import engine_from_config, pool

from semantic_graph.storage.models import GraphBase, ProjectsBase

# Alembic Config object
config = context.config

# Set up Python logging from the ini file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Resolve target database
# ---------------------------------------------------------------------------

TargetDB = Literal["projects", "graph"]


def _get_target_db() -> TargetDB:
    """Determine which database to migrate from the ``-x db=`` flag."""
    x_args = context.get_x_argument(as_dictionary=True)
    db = x_args.get("db", "projects")
    if db not in ("projects", "graph"):
        raise ValueError(
            f"Unknown target database {db!r}; expected 'projects' or 'graph'"
        )
    return db  # type: ignore[return-value]


def _get_database_url(target_db: TargetDB) -> str:
    """Return the full SQLite URL with ``~`` expanded and directories ensured.

    This reads the raw URL from ``alembic.ini``, expands a leading ``~``,
    and creates the parent directory tree so SQLite can create the file.
    """
    raw_url: str | None = config.get_main_option("sqlalchemy.url")
    if not raw_url:
        raise ValueError("sqlalchemy.url is not set in alembic.ini")

    # Replace the sqlite:/// prefix, expand ~, then re-add the prefix.
    prefix = "sqlite:///"
    path_part = raw_url[len(prefix) :]
    expanded = Path(path_part).expanduser()

    if target_db == "graph":
        # Graph databases live at the same root but are per-project; for
        # schema-only operations we point at a representative location.
        # The caller must supply a project_id via -x project_id=<uuid>
        # when targeting a specific project database.
        x_args = context.get_x_argument(as_dictionary=True)
        if "project_id" in x_args:
            expanded = expanded.parent / "projects" / x_args["project_id"] / "graph.db"
        else:
            expanded = expanded.parent / "projects" / "_template" / "graph.db"

    # Ensure the parent directory exists.
    expanded.parent.mkdir(parents=True, exist_ok=True)

    return f"{prefix}{expanded}"


# ---------------------------------------------------------------------------
# Select metadata for the target database
# ---------------------------------------------------------------------------

_target_db: TargetDB = _get_target_db()

if _target_db == "projects":
    target_metadata = ProjectsBase.metadata
else:
    target_metadata = GraphBase.metadata


# ---------------------------------------------------------------------------
# Migration runners
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = _get_database_url(_target_db)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Build a temporary config section with the resolved URL so
    # engine_from_config can connect using the expanded path.
    section = config.get_section(config.config_ini_section, {})
    resolved_url = _get_database_url(_target_db)
    section["sqlalchemy.url"] = resolved_url

    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
