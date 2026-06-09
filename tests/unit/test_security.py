"""Tests for path security and file validation utilities."""

from __future__ import annotations

from pathlib import Path

import pytest

from semantic_graph.utils.errors import PathSecurityError, PathTraversalError
from semantic_graph.utils.security import (
    DEFAULT_EXCLUDE_PATTERNS,
    canonicalize_path,
    is_binary_file,
    is_within_root,
    validate_project_root,
    validate_safe_path,
)


class TestCanonicalizePath:
    def test_resolves_relative_path(self, tmp_path: Path) -> None:
        (tmp_path / "sub").mkdir()
        result = canonicalize_path(tmp_path / "sub" / ".." / "sub")
        assert result == tmp_path / "sub"

    def test_resolves_dot_dot(self, tmp_path: Path) -> None:
        result = canonicalize_path(tmp_path / ".." / tmp_path.name)
        assert result == tmp_path

    def test_absolute_path_unchanged(self, tmp_path: Path) -> None:
        abs_path = tmp_path / "file.txt"
        abs_path.touch()
        result = canonicalize_path(abs_path)
        assert result == abs_path.resolve()

    def test_nonexistent_suffix(self, tmp_path: Path) -> None:
        """Non-existent trailing components are preserved after the existing prefix."""
        result = canonicalize_path(tmp_path / "nonexistent" / "child")
        assert result == tmp_path.resolve() / "nonexistent" / "child"


class TestIsWithinRoot:
    def test_path_inside_root(self, tmp_path: Path) -> None:
        (tmp_path / "sub").mkdir()
        assert is_within_root(tmp_path / "sub", tmp_path) is True

    def test_path_is_root(self, tmp_path: Path) -> None:
        assert is_within_root(tmp_path, tmp_path) is True

    def test_path_outside_root(self, tmp_path: Path) -> None:
        outside = tmp_path / ".." / "other"
        assert is_within_root(outside, tmp_path) is False

    def test_traversal_attempt(self, tmp_path: Path) -> None:
        assert is_within_root(tmp_path / ".." / "etc" / "passwd", tmp_path) is False


class TestValidateSafePath:
    def test_safe_path_returns_canonical(self, tmp_path: Path) -> None:
        (tmp_path / "sub").mkdir()
        result = validate_safe_path(tmp_path / "sub", tmp_path)
        assert result == tmp_path / "sub"

    def test_traversal_raises(self, tmp_path: Path) -> None:
        with pytest.raises(PathTraversalError):
            validate_safe_path(tmp_path / ".." / "etc" / "passwd", tmp_path)

    def test_traversal_dot_dot_slash(self, tmp_path: Path) -> None:
        with pytest.raises(PathTraversalError):
            validate_safe_path(tmp_path / "../../etc/passwd", tmp_path)


class TestIsBinaryFile:
    def test_text_file(self, tmp_path: Path) -> None:
        f = tmp_path / "hello.txt"
        f.write_text("hello world")
        assert is_binary_file(f) is False

    def test_binary_file_with_null(self, tmp_path: Path) -> None:
        f = tmp_path / "data.bin"
        f.write_bytes(b"some text\x00more text")
        assert is_binary_file(f) is True

    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.txt"
        f.write_text("")
        assert is_binary_file(f) is False

    def test_unreadable_file(self, tmp_path: Path) -> None:
        f = tmp_path / "no_read.bin"
        f.write_bytes(b"secret")
        f.chmod(0o000)
        try:
            assert is_binary_file(f) is True
        finally:
            f.chmod(0o644)

    def test_pure_text_large_file(self, tmp_path: Path) -> None:
        f = tmp_path / "large.txt"
        f.write_text("x" * 100_000)
        assert is_binary_file(f) is False


class TestValidateProjectRoot:
    def test_valid_directory(self, tmp_path: Path) -> None:
        result = validate_project_root(tmp_path)
        assert result == tmp_path.resolve()

    def test_nonexistent_path(self, tmp_path: Path) -> None:
        with pytest.raises(PathSecurityError, match="does not exist"):
            validate_project_root(tmp_path / "does_not_exist")

    def test_not_a_directory(self, tmp_path: Path) -> None:
        f = tmp_path / "file.txt"
        f.touch()
        with pytest.raises(PathSecurityError, match="not a directory"):
            validate_project_root(f)

    def test_system_root_rejected(self) -> None:
        with pytest.raises(PathSecurityError):
            validate_project_root(Path("/"))

    def test_etc_rejected(self) -> None:
        # /etc is a symlink to /private/etc on macOS; the validation
        # checks both the input path and the canonical path.
        with pytest.raises(PathSecurityError):
            validate_project_root(Path("/etc"))


class TestDefaultExcludePatterns:
    def test_contains_expected_patterns(self) -> None:
        assert ".git" in DEFAULT_EXCLUDE_PATTERNS
        assert "node_modules" in DEFAULT_EXCLUDE_PATTERNS
        assert ".venv" in DEFAULT_EXCLUDE_PATTERNS
        assert "__pycache__" in DEFAULT_EXCLUDE_PATTERNS
        assert "dist" in DEFAULT_EXCLUDE_PATTERNS
        assert "build" in DEFAULT_EXCLUDE_PATTERNS
