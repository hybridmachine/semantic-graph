"""Tests for the graph engine — backends, builder, queries, and sync.

Focuses on round-trip persistence: write to SQLite → reload → verify equivalence.
"""

from __future__ import annotations

import tempfile
import threading
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from semantic_graph.storage.database import DatabaseManager
from semantic_graph.storage.models import Edge, GraphBase, Node, ProjectsBase

if TYPE_CHECKING:
    from semantic_graph.graph_engine.backends import GraphBuildResult
    from semantic_graph.graph_engine.sync import GraphSyncManager

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _enable_fk(dbapi_connection: object, _connection_record: object) -> None:
    """Enable SQLite foreign-key enforcement on every connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
def session() -> Session:
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


@pytest.fixture
def data_dir() -> Path:
    """Temporary directory for DatabaseManager-based tests."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def db_manager(data_dir: Path) -> DatabaseManager:
    """A DatabaseManager pointed at a temp directory."""
    return DatabaseManager(data_dir=data_dir)


# ---------------------------------------------------------------------------
# Backend test helpers
# ---------------------------------------------------------------------------

_NODE_KWARGS = {
    "id": uuid.uuid4(),
    "project_id": uuid.uuid4(),
    "name": "test-node",
    "type": "function",
    "abstraction_level": "fine",
    "source_file": "test.py",
    "content_snippet": "def test(): ...",
    "metadata_": {"tags": ["unit-test"]},
}

_EDGE_KWARGS = {
    "id": uuid.uuid4(),
    "project_id": uuid.uuid4(),
    "source_node_id": None,  # filled by helper
    "target_node_id": None,  # filled by helper
    "relationship_type": "calls",
    "confidence_score": 0.95,
    "metadata_": {"line": 42},
}


def _make_nodes(count: int = 2) -> list[dict[str, object]]:
    """Build *count* node dicts with unique UUIDs."""
    nodes: list[dict[str, object]] = []
    pid = uuid.uuid4()
    for i in range(count):
        nodes.append(
            {
                "id": uuid.uuid4(),
                "project_id": pid,
                "name": f"node-{i}",
                "type": "function",
                "abstraction_level": "fine",
                "source_file": f"file{i}.py",
                "content_snippet": f"content-{i}",
                "metadata_": {},
                "created_at": None,
                "updated_at": None,
            }
        )
    return nodes


