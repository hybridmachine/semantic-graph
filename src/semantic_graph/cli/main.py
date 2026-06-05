"""Typer CLI application."""

import typer
from rich.console import Console

app = typer.Typer(
    name="semantic-graph",
    help="Semantic Graph Manager — create, manage, and query semantic graphs.",
    no_args_is_help=True,
)
console = Console()


@app.command(name="version")
def version() -> None:
    """Show the application version."""
    from semantic_graph import __version__

    console.print(f"semantic-graph {__version__}")


if __name__ == "__main__":
    app()
