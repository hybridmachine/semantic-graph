"""CLI commands for project management."""

from __future__ import annotations

import uuid

import typer
from rich.console import Console
from rich.table import Table

from semantic_graph.api.schemas.projects import ProjectCreate, ProjectUpdate
from semantic_graph.core.config import settings
from semantic_graph.core.project_manager import ProjectManager
from semantic_graph.storage.database import DatabaseManager
from semantic_graph.utils.errors import SemanticGraphError

projects_app = typer.Typer(
    name="project",
    help="Manage semantic-graph projects.",
    no_args_is_help=True,
)
console = Console()

_db = DatabaseManager(settings.data_dir)
_manager = ProjectManager(_db)


def _format_output(
    data: object, fmt: str
) -> None:
    """Render *data* in the requested format."""
    import json as _json

    if fmt == "json":
        if hasattr(data, "model_dump"):
            console.print(_json.dumps(data.model_dump(), default=str, indent=2))
        else:
            console.print(_json.dumps(data, default=str, indent=2))
    else:
        # Default: let the caller handle via Rich.
        pass


# ---------------------------------------------------------------------------
# project create
# ---------------------------------------------------------------------------


@projects_app.command(name="create")
def create_project(
    name: str = typer.Argument(..., help="Project name"),
    root_path: str = typer.Argument(..., help="Absolute path to the project folder"),
    include: list[str] | None = typer.Option(
        None, "--include", "-i", help="Glob patterns to include"
    ),
    exclude: list[str] | None = typer.Option(
        None, "--exclude", "-e", help="Glob patterns to exclude"
    ),
    no_gitignore: bool = typer.Option(
        False, "--no-gitignore", help="Do not respect .gitignore"
    ),
    max_file_size: int = typer.Option(
        10_485_760, "--max-file-size", help="Maximum file size in bytes"
    ),
    follow_symlinks: bool = typer.Option(
        False, "--follow-symlinks", help="Follow symlinks"
    ),
    llm_provider: str | None = typer.Option(
        None, "--llm-provider", help="LLM provider name"
    ),
    llm_model: str | None = typer.Option(
        None, "--llm-model", help="LLM model name"
    ),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format: table, json"
    ),
) -> None:
    """Create a new project."""
    payload = ProjectCreate(
        name=name,
        root_path=root_path,
        include_patterns=include or ["*"],
        exclude_patterns=exclude or [],
        respect_gitignore=not no_gitignore,
        max_file_size_bytes=max_file_size,
        follow_symlinks=follow_symlinks,
        llm_provider=llm_provider,
        llm_model=llm_model,
    )
    try:
        project = _manager.create_project(payload)
    except SemanticGraphError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    if format == "json":
        _format_output(project, "json")
    else:
        console.print(f"[green]Created project[/green] {project.name}")
        console.print(f"  ID:        {project.id}")
        console.print(f"  Root:      {project.root_path}")
        console.print(f"  Status:    {project.status}")


# ---------------------------------------------------------------------------
# project list
# ---------------------------------------------------------------------------


@projects_app.command(name="list")
def list_projects(
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format: table, json"
    ),
    offset: int = typer.Option(0, "--offset", help="Records to skip"),
    limit: int = typer.Option(20, "--limit", help="Max records to return"),
) -> None:
    """List all registered projects."""
    items, total = _manager.list_projects(offset=offset, limit=limit)

    if format == "json":
        import json as _json

        console.print(
            _json.dumps(
                {
                    "items": [item.model_dump() for item in items],
                    "total": total,
                },
                default=str,
                indent=2,
            )
        )
        return

    if total == 0:
        console.print("[dim]No projects registered.[/dim]")
        return

    table = Table(title=f"Projects ({total} total)")
    table.add_column("Name", style="cyan")
    table.add_column("ID", style="dim")
    table.add_column("Root Path")
    table.add_column("Status")

    for p in items:
        table.add_row(
            p.name,
            str(p.id),
            p.root_path,
            p.status,
        )
    console.print(table)


