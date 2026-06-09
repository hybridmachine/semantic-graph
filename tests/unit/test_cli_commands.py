"""Tests for CLI command structure and help output."""

from __future__ import annotations

from typer.testing import CliRunner

from semantic_graph.cli.main import app

runner = CliRunner()


class TestVersion:
    def test_version_command(self) -> None:
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "semantic-graph" in result.stdout

    def test_version_help(self) -> None:
        result = runner.invoke(app, ["version", "--help"])
        assert result.exit_code == 0
        assert "version" in result.stdout.lower()


class TestProjectGroup:
    def test_project_help(self) -> None:
        result = runner.invoke(app, ["project", "--help"])
        assert result.exit_code == 0
        assert "create" in result.stdout.lower()
        assert "list" in result.stdout.lower()
        assert "delete" in result.stdout.lower()
        assert "configure" in result.stdout.lower()

    def test_project_create_help(self) -> None:
        result = runner.invoke(app, ["project", "create", "--help"])
        assert result.exit_code == 0

    def test_project_list_help(self) -> None:
        result = runner.invoke(app, ["project", "list", "--help"])
        assert result.exit_code == 0

    def test_project_delete_help(self) -> None:
        result = runner.invoke(app, ["project", "delete", "--help"])
        assert result.exit_code == 0

    def test_project_configure_help(self) -> None:
        result = runner.invoke(app, ["project", "configure", "--help"])
        assert result.exit_code == 0

    def test_project_status_help(self) -> None:
        result = runner.invoke(app, ["project", "status", "--help"])
        assert result.exit_code == 0


class TestConfigGroup:
    def test_config_help(self) -> None:
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0
        assert "show" in result.stdout.lower()

    def test_config_show(self) -> None:
        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "API Host" in result.stdout

    def test_config_set(self) -> None:
        result = runner.invoke(app, ["config", "set", "debug", "true"])
        assert result.exit_code == 0


class TestTopLevelHelp:
    def test_top_level_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "project" in result.stdout
        assert "config" in result.stdout
        assert "version" in result.stdout
