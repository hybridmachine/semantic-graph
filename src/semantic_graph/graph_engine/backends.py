"""Graph backend abstraction with NetworkX and graph-tool implementations.

Provides a swappable backend layer so the graph engine can use graph-tool
when available and fall back to NetworkX for development and test environments.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from semantic_graph.graph_engine import GRAPH_TOOL_AVAILABLE

# ---------------------------------------------------------------------------
# Shared result type
# ---------------------------------------------------------------------------


@dataclass
class GraphBuildResult:
    """Result of building an in-memory graph from SQLite data.

    Holds the backend-specific graph object together with bidirectional
    mappings between domain UUIDs and internal vertex indices.  Query
    functions use these mappings to resolve UUIDs to vertices without
    coupling to a particular backend.

    Side-dict storage (``_node_attrs``, ``_edge_attrs``) is used by
    backends that do not have built-in per-vertex / per-edge attribute
    storage (e.g. graph-tool).  NetworkX stores attributes directly on
    the graph object but also populates these dicts for uniform access.
    """

    node_count: int
    edge_count: int
    backend_name: str
    _graph: Any = field(repr=False)
    _backend: GraphBackend = field(repr=False)
    _node_id_to_idx: dict[uuid.UUID, int] = field(default_factory=dict, repr=False)
    _idx_to_node_id: dict[int, uuid.UUID] = field(default_factory=dict, repr=False)
    # Side-dict storage for backends without built-in attribute storage.
    _node_attrs: dict[int, dict[str, Any]] = field(default_factory=dict, repr=False)
    _edge_attrs: dict[tuple[int, int], dict[str, Any]] = field(
        default_factory=dict, repr=False
    )

    # ------------------------------------------------------------------
    # Convenience helpers used by the query layer
    # ------------------------------------------------------------------

    def resolve(self, node_id: uuid.UUID) -> int | None:
        """Return the internal vertex index for *node_id*, or *None*."""
        return self._node_id_to_idx.get(node_id)

    def node_id(self, idx: int) -> uuid.UUID | None:
        """Return the domain UUID for internal vertex *idx*, or *None*."""
        return self._idx_to_node_id.get(idx)


# ---------------------------------------------------------------------------
# Abstract backend
# ---------------------------------------------------------------------------


class GraphBackend(ABC):
    """Abstract interface for graph backends.

    Subclasses implement build / query / mutate operations against a
    specific graph library (NetworkX, graph-tool, etc.).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable backend identifier (e.g. ``"networkx"``)."""
        ...

    # -- Build ----------------------------------------------------------------

    @abstractmethod
    def build(
        self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
    ) -> GraphBuildResult:
        """Construct an in-memory graph from *nodes* and *edges*.

        Each element in *nodes* and *edges* is a flat dict of column
        values (as returned by the SQLite ORM layer).  The backend is
        responsible for creating vertices, storing relevant properties,
        and populating the id↔index mappings on the result.
        """
        ...

    # -- Query ----------------------------------------------------------------

    @abstractmethod
    def get_node_attrs(
        self, build_result: GraphBuildResult, idx: int
    ) -> dict[str, Any]:
        """Return the stored attributes for the vertex at *idx*."""
        ...

    @abstractmethod
    def get_neighbor_indices(
        self,
        build_result: GraphBuildResult,
        idx: int,
        direction: str = "all",
    ) -> list[int]:
        """Return the internal indices of neighboring vertices.

        *direction* must be one of ``"out"``, ``"in"``, or ``"all"``.
        """
        ...

    @abstractmethod
    def get_edge_attrs(
        self,
        build_result: GraphBuildResult,
        src_idx: int,
        tgt_idx: int,
    ) -> dict[str, Any] | None:
        """Return stored attributes for the edge *src_idx* → *tgt_idx*,
        or *None* if no such edge exists."""
        ...

    @abstractmethod
    def node_count(self, build_result: GraphBuildResult) -> int:
        """Return the number of vertices in the graph."""
        ...

    @abstractmethod
    def edge_count(self, build_result: GraphBuildResult) -> int:
        """Return the number of edges in the graph."""
        ...

    # -- Mutate ---------------------------------------------------------------

    @abstractmethod
    def add_node(
        self, build_result: GraphBuildResult, node_attrs: dict[str, Any]
    ) -> int:
        """Add a vertex with *node_attrs* and return its internal index."""
        ...

    @abstractmethod
    def add_edge(
        self,
        build_result: GraphBuildResult,
        src_idx: int,
        tgt_idx: int,
        edge_attrs: dict[str, Any],
    ) -> None:
        """Add a directed edge *src_idx* → *tgt_idx* with *edge_attrs*."""
        ...


# ---------------------------------------------------------------------------
# NetworkX backend (always available)
# ---------------------------------------------------------------------------


class NetworkXBackend(GraphBackend):
    """Graph backend backed by `NetworkX <https://networkx.org/>`_.

    Uses ``nx.MultiDiGraph`` to support parallel edges between the same
    source and target nodes (keyed by edge ``id``).  Suitable for
    development, testing, and small-to-medium graphs.
    """

    @property
    def name(self) -> str:
        return "networkx"

    # -- Build ----------------------------------------------------------------

    def build(
        self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
    ) -> GraphBuildResult:
        import networkx as nx

        g: Any = nx.MultiDiGraph()
        node_id_to_idx: dict[uuid.UUID, int] = {}
        idx_to_node_id: dict[int, uuid.UUID] = {}
        node_attrs: dict[int, dict[str, Any]] = {}
        edge_attrs_side: dict[tuple[int, int], dict[str, Any]] = {}

        for idx, node in enumerate(nodes):
            g.add_node(idx, **{k: v for k, v in node.items() if k != "id"})
            nid = node["id"]
            node_id_to_idx[nid] = idx
            idx_to_node_id[idx] = nid
            node_attrs[idx] = {k: v for k, v in node.items()}

        for edge in edges:
            src_idx = node_id_to_idx[edge["source_node_id"]]
            tgt_idx = node_id_to_idx[edge["target_node_id"]]
            edge_key = str(edge.get("id", uuid.uuid4()))
            edge_data = {
                k: v
                for k, v in edge.items()
                if k not in ("source_node_id", "target_node_id")
            }
            g.add_edge(src_idx, tgt_idx, key=edge_key, **edge_data)
            edge_attrs_side[(src_idx, tgt_idx)] = edge_data

        return GraphBuildResult(
            node_count=len(nodes),
            edge_count=len(edges),
            backend_name=self.name,
            _graph=g,
            _backend=self,
            _node_id_to_idx=node_id_to_idx,
            _idx_to_node_id=idx_to_node_id,
            _node_attrs=node_attrs,
            _edge_attrs=edge_attrs_side,
        )

    # -- Query ----------------------------------------------------------------

    def get_node_attrs(
        self, build_result: GraphBuildResult, idx: int
    ) -> dict[str, Any]:
        g: Any = build_result._graph  # MultiDiGraph
        attrs: dict[str, Any] = dict(g.nodes[idx])
        # Inject the domain id so callers always have it
        attrs["id"] = build_result._idx_to_node_id[idx]
        return attrs

    def get_neighbor_indices(
        self,
        build_result: GraphBuildResult,
        idx: int,
        direction: str = "all",
    ) -> list[int]:
        g: Any = build_result._graph  # MultiDiGraph
        if direction == "out":
            return list(g.successors(idx))
        elif direction == "in":
            return list(g.predecessors(idx))
        else:
            return list(set(g.successors(idx)) | set(g.predecessors(idx)))

    def get_edge_attrs(
        self,
        build_result: GraphBuildResult,
        src_idx: int,
        tgt_idx: int,
    ) -> dict[str, Any] | None:
        g: Any = build_result._graph  # MultiDiGraph
        if not g.has_edge(src_idx, tgt_idx):
            return None
        # MultiDiGraph: get_edge_data returns {key: attrs}.
        edge_data = g.get_edge_data(src_idx, tgt_idx)
        if not edge_data:
            return None
        return dict(next(iter(edge_data.values())))

    def node_count(self, build_result: GraphBuildResult) -> int:
        g: Any = build_result._graph  # MultiDiGraph
        return int(g.number_of_nodes())

    def edge_count(self, build_result: GraphBuildResult) -> int:
        g: Any = build_result._graph  # MultiDiGraph
        return int(g.number_of_edges())

    # -- Mutate ---------------------------------------------------------------

    def add_node(
        self, build_result: GraphBuildResult, node_attrs: dict[str, Any]
    ) -> int:
        g: Any = build_result._graph  # MultiDiGraph
        new_idx = int(g.number_of_nodes())
        g.add_node(new_idx, **{k: v for k, v in node_attrs.items() if k != "id"})
        nid = node_attrs["id"]
        build_result._node_id_to_idx[nid] = new_idx
        build_result._idx_to_node_id[new_idx] = nid
        build_result._node_attrs[new_idx] = {k: v for k, v in node_attrs.items()}
        build_result.node_count += 1
        return new_idx

    def add_edge(
        self,
        build_result: GraphBuildResult,
        src_idx: int,
        tgt_idx: int,
        edge_attrs: dict[str, Any],
    ) -> None:
        g: Any = build_result._graph  # MultiDiGraph
        edge_key = str(edge_attrs.get("id", uuid.uuid4()))
        g.add_edge(src_idx, tgt_idx, key=edge_key, **edge_attrs)
        build_result._edge_attrs[(src_idx, tgt_idx)] = dict(edge_attrs)
        build_result.edge_count += 1


# ---------------------------------------------------------------------------
# graph-tool backend (optional)
# ---------------------------------------------------------------------------


class GraphToolBackend(GraphBackend):
    """Graph backend backed by `graph-tool <https://graph-tool.skewed.de/>`_.

    Provides high-performance in-memory graph operations.  Requires a
    working graph-tool installation (see project README).

    Node and edge attributes are stored in side-dict dictionaries keyed
    by vertex / edge index because graph-tool does not have built-in
    per-vertex / per-edge attribute storage without typed property maps.
    """

    @property
    def name(self) -> str:
        return "graph-tool"

    # -- Build ----------------------------------------------------------------

    def build(
        self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
    ) -> GraphBuildResult:
        from graph_tool import Graph

        g = Graph(directed=True)
        node_id_to_idx: dict[uuid.UUID, int] = {}
        idx_to_node_id: dict[int, uuid.UUID] = {}
        node_attrs: dict[int, dict[str, Any]] = {}
        edge_attrs_side: dict[tuple[int, int], dict[str, Any]] = {}

        # Pre-allocate vertices
        g.add_vertex(len(nodes))

        for idx, node in enumerate(nodes):
            nid = node["id"]
            node_id_to_idx[nid] = idx
            idx_to_node_id[idx] = nid
            node_attrs[idx] = {k: v for k, v in node.items()}

        # Add edges
        for edge in edges:
            src_idx = node_id_to_idx[edge["source_node_id"]]
            tgt_idx = node_id_to_idx[edge["target_node_id"]]
            g.add_edge(g.vertex(src_idx), g.vertex(tgt_idx))
            edge_attrs_side[(src_idx, tgt_idx)] = {
                k: v
                for k, v in edge.items()
                if k not in ("source_node_id", "target_node_id")
            }

        return GraphBuildResult(
            node_count=len(nodes),
            edge_count=len(edges),
            backend_name=self.name,
            _graph=g,
            _backend=self,
            _node_id_to_idx=node_id_to_idx,
            _idx_to_node_id=idx_to_node_id,
            _node_attrs=node_attrs,
            _edge_attrs=edge_attrs_side,
        )

    # -- Query ----------------------------------------------------------------

    def get_node_attrs(
        self, build_result: GraphBuildResult, idx: int
    ) -> dict[str, Any]:
        attrs = build_result._node_attrs.get(idx, {})
        # Ensure the domain id is always present
        attrs["id"] = build_result._idx_to_node_id[idx]
        return attrs

    def get_neighbor_indices(
        self,
        build_result: GraphBuildResult,
        idx: int,
        direction: str = "all",
    ) -> list[int]:
        from graph_tool import Graph

        g: Graph = build_result._graph
        v = g.vertex(idx)
        result: list[int] = []
        if direction in ("out", "all"):
            result.extend(int(w) for w in v.out_neighbors())
        if direction in ("in", "all"):
            result.extend(int(w) for w in v.in_neighbors())
        if direction == "all":
            result = list(set(result))
        return result

    def get_edge_attrs(
        self,
        build_result: GraphBuildResult,
        src_idx: int,
        tgt_idx: int,
    ) -> dict[str, Any] | None:
        from graph_tool import Graph

        g: Graph = build_result._graph
        e = g.edge(g.vertex(src_idx), g.vertex(tgt_idx))
        if e is None:
            return None
        return build_result._edge_attrs.get((src_idx, tgt_idx))

    def node_count(self, build_result: GraphBuildResult) -> int:
        from graph_tool import Graph

        g: Graph = build_result._graph
        return int(g.num_vertices())

    def edge_count(self, build_result: GraphBuildResult) -> int:
        from graph_tool import Graph

        g: Graph = build_result._graph
        return int(g.num_edges())

    # -- Mutate ---------------------------------------------------------------

    def add_node(
        self, build_result: GraphBuildResult, node_attrs: dict[str, Any]
    ) -> int:
        from graph_tool import Graph

        g: Graph = build_result._graph
        new_idx = int(g.num_vertices())
        g.add_vertex()
        nid = node_attrs["id"]
        build_result._node_id_to_idx[nid] = new_idx
        build_result._idx_to_node_id[new_idx] = nid
        build_result._node_attrs[new_idx] = {k: v for k, v in node_attrs.items()}
        build_result.node_count += 1
        return new_idx

    def add_edge(
        self,
        build_result: GraphBuildResult,
        src_idx: int,
        tgt_idx: int,
        edge_attrs: dict[str, Any],
    ) -> None:
        from graph_tool import Graph

        g: Graph = build_result._graph
        g.add_edge(g.vertex(src_idx), g.vertex(tgt_idx))
        build_result._edge_attrs[(src_idx, tgt_idx)] = dict(edge_attrs)
        build_result.edge_count += 1


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_backend(prefer: str | None = None) -> GraphBackend:
    """Return the best available graph backend.

    Parameters
    ----------
    prefer:
        Force a specific backend (``"graph-tool"`` or ``"networkx"``).
        Raises :class:`RuntimeError` if the requested backend is not
        available.  When *None*, graph-tool is used if installed,
        otherwise NetworkX.
    """
    if prefer == "graph-tool":
        if not GRAPH_TOOL_AVAILABLE:
            raise RuntimeError("graph-tool is not installed")
        return GraphToolBackend()
    if prefer == "networkx":
        return NetworkXBackend()

    if GRAPH_TOOL_AVAILABLE:
        return GraphToolBackend()
    return NetworkXBackend()
