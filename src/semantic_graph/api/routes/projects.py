"""Project management REST API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from semantic_graph.api.schemas.common import StatusResponse
from semantic_graph.api.schemas.projects import (
    FileManifestEntrySummary,
    FileManifestListResponse,
    ProjectCreate,
    ProjectDetail,
    ProjectListResponse,
    ProjectUpdate,
    ScanTrigger,
)
from semantic_graph.core.config import settings
from semantic_graph.core.project_manager import ProjectManager
from semantic_graph.storage.database import DatabaseManager
from semantic_graph.storage.repositories.file_manifest import (
    FileManifestEntryRepository,
)
from semantic_graph.utils.errors import (
    PathSecurityError,
    ProjectNotFoundError,
    ValidationError,
)

router = APIRouter()

# ---------------------------------------------------------------------------
# Application-level singletons (initialised once at module load)
# ---------------------------------------------------------------------------
_db = DatabaseManager(settings.data_dir)
_project_manager = ProjectManager(_db)
_file_manifest_repo = FileManifestEntryRepository()


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=ProjectDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(payload: ProjectCreate) -> ProjectDetail:
    """Register a new project with the given folder path and configuration."""
    try:
        return _project_manager.create_project(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except PathSecurityError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    offset: int = Query(default=0, ge=0, description="Records to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max records"),
) -> ProjectListResponse:
    """List all registered projects with pagination."""
    items, total = _project_manager.list_projects(offset=offset, limit=limit)
    return ProjectListResponse(
        items=items,
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{project_id}", response_model=ProjectDetail)
async def get_project(project_id: uuid.UUID) -> ProjectDetail:
    """Get full details for a project."""
    try:
        return _project_manager.get_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


@router.put("/{project_id}", response_model=ProjectDetail)
async def update_project(
    project_id: uuid.UUID, payload: ProjectUpdate
) -> ProjectDetail:
    """Update project configuration."""
    try:
        return _project_manager.update_project(project_id, payload)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except PathSecurityError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@router.delete("/{project_id}", response_model=StatusResponse)
async def delete_project(project_id: uuid.UUID) -> StatusResponse:
    """Delete a project and its associated graph data."""
    try:
        _project_manager.delete_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return StatusResponse(
        status="ok",
        message=f"Project {project_id} deleted",
    )


# ---------------------------------------------------------------------------
# Scan trigger
# ---------------------------------------------------------------------------


@router.post("/{project_id}/scan", response_model=StatusResponse)
async def trigger_scan(project_id: uuid.UUID, payload: ScanTrigger) -> StatusResponse:
    """Trigger a scan job for the project.

    This endpoint schedules a scan; actual processing is asynchronous.
    """
    try:
        _project_manager.get_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    # TODO: Enqueue an async scan job in a future iteration.
    return StatusResponse(
        status="ok",
        message=f"Scan ({payload.mode}) scheduled for project {project_id}",
    )


# ---------------------------------------------------------------------------
# File manifest
# ---------------------------------------------------------------------------


@router.get("/{project_id}/files", response_model=FileManifestListResponse)
async def list_project_files(
    project_id: uuid.UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> FileManifestListResponse:
    """List file manifest entries for a project."""
    try:
        _project_manager.get_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    with _db.project_session(project_id) as session:
        all_entries = _file_manifest_repo.list_by_project(session, project_id)
        total = len(all_entries)
        page = all_entries[offset : offset + limit]

    items = [FileManifestEntrySummary.model_validate(e) for e in page]
    return FileManifestListResponse(
        items=items,
        total=total,
        offset=offset,
        limit=limit,
    )
