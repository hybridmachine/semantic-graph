"""Path security and file validation utilities.

Provides canonicalization, path-traversal protection, symlink safety,
and binary-file detection used by the file scanner and API layers.
"""

from __future__ import annotations

from pathlib import Path

from semantic_graph.utils.errors import PathSecurityError, PathTraversalError

# Default directory patterns excluded from file scanning.
DEFAULT_EXCLUDE_PATTERNS: list[str] = [
    ".git",
    "node_modules",
    ".venv",
    "__pycache__",
    "dist",
    "build",
]


def canonicalize_path(path: Path) -> Path:
    """Return the absolute, canonical form of *path*.

    Resolves symlinks and normalises ``..`` and ``.`` components.
    The path does **not** need to exist on disk — only the longest
    existing prefix is resolved; remaining components are appended as-is.

    Raises :exc:`PathSecurityError` if resolution fails (e.g. permission
    denied on an intermediate directory).
    """
    try:
        resolved = path.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise PathSecurityError(
            f"Failed to resolve path {path!s}: {exc}"
        ) from exc
    return resolved


def is_within_root(path: Path, root: Path) -> bool:
    """Return *True* if *path* is inside *root*.

    Both arguments are canonicalised before comparison.  The check uses
    ``Path.is_relative_to`` (Python ≥ 3.9) so that the root itself is
    considered to be within itself.
    """
    try:
        canon_path = canonicalize_path(path)
        canon_root = canonicalize_path(root)
    except PathSecurityError:
        return False
    return canon_path.is_relative_to(canon_root)


def validate_safe_path(path: Path, root: Path) -> Path:
    """Canonicalise *path* and verify it lies within *root*.

    Returns the canonical absolute path on success.

    Raises:
        PathTraversalError: If the resolved path escapes *root*.
        PathSecurityError: If the path cannot be resolved.
    """
    canon_path = canonicalize_path(path)
    canon_root = canonicalize_path(root)

    if not canon_path.is_relative_to(canon_root):
        raise PathTraversalError(
            f"Path {path!s} resolves to {canon_path!s}, which is outside "
            f"the project root {canon_root!s}"
        )
    return canon_path


def is_binary_file(path: Path, sample_size: int = 8192) -> bool:
    """Return *True* if *path* appears to be a binary file.

    Reads the first *sample_size* bytes and looks for a null byte.
    Returns *False* for empty files (they are treated as text).
    """
    try:
        with path.open("rb") as fh:
            chunk = fh.read(sample_size)
    except (OSError, PermissionError):
        # Unreadable files are treated as binary to skip them safely.
        return True

    if not chunk:
        return False
    return b"\x00" in chunk


def validate_project_root(root_path: Path) -> Path:
    """Validate that *root_path* is suitable for use as a project root.

    Returns the canonical form of *root_path*.

    Raises:
        PathSecurityError: If the path does not exist, is not a directory,
            or appears to be a protected system directory.
    """
    canon = canonicalize_path(root_path)

    if not canon.exists():
        raise PathSecurityError(f"Project root does not exist: {canon}")
    if not canon.is_dir():
        raise PathSecurityError(f"Project root is not a directory: {canon}")

    # Reject well-known system directories as a safety measure.
    # Check the POSIX string so that symlinked system directories
    # (e.g. /etc → /private/etc on macOS) are still caught.
    protected_paths = {"/", "/etc", "/sys", "/proc", "/dev"}
    if canon.as_posix() in protected_paths or root_path.as_posix() in protected_paths:
        raise PathSecurityError(
            f"Project root cannot be a system directory: {canon}"
        )

    return canon
