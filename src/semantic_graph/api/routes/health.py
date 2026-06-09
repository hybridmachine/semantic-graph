"""Health check and version routes."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from fastapi import APIRouter

from semantic_graph.api.schemas.common import StatusResponse

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Return service health status."""
    return {"status": "ok"}


@router.get("/version", response_model=StatusResponse)
async def api_version() -> StatusResponse:
    """Return API version information.

    Falls back to ``"dev"`` when running from a source checkout
    without an installed distribution (e.g. ``uvicorn`` without
    ``pip install -e .``).
    """
    try:
        pkg_version = version("semantic-graph")
    except PackageNotFoundError:
        pkg_version = "dev"
    return StatusResponse(
        status="ok",
        message=f"semantic-graph v{pkg_version}",
    )
