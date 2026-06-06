"""Tests for SQLAlchemy ORM models."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture
def engine():
    """Create an in-memory SQLite engine for testing."""
    return create_engine("sqlite:///:memory:", echo=False)


@pytest.fixture
def session(engine):
    """Create tables and return a session.

    Creates all tables from both declarative bases in a single in-memory
    database — convenient for unit testing.
    """
    from semantic_graph.storage.models import GraphBase, ProjectsBase

    ProjectsBase.metadata.create_all(engine)
    GraphBase.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as s:
        yield s


class TestProjectModel:
    """Tests for the Project ORM model."""

    def test_create_project_with_required_fields(self, session: Session) -> None:
        """A Project can be created with only the required fields."""
        from semantic_graph.storage.models import Project

        project = Project(
            id=uuid.uuid4(),
            name="test-project",
            root_path="/Users/test/project",
        )
        session.add(project)
        session.commit()
        session.refresh(project)

        assert project.id is not None
        assert project.name == "test-project"
        assert project.root_path == "/Users/test/project"

    def test_create_project_with_all_fields(self, session: Session) -> None:
        """A Project can be created with all optional fields populated."""
        from semantic_graph.storage.models import Project

        project = Project(
            id=uuid.uuid4(),
            name="full-project",
            root_path="/data/project",
            include_patterns=["*.py", "*.md"],
            exclude_patterns=["*.pyc", "__pycache__"],
            respect_gitignore=True,
            max_file_size_bytes=1048576,
            follow_symlinks=False,
            llm_provider="openai",
            llm_model="gpt-4",
            llm_parameters={"temperature": 0.3, "max_tokens": 4096},
            status="idle",
        )
        session.add(project)
        session.commit()
        session.refresh(project)

        assert project.name == "full-project"
        assert project.include_patterns == ["*.py", "*.md"]
        assert project.exclude_patterns == ["*.pyc", "__pycache__"]
        assert project.respect_gitignore is True
        assert project.max_file_size_bytes == 1048576
        assert project.follow_symlinks is False
        assert project.llm_provider == "openai"
        assert project.llm_model == "gpt-4"
        assert project.llm_parameters == {"temperature": 0.3, "max_tokens": 4096}
        assert project.status == "idle"

    def test_project_timestamps_are_set(self, session: Session) -> None:
        """Created and updated timestamps are auto-populated."""
        from semantic_graph.storage.models import Project

        project = Project(
            id=uuid.uuid4(),
            name="ts-project",
            root_path="/tmp/ts",
        )
        session.add(project)
        session.commit()
        session.refresh(project)

        assert isinstance(project.created_at, datetime)
        assert isinstance(project.updated_at, datetime)
        # Both should be very close to now
        now = datetime.now(UTC)
        delta = now - project.created_at.replace(tzinfo=UTC)
        assert delta.total_seconds() < 5

    def test_project_name_is_unique(self, session: Session) -> None:
        """Project names must be unique."""
        from sqlalchemy.exc import IntegrityError

        from semantic_graph.storage.models import Project

        p1 = Project(id=uuid.uuid4(), name="unique-name", root_path="/a")
        p2 = Project(id=uuid.uuid4(), name="unique-name", root_path="/b")
        session.add(p1)
        session.commit()
        session.add(p2)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_project_default_values(self, session: Session) -> None:
        """Project model has sensible defaults for optional fields."""
        from semantic_graph.storage.models import Project

        project = Project(
            id=uuid.uuid4(),
            name="defaults-project",
            root_path="/tmp/defaults",
        )
        session.add(project)
        session.commit()
        session.refresh(project)

        assert project.respect_gitignore is True
        assert project.max_file_size_bytes == 10485760  # 10 MB default
        assert project.follow_symlinks is False
        assert project.status == "idle"
        assert project.include_patterns == []
        assert project.exclude_patterns == []

    def test_include_patterns_in_place_mutation(self, session: Session) -> None:
        """In-place list mutation to include_patterns is persisted."""
        from semantic_graph.storage.models import Project

        project = Project(
            id=uuid.uuid4(),
            name="mutable-list-test",
            root_path="/tmp/mut",
            include_patterns=["*.py"],
        )
        session.add(project)
        session.commit()

        # Mutate in-place
        project.include_patterns.append("*.md")
        session.commit()

        session.refresh(project)
        assert project.include_patterns == ["*.py", "*.md"]

    def test_llm_parameters_in_place_mutation(self, session: Session) -> None:
        """In-place dict mutation to llm_parameters is persisted."""
        from semantic_graph.storage.models import Project

        project = Project(
            id=uuid.uuid4(),
            name="mutable-dict-test",
            root_path="/tmp/mut",
            llm_parameters={"temperature": 0.3},
        )
        session.add(project)
        session.commit()

        # Mutate in-place
        project.llm_parameters["max_tokens"] = 4096  # type: ignore[index]
        session.commit()

        session.refresh(project)
        assert project.llm_parameters == {"temperature": 0.3, "max_tokens": 4096}


class TestNodeModel:
    """Tests for the Node ORM model."""

    def test_create_node(self, session: Session) -> None:
        """A Node can be created with required fields."""
        from semantic_graph.storage.models import Node

        project_id = uuid.uuid4()
        node = Node(
            id=uuid.uuid4(),
            project_id=project_id,
            name="get_user_function",
            type="function",
            abstraction_level="fine",
            source_file="src/auth.py",
            content_snippet="def get_user(id: int) -> User: ...",
        )
        session.add(node)
        session.commit()
        session.refresh(node)

        assert node.id is not None
        assert node.project_id == project_id
        assert node.name == "get_user_function"
        assert node.type == "function"
        assert node.abstraction_level == "fine"
        assert node.source_file == "src/auth.py"

    def test_node_metadata_json(self, session: Session) -> None:
        """Node extra_metadata is stored as JSON."""
        from semantic_graph.storage.models import Node

        node = Node(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            name="test-node",
            type="concept",
            abstraction_level="high",
            source_file="README.md",
            metadata_={"tags": ["auth", "security"], "priority": 1},
        )
        session.add(node)
        session.commit()
        session.refresh(node)

        assert node.metadata_ == {"tags": ["auth", "security"], "priority": 1}

    def test_node_timestamps(self, session: Session) -> None:
        """Node has auto-populated created_at and updated_at."""
        from semantic_graph.storage.models import Node

        node = Node(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            name="ts-node",
            type="class",
            abstraction_level="mid",
            source_file="models.py",
        )
        session.add(node)
        session.commit()
        session.refresh(node)

        assert isinstance(node.created_at, datetime)
        assert isinstance(node.updated_at, datetime)

    def test_node_metadata_in_place_mutation(self, session: Session) -> None:
        """In-place dict mutation to Node.metadata_ is persisted."""
        from semantic_graph.storage.models import Node

        node = Node(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            name="mutable-node",
            type="concept",
            abstraction_level="high",
            source_file="README.md",
            metadata_={"tags": ["auth"]},
        )
        session.add(node)
        session.commit()

        node.metadata_["tags"].append("security")  # type: ignore[index]
        node.metadata_["priority"] = 5  # type: ignore[index]
        session.commit()

        session.refresh(node)
        assert node.metadata_ == {"tags": ["auth", "security"], "priority": 5}


class TestEdgeModel:
    """Tests for the Edge ORM model."""

    def test_create_edge(self, session: Session) -> None:
        """An Edge can be created linking two nodes."""
        from semantic_graph.storage.models import Edge, Node

        project_id = uuid.uuid4()
        source = Node(
            id=uuid.uuid4(),
            project_id=project_id,
            name="source-fn",
            type="function",
            abstraction_level="fine",
        )
        target = Node(
            id=uuid.uuid4(),
            project_id=project_id,
            name="target-fn",
            type="function",
            abstraction_level="fine",
        )
        session.add_all([source, target])
        session.flush()

        edge = Edge(
            id=uuid.uuid4(),
            project_id=project_id,
            source_node_id=source.id,
            target_node_id=target.id,
            relationship_type="calls",
            confidence_score=0.95,
        )
        session.add(edge)
        session.commit()
        session.refresh(edge)

        assert edge.id is not None
        assert edge.project_id == project_id
        assert edge.source_node_id == source.id
        assert edge.target_node_id == target.id
        assert edge.relationship_type == "calls"
        assert edge.confidence_score == 0.95

    def test_edge_metadata_json(self, session: Session) -> None:
        """Edge extra_metadata is stored as JSON."""
        from semantic_graph.storage.models import Edge, Node

        project_id = uuid.uuid4()
        source = Node(
            id=uuid.uuid4(),
            project_id=project_id,
            name="meta-src",
            type="class",
            abstraction_level="mid",
        )
        target = Node(
            id=uuid.uuid4(),
            project_id=project_id,
            name="meta-tgt",
            type="class",
            abstraction_level="mid",
        )
        session.add_all([source, target])
        session.flush()

        edge = Edge(
            id=uuid.uuid4(),
            project_id=project_id,
            source_node_id=source.id,
            target_node_id=target.id,
            relationship_type="imports",
            confidence_score=0.8,
            metadata_={"module": "os", "line": 5},
        )
        session.add(edge)
        session.commit()
        session.refresh(edge)

        assert edge.metadata_ == {"module": "os", "line": 5}

    def test_edge_metadata_in_place_mutation(self, session: Session) -> None:
        """In-place dict mutation to Edge.metadata_ is persisted."""
        from semantic_graph.storage.models import Edge, Node

        project_id = uuid.uuid4()
        source = Node(
            id=uuid.uuid4(),
            project_id=project_id,
            name="mut-src",
            type="function",
            abstraction_level="fine",
        )
        target = Node(
            id=uuid.uuid4(),
            project_id=project_id,
            name="mut-tgt",
            type="function",
            abstraction_level="fine",
        )
        session.add_all([source, target])
        session.flush()

        edge = Edge(
            id=uuid.uuid4(),
            project_id=project_id,
            source_node_id=source.id,
            target_node_id=target.id,
            relationship_type="imports",
            confidence_score=0.8,
            metadata_={"module": "os"},
        )
        session.add(edge)
        session.commit()

        edge.metadata_["line"] = 5  # type: ignore[index]
        session.commit()

        session.refresh(edge)
        assert edge.metadata_ == {"module": "os", "line": 5}

    def test_edge_confidence_score_range(self, session: Session) -> None:
        """Confidence score accepts values between 0 and 1."""
        from semantic_graph.storage.models import Edge, Node

        project_id = uuid.uuid4()
        source = Node(
            id=uuid.uuid4(),
            project_id=project_id,
            name="score-src",
            type="concept",
            abstraction_level="high",
        )
        target = Node(
            id=uuid.uuid4(),
            project_id=project_id,
            name="score-tgt",
            type="concept",
            abstraction_level="high",
        )
        session.add_all([source, target])
        session.flush()

        edge_low = Edge(
            id=uuid.uuid4(),
            project_id=project_id,
            source_node_id=source.id,
            target_node_id=target.id,
            relationship_type="references",
            confidence_score=0.0,
        )
        edge_high = Edge(
            id=uuid.uuid4(),
            project_id=project_id,
            source_node_id=source.id,
            target_node_id=target.id,
            relationship_type="references",
            confidence_score=1.0,
        )
        session.add_all([edge_low, edge_high])
        session.commit()

        assert edge_low.confidence_score == 0.0
        assert edge_high.confidence_score == 1.0

    def test_edge_rejects_invalid_source_node_fk(
        self, session: Session
    ) -> None:
        """Edge with nonexistent source_node_id raises IntegrityError."""
        from sqlalchemy.exc import IntegrityError

        from semantic_graph.storage.models import Edge, Node

        project_id = uuid.uuid4()
        target = Node(
            id=uuid.uuid4(),
            project_id=project_id,
            name="valid-tgt",
            type="function",
            abstraction_level="fine",
        )
        session.add(target)
        session.flush()

        edge = Edge(
            id=uuid.uuid4(),
            project_id=project_id,
            source_node_id=uuid.uuid4(),  # no such node
            target_node_id=target.id,
            relationship_type="calls",
        )
        session.add(edge)
        with pytest.raises(IntegrityError):
            session.commit()


class TestProcessingJobModel:
    """Tests for the ProcessingJob ORM model."""

    @staticmethod
    def _create_project(session: Session, name: str, root_path: str):
        """Helper to create a project for FK references."""
        from semantic_graph.storage.models import Project

        project = Project(id=uuid.uuid4(), name=name, root_path=root_path)
        session.add(project)
        session.flush()
        return project

    def test_create_processing_job(self, session: Session) -> None:
        """A ProcessingJob can be created with required fields."""
        from semantic_graph.storage.models import ProcessingJob

        project = self._create_project(session, "job-test", "/tmp/jt")
        job = ProcessingJob(
            id=uuid.uuid4(),
            project_id=project.id,
            type="full",
            status="pending",
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        assert job.id is not None
        assert job.project_id == project.id
        assert job.type == "full"
        assert job.status == "pending"

    def test_processing_job_defaults(self, session: Session) -> None:
        """ProcessingJob has sensible defaults for counters."""
        from semantic_graph.storage.models import ProcessingJob

        project = self._create_project(session, "defaults-proj", "/tmp/dp")
        job = ProcessingJob(
            id=uuid.uuid4(),
            project_id=project.id,
            type="incremental",
            status="running",
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        assert job.progress == 0
        assert job.files_processed == 0
        assert job.files_total == 0
        assert job.errors == []
        assert job.started_at is not None

    def test_processing_job_errors_json(self, session: Session) -> None:
        """ProcessingJob errors are stored as JSON."""
        from semantic_graph.storage.models import ProcessingJob

        project = self._create_project(session, "errors-proj", "/tmp/ep")
        job = ProcessingJob(
            id=uuid.uuid4(),
            project_id=project.id,
            type="full",
            status="failed",
            errors=[
                {"file": "bad.py", "error": "Encoding error"},
                {"file": "corrupt.md", "error": "Parse failure"},
            ],
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        assert len(job.errors) == 2
        assert job.errors[0]["file"] == "bad.py"

    def test_processing_job_cancel_fields(self, session: Session) -> None:
        """ProcessingJob cancel fields start as None."""
        from semantic_graph.storage.models import ProcessingJob

        project = self._create_project(session, "cancel-proj", "/tmp/cp")
        job = ProcessingJob(
            id=uuid.uuid4(),
            project_id=project.id,
            type="full",
            status="running",
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        assert job.cancel_requested_at is None
        assert job.completed_at is None

    def test_errors_in_place_mutation(self, session: Session) -> None:
        """In-place list mutation to ProcessingJob.errors is persisted."""
        from semantic_graph.storage.models import ProcessingJob

        project = self._create_project(session, "mut-proj", "/tmp/mp")
        job = ProcessingJob(
            id=uuid.uuid4(),
            project_id=project.id,
            type="full",
            status="running",
            errors=[{"file": "a.py", "error": "syntax"}],
        )
        session.add(job)
        session.commit()

        job.errors.append({"file": "b.py", "error": "timeout"})
        session.commit()

        session.refresh(job)
        assert len(job.errors) == 2
        assert job.errors[1]["file"] == "b.py"

    def test_processing_job_rejects_invalid_project_fk(
        self, session: Session
    ) -> None:
        """ProcessingJob with nonexistent project_id raises IntegrityError."""
        from sqlalchemy.exc import IntegrityError

        from semantic_graph.storage.models import ProcessingJob

        job = ProcessingJob(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),  # no such project
            type="full",
            status="pending",
        )
        session.add(job)
        with pytest.raises(IntegrityError):
            session.commit()


class TestFileManifestEntryModel:
    """Tests for the FileManifestEntry ORM model."""

    def test_create_file_manifest_entry(self, session: Session) -> None:
        """A FileManifestEntry can be created with required fields."""
        from semantic_graph.storage.models import FileManifestEntry

        project_id = uuid.uuid4()
        entry = FileManifestEntry(
            id=uuid.uuid4(),
            project_id=project_id,
            relative_path="src/main.py",
            content_hash="abc123def456",
            size_bytes=2048,
            modified_at=datetime.now(UTC),
            extractor_id="python-code",
            extractor_version="1.0.0",
            status="processed",
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)

        assert entry.id is not None
        assert entry.project_id == project_id
        assert entry.relative_path == "src/main.py"
        assert entry.content_hash == "abc123def456"
        assert entry.size_bytes == 2048
        assert entry.extractor_id == "python-code"
        assert entry.extractor_version == "1.0.0"
        assert entry.status == "processed"

    def test_file_manifest_entry_defaults(self, session: Session) -> None:
        """FileManifestEntry has sensible defaults for optional fields."""
        from semantic_graph.storage.models import FileManifestEntry

        entry = FileManifestEntry(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            relative_path="docs/readme.md",
            content_hash="def789",
            size_bytes=512,
            modified_at=datetime.now(UTC),
            extractor_id="markdown",
            extractor_version="1.0.0",
            status="pending",
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)

        assert entry.skip_reason is None
        assert entry.last_processed_at is None

    def test_file_manifest_entry_skip_reason(self, session: Session) -> None:
        """FileManifestEntry can record why a file was skipped."""
        from semantic_graph.storage.models import FileManifestEntry

        entry = FileManifestEntry(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            relative_path="data/large.bin",
            content_hash="",
            size_bytes=500_000_000,
            modified_at=datetime.now(UTC),
            extractor_id="",
            extractor_version="",
            status="skipped",
            skip_reason="File exceeds maximum size",
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)

        assert entry.status == "skipped"
        assert entry.skip_reason == "File exceeds maximum size"

    def test_unique_project_path_constraint(self, session: Session) -> None:
        """Duplicate (project_id, relative_path) raises IntegrityError."""
        from sqlalchemy.exc import IntegrityError

        from semantic_graph.storage.models import FileManifestEntry

        project_id = uuid.uuid4()
        now = datetime.now(UTC)

        entry1 = FileManifestEntry(
            id=uuid.uuid4(),
            project_id=project_id,
            relative_path="src/main.py",
            content_hash="aaa",
            size_bytes=100,
            modified_at=now,
            extractor_id="python",
            extractor_version="1.0",
            status="processed",
        )
        session.add(entry1)
        session.commit()

        entry2 = FileManifestEntry(
            id=uuid.uuid4(),
            project_id=project_id,
            relative_path="src/main.py",
            content_hash="bbb",
            size_bytes=200,
            modified_at=now,
            extractor_id="python",
            extractor_version="1.0",
            status="pending",
        )
        session.add(entry2)
        with pytest.raises(IntegrityError):
            session.commit()


class TestModelRepr:
    """Tests for model __repr__ methods."""

    def test_project_repr(self) -> None:
        from semantic_graph.storage.models import Project

        p = Project(id=uuid.uuid4(), name="test", root_path="/tmp")
        r = repr(p)
        assert "Project" in r
        assert "test" in r

    def test_processing_job_repr(self) -> None:
        from semantic_graph.storage.models import ProcessingJob

        j = ProcessingJob(id=uuid.uuid4(), project_id=uuid.uuid4(), type="full")
        r = repr(j)
        assert "ProcessingJob" in r
        assert "full" in r

    def test_node_repr(self) -> None:
        from semantic_graph.storage.models import Node

        n = Node(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            name="my-node",
            type="concept",
            abstraction_level="high",
        )
        r = repr(n)
        assert "Node" in r
        assert "my-node" in r

    def test_edge_repr(self) -> None:
        from semantic_graph.storage.models import Edge

        sid, tid = uuid.uuid4(), uuid.uuid4()
        e = Edge(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            source_node_id=sid,
            target_node_id=tid,
            relationship_type="calls",
        )
        r = repr(e)
        assert "Edge" in r
        assert "calls" in r

    def test_file_manifest_entry_repr(self) -> None:
        from semantic_graph.storage.models import FileManifestEntry

        f = FileManifestEntry(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            relative_path="foo.py",
            content_hash="abc",
            size_bytes=10,
            modified_at=datetime.now(UTC),
            extractor_id="ext",
            extractor_version="1",
            status="pending",
        )
        r = repr(f)
        assert "FileManifestEntry" in r
        assert "foo.py" in r
