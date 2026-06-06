"""Graph builder — loads a project graph from SQLite into memory.

The load path is the only place that reads nodes and edges from the
per-project ``graph.db`` for the purpose of building an in-memory cache.
Once built, all read queries are served from memory (see :mod:`queries`).
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from semantic_graph.graph_engine.backends import (
    GraphBackend,
    GraphBuildResult,
    get_backend,
)
from semantic_graph.storage.models import Edge, Node


def load_graph(
    session: Session,
    project_id: uuid.UUID,
    *,
    backend: GraphBackend | None = None,
) -> GraphBuildResult:
    """Load all nodes and edges for *project_id* into an in-memory graph.

    Parameters
    ----------
    session:
        An open SQLAlchemy session bound to the project's ``graph.db``.
    project_id:
        The project whose graph should be loaded.
    backend:
        The graph backend to use.  When *None*, the best available
        backend is selected automatically (graph-tool if installed,
        otherwise NetworkX).

    Returns
    -------
    GraphBuildResult
        The in-memory graph with bidirectional node-id↔index mappings.

    """

    if backend is None:
        backend = get_backend()

    # ------------------------------------------------------------------
    # Load nodes
    # ------------------------------------------------------------------
    from sqlalchemy import select

    node_rows = list(session.scalars(select(Node).filter_by(project_id=project_id)))

    nodes: list[dict[str, object]] = []
    for node in node_rows:
        nodes.append(
            {
                "id": node.id,
                "project_id": node.project_id,
                "name": node.name,
                "type": node.type,
                "abstraction_level": node.abstraction_level,
                "source_file": node.source_file,
                "content_snippet": node.content_snippet,
                "metadata_": node.metadata_,
                "created_at": node.created_at,
                "updated_at": node.updated_at,
            }
        )

    # ------------------------------------------------------------------
    # Load edges
    # ------------------------------------------------------------------
    edge_rows = list(session.scalars(select(Edge).filter_by(project_id=project_id)))

    edges: list[dict[str, object]] = []
    for edge in edge_rows:
        edges.append(
            {
                "id": edge.id,
                "project_id": edge.project_id,
                "source_node_id": edge.source_node_id,
                "target_node_id": edge.target_node_id,
                "relationship_type": edge.relationship_type,
                "confidence_score": edge.confidence_score,
                "metadata_": edge.metadata_,
                "created_at": edge.created_at,
            }
        )

    return backend.build(nodes, edges)
