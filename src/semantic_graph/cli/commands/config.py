"""CLI commands for managing semantic-graph configuration."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from semantic_graph.core.config import settings

config_app = typer.Typer(
    name="config",
    help="View and manage semantic-graph configuration.",
    no_args_is_help=True,
)
console = Console()

CONFIG_FILE_HELP = "~/.semantic-graph/config.yaml"


@config_app.command(name="show")
def config_show() -> None:
    """Display the current configuration."""
    console.print("[bold]Current Configuration[/bold]")
    console.print(f"  App Name:       {settings.app_name}")
    console.print(f"  Debug:          {settings.debug}")
    console.print(f"  API Host:       {settings.api_host}")
    console.print(f"  API Port:       {settings.api_port}")
    console.print(f"  Data Directory: {settings.data_dir}")
    console.print(f"  CORS Origins:   {settings.cors_origins}")
    console.print()
    config_path = Path.home() / ".semantic-graph" / "config.yaml"
    console.print(f"[dim]Config file: {config_path}[/dim]")
    console.print(
        "[dim]Override via environment variables: SEMANTIC_GRAPH_<SETTING>[/dim]"
    )


@config_app.command(name="set")
def config_set(
    key: str = typer.Argument(..., help="Configuration key to set"),
    value: str = typer.Argument(..., help="Value to assign"),
) -> None:
    """Set a configuration value (persisted to config file)."""
    # For now, direct the user to env vars; persistent config file
    # support can be added in a future iteration.
    console.print(
        "[yellow]Persistent config file not yet implemented.[/yellow]"
    )
    console.print(
        f"To override [bold]{key}[/bold], set the environment variable "
        f"[bold]SEMANTIC_GRAPH_{key.upper()}[/bold]={value}"
    )
