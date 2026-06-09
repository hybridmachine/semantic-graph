"""Tests for the file scanner."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from semantic_graph.extractors.scanner import FileScanner, ScanReport


@pytest.fixture
def project_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def scanner() -> FileScanner:
    return FileScanner()


class TestBasicScan:
    def test_empty_directory(self, tmp_path: Path, project_id: uuid.UUID) -> None:
        scanner = FileScanner()
        report = scanner.scan(project_id, tmp_path)
        assert isinstance(report, ScanReport)
        assert report.total_files == 0

    def test_single_text_file(
        self, tmp_path: Path, project_id: uuid.UUID
    ) -> None:
        (tmp_path / "readme.md").write_text("# Hello")
        report = FileScanner().scan(project_id, tmp_path)
        assert len(report.included) == 1
        assert report.included[0].relative_path == "readme.md"
        assert report.included[0].status == "included"
        assert report.included[0].content_hash is not None

    def test_multiple_files(
        self, tmp_path: Path, project_id: uuid.UUID
    ) -> None:
        (tmp_path / "a.py").write_text("x=1")
        (tmp_path / "b.py").write_text("y=2")
        report = FileScanner().scan(project_id, tmp_path)
        assert len(report.included) == 2

    def test_nested_directory(
        self, tmp_path: Path, project_id: uuid.UUID
    ) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.py").write_text("pass")
        report = FileScanner().scan(project_id, tmp_path)
        assert len(report.included) == 1
        assert report.included[0].relative_path == "sub/nested.py"


class TestDefaultExcludes:
    def test_git_directory_skipped(
        self, tmp_path: Path, project_id: uuid.UUID
    ) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("...")
        report = FileScanner().scan(project_id, tmp_path)
        assert len(report.included) == 0
        assert any(".git" in s.relative_path for s in report.skipped)

    def test_node_modules_skipped(
        self, tmp_path: Path, project_id: uuid.UUID
    ) -> None:
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "pkg").mkdir()
        (tmp_path / "node_modules" / "pkg" / "index.js").write_text("// js")
        report = FileScanner().scan(project_id, tmp_path)
        assert len(report.included) == 0

    def test_pycache_skipped(
        self, tmp_path: Path, project_id: uuid.UUID
    ) -> None:
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "foo.pyc").write_bytes(b"\x00")
        report = FileScanner().scan(project_id, tmp_path)
        assert len(report.included) == 0

    def test_venv_skipped(
        self, tmp_path: Path, project_id: uuid.UUID
    ) -> None:
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv" / "bin").mkdir()
        (tmp_path / ".venv" / "bin" / "python").write_text("")
        report = FileScanner().scan(project_id, tmp_path)
        assert len(report.included) == 0


class TestGitignore:
    def test_respects_gitignore(
        self, tmp_path: Path, project_id: uuid.UUID
    ) -> None:
        (tmp_path / ".gitignore").write_text("*.log\n")
        (tmp_path / "app.py").write_text("pass")
        (tmp_path / "debug.log").write_text("log data")
        report = FileScanner().scan(project_id, tmp_path)
        included = [r.relative_path for r in report.included]
        assert "app.py" in included
        assert "debug.log" not in included

    def test_gitignore_negation(
        self, tmp_path: Path, project_id: uuid.UUID
    ) -> None:
        (tmp_path / ".gitignore").write_text("*.log\n!keep.log\n")
        (tmp_path / "debug.log").write_text("bad")
        (tmp_path / "keep.log").write_text("good")
        report = FileScanner().scan(project_id, tmp_path)
        included = [r.relative_path for r in report.included]
        assert "keep.log" in included
        assert "debug.log" not in included

    def test_can_disable_gitignore(
        self, tmp_path: Path, project_id: uuid.UUID
    ) -> None:
        (tmp_path / ".gitignore").write_text("*.log\n")
        (tmp_path / "debug.log").write_text("log data")
        scanner = FileScanner(respect_gitignore=False)
        report = scanner.scan(project_id, tmp_path)
        included = [r.relative_path for r in report.included]
        assert "debug.log" in included


class TestIncludeExclude:
    def test_include_patterns(
        self, tmp_path: Path, project_id: uuid.UUID
    ) -> None:
        (tmp_path / "a.py").write_text("pass")
        (tmp_path / "b.txt").write_text("hi")
        scanner = FileScanner(include_patterns=["*.py"])
        report = scanner.scan(project_id, tmp_path)
        included = [r.relative_path for r in report.included]
        assert "a.py" in included
        assert "b.txt" not in included

    def test_exclude_patterns(
        self, tmp_path: Path, project_id: uuid.UUID
    ) -> None:
        (tmp_path / "a.py").write_text("pass")
        (tmp_path / "test_a.py").write_text("pass")
        scanner = FileScanner(exclude_patterns=["test_*.py"])
        report = scanner.scan(project_id, tmp_path)
        included = [r.relative_path for r in report.included]
        assert "a.py" in included
        assert "test_a.py" not in included


class TestBinaryDetection:
    def test_binary_file_skipped(
        self, tmp_path: Path, project_id: uuid.UUID
    ) -> None:
        (tmp_path / "data.bin").write_bytes(b"\x00\x01\x02\x03")
        report = FileScanner().scan(project_id, tmp_path)
        assert len(report.included) == 0
        assert any("Binary" in (s.skip_reason or "") for s in report.skipped)

    def test_text_file_included(
        self, tmp_path: Path, project_id: uuid.UUID
    ) -> None:
        (tmp_path / "code.py").write_text("import os")
        report = FileScanner().scan(project_id, tmp_path)
        assert len(report.included) == 1


class TestSymlinks:
    def test_symlink_skipped_by_default(
        self, tmp_path: Path, project_id: uuid.UUID
    ) -> None:
        target = tmp_path / "real.py"
        target.write_text("x=1")
        link = tmp_path / "link.py"
        link.symlink_to(target)
        report = FileScanner().scan(project_id, tmp_path)
        assert len(report.included) == 1  # only real.py
        assert any("link.py" in s.relative_path for s in report.skipped)

    def test_symlink_outside_root_blocked(
        self, tmp_path: Path, project_id: uuid.UUID
    ) -> None:
        outside = tmp_path.parent / "outside.txt"
        outside.write_text("secret")
        try:
            link = tmp_path / "escape"
            link.symlink_to(outside)
            scanner = FileScanner(follow_symlinks=True)
            report = scanner.scan(project_id, tmp_path)
            # The symlink should be skipped, not followed.
            assert all(
                "outside" not in (s.relative_path) for s in report.included
            )
        finally:
            outside.unlink(missing_ok=True)


class TestMaxFileSize:
    def test_oversized_file_skipped(
        self, tmp_path: Path, project_id: uuid.UUID
    ) -> None:
        (tmp_path / "big.txt").write_text("x" * 5000)
        scanner = FileScanner(max_file_size_bytes=100)
        report = scanner.scan(project_id, tmp_path)
        assert len(report.included) == 0
        assert any("exceeds max" in (s.skip_reason or "") for s in report.skipped)

    def test_small_file_included(
        self, tmp_path: Path, project_id: uuid.UUID
    ) -> None:
        (tmp_path / "small.txt").write_text("hi")
        scanner = FileScanner(max_file_size_bytes=1024)
        report = scanner.scan(project_id, tmp_path)
        assert len(report.included) == 1


class TestScanReportProperties:
    def test_total_files(self, tmp_path: Path, project_id: uuid.UUID) -> None:
        (tmp_path / "a.py").write_text("1")
        scanner = FileScanner(max_file_size_bytes=1)
        report = scanner.scan(project_id, tmp_path)
        assert report.total_files >= 1

    def test_content_hash_consistent(
        self, tmp_path: Path, project_id: uuid.UUID
    ) -> None:
        (tmp_path / "a.py").write_text("hello")
        report1 = FileScanner().scan(project_id, tmp_path)
        report2 = FileScanner().scan(project_id, tmp_path)
        assert report1.included[0].content_hash == report2.included[0].content_hash


class TestManifestIntegration:
    def test_build_manifest_entry_included(
        self, tmp_path: Path, project_id: uuid.UUID
    ) -> None:
        from semantic_graph.extractors.scanner import FileScanResult

        result = FileScanResult(
            relative_path="test.py",
            absolute_path=tmp_path / "test.py",
            size_bytes=100,
            status="included",
            content_hash="abc123",
        )
        entry = FileScanner.build_manifest_entry(project_id, result)
        assert entry.project_id == project_id
        assert entry.relative_path == "test.py"
        assert entry.status == "pending"
        assert entry.content_hash == "abc123"

    def test_build_manifest_entry_skipped(
        self, tmp_path: Path, project_id: uuid.UUID
    ) -> None:
        from semantic_graph.extractors.scanner import FileScanResult

        result = FileScanResult(
            relative_path="bad.bin",
            absolute_path=tmp_path / "bad.bin",
            size_bytes=500,
            status="skipped",
            skip_reason="Binary file",
        )
        entry = FileScanner.build_manifest_entry(project_id, result)
        assert entry.status == "skipped"
        assert entry.skip_reason == "Binary file"

    def test_scan_report_structure(self, project_id: uuid.UUID) -> None:
        report = ScanReport(project_id=project_id)
        assert report.total_files == 0
        assert report.included == []
        assert report.skipped == []
