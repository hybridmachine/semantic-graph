"""Tests for repository/DAL classes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from semantic_graph.storage.models import (
    GraphBase,
    Project,
    ProjectsBase,
)


def _enable_fk(dbapi_connection, _connection_record):
    """Enable SQLite foreign-key enforcement on every connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
def session():
    """In-memory SQLite session with all tables pre-created.

    Registers a per-engine connect listener for FK enforcement so tests
    in this module are self-contained and not order-dependent.
    """
    engine = create_engine("sqlite:///:memory:", echo=False)
    event.listen(engine, "connect", _enable_fk)
    ProjectsBase.metadata.create_all(engine)
    GraphBase.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as s:
        yield s


# ---------------------------------------------------------------------------
# BaseRepository tests
# ---------------------------------------------------------------------------


class TestBaseRepository:
    """Tests for the generic BaseRepository CRUD operations."""

    def test_create_entity(self, session: Session) -> None:
        from semantic_graph.storage.repositories.base import BaseRepository

        repo = BaseRepository(Project)
        project = repo.create(
            session,
            id=uuid.uuid4(),
            name="repo-test",
            root_path="/data/repo",
        )
        session.flush()

        assert project.id is not None
        assert project.name == "repo-test"

    def test_get_by_id_found(self, session: Session) -> None:
        from semantic_graph.storage.repositories.base import BaseRepository

        repo = BaseRepository(Project)
        pid = uuid.uuid4()
        repo.create(session, id=pid, name="find-me", root_path="/tmp/find")
        session.flush()

        found = repo.get_by_id(session, pid)
        assert found is not None
        assert found.name == "find-me"

    def test_get_by_id_not_found(self, session: Session) -> None:
        from semantic_graph.storage.repositories.base import BaseRepository

        repo = BaseRepository(Project)
        result = repo.get_by_id(session, uuid.uuid4())
        assert result is None

    def test_update_entity(self, session: Session) -> None:
        from semantic_graph.storage.repositories.base import BaseRepository

        repo = BaseRepository(Project)
        project = repo.create(
            session,
            id=uuid.uuid4(),
            name="before-update",
            root_path="/old",
        )
        session.flush()

        project.name = "after-update"
        updated = repo.update(session, project)
        session.flush()

        assert updated.name == "after-update"

        # Verify persistence
        found = repo.get_by_id(session, project.id)
        assert found is not None
        assert found.name == "after-update"

    def test_delete_entity(self, session: Session) -> None:
        from semantic_graph.storage.repositories.base import BaseRepository

        repo = BaseRepository(Project)
        project = repo.create(
            session,
            id=uuid.uuid4(),
            name="delete-me",
            root_path="/tmp/del",
        )
        session.flush()

        repo.delete(session, project)
        session.flush()

        assert repo.get_by_id(session, project.id) is None

    def test_list_all(self, session: Session) -> None:
        from semantic_graph.storage.repositories.base import BaseRepository

        repo = BaseRepository(Project)
        repo.create(session, id=uuid.uuid4(), name="a", root_path="/a")
        repo.create(session, id=uuid.uuid4(), name="b", root_path="/b")
        session.flush()

        all_projects = repo.list_all(session)
        assert len(all_projects) == 2
        names = {p.name for p in all_projects}
        assert names == {"a", "b"}

    def test_list_all_with_limit_and_offset(self, session: Session) -> None:
        from semantic_graph.storage.repositories.base import BaseRepository

        repo = BaseRepository(Project)
        for i in range(5):
            repo.create(session, id=uuid.uuid4(), name=f"p{i}", root_path=f"/p{i}")
        session.flush()

        page = repo.list_all(session, limit=2, offset=1)
        assert len(page) == 2


# ---------------------------------------------------------------------------
# ProjectRepository tests
# ---------------------------------------------------------------------------


