"""Global exception handler that returns clean JSON error responses."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.status import (
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from semantic_graph.api.schemas.common import ErrorResponse
from semantic_graph.utils.errors import SemanticGraphError
from semantic_graph.utils.logging import get_logger

logger = get_logger("semantic_graph.api")


async def semantic_graph_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Convert unhandled exceptions into structured JSON error responses.

    Known :class:`SemanticGraphError` subclasses are mapped to appropriate
    HTTP status codes.  Everything else is treated as a 500.
    """
    if isinstance(exc, SemanticGraphError):
        status_code = _status_for_error(exc)
        logger.warning(
            "Application error: %s (status=%d)", type(exc).__name__, status_code
        )
    else:
        status_code = HTTP_500_INTERNAL_SERVER_ERROR
        logger.exception("Unhandled exception: %s", exc)

    error = ErrorResponse(
        detail=str(exc),
        error_type=type(exc).__name__,
        status_code=status_code,
    )
    return JSONResponse(
        status_code=status_code,
        content=error.model_dump(),
    )


def _status_for_error(exc: SemanticGraphError) -> int:
    from semantic_graph.utils.errors import (
        PathSecurityError,
        PathTraversalError,
        ProjectNotFoundError,
        ValidationError,
    )

    mapping: dict[type[SemanticGraphError], int] = {
        ProjectNotFoundError: 404,
        PathTraversalError: 403,
        PathSecurityError: 403,
        ValidationError: HTTP_422_UNPROCESSABLE_ENTITY,
    }
    for cls, status in mapping.items():
        if isinstance(exc, cls):
            return status
    return HTTP_500_INTERNAL_SERVER_ERROR
