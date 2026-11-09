"""Filesystem-only checks for a disposable Git worktree.

This module does not create worktrees, invoke Git, write files, or apply patches.
It validates an already-created candidate directory before a future stage may
consider it. Callers must separately verify the pinned commit and clean Git state.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import stat
from typing import Iterable


class WorktreePolicyError(ValueError):
    """Raised when a candidate worktree violates the filesystem policy."""


@dataclass(frozen=True)
class WorktreeCheck:
    root: Path
    source_checkout: Path
    checked_paths: tuple[str, ...]


def _absolute_without_symlinks(path: Path) -> Path:
    candidate = Path(os.path.abspath(os.fspath(path)))
    anchor = Path(candidate.anchor)
    current = anchor
    for part in candidate.parts[1:]:
        current = current / part
        try:
            mode = current.lstat().st_mode
        except OSError as exc:
            raise WorktreePolicyError(f"Path component is missing or inaccessible: {current}") from exc
        if stat.S_ISLNK(mode):
            raise WorktreePolicyError(f"Symlink path component is not allowed: {current}")
    if not candidate.is_dir():
        raise WorktreePolicyError("Worktree and source checkout paths must be directories")
    return candidate


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_disposable_worktree(
    worktree_root: str | os.PathLike[str],
    source_checkout: str | os.PathLike[str],
    *,
    allowed_paths: Iterable[str],
) -> WorktreeCheck:
    """Validate separation and regular-file targets in an existing worktree.

    This is a fail-closed preflight only, not proof of a clean Git state,
    correct HEAD, or safe concurrent use. Those checks belong to the runner.
    """
    if isinstance(allowed_paths, (str, bytes)):
        raise WorktreePolicyError("allowed_paths must be a collection of relative paths")
    try:
        root = _absolute_without_symlinks(Path(worktree_root))
        source = _absolute_without_symlinks(Path(source_checkout))
    except TypeError as exc:
        raise WorktreePolicyError("Worktree paths must be path-like values") from exc

    if root == source or _is_within(root, source) or _is_within(source, root):
        raise WorktreePolicyError("Disposable worktree and source checkout must be separate sibling trees")

    checked: list[str] = []
    for raw in allowed_paths:
        if not isinstance(raw, str) or not raw or raw.startswith(("/", "\\")) or "\\" in raw:
            raise WorktreePolicyError("Target paths must be non-empty relative POSIX paths")
        parts = raw.split("/")
        if any(part in ("", ".", "..") for part in parts) or ":" in raw:
            raise WorktreePolicyError(f"Non-canonical target path: {raw!r}")
        current = root
        for part in parts:
            current = current / part
            try:
                mode = current.lstat().st_mode
            except OSError as exc:
                raise WorktreePolicyError(f"Target path is missing or inaccessible: {raw!r}") from exc
            if stat.S_ISLNK(mode):
                raise WorktreePolicyError(f"Symlink target is not allowed: {raw!r}")
        if not stat.S_ISREG(mode):
            raise WorktreePolicyError(f"Target must be an existing regular file: {raw!r}")
        checked.append(raw)

    if not checked:
        raise WorktreePolicyError("At least one exact target path is required")
    return WorktreeCheck(root=root, source_checkout=source, checked_paths=tuple(checked))