# ---------------------------------------------------------------------------
# project delete
# ---------------------------------------------------------------------------


@projects_app.command(name="delete")
def delete_project(
    name_or_id: str = typer.Argument(..., help="Project name or UUID"),
    force: bool = typer.Option(
        False, "--force", "-y", help="Skip confirmation prompt"
    ),
) -> None:
    """Delete a project and its graph data."""
    project_id = _resolve_project_id(name_or_id)

    if not force:
        confirm = typer.confirm(
            f"Delete project '{name_or_id}' and all its graph data?"
        )
        if not confirm:
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(0)

    try:
        _manager.delete_project(project_id)
    except SemanticGraphError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    console.print(f"[green]Deleted project[/green] {name_or_id}")


# ---------------------------------------------------------------------------
# project configure
# ---------------------------------------------------------------------------


@projects_app.command(name="configure")
def configure_project(
    name_or_id: str = typer.Argument(..., help="Project name or UUID"),
    include: list[str] | None = typer.Option(
        None, "--include", "-i", help="Glob patterns to include"
    ),
    exclude: list[str] | None = typer.Option(
        None, "--exclude", "-e", help="Glob patterns to exclude"
    ),
    llm_provider: str | None = typer.Option(
        None, "--llm-provider", help="LLM provider name"
    ),
    llm_model: str | None = typer.Option(
        None, "--llm-model", help="LLM model name"
    ),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format: table, json"
    ),
) -> None:
    """Update project configuration."""
    project_id = _resolve_project_id(name_or_id)

    update = ProjectUpdate()
    if include is not None:
        update.include_patterns = include
    if exclude is not None:
        update.exclude_patterns = exclude
    if llm_provider is not None:
        update.llm_provider = llm_provider
    if llm_model is not None:
        update.llm_model = llm_model

    try:
        project = _manager.update_project(project_id, update)
    except SemanticGraphError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    if format == "json":
        _format_output(project, "json")
    else:
        console.print(f"[green]Updated project[/green] {project.name}")


# ---------------------------------------------------------------------------
# project status
# ---------------------------------------------------------------------------


@projects_app.command(name="status")
def project_status(
    name_or_id: str = typer.Argument(..., help="Project name or UUID"),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format: table, json"
    ),
) -> None:
    """Show detailed status for a project."""
    project_id = _resolve_project_id(name_or_id)

    try:
        project = _manager.get_project(project_id)
    except SemanticGraphError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    if format == "json":
        _format_output(project, "json")
    else:
        console.print(f"[bold]{project.name}[/bold]")
        console.print(f"  ID:              {project.id}")
        console.print(f"  Root Path:       {project.root_path}")
        console.print(f"  Status:          {project.status}")
        console.print(f"  Nodes:           {project.node_count}")
        console.print(f"  Edges:           {project.edge_count}")
        console.print(f"  Include Patterns: {project.include_patterns}")
        console.print(f"  Exclude Patterns: {project.exclude_patterns}")
        console.print(f"  Respect .gitignore: {project.respect_gitignore}")
        console.print(f"  Max File Size:   {project.max_file_size_bytes}")
        console.print(f"  Follow Symlinks: {project.follow_symlinks}")
        console.print(f"  Created:         {project.created_at}")
        console.print(f"  Updated:         {project.updated_at}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_project_id(name_or_id: str) -> uuid.UUID:
    """Resolve a name or UUID string to a project UUID.

    If *name_or_id* parses as a UUID it is used directly.  Otherwise it is
    treated as a project name and looked up via a direct DB query.
    """
    try:
        return uuid.UUID(name_or_id)
    except ValueError:
        pass

    # Look up by name — uses a direct DB query, not a paginated list.
    project = _manager.get_project_by_name(name_or_id)
    if project is not None:
        return project.id

    console.print(f"[red]Project not found:[/red] {name_or_id}")
    raise typer.Exit(1)