class TestProjectRepository:
    """Tests for Project-specific repository methods."""

    def test_get_by_name_found(self, session: Session) -> None:
        from semantic_graph.storage.repositories.project import ProjectRepository

        repo = ProjectRepository()
        pid = uuid.uuid4()
        repo.create(session, id=pid, name="unique-project", root_path="/u")
        session.flush()

        found = repo.get_by_name(session, "unique-project")
        assert found is not None
        assert found.id == pid

    def test_get_by_name_not_found(self, session: Session) -> None:
        from semantic_graph.storage.repositories.project import ProjectRepository

        repo = ProjectRepository()
        result = repo.get_by_name(session, "nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# NodeRepository tests
# ---------------------------------------------------------------------------


class TestNodeRepository:
    """Tests for Node-specific repository methods."""

    def test_list_by_project(self, session: Session) -> None:
        from semantic_graph.storage.repositories.node import NodeRepository

        pid_a = uuid.uuid4()
        pid_b = uuid.uuid4()

        repo = NodeRepository()
        repo.create(
            session,
            id=uuid.uuid4(),
            project_id=pid_a,
            name="node-a1",
            type="function",
            abstraction_level="fine",
            source_file="a.py",
        )
        repo.create(
            session,
            id=uuid.uuid4(),
            project_id=pid_a,
            name="node-a2",
            type="class",
            abstraction_level="mid",
            source_file="a.py",
        )
        repo.create(
            session,
            id=uuid.uuid4(),
            project_id=pid_b,
            name="node-b1",
            type="concept",
            abstraction_level="high",
            source_file="b.md",
        )
        session.flush()

        a_nodes = repo.list_by_project(session, pid_a)
        b_nodes = repo.list_by_project(session, pid_b)

        assert len(a_nodes) == 2
        assert len(b_nodes) == 1
        assert all(n.project_id == pid_a for n in a_nodes)


# ---------------------------------------------------------------------------
# EdgeRepository tests
# ---------------------------------------------------------------------------


class TestEdgeRepository:
    """Tests for Edge-specific repository methods."""

    @staticmethod
    def _create_node(
        session: Session, project_id: uuid.UUID, name: str
    ):
        """Helper to create a node for FK references."""
        from semantic_graph.storage.models import Node

        node = Node(
            id=uuid.uuid4(),
            project_id=project_id,
            name=name,
            type="function",
            abstraction_level="fine",
        )
        session.add(node)
        session.flush()
        return node

    def test_list_by_project(self, session: Session) -> None:
        from semantic_graph.storage.repositories.edge import EdgeRepository

        pid_a = uuid.uuid4()
        pid_b = uuid.uuid4()
        src = self._create_node(session, pid_a, "src")
        tgt = self._create_node(session, pid_a, "tgt")

        repo = EdgeRepository()
        repo.create(
            session,
            id=uuid.uuid4(),
            project_id=pid_a,
            source_node_id=src.id,
            target_node_id=tgt.id,
            relationship_type="calls",
        )
        repo.create(
            session,
            id=uuid.uuid4(),
            project_id=pid_a,
            source_node_id=tgt.id,
            target_node_id=src.id,
            relationship_type="imports",
        )
        repo.create(
            session,
            id=uuid.uuid4(),
            project_id=pid_b,
            source_node_id=src.id,
            target_node_id=tgt.id,
            relationship_type="references",
        )
        session.flush()

        a_edges = repo.list_by_project(session, pid_a)
        b_edges = repo.list_by_project(session, pid_b)

        assert len(a_edges) == 2
        assert len(b_edges) == 1

    def test_list_by_source_node(self, session: Session) -> None:
        from semantic_graph.storage.repositories.edge import EdgeRepository

        pid = uuid.uuid4()
        src_a = self._create_node(session, pid, "src-a")
        src_b = self._create_node(session, pid, "src-b")
        tgt = self._create_node(session, pid, "tgt")

        repo = EdgeRepository()
        repo.create(
            session,
            id=uuid.uuid4(),
            project_id=pid,
            source_node_id=src_a.id,
            target_node_id=tgt.id,
            relationship_type="calls",
        )
        repo.create(
            session,
            id=uuid.uuid4(),
            project_id=pid,
            source_node_id=src_a.id,
            target_node_id=tgt.id,
            relationship_type="imports",
        )
        repo.create(
            session,
            id=uuid.uuid4(),
            project_id=pid,
            source_node_id=src_b.id,
            target_node_id=tgt.id,
            relationship_type="references",
        )
        session.flush()

        from_a = repo.list_by_source_node(session, src_a.id)
        from_b = repo.list_by_source_node(session, src_b.id)

        assert len(from_a) == 2
        assert len(from_b) == 1

    def test_list_by_target_node(self, session: Session) -> None:
        from semantic_graph.storage.repositories.edge import EdgeRepository

        pid = uuid.uuid4()
        src = self._create_node(session, pid, "src")
        tgt_a = self._create_node(session, pid, "tgt-a")
        tgt_b = self._create_node(session, pid, "tgt-b")

        repo = EdgeRepository()
        repo.create(
            session,
            id=uuid.uuid4(),
            project_id=pid,
            source_node_id=src.id,
            target_node_id=tgt_a.id,
            relationship_type="calls",
        )
        repo.create(
            session,
            id=uuid.uuid4(),
            project_id=pid,
            source_node_id=src.id,
            target_node_id=tgt_b.id,
            relationship_type="imports",
        )
        session.flush()

        to_a = repo.list_by_target_node(session, tgt_a.id)
        to_b = repo.list_by_target_node(session, tgt_b.id)

        assert len(to_a) == 1
        assert len(to_b) == 1


# ---------------------------------------------------------------------------
# ProcessingJobRepository tests
# ---------------------------------------------------------------------------


class TestProcessingJobRepository:
    """Tests for ProcessingJob-specific repository methods."""

    def test_list_by_project(self, session: Session) -> None:
        from semantic_graph.storage.repositories.processing_job import (
            ProcessingJobRepository,
        )

        pid_a = uuid.uuid4()
        pid_b = uuid.uuid4()

        # Need projects for FK constraints
        session.add(Project(id=pid_a, name="pa", root_path="/pa"))
        session.add(Project(id=pid_b, name="pb", root_path="/pb"))
        session.flush()

        repo = ProcessingJobRepository()
        repo.create(
            session,
            id=uuid.uuid4(),
            project_id=pid_a,
            type="full",
            status="completed",
        )
        repo.create(
            session,
            id=uuid.uuid4(),
            project_id=pid_a,
            type="incremental",
            status="running",
        )
        repo.create(
            session,
            id=uuid.uuid4(),
            project_id=pid_b,
            type="full",
            status="pending",
        )
        session.flush()

        a_jobs = repo.list_by_project(session, pid_a)
        b_jobs = repo.list_by_project(session, pid_b)

        assert len(a_jobs) == 2
        assert len(b_jobs) == 1


# ---------------------------------------------------------------------------
# FileManifestEntryRepository tests
# ---------------------------------------------------------------------------


class TestFileManifestEntryRepository:
    """Tests for FileManifestEntry-specific repository methods."""

    def test_list_by_project(self, session: Session) -> None:
        from semantic_graph.storage.repositories.file_manifest import (
            FileManifestEntryRepository,
        )

        pid_a = uuid.uuid4()
        pid_b = uuid.uuid4()

        repo = FileManifestEntryRepository()
        now = datetime.now(UTC)
        repo.create(
            session,
            id=uuid.uuid4(),
            project_id=pid_a,
            relative_path="src/main.py",
            content_hash="abc",
            size_bytes=100,
            modified_at=now,
            extractor_id="python",
            extractor_version="1.0",
            status="processed",
        )
        repo.create(
            session,
            id=uuid.uuid4(),
            project_id=pid_a,
            relative_path="src/utils.py",
            content_hash="def",
            size_bytes=200,
            modified_at=now,
            extractor_id="python",
            extractor_version="1.0",
            status="processed",
        )
        repo.create(
            session,
            id=uuid.uuid4(),
            project_id=pid_b,
            relative_path="README.md",
            content_hash="ghi",
            size_bytes=50,
            modified_at=now,
            extractor_id="markdown",
            extractor_version="1.0",
            status="pending",
        )
        session.flush()

        a_entries = repo.list_by_project(session, pid_a)
        b_entries = repo.list_by_project(session, pid_b)

        assert len(a_entries) == 2
        assert len(b_entries) == 1

    def test_get_by_path_found(self, session: Session) -> None:
        from semantic_graph.storage.repositories.file_manifest import (
            FileManifestEntryRepository,
        )

        pid = uuid.uuid4()
        repo = FileManifestEntryRepository()
        now = datetime.now(UTC)
        repo.create(
            session,
            id=uuid.uuid4(),
            project_id=pid,
            relative_path="docs/api.md",
            content_hash="xyz",
            size_bytes=300,
            modified_at=now,
            extractor_id="markdown",
            extractor_version="1.0",
            status="processed",
        )
        session.flush()

        found = repo.get_by_path(session, pid, "docs/api.md")
        assert found is not None
        assert found.content_hash == "xyz"

    def test_get_by_path_not_found(self, session: Session) -> None:
        from semantic_graph.storage.repositories.file_manifest import (
            FileManifestEntryRepository,
        )

        repo = FileManifestEntryRepository()
        result = repo.get_by_path(session, uuid.uuid4(), "nonexistent.md")
        assert result is None