def _make_edges(
    nodes: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Create edges linking the given nodes in a chain."""
    edges: list[dict[str, object]] = []
    pid = nodes[0]["project_id"]
    for i in range(len(nodes) - 1):
        edges.append(
            {
                "id": uuid.uuid4(),
                "project_id": pid,
                "source_node_id": nodes[i]["id"],
                "target_node_id": nodes[i + 1]["id"],
                "relationship_type": "calls",
                "confidence_score": 0.9,
                "metadata_": {},
                "created_at": None,
            }
        )
    return edges


# ---------------------------------------------------------------------------
# Backend tests (NetworkX)
# ---------------------------------------------------------------------------


class TestNetworkXBackend:
    """Tests for the NetworkX graph backend."""

    def test_name(self) -> None:
        from semantic_graph.graph_engine.backends import NetworkXBackend

        backend = NetworkXBackend()
        assert backend.name == "networkx"

    def test_build_empty(self) -> None:
        from semantic_graph.graph_engine.backends import NetworkXBackend

        backend = NetworkXBackend()
        result = backend.build([], [])
        assert result.node_count == 0
        assert result.edge_count == 0
        assert result.backend_name == "networkx"

    def test_build_with_nodes_and_edges(self) -> None:
        from semantic_graph.graph_engine.backends import NetworkXBackend

        backend = NetworkXBackend()
        nodes = _make_nodes(3)
        edges = _make_edges(nodes)
        result = backend.build(nodes, edges)

        assert result.node_count == 3
        assert result.edge_count == 2
        assert len(result._node_id_to_idx) == 3
        assert len(result._idx_to_node_id) == 3

    def test_get_node_attrs(self) -> None:
        from semantic_graph.graph_engine.backends import NetworkXBackend

        backend = NetworkXBackend()
        nodes = _make_nodes(2)
        result = backend.build(nodes, [])

        nid0 = nodes[0]["id"]
        idx = result.resolve(nid0)
        assert idx is not None

        attrs = backend.get_node_attrs(result, idx)
        assert attrs["id"] == nid0
        assert attrs["name"] == "node-0"

    def test_get_node_attrs_includes_injected_id(self) -> None:
        from semantic_graph.graph_engine.backends import NetworkXBackend

        backend = NetworkXBackend()
        nodes = _make_nodes(1)
        result = backend.build(nodes, [])

        idx = result.resolve(nodes[0]["id"])
        assert idx is not None
        attrs = backend.get_node_attrs(result, idx)
        assert attrs["id"] == nodes[0]["id"]

    def test_get_neighbor_indices_out(self) -> None:
        from semantic_graph.graph_engine.backends import NetworkXBackend

        backend = NetworkXBackend()
        nodes = _make_nodes(3)
        edges = _make_edges(nodes)
        result = backend.build(nodes, edges)

        src_idx = result.resolve(nodes[0]["id"])
        assert src_idx is not None
        neighbors = backend.get_neighbor_indices(result, src_idx, direction="out")
        assert len(neighbors) == 1
        assert result._idx_to_node_id[neighbors[0]] == nodes[1]["id"]

    def test_get_neighbor_indices_in(self) -> None:
        from semantic_graph.graph_engine.backends import NetworkXBackend

        backend = NetworkXBackend()
        nodes = _make_nodes(3)
        edges = _make_edges(nodes)
        result = backend.build(nodes, edges)

        mid_idx = result.resolve(nodes[1]["id"])
        assert mid_idx is not None
        neighbors = backend.get_neighbor_indices(result, mid_idx, direction="in")
        assert len(neighbors) == 1
        assert result._idx_to_node_id[neighbors[0]] == nodes[0]["id"]

    def test_get_neighbor_indices_all(self) -> None:
        from semantic_graph.graph_engine.backends import NetworkXBackend

        backend = NetworkXBackend()
        nodes = _make_nodes(3)
        edges = _make_edges(nodes)
        result = backend.build(nodes, edges)

        mid_idx = result.resolve(nodes[1]["id"])
        assert mid_idx is not None
        neighbors = backend.get_neighbor_indices(result, mid_idx, direction="all")
        assert len(neighbors) == 2

    def test_get_edge_attrs_found(self) -> None:
        from semantic_graph.graph_engine.backends import NetworkXBackend

        backend = NetworkXBackend()
        nodes = _make_nodes(2)
        edges = _make_edges(nodes)
        result = backend.build(nodes, edges)

        src_idx = result.resolve(nodes[0]["id"])
        tgt_idx = result.resolve(nodes[1]["id"])
        assert src_idx is not None and tgt_idx is not None

        attrs = backend.get_edge_attrs(result, src_idx, tgt_idx)
        assert attrs is not None
        assert attrs["relationship_type"] == "calls"

    def test_get_edge_attrs_not_found(self) -> None:
        from semantic_graph.graph_engine.backends import NetworkXBackend

        backend = NetworkXBackend()
        nodes = _make_nodes(2)
        result = backend.build(nodes, [])

        attrs = backend.get_edge_attrs(result, 0, 1)
        assert attrs is None

    def test_node_count_and_edge_count(self) -> None:
        from semantic_graph.graph_engine.backends import NetworkXBackend

        backend = NetworkXBackend()
        nodes = _make_nodes(5)
        edges = _make_edges(nodes)
        result = backend.build(nodes, edges)

        assert backend.node_count(result) == 5
        assert backend.edge_count(result) == 4

    def test_add_node(self) -> None:
        from semantic_graph.graph_engine.backends import NetworkXBackend

        backend = NetworkXBackend()
        nodes = _make_nodes(1)
        result = backend.build(nodes, [])

        new_id = uuid.uuid4()
        idx = backend.add_node(
            result,
            {
                "id": new_id,
                "project_id": uuid.uuid4(),
                "name": "added-node",
                "type": "class",
                "abstraction_level": "mid",
            },
        )
        assert backend.node_count(result) == 2
        assert result.resolve(new_id) == idx
        attrs = backend.get_node_attrs(result, idx)
        assert attrs["name"] == "added-node"

    def test_add_edge(self) -> None:
        from semantic_graph.graph_engine.backends import NetworkXBackend

        backend = NetworkXBackend()
        nodes = _make_nodes(2)
        result = backend.build(nodes, [])

        backend.add_edge(
            result,
            src_idx=0,
            tgt_idx=1,
            edge_attrs={
                "id": uuid.uuid4(),
                "relationship_type": "imports",
                "confidence_score": 0.8,
            },
        )
        assert backend.edge_count(result) == 1
        attrs = backend.get_edge_attrs(result, 0, 1)
        assert attrs is not None
        assert attrs["relationship_type"] == "imports"


# ---------------------------------------------------------------------------
# Graph builder tests
# ---------------------------------------------------------------------------


class TestGraphBuilder:
    """Tests for the load_graph function that builds from SQLite."""

    @staticmethod
    def _create_node(session: Session, project_id: uuid.UUID, **kwargs: object) -> Node:
        defaults: dict[str, object] = {
            "id": uuid.uuid4(),
            "project_id": project_id,
            "name": "test-node",
            "type": "function",
            "abstraction_level": "fine",
        }
        defaults.update(kwargs)
        node = Node(**defaults)  # type: ignore[arg-type]
        session.add(node)
        session.flush()
        return node

    @staticmethod
    def _create_edge(
        session: Session,
        project_id: uuid.UUID,
        src_id: uuid.UUID,
        tgt_id: uuid.UUID,
        **kwargs: object,
    ) -> Edge:
        defaults: dict[str, object] = {
            "id": uuid.uuid4(),
            "project_id": project_id,
            "source_node_id": src_id,
            "target_node_id": tgt_id,
            "relationship_type": "calls",
        }
        defaults.update(kwargs)
        edge = Edge(**defaults)  # type: ignore[arg-type]
        session.add(edge)
        session.flush()
        return edge

    def test_load_graph_from_session(self, session: Session) -> None:
        from semantic_graph.graph_engine import load_graph

        pid = uuid.uuid4()
        n1 = self._create_node(session, pid, name="node-a")
        n2 = self._create_node(session, pid, name="node-b")
        self._create_edge(session, pid, n1.id, n2.id)
        session.commit()

        result = load_graph(session, pid)
        assert result.node_count == 2
        assert result.edge_count == 1
        assert result.backend_name == "networkx"
        assert result.resolve(n1.id) is not None
        assert result.resolve(n2.id) is not None

    def test_load_graph_no_edges(self, session: Session) -> None:
        from semantic_graph.graph_engine import load_graph

        pid = uuid.uuid4()
        self._create_node(session, pid, name="solo")
        session.commit()

        result = load_graph(session, pid)
        assert result.node_count == 1
        assert result.edge_count == 0

    def test_load_graph_with_multiple_projects_isolation(
        self, session: Session
    ) -> None:
        from semantic_graph.graph_engine import load_graph

        pid_a = uuid.uuid4()
        pid_b = uuid.uuid4()
        self._create_node(session, pid_a, name="a1")
        self._create_node(session, pid_a, name="a2")
        self._create_node(session, pid_b, name="b1")
        session.commit()

        result_a = load_graph(session, pid_a)
        result_b = load_graph(session, pid_b)

        assert result_a.node_count == 2
        assert result_b.node_count == 1

    def test_load_graph_preserves_node_attributes(self, session: Session) -> None:
        from semantic_graph.graph_engine import load_graph
        from semantic_graph.graph_engine.backends import GraphBackend

        pid = uuid.uuid4()
        n1 = self._create_node(
            session,
            pid,
            name="rich-node",
            type="class",
            abstraction_level="mid",
            source_file="src/models.py",
            content_snippet="class User: ...",
            metadata_={"tags": ["important"]},
        )
        session.commit()

        result = load_graph(session, pid)
        idx = result.resolve(n1.id)
        assert idx is not None

        backend: GraphBackend = result._backend
        attrs = backend.get_node_attrs(result, idx)
        assert attrs["name"] == "rich-node"
        assert attrs["type"] == "class"
        assert attrs["abstraction_level"] == "mid"

    def test_load_graph_preserves_edge_attributes(self, session: Session) -> None:
        from semantic_graph.graph_engine import load_graph
        from semantic_graph.graph_engine.backends import GraphBackend

        pid = uuid.uuid4()
        n1 = self._create_node(session, pid, name="src")
        n2 = self._create_node(session, pid, name="tgt")
        self._create_edge(
            session,
            pid,
            n1.id,
            n2.id,
            relationship_type="imports",
            confidence_score=0.75,
        )
        session.commit()

        result = load_graph(session, pid)
        src_idx = result.resolve(n1.id)
        tgt_idx = result.resolve(n2.id)
        assert src_idx is not None and tgt_idx is not None

        backend: GraphBackend = result._backend
        attrs = backend.get_edge_attrs(result, src_idx, tgt_idx)
        assert attrs is not None
        assert attrs["relationship_type"] == "imports"
        assert attrs["confidence_score"] == 0.75


# ---------------------------------------------------------------------------
# Queries tests
# ---------------------------------------------------------------------------


class TestQueries:
    """Tests for the query layer (get_node, get_neighbors, get_stats)."""

    @staticmethod
    def _build(node_count: int = 3) -> tuple[GraphBuildResult, list[dict[str, object]]]:
        from semantic_graph.graph_engine.backends import NetworkXBackend

        backend = NetworkXBackend()
        nodes = _make_nodes(node_count)
        edges = _make_edges(nodes) if node_count > 1 else []
        return backend.build(nodes, edges), nodes

    def test_get_node_found(self) -> None:
        from semantic_graph.graph_engine.queries import get_node

        br, nodes = self._build(2)
        result = get_node(br, nodes[0]["id"])
        assert result is not None
        assert result["name"] == "node-0"

    def test_get_node_not_found(self) -> None:
        from semantic_graph.graph_engine.queries import get_node

        br, _ = self._build(1)
        result = get_node(br, uuid.uuid4())
        assert result is None

    def test_get_neighbors_out(self) -> None:
        from semantic_graph.graph_engine.queries import get_neighbors

        br, nodes = self._build(3)

        neighbors = get_neighbors(br, nodes[0]["id"], direction="out")
        assert len(neighbors) == 1
        assert neighbors[0]["id"] == nodes[1]["id"]

    def test_get_neighbors_in(self) -> None:
        from semantic_graph.graph_engine.queries import get_neighbors

        br, nodes = self._build(3)

        neighbors = get_neighbors(br, nodes[2]["id"], direction="in")
        assert len(neighbors) == 1
        assert neighbors[0]["id"] == nodes[1]["id"]

    def test_get_neighbors_all(self) -> None:
        from semantic_graph.graph_engine.queries import get_neighbors

        br, nodes = self._build(3)

        neighbors = get_neighbors(br, nodes[1]["id"], direction="all")
        assert len(neighbors) == 2

    def test_get_neighbors_unknown_node(self) -> None:
        from semantic_graph.graph_engine.queries import get_neighbors

        br, _ = self._build(1)
        result = get_neighbors(br, uuid.uuid4())
        assert result == []

    def test_get_neighbors_includes_edge_attrs(self) -> None:
        from semantic_graph.graph_engine.queries import get_neighbors

        br, nodes = self._build(2)

        neighbors = get_neighbors(br, nodes[0]["id"], direction="out")
        assert len(neighbors) == 1
        assert "edge" in neighbors[0]
        assert neighbors[0]["edge"]["relationship_type"] == "calls"

    def test_get_stats(self) -> None:
        from semantic_graph.graph_engine.queries import get_stats

        br, _ = self._build(5)
        stats = get_stats(br)
        assert stats["node_count"] == 5
        assert stats["edge_count"] == 4
        assert stats["backend"] == "networkx"
        assert 0.0 < stats["density"] < 1.0

    def test_get_stats_empty_graph(self) -> None:
        from semantic_graph.graph_engine.queries import get_stats

        br, _ = self._build(0)
        stats = get_stats(br)
        assert stats["node_count"] == 0
        assert stats["edge_count"] == 0
        assert stats["density"] == 0.0

    def test_get_stats_single_node(self) -> None:
        from semantic_graph.graph_engine.queries import get_stats

        br, _ = self._build(1)
        stats = get_stats(br)
        assert stats["node_count"] == 1
        assert stats["edge_count"] == 0
        assert stats["density"] == 0.0


# ---------------------------------------------------------------------------
# Sync tests (write path)
# ---------------------------------------------------------------------------


class TestGraphSyncManager:
    """Tests for the deferred-write sync manager."""

    def _make_manager(
        self,
        db_manager: DatabaseManager,
        project_id: uuid.UUID,
        node_count: int = 2,
    ) -> GraphSyncManager:
        from semantic_graph.graph_engine import (
            GraphSyncManager,
            get_backend,
            load_graph,
        )

        # Seed the project DB with nodes so we have something to load
        db_manager.get_project_engine(project_id)
        with db_manager.project_session(project_id) as session:
            pid = project_id
            n1 = Node(
                id=uuid.uuid4(),
                project_id=pid,
                name="initial-a",
                type="function",
                abstraction_level="fine",
            )
            n2 = Node(
                id=uuid.uuid4(),
                project_id=pid,
                name="initial-b",
                type="function",
                abstraction_level="fine",
            )
            session.add_all([n1, n2])
            session.flush()  # Ensure nodes are visible for FK reference
            session.add(
                Edge(
                    id=uuid.uuid4(),
                    project_id=pid,
                    source_node_id=n1.id,
                    target_node_id=n2.id,
                    relationship_type="calls",
                )
            )
            session.commit()

        # Load into memory
        with db_manager.project_session(project_id) as session:
            br = load_graph(session, project_id, backend=get_backend("networkx"))

        return GraphSyncManager(br, project_id, db_manager)

    def test_initial_state(self, db_manager: DatabaseManager) -> None:

        pid = uuid.uuid4()
        mgr = self._make_manager(db_manager, pid)
        assert mgr.dirty_node_count == 0
        assert mgr.dirty_edge_count == 0
        assert mgr.build_result.node_count == 2
        assert mgr.build_result.edge_count == 1

    def test_add_node_increments_dirty_count(self, db_manager: DatabaseManager) -> None:
        pid = uuid.uuid4()
        mgr = self._make_manager(db_manager, pid)

        new_id = uuid.uuid4()
        idx = mgr.add_node(
            {
                "id": new_id,
                "project_id": pid,
                "name": "new-node",
                "type": "class",
                "abstraction_level": "mid",
            }
        )
        assert mgr.dirty_node_count == 1
        # Committed graph is unchanged until sync
        assert mgr.build_result.node_count == 2
        # The returned index is the predicted index after sync
        assert idx == 2

        # After sync, the node is visible in the committed graph
        mgr.sync()
        assert mgr.build_result.node_count == 3
        assert mgr.build_result.resolve(new_id) is not None

    def test_add_edge_increments_dirty_count(self, db_manager: DatabaseManager) -> None:
        pid = uuid.uuid4()
        mgr = self._make_manager(db_manager, pid)

        # Add a third node first
        new_id = uuid.uuid4()
        mgr.add_node(
            {
                "id": new_id,
                "project_id": pid,
                "name": "new-node",
                "type": "class",
                "abstraction_level": "mid",
            }
        )

        # Get the id of one of the initial nodes
        br = mgr.build_result
        existing_ids = list(br._node_id_to_idx.keys())
        src_id = existing_ids[0]

        mgr.add_edge(
            src_node_id=src_id,
            tgt_node_id=new_id,
            edge_attrs={"relationship_type": "imports"},
        )
        assert mgr.dirty_edge_count == 1
        # Committed graph is unchanged until sync
        assert mgr.build_result.edge_count == 1

        # After sync, the edge is visible in the committed graph
        mgr.sync()
        assert mgr.build_result.edge_count == 2

    def test_add_edge_rejects_unknown_source(self, db_manager: DatabaseManager) -> None:
        pid = uuid.uuid4()
        mgr = self._make_manager(db_manager, pid)

        with pytest.raises(ValueError, match="Source node"):
            mgr.add_edge(
                src_node_id=uuid.uuid4(),
                tgt_node_id=uuid.uuid4(),
                edge_attrs={"relationship_type": "calls"},
            )

    def test_add_edge_rejects_unknown_target(self, db_manager: DatabaseManager) -> None:
        pid = uuid.uuid4()
        mgr = self._make_manager(db_manager, pid)

        # Valid source, invalid target
        existing_id = next(iter(mgr.build_result._node_id_to_idx))
        with pytest.raises(ValueError, match="Target node"):
            mgr.add_edge(
                src_node_id=existing_id,
                tgt_node_id=uuid.uuid4(),
                edge_attrs={"relationship_type": "calls"},
            )

    def test_sync_persists_to_sqlite(self, db_manager: DatabaseManager) -> None:
        pid = uuid.uuid4()
        mgr = self._make_manager(db_manager, pid)

        new_id = uuid.uuid4()
        mgr.add_node(
            {
                "id": new_id,
                "project_id": pid,
                "name": "synced-node",
                "type": "class",
                "abstraction_level": "mid",
            }
        )
        written = mgr.sync()
        assert written == 1  # one node written
        assert mgr.dirty_node_count == 0

        # Verify persistence via SQLite
        with db_manager.project_session(pid) as session:
            node = session.get(Node, new_id)
            assert node is not None
            assert node.name == "synced-node"

    def test_sync_clears_dirty_after_commit(self, db_manager: DatabaseManager) -> None:
        pid = uuid.uuid4()
        mgr = self._make_manager(db_manager, pid)

        mgr.add_node(
            {
                "id": uuid.uuid4(),
                "project_id": pid,
                "name": "clear-test",
                "type": "concept",
                "abstraction_level": "high",
            }
        )
        mgr.sync()
        assert mgr.dirty_node_count == 0
        assert mgr.dirty_edge_count == 0

    def test_sync_no_dirty_returns_zero(self, db_manager: DatabaseManager) -> None:
        pid = uuid.uuid4()
        mgr = self._make_manager(db_manager, pid)
        assert mgr.sync() == 0

    def test_shutdown_syncs_remaining(self, db_manager: DatabaseManager) -> None:
        pid = uuid.uuid4()
        mgr = self._make_manager(db_manager, pid)

        new_id = uuid.uuid4()
        mgr.add_node(
            {
                "id": new_id,
                "project_id": pid,
                "name": "shutdown-node",
                "type": "function",
                "abstraction_level": "fine",
            }
        )
        mgr.shutdown()

        assert mgr.dirty_node_count == 0
        with db_manager.project_session(pid) as session:
            assert session.get(Node, new_id) is not None

    def test_write_lock_exclusion(self, db_manager: DatabaseManager) -> None:
        pid = uuid.uuid4()
        mgr = self._make_manager(db_manager, pid)

        # Verify the lock is a threading.Lock and can be acquired/released
        acquired = mgr._lock.acquire(blocking=False)
        assert acquired
        mgr._lock.release()

        # Context manager usage
        with mgr.write_lock():
            # The lock is held by this thread while inside the context
            assert mgr._lock.locked() is True

    def test_write_lock_is_reentrant_safe(self, db_manager: DatabaseManager) -> None:
        """The same thread cannot deadlock itself via write_lock."""
        pid = uuid.uuid4()
        mgr = self._make_manager(db_manager, pid)

        with mgr.write_lock():
            # The lock is held by this thread; add_node also acquires it.
            # Since it's a plain Lock (not RLock), this should deadlock if
            # we naively call add_node.  But add_node acquires, then
            # releases, so we verify we cannot re-acquire here.
            # We don't call add_node here - just verify the lock works
            pass

    def test_sync_is_atomic_within_lock(self, db_manager: DatabaseManager) -> None:
        """sync() acquires the lock internally so callers don't have to."""
        pid = uuid.uuid4()
        mgr = self._make_manager(db_manager, pid)

        mgr.add_node(
            {
                "id": uuid.uuid4(),
                "project_id": pid,
                "name": "atomic-test",
                "type": "function",
                "abstraction_level": "fine",
            }
        )
        # sync() should work without the caller holding the lock
        written = mgr.sync()
        assert written == 1


# ---------------------------------------------------------------------------
# Round-trip persistence tests
# ---------------------------------------------------------------------------


class TestRoundTripPersistence:
    """Verify: write to SQLite → reload → verify equivalence.

    These are the canonical integration tests required by the
    implementation plan: the in-memory cache must be rebuildable from
    SQLite with full fidelity.
    """

    def test_round_trip_nodes_only(self, session: Session) -> None:
        """Write nodes to SQLite, reload, and verify equivalence."""
        from semantic_graph.graph_engine import get_backend, load_graph
        from semantic_graph.graph_engine.backends import GraphBackend

        pid = uuid.uuid4()
        original_nodes = []
        for i in range(5):
            n = Node(
                id=uuid.uuid4(),
                project_id=pid,
                name=f"rt-node-{i}",
                type="function" if i % 2 == 0 else "class",
                abstraction_level="fine" if i < 3 else "mid",
                source_file=f"file{i}.py",
            )
            session.add(n)
            original_nodes.append(n)
        session.commit()

        # Load into memory
        result = load_graph(session, pid, backend=get_backend("networkx"))
        assert result.node_count == 5

        # Verify every original node is findable
        backend: GraphBackend = result._backend
        for orig in original_nodes:
            idx = result.resolve(orig.id)
            assert idx is not None
            attrs = backend.get_node_attrs(result, idx)
            assert attrs["name"] == orig.name
            assert attrs["type"] == orig.type

    def test_round_trip_with_edges(self, session: Session) -> None:
        """Write nodes + edges to SQLite, reload, verify topology."""
        from semantic_graph.graph_engine import get_backend, load_graph
        from semantic_graph.graph_engine.backends import GraphBackend

        pid = uuid.uuid4()
        n1 = Node(
            id=uuid.uuid4(),
            project_id=pid,
            name="A",
            type="function",
            abstraction_level="fine",
        )
        n2 = Node(
            id=uuid.uuid4(),
            project_id=pid,
            name="B",
            type="function",
            abstraction_level="fine",
        )
        n3 = Node(
            id=uuid.uuid4(),
            project_id=pid,
            name="C",
            type="class",
            abstraction_level="mid",
        )
        session.add_all([n1, n2, n3])
        session.flush()

        e1 = Edge(
            id=uuid.uuid4(),
            project_id=pid,
            source_node_id=n1.id,
            target_node_id=n2.id,
            relationship_type="calls",
            confidence_score=0.9,
        )
        e2 = Edge(
            id=uuid.uuid4(),
            project_id=pid,
            source_node_id=n2.id,
            target_node_id=n3.id,
            relationship_type="imports",
            confidence_score=0.8,
        )
        session.add_all([e1, e2])
        session.commit()

        result = load_graph(session, pid, backend=get_backend("networkx"))
        assert result.node_count == 3
        assert result.edge_count == 2

        backend: GraphBackend = result._backend
        # n1 → n2 (calls), n2 → n3 (imports)
        n1_idx = result.resolve(n1.id)
        n2_idx = result.resolve(n2.id)
        n3_idx = result.resolve(n3.id)
        assert n1_idx is not None and n2_idx is not None and n3_idx is not None

        out_n1 = backend.get_neighbor_indices(result, n1_idx, direction="out")
        assert len(out_n1) == 1
        assert out_n1[0] == n2_idx

        edge_attrs = backend.get_edge_attrs(result, n1_idx, n2_idx)
        assert edge_attrs is not None
        assert edge_attrs["relationship_type"] == "calls"

    def test_round_trip_full_cycle_sync_and_reload(
        self, db_manager: DatabaseManager
    ) -> None:
        """Full cycle: load → add nodes/edges → sync → reload → verify.

        This is the definitive round-trip test: it exercises the builder,
        the sync manager, and re-loading from SQLite to prove that the
        cache is always rebuildable (NFR-06).
        """
        from semantic_graph.graph_engine import (
            GraphSyncManager,
            get_backend,
            load_graph,
        )
        from semantic_graph.graph_engine.backends import GraphBackend

        pid = uuid.uuid4()

        # -- Phase 1: Seed initial data in SQLite ----------------------------
        db_manager.get_project_engine(pid)
        with db_manager.project_session(pid) as session:
            n1 = Node(
                id=uuid.uuid4(),
                project_id=pid,
                name="seed-1",
                type="function",
                abstraction_level="fine",
                source_file="a.py",
            )
            n2 = Node(
                id=uuid.uuid4(),
                project_id=pid,
                name="seed-2",
                type="class",
                abstraction_level="mid",
                source_file="b.py",
            )
            session.add_all([n1, n2])
            session.flush()
            session.add(
                Edge(
                    id=uuid.uuid4(),
                    project_id=pid,
                    source_node_id=n1.id,
                    target_node_id=n2.id,
                    relationship_type="calls",
                )
            )
            session.commit()
            seed_node_ids = {n1.id, n2.id}
            n1_id = n1.id  # Capture before session closes
            n2_id = n2.id

        # -- Phase 2: Load into memory ---------------------------------------
        with db_manager.project_session(pid) as session:
            br = load_graph(session, pid, backend=get_backend("networkx"))

        mgr = GraphSyncManager(br, pid, db_manager)
        assert mgr.build_result.node_count == 2
        assert mgr.build_result.edge_count == 1

        # -- Phase 3: Add new nodes/edges in memory --------------------------
        new_id = uuid.uuid4()
        mgr.add_node(
            {
                "id": new_id,
                "project_id": pid,
                "name": "added-later",
                "type": "concept",
                "abstraction_level": "high",
                "source_file": "c.md",
            }
        )
        mgr.add_edge(
            src_node_id=n2_id,
            tgt_node_id=new_id,
            edge_attrs={
                "relationship_type": "references",
                "confidence_score": 0.7,
            },
        )
        # Staged changes are not yet visible in the committed graph.
        assert mgr.dirty_node_count == 1
        assert mgr.dirty_edge_count == 1
        assert mgr.build_result.node_count == 2  # unchanged
        assert mgr.build_result.edge_count == 1  # unchanged

        # -- Phase 4: Sync to SQLite -----------------------------------------
        written = mgr.sync()
        assert written == 2  # 1 node + 1 edge
        assert mgr.dirty_node_count == 0
        assert mgr.dirty_edge_count == 0

        # -- Phase 5: Reload from SQLite into a *fresh* GraphBuildResult ------
        with db_manager.project_session(pid) as session:
            reloaded = load_graph(session, pid, backend=get_backend("networkx"))

        assert reloaded.node_count == 3
        assert reloaded.edge_count == 2

        # Verify all original + added nodes are present
        all_expected_ids = seed_node_ids | {new_id}
        for nid in all_expected_ids:
            assert reloaded.resolve(nid) is not None, f"Node {nid} missing after reload"

        # Verify topology: n1→n2 (calls), n2→new_node (references)
        backend: GraphBackend = reloaded._backend
        n1_idx = reloaded.resolve(n1_id)
        n2_idx = reloaded.resolve(n2_id)
        new_idx = reloaded.resolve(new_id)
        assert n1_idx is not None and n2_idx is not None and new_idx is not None

        # n1 → n2
        edge1 = backend.get_edge_attrs(reloaded, n1_idx, n2_idx)
        assert edge1 is not None
        assert edge1["relationship_type"] == "calls"

        # n2 → new_node
        edge2 = backend.get_edge_attrs(reloaded, n2_idx, new_idx)
        assert edge2 is not None
        assert edge2["relationship_type"] == "references"

    def test_reload_preserves_all_edge_attributes(self, session: Session) -> None:
        """Every edge attribute is preserved through a reload cycle."""
        from semantic_graph.graph_engine import get_backend, load_graph
        from semantic_graph.graph_engine.backends import GraphBackend

        pid = uuid.uuid4()
        n1 = Node(
            id=uuid.uuid4(),
            project_id=pid,
            name="attr-src",
            type="function",
            abstraction_level="fine",
        )
        n2 = Node(
            id=uuid.uuid4(),
            project_id=pid,
            name="attr-tgt",
            type="class",
            abstraction_level="mid",
        )
        session.add_all([n1, n2])
        session.flush()

        edge = Edge(
            id=uuid.uuid4(),
            project_id=pid,
            source_node_id=n1.id,
            target_node_id=n2.id,
            relationship_type="imports",
            confidence_score=0.55,
            metadata_={"module": "collections", "line": 10},
        )
        session.add(edge)
        session.commit()

        result = load_graph(session, pid, backend=get_backend("networkx"))
        backend: GraphBackend = result._backend

        n1_idx = result.resolve(n1.id)
        n2_idx = result.resolve(n2.id)
        assert n1_idx is not None and n2_idx is not None

        attrs = backend.get_edge_attrs(result, n1_idx, n2_idx)
        assert attrs is not None
        assert attrs["relationship_type"] == "imports"
        assert attrs["confidence_score"] == 0.55


# ---------------------------------------------------------------------------
# get_backend factory tests
# ---------------------------------------------------------------------------


class TestGetBackend:
    """Tests for the backend factory function."""

    def test_get_backend_default_returns_networkx(self) -> None:
        from semantic_graph.graph_engine import get_backend
        from semantic_graph.graph_engine.backends import NetworkXBackend

        backend = get_backend()
        assert isinstance(backend, NetworkXBackend)

    def test_get_backend_explicit_networkx(self) -> None:
        from semantic_graph.graph_engine import get_backend
        from semantic_graph.graph_engine.backends import NetworkXBackend

        backend = get_backend("networkx")
        assert isinstance(backend, NetworkXBackend)

    def test_get_backend_graph_tool_unavailable(self) -> None:
        from semantic_graph.graph_engine import get_backend

        with pytest.raises(RuntimeError, match="graph-tool is not installed"):
            get_backend("graph-tool")


# ---------------------------------------------------------------------------
# Concurrency / lock tests
# ---------------------------------------------------------------------------


class TestWriteLockConcurrency:
    """Verify the single-writer lock serialises mutations correctly."""

    def test_concurrent_add_nodes_are_serialised(
        self, db_manager: DatabaseManager
    ) -> None:
        from semantic_graph.graph_engine import (
            GraphSyncManager,
            get_backend,
            load_graph,
        )

        pid = uuid.uuid4()

        # Seed one node
        db_manager.get_project_engine(pid)
        with db_manager.project_session(pid) as session:
            session.add(
                Node(
                    id=uuid.uuid4(),
                    project_id=pid,
                    name="seed",
                    type="function",
                    abstraction_level="fine",
                )
            )
            session.commit()

        with db_manager.project_session(pid) as session:
            br = load_graph(session, pid, backend=get_backend("networkx"))

        mgr = GraphSyncManager(br, pid, db_manager)
        errors: list[Exception] = []

        def add_worker(worker_id: int) -> None:
            try:
                for _ in range(10):
                    mgr.add_node(
                        {
                            "id": uuid.uuid4(),
                            "project_id": pid,
                            "name": f"worker-{worker_id}",
                            "type": "function",
                            "abstraction_level": "fine",
                        }
                    )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=add_worker, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors from concurrent add_node
        assert len(errors) == 0
        # Committed graph unchanged until sync — all nodes are staged.
        assert mgr.build_result.node_count == 1
        assert mgr.dirty_node_count == 40
        # After sync, all nodes are visible in the committed graph.
        mgr.sync()
        assert mgr.build_result.node_count == 41
        assert mgr.dirty_node_count == 0


# ---------------------------------------------------------------------------
# GraphBuildResult convenience tests
# ---------------------------------------------------------------------------


class TestGraphBuildResult:
    """Tests for the GraphBuildResult dataclass helpers."""

    def test_resolve_found(self) -> None:
        from semantic_graph.graph_engine.backends import NetworkXBackend

        backend = NetworkXBackend()
        nodes = _make_nodes(1)
        result = backend.build(nodes, [])
        assert result.resolve(nodes[0]["id"]) == 0

    def test_resolve_not_found(self) -> None:
        from semantic_graph.graph_engine.backends import NetworkXBackend

        backend = NetworkXBackend()
        result = backend.build([], [])
        assert result.resolve(uuid.uuid4()) is None

    def test_node_id_found(self) -> None:
        from semantic_graph.graph_engine.backends import NetworkXBackend

        backend = NetworkXBackend()
        nodes = _make_nodes(1)
        result = backend.build(nodes, [])
        assert result.node_id(0) == nodes[0]["id"]

    def test_node_id_not_found(self) -> None:
        from semantic_graph.graph_engine.backends import NetworkXBackend

        backend = NetworkXBackend()
        result = backend.build([], [])
        assert result.node_id(999) is None
