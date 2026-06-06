"""Write path — deferred SQLite persistence with single-writer locking.

SQLite is updated only at defined sync boundaries: job completion, explicit
sync request, or graceful shutdown.  Reads continue against the last-good
committed graph while writes are in-flight (read isolation): mutations are
staged in dirty lists and applied to the in-memory graph only after
successful SQLite persistence.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from semantic_graph.graph_engine.backends import GraphBackend, GraphBuildResult
from semantic_graph.storage.database import DatabaseManager
from semantic_graph.storage.models import Edge, Node


class GraphSyncManager:
    """Manages an in-memory graph and defers SQLite writes to sync boundaries.

    New nodes and edges are staged in dirty lists and are **not** visible
    to read queries until :meth:`sync` commits them to both SQLite and the
    in-memory graph in a single atomic step.  This ensures that failed,
    cancelled, or rolled-back jobs never expose graph state that has not
    reached SQLite.

    A per-project :class:`threading.Lock` ensures that only one writer
    modifies the graph at a time (see §6.2 of REQUIREMENTS.md).
    """

    def __init__(
        self,
        build_result: GraphBuildResult,
        project_id: uuid.UUID,
        db_manager: DatabaseManager,
    ) -> None:
        self._committed = build_result
        self._project_id = project_id
        self._db_manager = db_manager
        self._lock = threading.Lock()

        # Nodes / edges that have been staged but not yet persisted to
        # SQLite or applied to the committed in-memory graph.
        self._dirty_nodes: list[dict[str, Any]] = []
        self._dirty_edges: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def build_result(self) -> GraphBuildResult:
        """The committed in-memory graph (does **not** include staged changes)."""
        return self._committed

    @property
    def dirty_node_count(self) -> int:
        """Number of nodes waiting to be synced to SQLite."""
        return len(self._dirty_nodes)

    @property
    def dirty_edge_count(self) -> int:
        """Number of edges waiting to be synced to SQLite."""
        return len(self._dirty_edges)

    # ------------------------------------------------------------------
    # Write lock
    # ------------------------------------------------------------------

    @contextmanager
    def write_lock(self) -> Generator[None, None, None]:
        """Acquire the single-writer lock for this project.

        Reads may continue against :attr:`build_result` while the lock is
        held — the lock only serialises mutations and sync operations.
        """
        acquired = self._lock.acquire(blocking=True)
        try:
            yield
        finally:
            if acquired:
                self._lock.release()

    # ------------------------------------------------------------------
    # Node existence helpers (check both committed and staged)
    # ------------------------------------------------------------------

    def _node_exists(self, node_id: uuid.UUID) -> bool:
        """Return *True* if *node_id* exists in the committed graph or
        in the staged dirty-nodes list."""
        if self._committed.resolve(node_id) is not None:
            return True
        return any(n.get("id") == node_id for n in self._dirty_nodes)

    # ------------------------------------------------------------------
    # Stage mutations (deferred write — not visible to readers)
    # ------------------------------------------------------------------

    def add_node(self, node_attrs: dict[str, Any]) -> int:
        """Stage a node for the next :meth:`sync`.

        The node is **not** visible to read queries until sync completes.

        Parameters
        ----------
        node_attrs:
            Dictionary of :class:`Node` column values.  Must include
            ``"id"``, ``"project_id"``, ``"name"``, ``"type"``, and
            ``"abstraction_level"``.

        Returns
        -------
        int
            The predicted internal vertex index the node will have after
            sync.  This is based on the current committed node count plus
            the number of already-staged nodes.
        """
        with self._lock:
            predicted_idx = self._committed.node_count + len(self._dirty_nodes)
            self._dirty_nodes.append(dict(node_attrs))
            return predicted_idx

    def add_edge(
        self,
        src_node_id: uuid.UUID,
        tgt_node_id: uuid.UUID,
        edge_attrs: dict[str, Any],
    ) -> None:
        """Stage an edge for the next :meth:`sync`.

        The edge is **not** visible to read queries until sync completes.

        Parameters
        ----------
        src_node_id:
            Domain UUID of the source node (must exist in committed graph
            or in staged nodes).
        tgt_node_id:
            Domain UUID of the target node (must exist in committed graph
            or in staged nodes).
        edge_attrs:
            Dictionary of :class:`Edge` column values.  Must include at
            least ``"relationship_type"``.

        Raises
        ------
        ValueError:
            If either the source or target node is not found in the
            committed graph or staged nodes.
        """
        with self._lock:
            if not self._node_exists(src_node_id):
                raise ValueError(
                    f"Source node {src_node_id} not found in graph or staged nodes"
                )
            if not self._node_exists(tgt_node_id):
                raise ValueError(
                    f"Target node {tgt_node_id} not found in graph or staged nodes"
                )

            # Overwrite FK fields from method parameters and manager state
            # so the edge persisted to SQLite always matches the caller's
            # intent, regardless of what was supplied in edge_attrs.
            full_attrs = dict(edge_attrs)
            full_attrs["source_node_id"] = src_node_id
            full_attrs["target_node_id"] = tgt_node_id
            full_attrs["project_id"] = self._project_id
            if "id" not in full_attrs:
                full_attrs["id"] = uuid.uuid4()

            self._dirty_edges.append(full_attrs)

    # ------------------------------------------------------------------
    # Sync to SQLite
    # ------------------------------------------------------------------

    def sync(self) -> int:
        """Persist all dirty nodes and edges to SQLite and the in-memory graph.

        The operation runs inside the writer lock so that no concurrent
        mutations can interleave with the flush.  Staged changes are
        applied to the committed in-memory graph **only after** SQLite
        persistence succeeds, maintaining read isolation.

        Returns
        -------
        int
            Total number of rows written (nodes + edges).

        Raises
        ------
        Exception:
            On SQLite write failure the transaction is rolled back,
            dirty lists are preserved so the caller may retry, and the
            committed in-memory graph is unchanged.
        """
        with self._lock:
            return self._sync_unlocked()

    def _sync_unlocked(self) -> int:
        """Internal sync — caller must hold ``self._lock``."""
        if not self._dirty_nodes and not self._dirty_edges:
            return 0

        # -- Phase 1: Persist to SQLite ---------------------------------------
        written = self._persist_to_sqlite()

        # -- Phase 2: Apply to committed in-memory graph ----------------------
        # Only reached if SQLite persistence succeeded.
        backend: GraphBackend = self._committed._backend
        staged_node_indices: dict[uuid.UUID, int] = {}

        for node_attrs in self._dirty_nodes:
            idx = backend.add_node(self._committed, node_attrs)
            staged_node_indices[node_attrs["id"]] = idx

        for edge_attrs in self._dirty_edges:
            src_id: uuid.UUID = edge_attrs["source_node_id"]
            tgt_id: uuid.UUID = edge_attrs["target_node_id"]

            resolved_src = self._committed.resolve(src_id)
            src_idx = (
                resolved_src
                if resolved_src is not None
                else staged_node_indices[src_id]
            )
            resolved_tgt = self._committed.resolve(tgt_id)
            tgt_idx = (
                resolved_tgt
                if resolved_tgt is not None
                else staged_node_indices[tgt_id]
            )
            backend.add_edge(self._committed, src_idx, tgt_idx, edge_attrs)

        # -- Phase 3: Clear dirty lists ---------------------------------------
        self._dirty_nodes.clear()
        self._dirty_edges.clear()
        return written

    def _persist_to_sqlite(self) -> int:
        """Write dirty nodes and edges to SQLite.

        Returns the number of rows written.  On failure the database
        transaction is rolled back and the exception propagates.
        """
        written = 0
        with self._db_manager.project_session(self._project_id) as session:
            for node_attrs in self._dirty_nodes:
                node = Node(
                    id=node_attrs.get("id", uuid.uuid4()),
                    project_id=node_attrs.get("project_id", self._project_id),
                    name=node_attrs["name"],
                    type=node_attrs["type"],
                    abstraction_level=node_attrs.get("abstraction_level", "fine"),
                    source_file=node_attrs.get("source_file"),
                    content_snippet=node_attrs.get("content_snippet"),
                    metadata_=node_attrs.get("metadata_", {}),
                )
                session.add(node)
                written += 1

            session.flush()  # Ensure node rows exist before adding edges

            for edge_attrs in self._dirty_edges:
                edge = Edge(
                    id=edge_attrs.get("id", uuid.uuid4()),
                    project_id=edge_attrs.get("project_id", self._project_id),
                    source_node_id=edge_attrs["source_node_id"],
                    target_node_id=edge_attrs["target_node_id"],
                    relationship_type=edge_attrs.get("relationship_type", "references"),
                    confidence_score=edge_attrs.get("confidence_score", 1.0),
                    metadata_=edge_attrs.get("metadata_", {}),
                )
                session.add(edge)
                written += 1

            # session.commit() happens on exit of the context manager

        return written

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        """Graceful shutdown — sync remaining changes to SQLite.

        Call this during application teardown to ensure no in-memory
        changes are lost.
        """
        self.sync()
