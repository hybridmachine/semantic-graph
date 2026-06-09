"""CLI command modules."""

from semantic_graph.cli.commands.config import config_app
from semantic_graph.cli.commands.projects import projects_app

__all__ = [
    "config_app",
    "projects_app",
]
