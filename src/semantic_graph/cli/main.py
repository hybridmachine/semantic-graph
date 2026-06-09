"""Typer CLI application."""

from __future__ import annotations

import typer
from rich.console import Console

from semantic_graph.cli.commands import config_app, projects_app

app = typer.Typer(
    name="semantic-graph",
    help="Semantic Graph Manager — create, manage, and query semantic graphs.",
    no_args_is_help=True,
)
console = Console()

# ---------------------------------------------------------------------------
# Sub-command groups
# ---------------------------------------------------------------------------
app.add_typer(projects_app, name="project")
app.add_typer(config_app, name="config")


@app.command(name="version")
def version() -> None:
    """Show the application version."""
    from semantic_graph import __version__

    console.print(f"semantic-graph {__version__}")


if __name__ == "__main__":
    app()
