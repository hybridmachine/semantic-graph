"""Smoke tests for the FastAPI application."""

from __future__ import annotations

from fastapi.testclient import TestClient

from semantic_graph.api.main import app


def test_app_imports() -> None:
    """FastAPI app instantiates without error."""
    assert app is not None


def test_health_route_exists() -> None:
    """GET /api/v1/health returns 200 with status ok."""
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version_route() -> None:
    """GET /api/v1/version returns 200 with version info."""
    client = TestClient(app)
    response = client.get("/api/v1/version")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "semantic-graph" in data["message"]


def test_cors_headers_present() -> None:
    """CORS headers are included on preflight and normal responses."""
    client = TestClient(app)
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    # CORS middleware should set allow-origin for allowed origins
    assert "access-control-allow-origin" in response.headers
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_404_returns_json_error() -> None:
    """Unknown routes return structured JSON error (via exception handler)."""
    client = TestClient(app)
    response = client.get("/api/v1/nonexistent")
    assert response.status_code == 404
    # Fallback: 404s from routing are FastAPI-level, our exception
    # handler catches uncaught exceptions.  The 404 is still JSON.
    data = response.json()
    assert "detail" in data
