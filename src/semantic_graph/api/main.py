"""FastAPI application entry point."""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from semantic_graph.api.middleware import (
    RequestLoggingMiddleware,
    semantic_graph_exception_handler,
)
from semantic_graph.api.routes import graph, health, llm, projects
from semantic_graph.core.config import settings
from semantic_graph.utils.errors import SemanticGraphError

app = FastAPI(
    title="Semantic Graph Manager",
    version="0.1.0",
    # Return HTTP 422 with Pydantic validation detail on invalid input.
)

# ---------------------------------------------------------------------------
# CORS middleware — origins from config, defaults to localhost only (NFR-24)
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------
app.add_middleware(RequestLoggingMiddleware)

# ---------------------------------------------------------------------------
# Global exception handler → structured JSON
# ---------------------------------------------------------------------------
app.add_exception_handler(SemanticGraphError, semantic_graph_exception_handler)
app.add_exception_handler(Exception, semantic_graph_exception_handler)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(health.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(graph.router, prefix="/api/v1/graph", tags=["graph"])
app.include_router(llm.router, prefix="/api/v1/llm", tags=["llm"])


def start() -> None:
    """Launch the API server (entry point: ``semantic-graph-server``)."""
    uvicorn.run(
        "semantic_graph.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    start()
