"""Tests for the DatabaseManager."""

import tempfile
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from semantic_graph.storage.database import DatabaseManager
from semantic_graph.storage.models import (
    Edge,
    Node,
    ProcessingJob,
    Project,
)


@pytest.fixture
def data_dir():
    """Temporary directory for database files."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def db_manager(data_dir):
    """A DatabaseManager pointed at a temp directory."""
    return DatabaseManager(data_dir=data_dir)


class TestDatabaseManagerInit:
    """Tests for DatabaseManager initialization."""

    def test_creates_data_directory_if_missing(self, data_dir: Path) -> None:
        """The data directory is created if it doesn't exist."""
        subdir = data_dir / "nested" / "path"
        _ = DatabaseManager(data_dir=subdir)
        assert subdir.exists()
        assert subdir.is_dir()

    def test_creates_projects_db_on_init(self, db_manager: DatabaseManager) -> None:
        """projects.db is created and populated with tables on init."""
        projects_db = db_manager.data_dir / "projects.db"
        assert projects_db.exists()

    def test_projects_db_has_project_table(self, db_manager: DatabaseManager) -> None:
        """The projects table exists in projects.db after init."""
        with db_manager.projects_session() as session:
            result = session.execute(
                text(
                    "SELECT name FROM sqlite_master"
                    " WHERE type='table' AND name='projects'"
                )
            )
            assert result.scalar() == "projects"

    def test_projects_db_has_processing_jobs_table(
        self, db_manager: DatabaseManager
    ) -> None:
        """The processing_jobs table exists in projects.db after init."""
        with db_manager.projects_session() as session:
            result = session.execute(
                text(
                    "SELECT name FROM sqlite_master"
                    " WHERE type='table' AND name='processing_jobs'"
                )
            )
            assert result.scalar() == "processing_jobs"

    def test_get_project_db_path(self, db_manager: DatabaseManager) -> None:
        """Returns the correct path for a project's graph.db."""
        project_id = uuid.uuid4()
        path = db_manager.get_project_db_path(project_id)
        expected = db_manager.data_dir / "projects" / str(project_id) / "graph.db"
        assert path == expected


class TestPerProjectDatabase:
    """Tests for per-project graph.db management."""

    def test_creates_project_db_on_demand(self, db_manager: DatabaseManager) -> None:
        """A per-project graph.db is created when first requested."""
        project_id = uuid.uuid4()
        _ = db_manager.get_project_engine(project_id)
        db_path = db_manager.get_project_db_path(project_id)
        assert db_path.exists()

    def test_project_db_has_node_table(self, db_manager: DatabaseManager) -> None:
        """The nodes table exists in a per-project graph.db."""
        project_id = uuid.uuid4()
        _ = db_manager.get_project_engine(project_id)
        with db_manager.project_session(project_id) as session:
            result = session.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='nodes'"
                )
            )
            assert result.scalar() == "nodes"

    def test_project_db_has_edge_table(self, db_manager: DatabaseManager) -> None:
        """The edges table exists in a per-project graph.db."""
        project_id = uuid.uuid4()
        db_manager.get_project_engine(project_id)
        with db_manager.project_session(project_id) as session:
            result = session.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='edges'"
                )
            )
            assert result.scalar() == "edges"

    def test_project_db_has_file_manifest_table(
        self, db_manager: DatabaseManager
    ) -> None:
        """The file_manifest table exists in a per-project graph.db."""
        project_id = uuid.uuid4()
        db_manager.get_project_engine(project_id)
        with db_manager.project_session(project_id) as session:
            result = session.execute(
                text(
                    "SELECT name FROM sqlite_master"
                    " WHERE type='table' AND name='file_manifest'"
                )
            )
            assert result.scalar() == "file_manifest"

    def test_multiple_project_dbs_independent(
        self, db_manager: DatabaseManager
    ) -> None:
        """Each project gets its own independent graph.db."""
        pid_a = uuid.uuid4()
        pid_b = uuid.uuid4()

        db_manager.get_project_engine(pid_a)
        db_manager.get_project_engine(pid_b)

        path_a = db_manager.get_project_db_path(pid_a)
        path_b = db_manager.get_project_db_path(pid_b)

        assert path_a != path_b
        assert path_a.exists()
        assert path_b.exists()


