"""File-system scanner that discovers files for a project.

Uses glob-based include/exclude rules, optional ``.gitignore`` respect,
binary-file detection, and path-safety checks to produce a structured
list of files ready for extraction.
"""

from __future__ import annotations

import fnmatch
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from semantic_graph.storage.models import FileManifestEntry
from semantic_graph.utils.errors import PathSecurityError
from semantic_graph.utils.security import (
    DEFAULT_EXCLUDE_PATTERNS,
    canonicalize_path,
    is_binary_file,
    is_within_root,
    validate_project_root,
)


@dataclass
class FileScanResult:
    """A single file discovered (or skipped) during a scan."""

    relative_path: str
    absolute_path: Path
    size_bytes: int
    status: str  # "included" | "skipped"
    skip_reason: str | None = None
    content_hash: str | None = None

    def compute_content_hash(self, algorithm: str = "sha256") -> str:
        """Compute and return the content hash for this file."""
        h = hashlib.new(algorithm)
        with self.absolute_path.open("rb") as fh:
            while True:
                chunk = fh.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()


@dataclass
class ScanReport:
    """Aggregate result of a project scan."""

    project_id: uuid.UUID
    included: list[FileScanResult] = field(default_factory=list)
    skipped: list[FileScanResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def total_files(self) -> int:
        return len(self.included) + len(self.skipped)


class FileScanner:
    """Discovers files in a project root with configurable filtering."""

    def __init__(
        self,
        *,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        respect_gitignore: bool = True,
        max_file_size_bytes: int = 10_485_760,  # 10 MB
        follow_symlinks: bool = False,
        extra_exclude_patterns: list[str] | None = None,
    ) -> None:
        self.include_patterns = include_patterns or ["*"]
        self.exclude_patterns = exclude_patterns or []
        self.respect_gitignore = respect_gitignore
        self.max_file_size_bytes = max_file_size_bytes
        self.follow_symlinks = follow_symlinks
        self.extra_exclude_patterns = extra_exclude_patterns or []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan(
        self,
        project_id: uuid.UUID,
        root_path: Path,
    ) -> ScanReport:
        """Scan *root_path* and return a :class:`ScanReport`.

        Path traversal is protected via :func:`validate_project_root`.
        """
        safe_root = validate_project_root(root_path)
        report = ScanReport(project_id=project_id)

        # Load .gitignore patterns if configured.
        gitignore_patterns: list[str] = []
        if self.respect_gitignore:
            gitignore_patterns = self._load_gitignore(safe_root)

        # Walk the tree, using safe_root as both the starting point
        # and the base for relative-path computation.
        self._walk(
            current_dir=safe_root,
            base_root=safe_root,
            report=report,
            gitignore_patterns=gitignore_patterns,
        )
        return report

    # ------------------------------------------------------------------
    # Internal walk
    # ------------------------------------------------------------------

    def _walk(
        self,
        current_dir: Path,
        base_root: Path,
        report: ScanReport,
        gitignore_patterns: list[str],
    ) -> None:
        """Recursively walk *current_dir* and populate *report*.

        *base_root* is the project root used for relative-path computation;
        it stays constant across recursive calls.
        """
        try:
            entries = sorted(current_dir.iterdir())
        except OSError as exc:
            report.errors.append(f"Failed to read directory {current_dir}: {exc}")
            return

        for entry in entries:
            rel = str(entry.relative_to(base_root))

            # --- Exclude based on default / extra patterns ----------
            if self._matches_exclude(entry.name) or self._matches_extra(entry.name):
                report.skipped.append(
                    FileScanResult(
                        relative_path=rel,
                        absolute_path=entry,
                        size_bytes=0,
                        status="skipped",
                        skip_reason="Matches default or extra exclude pattern",
                    )
                )
                continue

            # --- Symlinks (checked BEFORE is_dir to avoid traversal) ---
            if entry.is_symlink():
                if not self.follow_symlinks:
                    report.skipped.append(
                        FileScanResult(
                            relative_path=rel,
                            absolute_path=entry,
                            size_bytes=0,
                            status="skipped",
                            skip_reason="Symlink (follow_symlinks=False)",
                        )
                    )
                    continue
                # When following symlinks, verify the target is safe.
                try:
                    target = canonicalize_path(entry)
                    if not is_within_root(target, base_root):
                        report.skipped.append(
                            FileScanResult(
                                relative_path=rel,
                                absolute_path=entry,
                                size_bytes=0,
                                status="skipped",
                                skip_reason="Symlink target outside project root",
                            )
                        )
                        continue
                    # Safe symlink — treat target as the effective entry.
                    entry = target
                except PathSecurityError as exc:
                    report.skipped.append(
                        FileScanResult(
                            relative_path=rel,
                            absolute_path=entry,
                            size_bytes=0,
                            status="skipped",
                            skip_reason=f"Symlink resolution failed: {exc}",
                        )
                    )
                    continue

            # --- Directories: recurse (unless gitignored) -----------
            if entry.is_dir():
                if self.respect_gitignore and self._is_gitignored(
                    rel, gitignore_patterns
                ):
                    report.skipped.append(
                        FileScanResult(
                            relative_path=rel,
                            absolute_path=entry,
                            size_bytes=0,
                            status="skipped",
                            skip_reason="Matches .gitignore pattern",
                        )
                    )
                    continue
                self._walk(entry, base_root, report, gitignore_patterns)
                continue

            # --- Regular file checks --------------------------------------
            if not entry.is_file():
                continue

            # Check .gitignore for files.
            if self.respect_gitignore and self._is_gitignored(rel, gitignore_patterns):
                report.skipped.append(
                    FileScanResult(
                        relative_path=rel,
                        absolute_path=entry,
                        size_bytes=0,
                        status="skipped",
                        skip_reason="Matches .gitignore pattern",
                    )
                )
                continue

            # Include/exclude glob matching.
            if not self._matches_include(rel):
                report.skipped.append(
                    FileScanResult(
                        relative_path=rel,
                        absolute_path=entry,
                        size_bytes=0,
                        status="skipped",
                        skip_reason="Does not match include patterns",
                    )
                )
                continue

            if self._matches_user_exclude(rel):
                report.skipped.append(
                    FileScanResult(
                        relative_path=rel,
                        absolute_path=entry,
                        size_bytes=0,
                        status="skipped",
                        skip_reason="Matches user exclude patterns",
                    )
                )
                continue

            # File size.
            try:
                size = entry.stat().st_size
            except OSError as exc:
                report.skipped.append(
                    FileScanResult(
                        relative_path=rel,
                        absolute_path=entry,
                        size_bytes=0,
                        status="skipped",
                        skip_reason=f"Unable to stat file: {exc}",
                    )
                )
                continue

            if size > self.max_file_size_bytes:
                report.skipped.append(
                    FileScanResult(
                        relative_path=rel,
                        absolute_path=entry,
                        size_bytes=size,
                        status="skipped",
                        skip_reason=(
                            f"File size {size} exceeds max {self.max_file_size_bytes}"
                        ),
                    )
                )
                continue

            # Binary detection.
            if is_binary_file(entry):
                report.skipped.append(
                    FileScanResult(
                        relative_path=rel,
                        absolute_path=entry,
                        size_bytes=size,
                        status="skipped",
                        skip_reason="Binary file detected",
                    )
                )
                continue

            # Included!
            result = FileScanResult(
                relative_path=rel,
                absolute_path=entry,
                size_bytes=size,
                status="included",
            )
            try:
                result.content_hash = result.compute_content_hash()
            except OSError as exc:
                report.skipped.append(
                    FileScanResult(
                        relative_path=rel,
                        absolute_path=entry,
                        size_bytes=size,
                        status="skipped",
                        skip_reason=f"File inaccessible during hash computation: {exc}",
                    )
                )
                continue
            report.included.append(result)

    # ------------------------------------------------------------------
    # Pattern matching helpers
    # ------------------------------------------------------------------

    def _matches_include(self, relative_path: str) -> bool:
        """True if *relative_path* matches at least one include pattern."""
        for pat in self.include_patterns:
            if fnmatch.fnmatch(relative_path, pat):
                return True
        return False

    def _matches_user_exclude(self, relative_path: str) -> bool:
        """True if *relative_path* matches any user-configured exclude."""
        for pat in self.exclude_patterns:
            if fnmatch.fnmatch(relative_path, pat):
                return True
        return False

    def _matches_exclude(self, name: str) -> bool:
        """True if the file/directory *name* matches default exclude patterns."""
        for pat in DEFAULT_EXCLUDE_PATTERNS:
            if fnmatch.fnmatch(name, pat):
                return True
        return False

    def _matches_extra(self, name: str) -> bool:
        """True if *name* matches extra (caller-supplied) exclude patterns."""
        for pat in self.extra_exclude_patterns:
            if fnmatch.fnmatch(name, pat):
                return True
        return False

    # ------------------------------------------------------------------
    # .gitignore support
    # ------------------------------------------------------------------

    @staticmethod
    def _load_gitignore(root: Path) -> list[str]:
        """Load patterns from ``.gitignore`` in *root*, if present."""
        gitignore = root / ".gitignore"
        if not gitignore.is_file():
            return []
        try:
            lines = gitignore.read_text().splitlines()
        except OSError:
            return []
        patterns: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            patterns.append(stripped)
        return patterns

    @staticmethod
    def _is_gitignored(relative_path: str, patterns: list[str]) -> bool:
        """True if *relative_path* matches any gitignore-style pattern.

        Patterns are evaluated in order; later negation patterns (``!``)
        can override earlier matches, matching real ``.gitignore`` behaviour.
        """
        ignored = False
        for pat in patterns:
            negate = pat.startswith("!")
            clean = pat[1:] if negate else pat

            matched = fnmatch.fnmatch(relative_path, clean)
            # Also match directory patterns (e.g. "build/" should match
            # "build/output/file.py" and "src/build/file.py").
            if not matched and clean.endswith("/"):
                dir_pat = clean.rstrip("/")
                parts = relative_path.split("/")
                # Check every directory component in the path, not just the first.
                for part in parts[:-1]:
                    if fnmatch.fnmatch(part, dir_pat):
                        matched = True
                        break
                # Also handle multi-segment directory patterns like "src/build/".
                if not matched and relative_path.startswith(dir_pat + "/"):
                    matched = True

            if matched:
                # Negation toggles the ignored state; a non-negated
                # pattern sets it to True.
                ignored = not negate

        return ignored

    # ------------------------------------------------------------------
    # Manifest integration
    # ------------------------------------------------------------------

    @staticmethod
    def build_manifest_entry(
        project_id: uuid.UUID,
        result: FileScanResult,
        extractor_id: str = "unknown",
        extractor_version: str = "0.1.0",
    ) -> FileManifestEntry:
        """Create a :class:`FileManifestEntry` from a :class:`FileScanResult`."""
        now = datetime.now(UTC)
        return FileManifestEntry(
            project_id=project_id,
            relative_path=result.relative_path,
            content_hash=result.content_hash or "",
            size_bytes=result.size_bytes,
            modified_at=now,
            extractor_id=extractor_id if result.status == "included" else "skipped",
            extractor_version=extractor_version,
            status=("pending" if result.status == "included" else result.status),
            skip_reason=result.skip_reason,
            last_processed_at=None,
        )
