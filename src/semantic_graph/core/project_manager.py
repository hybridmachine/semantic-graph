"""Project manager — business logic for project lifecycle."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from semantic_graph.api.schemas.projects import (
    ProjectCreate,
    ProjectDetail,
    ProjectSummary,
    ProjectUpdate,
)
from semantic_graph.storage.database import DatabaseManager
from semantic_graph.storage.models import Project
from semantic_graph.storage.repositories.project import ProjectRepository
from semantic_graph.utils.errors import ProjectNotFoundError, ValidationError
from semantic_graph.utils.security import validate_project_root


class ProjectManager:
    """Coordinates project CRUD, validation, and lifecycle operations."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db
        self._project_repo = ProjectRepository()

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_project(self, payload: ProjectCreate) -> ProjectDetail:
        """Register a new project.

        Validates that the root path exists and is a safe directory,
        then persists the project record.
        """
        root_path = validate_project_root(Path(payload.root_path))

        with self._db.projects_session() as session:
            existing = self._project_repo.get_by_name(session, payload.name)
            if existing is not None:
                raise ValidationError(
                    f"A project named '{payload.name}' already exists"
                )

            project = self._project_repo.create(
                session,
                name=payload.name,
                root_path=str(root_path),
                include_patterns=payload.include_patterns,
                exclude_patterns=payload.exclude_patterns,
                respect_gitignore=payload.respect_gitignore,
                max_file_size_bytes=payload.max_file_size_bytes,
                follow_symlinks=payload.follow_symlinks,
                llm_provider=payload.llm_provider,
                llm_model=payload.llm_model,
                llm_parameters=payload.llm_parameters,
            )
            return self._to_detail(project)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_project(self, project_id: uuid.UUID) -> ProjectDetail:
        """Return full details for *project_id*."""
        with self._db.projects_session() as session:
            project = self._get_or_raise(session, project_id)
            return self._to_detail(project)

    def get_project_by_name(self, name: str) -> ProjectDetail | None:
        """Return full details for the project named *name*, or *None*."""
        with self._db.projects_session() as session:
            project = self._project_repo.get_by_name(session, name)
            if project is None:
                return None
            return self._to_detail(project)

    def list_projects(
        self, *, offset: int = 0, limit: int = 20
    ) -> tuple[list[ProjectSummary], int]:
        """Return paginated project summaries and total count."""
        with self._db.projects_session() as session:
            all_projects = self._project_repo.list_all(session)
            total = len(all_projects)
            page = all_projects[offset : offset + limit]
            summaries = [self._to_summary(p) for p in page]
            return summaries, total

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update_project(
        self, project_id: uuid.UUID, payload: ProjectUpdate
    ) -> ProjectDetail:
        """Update project configuration fields."""
        update_data = payload.model_dump(exclude_unset=True)

        # Validate root_path if provided, storing the canonical form.
        if "root_path" in update_data:
            update_data["root_path"] = str(
                validate_project_root(Path(update_data["root_path"]))
            )

        with self._db.projects_session() as session:
            proj = self._get_or_raise(session, project_id)

            # Validate name uniqueness within the same transaction to avoid TOCTOU.
            new_name = update_data.get("name")
            if new_name is not None and new_name != proj.name:
                existing = self._project_repo.get_by_name(session, new_name)
                if existing is not None and existing.id != project_id:
                    raise ValidationError(
                        f"A project named '{new_name}' already exists"
                    )

            for field, value in update_data.items():
                setattr(proj, field, value)
            updated = self._project_repo.update(session, proj)
            return self._to_detail(updated)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_project(self, project_id: uuid.UUID) -> None:
        """Delete a project and its associated graph database."""
        with self._db.projects_session() as session:
            proj = self._get_or_raise(session, project_id)
            self._project_repo.delete(session, proj)

        # Remove the per-project graph database directory.
        graph_db_dir = self._db.get_project_db_path(project_id).parent
        if graph_db_dir.exists():
            shutil.rmtree(graph_db_dir)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_or_raise(
        self, session: object, project_id: uuid.UUID
    ) -> Project:
        """Return the project or raise.  *session* stays open for callers."""
        from sqlalchemy.orm import Session as OrmSession

        assert isinstance(session, OrmSession)
        project = self._project_repo.get_by_id(session, project_id)
        if project is None:
            raise ProjectNotFoundError(f"Project {project_id} not found")
        return project

    @staticmethod
    def _to_summary(project: Project) -> ProjectSummary:
        return ProjectSummary(
            id=project.id,
            name=project.name,
            root_path=project.root_path,
            status=project.status,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    @staticmethod
    def _to_detail(project: Project) -> ProjectDetail:
        return ProjectDetail(
            id=project.id,
            name=project.name,
            root_path=project.root_path,
            status=project.status,
            include_patterns=project.include_patterns,
            exclude_patterns=project.exclude_patterns,
            respect_gitignore=project.respect_gitignore,
            max_file_size_bytes=project.max_file_size_bytes,
            follow_symlinks=project.follow_symlinks,
            llm_provider=project.llm_provider,
            llm_model=project.llm_model,
            llm_parameters=project.llm_parameters,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )
