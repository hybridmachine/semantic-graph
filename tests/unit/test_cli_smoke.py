"""Smoke tests for the Typer CLI application."""

import typer

from semantic_graph.cli.main import app


def test_cli_app_imports() -> None:
    assert app is not None


def test_cli_app_is_typer() -> None:
    assert isinstance(app, typer.Typer)


def test_cli_has_version_command() -> None:
    registered = {cmd.name for cmd in app.registered_commands}
    assert "version" in registered
