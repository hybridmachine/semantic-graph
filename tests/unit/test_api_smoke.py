"""Smoke tests for the FastAPI application."""

from fastapi.testclient import TestClient

from semantic_graph.api.main import app


def test_app_imports() -> None:
    assert app is not None


def test_health_route_exists() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
