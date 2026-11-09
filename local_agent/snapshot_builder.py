"""Build and remove uniquely-owned disposable snapshots from verified Git blobs.

This is a filesystem-writing primitive only. It does not launch Sandbox,
execute validation commands, apply patches, or connect to the local agent runner.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
import tempfile
from typing import Iterable

from .git_acquisition import GitAcquisitionResult, VerifiedBlobContent
from .snapshot_policy import SnapshotLimits, _safe_path


class SnapshotBuildError(ValueError):
    """Raised when a disposable snapshot cannot be built or safely removed."""


_MARKER = ".agent-snapshot-owner.json"
_MARKER_VERSION = 1
_REPARSE_ATTRIBUTE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


@dataclass(frozen=True)
class SnapshotBuildResult:
    """Ownership receipt required for later cleanup of one created snapshot."""
    path: Path
    commit: str
    manifest_sha256: str
    owner_token: str
    files: tuple[str, ...]


def _is_reparse_or_link(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & _REPARSE_ATTRIBUTE)


def _existing_directory(path: str | os.PathLike[str], label: str) -> Path:
    raw = Path(path)
    if not raw.is_absolute():
        raise SnapshotBuildError(f"{label} must be an absolute path")
    if any(part in (".", "..") for part in raw.parts[1:]):
        raise SnapshotBuildError(f"{label} contains a non-canonical path component")
    current = Path(raw.anchor)
    for part in raw.parts[1:]:
        current = current / part
        try:
            if _is_reparse_or_link(current):
                raise SnapshotBuildError(f"{label} contains a symlink or reparse point")
            info = current.lstat()
        except FileNotFoundError as exc:
            raise SnapshotBuildError(f"{label} does not exist") from exc
        if not stat.S_ISDIR(info.st_mode):
            raise SnapshotBuildError(f"{label} contains a non-directory component")
    return raw


def _disjoint(left: Path, right: Path) -> bool:
    try:
        left.relative_to(right)
        return False
    except ValueError:
        pass
    try:
        right.relative_to(left)
        return False
    except ValueError:
        return True


def _verified_payload(acquisition: GitAcquisitionResult) -> tuple[str, str, tuple[VerifiedBlobContent, ...]]:
    if not isinstance(acquisition, GitAcquisitionResult):
        raise SnapshotBuildError("A completed trusted Git acquisition result is required")
    tree = acquisition.tree
    commit = getattr(acquisition, "pinned_commit", None)
    manifest_sha256 = getattr(acquisition, "manifest_sha256", None)
    if not isinstance(commit, str) or len(commit) not in (40, 64) or any(c not in "0123456789abcdef" for c in commit):
        raise SnapshotBuildError("Acquisition result has no full pinned commit")
    if not isinstance(manifest_sha256, str) or len(manifest_sha256) != 64 or any(c not in "0123456789abcdef" for c in manifest_sha256):
        raise SnapshotBuildError("Acquisition result has no validated manifest digest")
    blobs = getattr(acquisition, "blob_contents", None)
    verifications = getattr(acquisition, "blob_verifications", None)
    entries = getattr(tree, "entries", None)
    if not isinstance(blobs, tuple) or not isinstance(verifications, tuple) or not isinstance(entries, tuple):
        raise SnapshotBuildError("Acquisition result is missing immutable verified content")
    if not 1 <= len(entries) <= 500 or len(blobs) != len(entries) or len(verifications) != len(entries):
        raise SnapshotBuildError("Verified content does not exactly match the pinned tree")
    by_path: dict[str, VerifiedBlobContent] = {}
    verify_by_path = {item.path: item for item in verifications}
    if len(verify_by_path) != len(verifications) or set(verify_by_path) != {item.path for item in entries}:
        raise SnapshotBuildError("Git verification records do not exactly match the pinned tree")
    if getattr(tree, "object_format", None) not in ("sha1", "sha256"):
        raise SnapshotBuildError("Pinned tree object format is invalid")
    total = 0
    for blob in blobs:
        if not isinstance(blob, VerifiedBlobContent):
            raise SnapshotBuildError("Invalid verified blob content record")
        path = _safe_path(blob.path, SnapshotLimits())
        if path != blob.path or path in by_path or not isinstance(blob.content, bytes):
            raise SnapshotBuildError("Blob path or content is invalid")
        if not isinstance(blob.size_bytes, int) or isinstance(blob.size_bytes, bool) or blob.size_bytes != len(blob.content) or blob.size_bytes > 2_000_000:
            raise SnapshotBuildError("Blob content size is invalid")
        if blob.object_format not in ("sha1", "sha256") or blob.object_format != tree.object_format:
            raise SnapshotBuildError("Blob Git object format is invalid")
        git_hash = hashlib.new(blob.object_format)
        git_hash.update(f"blob {blob.size_bytes}".encode("ascii") + bytes((0,)))
        git_hash.update(blob.content)
        actual_oid = git_hash.hexdigest()
        actual_sha = hashlib.sha256(blob.content).hexdigest()
        if actual_oid != blob.git_object_id or actual_sha != blob.sha256:
            raise SnapshotBuildError(f"Blob content failed independent digest verification: {path}")
        verified = verify_by_path.get(path)
        if verified is None or verified.git_object_id != actual_oid or verified.sha256 != actual_sha or verified.size_bytes != blob.size_bytes:
            raise SnapshotBuildError(f"Blob does not match its Git verification record: {path}")
        by_path[path] = blob
        total += blob.size_bytes
        if total > 20_000_000:
            raise SnapshotBuildError("Verified content exceeds the total snapshot size limit")
    tree_by_path = {item.path: item for item in entries}
    if len(tree_by_path) != len(entries) or set(tree_by_path) != set(by_path):
        raise SnapshotBuildError("Verified content paths differ from the pinned Git tree")
    if total != getattr(tree, "total_bytes", None):
        raise SnapshotBuildError("Verified content total differs from pinned tree metadata")
    for path, entry in tree_by_path.items():
        blob = by_path[path]
        if entry.object_id != blob.git_object_id or entry.size_bytes != blob.size_bytes:
            raise SnapshotBuildError(f"Blob does not match pinned tree metadata: {path}")
    ordered = tuple(by_path[path] for path in sorted(by_path))
    return commit, manifest_sha256, ordered


def _write_exclusive(path: Path, content: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    digest = hashlib.sha256()
    written = 0
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            view = memoryview(content)
            for offset in range(0, len(view), 65_536):
                chunk = view[offset:offset + 65_536]
                count = stream.write(chunk)
                if count != len(chunk):
                    raise SnapshotBuildError("Short write while creating snapshot file")
                digest.update(chunk)
                written += count
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        raise
    if written != len(content) or digest.digest() != hashlib.sha256(content).digest():
        raise SnapshotBuildError("Written snapshot file failed size or digest verification")


def _marker_payload(token: str, commit: str, manifest_sha256: str, files: tuple[str, ...]) -> bytes:
    data = {
        "version": _MARKER_VERSION,
        "owner_token": token,
        "commit": commit,
        "manifest_sha256": manifest_sha256,
        "files": list(files),
    }
    return (json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def build_disposable_snapshot(
    acquisition: GitAcquisitionResult,
    *,
    validation_parent: str | os.PathLike[str],
    source_checkout: str | os.PathLike[str],
) -> SnapshotBuildResult:
    """Write verified blobs beneath an existing dedicated temp parent.

    The source checkout is never mapped or modified. The caller must provide
    an existing validation parent disjoint from the source checkout.
    """
    commit, manifest_sha256, blobs = _verified_payload(acquisition)
    parent = _existing_directory(validation_parent, "Validation parent")
    source = _existing_directory(source_checkout, "Source checkout")
    if not _disjoint(parent, source):
        raise SnapshotBuildError("Validation parent must be disjoint from the source checkout")
    token = secrets.token_hex(32)
    files = tuple(blob.path for blob in blobs)
    root = Path(tempfile.mkdtemp(prefix=".agent-validation-", dir=parent))
    marker = root / _MARKER
    marker_bytes = _marker_payload(token, commit, manifest_sha256, files)
    try:
        _write_exclusive(marker, marker_bytes)
        expected_dirs: set[str] = set()
        for blob in blobs:
            parts = blob.path.split("/")
            current = root
            for part in parts[:-1]:
                current = current / part
                if not current.exists():
                    current.mkdir()
                if _is_reparse_or_link(current) or not current.is_dir():
                    raise SnapshotBuildError("Snapshot path contains a symlink or non-directory")
                expected_dirs.add(current.relative_to(root).as_posix())
            target = current / parts[-1]
            if target.exists() or target.is_symlink():
                raise SnapshotBuildError("Snapshot target unexpectedly exists")
            _write_exclusive(target, blob.content)
        # Reconcile the exact directory tree without following links.
        expected_files = set(files) | {_MARKER}
        found_files: set[str] = set()
        found_dirs: set[str] = set()
        for current, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
            base = Path(current)
            for name in list(dirnames):
                item = base / name
                if _is_reparse_or_link(item) or not item.is_dir():
                    raise SnapshotBuildError("Snapshot contains a link or non-directory")
                found_dirs.add(item.relative_to(root).as_posix())
            for name in filenames:
                item = base / name
                if _is_reparse_or_link(item) or not item.is_file():
                    raise SnapshotBuildError("Snapshot contains a link or non-regular file")
                found_files.add(item.relative_to(root).as_posix())
        if found_files != expected_files or found_dirs != expected_dirs:
            raise SnapshotBuildError("Created snapshot does not match its exact manifest")
        return SnapshotBuildResult(root, commit, manifest_sha256, token, files)
    except Exception:
        # Only attempt cleanup after our exclusive ownership marker exists.
        if marker.exists():
            try:
                _remove_owned(root, token, commit, manifest_sha256, files)
            except Exception:
                pass
        raise


def _remove_owned(root: Path, token: str, commit: str, manifest_sha256: str, files: tuple[str, ...]) -> None:
    if _is_reparse_or_link(root) or not root.is_dir():
        raise SnapshotBuildError("Owned snapshot root is no longer a regular directory")
    marker = root / _MARKER
    if _is_reparse_or_link(marker) or not marker.is_file():
        raise SnapshotBuildError("Snapshot ownership marker is missing or unsafe")
    try:
        actual = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SnapshotBuildError("Snapshot ownership marker cannot be read") from exc
    expected = json.loads(_marker_payload(token, commit, manifest_sha256, files))
    if actual != expected:
        raise SnapshotBuildError("Snapshot ownership marker does not match the cleanup receipt")
    expected_files = set(files) | {_MARKER}
    expected_dirs: set[str] = set()
    for path in files:
        parts = path.split("/")
        for index in range(1, len(parts)):
            expected_dirs.add("/".join(parts[:index]))
    found_files: set[str] = set()
    found_dirs: set[str] = set()
    for current, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        base = Path(current)
        for name in dirnames:
            item = base / name
            if _is_reparse_or_link(item) or not item.is_dir():
                raise SnapshotBuildError("Refusing cleanup: unexpected link or directory")
            found_dirs.add(item.relative_to(root).as_posix())
        for name in filenames:
            item = base / name
            if _is_reparse_or_link(item) or not item.is_file():
                raise SnapshotBuildError("Refusing cleanup: unexpected link or file")
            found_files.add(item.relative_to(root).as_posix())
    if found_files != expected_files or found_dirs != expected_dirs:
        raise SnapshotBuildError("Refusing cleanup: snapshot contains unexpected entries")
    for relative in sorted(expected_files - {_MARKER}, key=lambda value: value.count("/"), reverse=True):
        (root / Path(*relative.split("/"))).unlink()
    marker.unlink()
    for relative in sorted(expected_dirs, key=lambda value: value.count("/"), reverse=True):
        (root / Path(*relative.split("/"))).rmdir()
    root.rmdir()


def cleanup_disposable_snapshot(result: SnapshotBuildResult) -> None:
    """Remove only the exact tree proven by the unique ownership receipt."""
    if not isinstance(result, SnapshotBuildResult):
        raise SnapshotBuildError("A snapshot ownership receipt is required")
    root = Path(result.path)
    if (not root.is_absolute() or not isinstance(result.owner_token, str) or len(result.owner_token) != 64
            or any(char not in "0123456789abcdef" for char in result.owner_token) or not isinstance(result.files, tuple)):
        raise SnapshotBuildError("Snapshot ownership receipt is invalid")
    if not isinstance(result.commit, str) or len(result.commit) not in (40, 64):
        raise SnapshotBuildError("Snapshot ownership commit is invalid")
    if not isinstance(result.manifest_sha256, str) or len(result.manifest_sha256) != 64:
        raise SnapshotBuildError("Snapshot ownership manifest digest is invalid")
    if not 1 <= len(result.files) <= 500 or len(set(result.files)) != len(result.files):
        raise SnapshotBuildError("Snapshot ownership receipt file list is invalid")
    if any(_safe_path(path, SnapshotLimits()) != path for path in result.files):
        raise SnapshotBuildError("Snapshot ownership receipt contains an unsafe path")
    if any(char not in "0123456789abcdef" for char in result.commit):
        raise SnapshotBuildError("Snapshot ownership commit is invalid")
    if any(char not in "0123456789abcdef" for char in result.manifest_sha256):
        raise SnapshotBuildError("Snapshot ownership manifest digest is invalid")
    _remove_owned(root, result.owner_token, result.commit, result.manifest_sha256, result.files)
