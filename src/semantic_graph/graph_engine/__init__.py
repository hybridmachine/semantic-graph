"""Graph engine package.

Probes for graph-tool availability at import time and exposes a backend marker.
graph-tool is not available via pip; see README for installation instructions.

Public API
----------
- :func:`get_backend` — select the best available graph backend.
- :func:`load_graph` — load a project's nodes and edges into memory.
- :func:`get_node` / :func:`get_neighbors` / :func:`get_stats` — read queries.
- :class:`GraphSyncManager` — deferred SQLite write path with single-writer lock.
"""

import importlib.util

GRAPH_TOOL_AVAILABLE: bool = importlib.util.find_spec("graph_tool") is not None
GRAPH_BACKEND: str = "graph-tool" if GRAPH_TOOL_AVAILABLE else "fallback"
GRAPH_TOOL_IMPORT_ERROR: str | None = (
    None
    if GRAPH_TOOL_AVAILABLE
    else (
        "graph-tool is not installed. See README for installation instructions. "
        "A NetworkX-based fallback is available for development and small graphs only."
    )
)

from semantic_graph.graph_engine.backends import (  # noqa: E402, F401
    GraphBackend,
    GraphBuildResult,
    GraphToolBackend,
    NetworkXBackend,
    get_backend,
)
from semantic_graph.graph_engine.graph_builder import load_graph  # noqa: E402, F401
from semantic_graph.graph_engine.queries import (  # noqa: E402, F401
    get_neighbors,
    get_node,
    get_stats,
)
from semantic_graph.graph_engine.sync import GraphSyncManager  # noqa: E402, F401

__all__ = [
    "GRAPH_TOOL_AVAILABLE",
    "GRAPH_BACKEND",
    "GRAPH_TOOL_IMPORT_ERROR",
    "GraphBackend",
    "GraphBuildResult",
    "GraphToolBackend",
    "NetworkXBackend",
    "get_backend",
    "load_graph",
    "get_node",
    "get_neighbors",
    "get_stats",
    "GraphSyncManager",
]
