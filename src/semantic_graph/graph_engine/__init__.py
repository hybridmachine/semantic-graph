"""Graph engine package.

Probes for graph-tool availability at import time and exposes a backend marker.
graph-tool is not available via pip; see README for installation instructions.
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
