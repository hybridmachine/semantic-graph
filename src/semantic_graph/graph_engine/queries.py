"""Graph query engine — serves reads from the in-memory graph.

All read operations are served directly from the :class:`GraphBuildResult`
held in memory; there is **no SQLite round-trip** on the read path.
"""

from __future__ import annotations

import uuid
from typing import Any

from semantic_graph.graph_engine.backends import GraphBackend, GraphBuildResult


def get_node(
    build_result: GraphBuildResult, node_id: uuid.UUID
) -> dict[str, Any] | None:
    """Return the attributes for *node_id*, or *None* if not found.

    Parameters
    ----------
    build_result:
        The in-memory graph to query.
    node_id:
        The domain UUID of the node.

    Returns
    -------
    dict | None
        A dictionary of node attributes (including ``"id"``), or *None*.
    """
    idx = build_result.resolve(node_id)
    if idx is None:
        return None
    backend: GraphBackend = build_result._backend
    return backend.get_node_attrs(build_result, idx)


def get_neighbors(
    build_result: GraphBuildResult,
    node_id: uuid.UUID,
    *,
    direction: str = "all",
) -> list[dict[str, Any]]:
    """Return the neighbor nodes of *node_id*.

    Parameters
    ----------
    build_result:
        The in-memory graph to query.
    node_id:
        The domain UUID of the node whose neighbors are fetched.
    direction:
        ``"out"`` — only outgoing edges from *node_id*.
        ``"in"``  — only incoming edges to *node_id*.
        ``"all"`` — both directions (default).

    Returns
    -------
    list[dict]
        A list of neighbor node attribute dictionaries.  Each includes
        the edge attributes under the key ``"edge"`` when a single edge
        connects the two vertices.  When multiple edges exist between
        the same pair only the first is reported.
    """
    idx = build_result.resolve(node_id)
    if idx is None:
        return []

    backend: GraphBackend = build_result._backend
    neighbor_indices = backend.get_neighbor_indices(build_result, idx, direction)

    results: list[dict[str, Any]] = []
    seen: set[int] = set()
    for nidx in neighbor_indices:
        if nidx in seen:
            continue
        seen.add(nidx)
        entry = backend.get_node_attrs(build_result, nidx)
        # Attach edge information according to direction so that the
        # returned edge metadata always corresponds to the edge that
        # caused the neighbor to be returned.
        if direction == "out":
            edge = backend.get_edge_attrs(build_result, idx, nidx)
        elif direction == "in":
            edge = backend.get_edge_attrs(build_result, nidx, idx)
        else:
            # "all" — prefer outgoing, fall back to incoming.
            edge = backend.get_edge_attrs(
                build_result, idx, nidx
            ) or backend.get_edge_attrs(build_result, nidx, idx)
        if edge is not None:
            entry["edge"] = edge
        results.append(entry)

    return results


def get_stats(build_result: GraphBuildResult) -> dict[str, Any]:
    """Return summary statistics for the in-memory graph.

    Parameters
    ----------
    build_result:
        The in-memory graph to summarize.

    Returns
    -------
    dict
        Keys: ``"node_count"``, ``"edge_count"``, ``"backend"``,
        ``"density"`` (approximate for directed graphs).
    """
    backend: GraphBackend = build_result._backend
    n = backend.node_count(build_result)
    m = backend.edge_count(build_result)
    # Directed density: m / (n * (n-1)), or 0.0 when n < 2
    density = m / (n * (n - 1)) if n > 1 else 0.0

    return {
        "node_count": n,
        "edge_count": m,
        "backend": build_result.backend_name,
        "density": round(density, 6),
    }
