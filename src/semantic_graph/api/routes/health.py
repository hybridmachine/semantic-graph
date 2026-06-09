"""Health check and version routes."""

from __future__ import annotations

from importlib.metadata import version

from fastapi import APIRouter

from semantic_graph.api.schemas.common import StatusResponse

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Return service health status."""
    return {"status": "ok"}


@router.get("/version", response_model=StatusResponse)
async def api_version() -> StatusResponse:
    """Return API version information."""
    return StatusResponse(
        status="ok",
        message=f"semantic-graph v{version('semantic-graph')}",
    )
