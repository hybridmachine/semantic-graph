"""Tests for project CRUD API endpoints."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from semantic_graph.api.main import app


@pytest.fixture
def client() -> TestClient:
    """Return a TestClient for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def unique_name() -> str:
    """Return a project name unique to this test run."""
    return f"test-{uuid.uuid4().hex[:12]}"


class TestCreateProject:
    def test_create_success(
        self, client: TestClient, tmp_path: Path, unique_name: str
    ) -> None:
        resp = client.post(
            "/api/v1/projects",
            json={"name": unique_name, "root_path": str(tmp_path)},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["name"] == unique_name
        assert data["root_path"] == str(tmp_path)
        assert "id" in data

    def test_create_duplicate_name(
        self, client: TestClient, tmp_path: Path, unique_name: str
    ) -> None:
        client.post(
            "/api/v1/projects",
            json={"name": unique_name, "root_path": str(tmp_path)},
        )
        resp = client.post(
            "/api/v1/projects",
            json={"name": unique_name, "root_path": str(tmp_path)},
        )
        assert resp.status_code == 422

    def test_create_invalid_root(self, client: TestClient, unique_name: str) -> None:
        resp = client.post(
            "/api/v1/projects",
            json={
                "name": unique_name,
                "root_path": "/nonexistent/path/12345",
            },
        )
        assert resp.status_code in (403, 422)

    def test_create_relative_root_rejected(
        self, client: TestClient, unique_name: str
    ) -> None:
        resp = client.post(
            "/api/v1/projects",
            json={"name": unique_name, "root_path": "relative/path"},
        )
        assert resp.status_code == 422

    def test_create_with_all_options(
        self, client: TestClient, tmp_path: Path, unique_name: str
    ) -> None:
        resp = client.post(
            "/api/v1/projects",
            json={
                "name": unique_name,
                "root_path": str(tmp_path),
                "include_patterns": ["*.py"],
                "exclude_patterns": ["test_*.py"],
                "respect_gitignore": False,
                "max_file_size_bytes": 1024,
                "follow_symlinks": True,
                "llm_provider": "openai",
                "llm_model": "gpt-4",
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["include_patterns"] == ["*.py"]
        assert data["exclude_patterns"] == ["test_*.py"]
        assert data["respect_gitignore"] is False
        assert data["max_file_size_bytes"] == 1024
        assert data["follow_symlinks"] is True
        assert data["llm_provider"] == "openai"


class TestListProjects:
    def test_list_returns_array(self, client: TestClient) -> None:
        resp = client.get("/api/v1/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["items"], list)
        assert "total" in data

    def test_pagination_bounds(self, client: TestClient) -> None:
        resp = client.get("/api/v1/projects?offset=0&limit=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 1


class TestGetProject:
    def test_get_existing(
        self, client: TestClient, tmp_path: Path, unique_name: str
    ) -> None:
        create = client.post(
            "/api/v1/projects",
            json={"name": unique_name, "root_path": str(tmp_path)},
        )
        pid = create.json()["id"]
        resp = client.get(f"/api/v1/projects/{pid}")
        assert resp.status_code == 200
        assert resp.json()["name"] == unique_name

    def test_get_nonexistent(self, client: TestClient) -> None:
        fake_id = uuid.uuid4()
        resp = client.get(f"/api/v1/projects/{fake_id}")
        assert resp.status_code == 404


class TestUpdateProject:
    def test_update_name(
        self, client: TestClient, tmp_path: Path, unique_name: str
    ) -> None:
        create = client.post(
            "/api/v1/projects",
            json={"name": unique_name, "root_path": str(tmp_path)},
        )
        pid = create.json()["id"]
        new_name = f"updated-{uuid.uuid4().hex[:8]}"
        resp = client.put(f"/api/v1/projects/{pid}", json={"name": new_name})
        assert resp.status_code == 200
        assert resp.json()["name"] == new_name

    def test_update_nonexistent(self, client: TestClient) -> None:
        resp = client.put(
            f"/api/v1/projects/{uuid.uuid4()}",
            json={"name": "nope"},
        )
        assert resp.status_code == 404


class TestDeleteProject:
    def test_delete_existing(
        self, client: TestClient, tmp_path: Path, unique_name: str
    ) -> None:
        create = client.post(
            "/api/v1/projects",
            json={"name": unique_name, "root_path": str(tmp_path)},
        )
        pid = create.json()["id"]
        resp = client.delete(f"/api/v1/projects/{pid}")
        assert resp.status_code == 200
        # Verify gone.
        get_resp = client.get(f"/api/v1/projects/{pid}")
        assert get_resp.status_code == 404

    def test_delete_nonexistent(self, client: TestClient) -> None:
        resp = client.delete(f"/api/v1/projects/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestTriggerScan:
    def test_trigger_scan(
        self, client: TestClient, tmp_path: Path, unique_name: str
    ) -> None:
        create = client.post(
            "/api/v1/projects",
            json={"name": unique_name, "root_path": str(tmp_path)},
        )
        pid = create.json()["id"]
        resp = client.post(
            f"/api/v1/projects/{pid}/scan",
            json={"mode": "incremental"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_trigger_scan_full_mode(
        self, client: TestClient, tmp_path: Path, unique_name: str
    ) -> None:
        create = client.post(
            "/api/v1/projects",
            json={"name": unique_name, "root_path": str(tmp_path)},
        )
        pid = create.json()["id"]
        resp = client.post(
            f"/api/v1/projects/{pid}/scan",
            json={"mode": "full"},
        )
        assert resp.status_code == 200

    def test_trigger_scan_bad_mode(
        self, client: TestClient, tmp_path: Path, unique_name: str
    ) -> None:
        create = client.post(
            "/api/v1/projects",
            json={"name": unique_name, "root_path": str(tmp_path)},
        )
        pid = create.json()["id"]
        resp = client.post(
            f"/api/v1/projects/{pid}/scan",
            json={"mode": "invalid"},
        )
        assert resp.status_code == 422


class TestListFiles:
    def test_list_files_returns_array(
        self, client: TestClient, tmp_path: Path, unique_name: str
    ) -> None:
        create = client.post(
            "/api/v1/projects",
            json={"name": unique_name, "root_path": str(tmp_path)},
        )
        pid = create.json()["id"]
        resp = client.get(f"/api/v1/projects/{pid}/files")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