class TestCRUDOperations:
    """Integration-style tests for actual CRUD across both databases."""

    def test_create_and_retrieve_project(self, db_manager: DatabaseManager) -> None:
        """A Project can be created in projects.db and retrieved."""
        pid = uuid.uuid4()
        with db_manager.projects_session() as session:
            project = Project(
                id=pid,
                name="crud-test",
                root_path="/data/crud",
            )
            session.add(project)
            session.commit()

        with db_manager.projects_session() as session:
            retrieved = session.get(Project, pid)
            assert retrieved is not None
            assert retrieved.name == "crud-test"

    def test_create_node_in_project_db(self, db_manager: DatabaseManager) -> None:
        """A Node can be created in a per-project graph.db."""
        project_id = uuid.uuid4()
        node_id = uuid.uuid4()

        db_manager.get_project_engine(project_id)
        with db_manager.project_session(project_id) as session:
            node = Node(
                id=node_id,
                project_id=project_id,
                name="test-node",
                type="function",
                abstraction_level="fine",
                source_file="lib.py",
            )
            session.add(node)
            session.commit()

        with db_manager.project_session(project_id) as session:
            retrieved = session.get(Node, node_id)
            assert retrieved is not None
            assert retrieved.name == "test-node"

    def test_create_job_in_projects_db(self, db_manager: DatabaseManager) -> None:
        """A ProcessingJob can be created in projects.db."""
        project_id = uuid.uuid4()
        job_id = uuid.uuid4()

        # Create the referenced project first
        with db_manager.projects_session() as session:
            project = Project(id=project_id, name="job-test", root_path="/tmp/jt")
            session.add(project)
            session.commit()

        with db_manager.projects_session() as session:
            job = ProcessingJob(
                id=job_id,
                project_id=project_id,
                type="full",
                status="pending",
            )
            session.add(job)
            session.commit()

        with db_manager.projects_session() as session:
            retrieved = session.get(ProcessingJob, job_id)
            assert retrieved is not None
            assert retrieved.project_id == project_id

    def test_orphan_processing_job_rejected(self, db_manager: DatabaseManager) -> None:
        """ProcessingJob referencing nonexistent project raises IntegrityError."""
        import uuid as _uuid

        fake_project_id = _uuid.uuid4()

        with pytest.raises(IntegrityError, match="FOREIGN KEY"):
            with db_manager.projects_session() as session:
                job = ProcessingJob(
                    id=_uuid.uuid4(),
                    project_id=fake_project_id,  # no such project
                    type="full",
                    status="pending",
                )
                session.add(job)
                # Commit inside the managed session will fail on FK

    def test_orphan_edge_rejected(self, db_manager: DatabaseManager) -> None:
        """Edge referencing nonexistent node raises IntegrityError."""
        import uuid as _uuid

        project_id = _uuid.uuid4()

        # Create the project first
        with db_manager.projects_session() as session:
            project = Project(id=project_id, name="fk-edge-test", root_path="/fk")
            session.add(project)
            session.commit()

        db_manager.get_project_engine(project_id)
        with pytest.raises(IntegrityError, match="FOREIGN KEY"):
            with db_manager.project_session(project_id) as session:
                edge = Edge(
                    id=_uuid.uuid4(),
                    project_id=project_id,
                    source_node_id=_uuid.uuid4(),  # no such node
                    target_node_id=_uuid.uuid4(),  # no such node
                    relationship_type="calls",
                )
                session.add(edge)
                # Commit inside the managed session will fail on FK


class TestSessionErrorHandling:
    """Tests for transactional rollback on errors."""

    def test_projects_session_rolls_back_on_error(
        self, db_manager: DatabaseManager
    ) -> None:
        """An unhandled exception inside projects_session rolls back."""
        pid = uuid.uuid4()
        try:
            with db_manager.projects_session() as session:
                p = Project(id=pid, name="rollback-test", root_path="/rt")
                session.add(p)
                raise RuntimeError("forced error")
        except RuntimeError:
            pass

        # The project must NOT have been persisted.
        with db_manager.projects_session() as session:
            assert session.get(Project, pid) is None

    def test_project_session_rolls_back_on_error(
        self, db_manager: DatabaseManager
    ) -> None:
        """An unhandled exception inside project_session rolls back."""
        project_id = uuid.uuid4()
        node_id = uuid.uuid4()
        db_manager.get_project_engine(project_id)
        try:
            with db_manager.project_session(project_id) as session:
                n = Node(
                    id=node_id,
                    project_id=project_id,
                    name="rb-node",
                    type="function",
                    abstraction_level="fine",
                )
                session.add(n)
                raise RuntimeError("forced error")
        except RuntimeError:
            pass

        with db_manager.project_session(project_id) as session:
            assert session.get(Node, node_id) is None


class TestDispose:
    """Tests for resource cleanup."""

    def test_dispose_closes_all_engines(self, db_manager: DatabaseManager) -> None:
        """Dispose closes the projects engine and all project engines."""
        pid = uuid.uuid4()
        db_manager.get_project_engine(pid)
        # Should not raise
        db_manager.dispose()
