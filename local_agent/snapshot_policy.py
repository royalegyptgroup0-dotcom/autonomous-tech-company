"""Validate a pinned Git-tree manifest before a disposable snapshot is built.

Planning-only: no Git, filesystem reads/writes, archive extraction, copying,
or command execution. Input must come from trusted inspection of one pinned commit.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Iterable, Mapping


class SnapshotPolicyError(ValueError):
    """Raised when a candidate snapshot manifest violates policy."""


@dataclass(frozen=True)
class SnapshotLimits:
    max_entries: int = 500
    max_file_bytes: int = 2_000_000
    max_total_bytes: int = 20_000_000
    max_path_length: int = 240


@dataclass(frozen=True)
class SnapshotEntry:
    path: str
    mode: str
    object_type: str
    size_bytes: int


@dataclass(frozen=True)
class SnapshotManifest:
    commit: str
    entries: tuple[SnapshotEntry, ...]
    total_bytes: int
    sha256: str


_BLOCKED_COMPONENTS = {
    ".git", ".ssh", ".aws", ".azure", ".config", ".npm", ".cache",
    ".venv", "venv", "node_modules", "__pycache__", "credentials",
    "secrets", "private", "certs", "certificates",
}
_BLOCKED_FILES = {
    ".env", ".env.local", ".env.production", ".netrc", ".npmrc",
    ".pypirc", ".gitconfig", ".git-credentials", "id_rsa",
    "id_ed25519", "known_hosts", "credentials.json",
}
_BLOCKED_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".jks", ".keystore")
_RESERVED = re.compile(
    r"^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]|COM[¹²³]|LPT[¹²³])(?:\..*)?$",
    re.IGNORECASE,
)
_SHA = re.compile(r"^[0-9a-f]{40,64}$")


def _safe_path(path: object, limits: SnapshotLimits) -> str:
    if not isinstance(path, str) or not path or len(path) > limits.max_path_length:
        raise SnapshotPolicyError("Snapshot path is empty or exceeds the path limit")
    if (
        path.startswith(("/", "~")) or "\\" in path or ":" in path
        or any(ord(ch) < 32 or ord(ch) == 127 for ch in path)
        or any(ch.isspace() for ch in path) or "//" in path or path.endswith("/")
    ):
        raise SnapshotPolicyError(f"Unsafe or ambiguous snapshot path: {path!r}")
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise SnapshotPolicyError(f"Non-canonical or traversing snapshot path: {path!r}")
    for part in parts:
        folded = part.casefold()
        if _RESERVED.fullmatch(part):
            raise SnapshotPolicyError("Windows reserved device names are not allowed")
        if (
            folded in _BLOCKED_COMPONENTS or folded in _BLOCKED_FILES
            or folded.startswith(".env") or folded.endswith(_BLOCKED_SUFFIXES)
        ):
            raise SnapshotPolicyError(f"Protected snapshot path: {path!r}")
    return path


def _normalise_allowlist(allowed_paths: Iterable[str], limits: SnapshotLimits) -> set[str]:
    if isinstance(allowed_paths, (str, bytes)):
        raise SnapshotPolicyError("allowed_paths must be a collection of exact paths")
    try:
        items = list(allowed_paths)
    except (TypeError, ValueError) as exc:
        raise SnapshotPolicyError("allowed_paths must be iterable") from exc
    if not items or len(items) > limits.max_entries:
        raise SnapshotPolicyError("Exact snapshot allowlist must be non-empty and bounded")
    result: set[str] = set()
    folded: set[str] = set()
    for item in items:
        path = _safe_path(item, limits)
        if path in result or path.casefold() in folded:
            raise SnapshotPolicyError("Duplicate or Windows case-colliding allowlist path")
        result.add(path)
        folded.add(path.casefold())
    return result


def validate_snapshot_manifest(
    *, commit: str, tree_entries: Iterable[Mapping[str, object]],
    allowed_paths: Iterable[str], limits: SnapshotLimits = SnapshotLimits(),
) -> SnapshotManifest:
    """Validate pinned-tree metadata against an exact local file allowlist.

    Each entry has exactly path, mode, type and size. Only regular Git blobs
    (100644/100755) are accepted. Every allowlisted path must exist exactly once.
    """
    if not isinstance(limits, SnapshotLimits):
        raise SnapshotPolicyError("limits must be a SnapshotLimits value")
    defaults = SnapshotLimits()
    for field in ("max_entries", "max_file_bytes", "max_total_bytes", "max_path_length"):
        value = getattr(limits, field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1 or value > getattr(defaults, field):
            raise SnapshotPolicyError(f"{field} must be within its safe default")
    if not isinstance(commit, str) or not _SHA.fullmatch(commit):
        raise SnapshotPolicyError("A full pinned Git object ID is required")
    allowed = _normalise_allowlist(allowed_paths, limits)
    if isinstance(tree_entries, (str, bytes)):
        raise SnapshotPolicyError("tree_entries must be structured metadata")
    try:
        raw_entries = list(tree_entries)
    except (TypeError, ValueError) as exc:
        raise SnapshotPolicyError("tree_entries must be iterable") from exc
    if not raw_entries or len(raw_entries) > limits.max_entries:
        raise SnapshotPolicyError("Pinned tree entry count is empty or exceeds the limit")

    accepted: dict[str, SnapshotEntry] = {}
    folded_paths: dict[str, str] = {}
    total = 0
    for raw in raw_entries:
        if not isinstance(raw, Mapping) or set(raw) != {"path", "mode", "type", "size"}:
            raise SnapshotPolicyError("Each tree entry must use the exact metadata schema")
        path = _safe_path(raw["path"], limits)
        mode, object_type, size = raw["mode"], raw["type"], raw["size"]
        if mode not in ("100644", "100755") or object_type != "blob":
            raise SnapshotPolicyError("Only regular Git file blobs may enter a snapshot")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise SnapshotPolicyError("File size must be a non-negative integer")
        if size > limits.max_file_bytes:
            raise SnapshotPolicyError(f"Snapshot file exceeds per-file limit: {path}")
        if path not in allowed:
            raise SnapshotPolicyError(f"Tree contains a path outside the exact allowlist: {path}")
        if path in accepted:
            raise SnapshotPolicyError(f"Duplicate tree path: {path}")
        folded = path.casefold()
        if folded in folded_paths and folded_paths[folded] != path:
            raise SnapshotPolicyError("Tree contains Windows case-colliding paths")
        folded_paths[folded] = path
        total += size
        if total > limits.max_total_bytes:
            raise SnapshotPolicyError("Snapshot total byte limit exceeded")
        accepted[path] = SnapshotEntry(path, mode, object_type, size)

    if allowed.difference(accepted):
        raise SnapshotPolicyError("Allowlisted paths are missing from the pinned tree")
    ordered = tuple(accepted[path] for path in sorted(accepted))
    canonical = {
        "commit": commit,
        "entries": [
            {"path": item.path, "mode": item.mode, "type": item.object_type, "size": item.size_bytes}
            for item in ordered
        ],
        "total_bytes": total,
    }
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return SnapshotManifest(commit, ordered, total, digest)
