"""Smoke tests for the Typer CLI application."""

from __future__ import annotations

import typer

from semantic_graph.cli.main import app


def test_cli_app_imports() -> None:
    """Typer app instantiates without error."""
    assert app is not None


def test_cli_app_is_typer() -> None:
    """App is a Typer instance."""
    assert isinstance(app, typer.Typer)


def test_cli_has_version_command() -> None:
    """The top-level version command is registered."""
    registered = {cmd.name for cmd in app.registered_commands}
    assert "version" in registered


def test_cli_has_project_group() -> None:
    """The 'project' sub-command group is registered."""
    registered = {cmd.name for cmd in app.registered_groups}
    assert "project" in registered


def test_cli_has_config_group() -> None:
    """The 'config' sub-command group is registered."""
    registered = {cmd.name for cmd in app.registered_groups}
    assert "config" in registered
