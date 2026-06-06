"""initial schema

Revision ID: 5ba2446fa7ea
Revises:
Create Date: 2026-06-05 19:25:10.658006

This revision is target-aware: it inspects the ``-x db=`` Alembic
argument and applies the appropriate schema for the target database.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision: str = "5ba2446fa7ea"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _target_db() -> str:
    """Return the target database from the ``-x db=`` argument."""
    x_args = context.get_x_argument(as_dictionary=True)
    return x_args.get("db", "projects")


def upgrade() -> None:
    """Upgrade schema for the targeted database."""
    db = _target_db()

    if db == "projects":
        _upgrade_projects()
    elif db == "graph":
        _upgrade_graph()


def downgrade() -> None:
    """Downgrade schema for the targeted database."""
    db = _target_db()

    if db == "projects":
        _downgrade_projects()
    elif db == "graph":
        _downgrade_graph()


# ---------------------------------------------------------------------------
# Projects schema (projects.db)
# ---------------------------------------------------------------------------


def _upgrade_projects() -> None:
    op.create_table(
        "projects",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("root_path", sa.String(length=1024), nullable=False),
        sa.Column("include_patterns", sqlite.JSON(), nullable=False),
        sa.Column("exclude_patterns", sqlite.JSON(), nullable=False),
        sa.Column("respect_gitignore", sa.Boolean(), nullable=False),
        sa.Column("max_file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("follow_symlinks", sa.Boolean(), nullable=False),
        sa.Column("llm_provider", sa.String(length=100), nullable=True),
        sa.Column("llm_model", sa.String(length=255), nullable=True),
        sa.Column("llm_parameters", sqlite.JSON(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "processing_jobs",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("files_processed", sa.Integer(), nullable=False),
        sa.Column("files_total", sa.Integer(), nullable=False),
        sa.Column("errors", sqlite.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("cancel_requested_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def _downgrade_projects() -> None:
    op.drop_table("processing_jobs")
    op.drop_table("projects")


# ---------------------------------------------------------------------------
# Graph schema (per-project graph.db)
# ---------------------------------------------------------------------------


def _upgrade_graph() -> None:
    op.create_table(
        "nodes",
        sa.Column("project_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("abstraction_level", sa.String(length=20), nullable=False),
        sa.Column("source_file", sa.String(length=1024), nullable=True),
        sa.Column("content_snippet", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            sqlite.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_nodes_project_id", "nodes", ["project_id"])
    op.create_table(
        "edges",
        sa.Column("project_id", sa.Uuid(), nullable=False, index=True),
        sa.Column(
            "source_node_id",
            sa.Uuid(),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "target_node_id",
            sa.Uuid(),
            nullable=False,
            index=True,
        ),
        sa.Column("relationship_type", sa.String(length=100), nullable=False),
        sa.Column(
            "confidence_score",
            sa.Float(),
            nullable=False,
            server_default=sa.text("1.0"),
        ),
        sa.Column(
            "metadata",
            sqlite.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_node_id"],
            ["nodes.id"],
        ),
        sa.ForeignKeyConstraint(
            ["target_node_id"],
            ["nodes.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_edges_project_id", "edges", ["project_id"])
    op.create_index("ix_edges_source_node_id", "edges", ["source_node_id"])
    op.create_index("ix_edges_target_node_id", "edges", ["target_node_id"])
    op.create_table(
        "file_manifest",
        sa.Column("project_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("relative_path", sa.String(length=2048), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("modified_at", sa.DateTime(), nullable=False),
        sa.Column("extractor_id", sa.String(length=100), nullable=False),
        sa.Column("extractor_version", sa.String(length=50), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("skip_reason", sa.String(length=1024), nullable=True),
        sa.Column("last_processed_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "relative_path",
            name="uq_file_manifest_path",
        ),
    )


def _downgrade_graph() -> None:
    op.drop_table("file_manifest")
    op.drop_table("edges")
    op.drop_table("nodes")
