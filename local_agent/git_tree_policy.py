"""Parse bounded Git ls-tree metadata for one pinned snapshot allowlist.

Pure parser only: it does not invoke Git, read files, or execute commands.
The caller must obtain this output from a trusted, fixed Git invocation against
an already authenticated and pinned commit.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import islice
import re
from typing import Iterable

from .snapshot_policy import SnapshotPolicyError, SnapshotLimits, _safe_path


class GitTreePolicyError(ValueError):
    """Raised when pinned Git tree metadata is malformed or unsafe."""


@dataclass(frozen=True)
class PinnedTreeObject:
    path: str
    mode: str
    object_type: str
    object_id: str
    size_bytes: int


@dataclass(frozen=True)
class PinnedTreeMetadata:
    object_format: str
    entries: tuple[PinnedTreeObject, ...]
    total_bytes: int

    @property
    def snapshot_entries(self) -> tuple[dict[str, object], ...]:
        """Return the exact metadata schema accepted by snapshot_policy."""
        return tuple(
            {
                "path": item.path,
                "mode": item.mode,
                "type": item.object_type,
                "size": item.size_bytes,
            }
            for item in self.entries
        )


def parse_ls_tree_output(
    output: bytes,
    *,
    expected_paths: Iterable[str],
    object_format: str,
    max_output_bytes: int = 2_000_000,
    max_entries: int = 500,
    max_total_bytes: int = 20_000_000,
) -> PinnedTreeMetadata:
    """Parse \`git ls-tree -r -l -z <full-commit> -- <exact-paths>\` output.

    Only regular Git blobs are accepted. Every expected path must appear
    exactly once; unexpected entries, links, submodules, trees, malformed
    records, non-UTF-8 names, case collisions and unbounded metadata fail closed.
    The caller remains responsible for authenticating the commit and ensuring
    that Git was invoked with a fixed argv, safe environment and timeout.
    """
    if not isinstance(output, bytes):
        raise GitTreePolicyError("Git tree output must be bytes")
    if not isinstance(max_output_bytes, int) or isinstance(max_output_bytes, bool) or not 1 <= max_output_bytes <= 2_000_000:
        raise GitTreePolicyError("Git tree output limit exceeds its safe bound")
    if len(output) > max_output_bytes:
        raise GitTreePolicyError("Git tree output exceeds its byte limit")
    if not isinstance(max_entries, int) or isinstance(max_entries, bool) or not 1 <= max_entries <= 500:
        raise GitTreePolicyError("Git tree entry limit exceeds its safe bound")
    if not isinstance(max_total_bytes, int) or isinstance(max_total_bytes, bool) or not 1 <= max_total_bytes <= 20_000_000:
        raise GitTreePolicyError("Git tree total size limit exceeds its safe bound")
    if object_format not in ("sha1", "sha256"):
        raise GitTreePolicyError("Git object format must be sha1 or sha256")
    oid_length = 40 if object_format == "sha1" else 64

    if isinstance(expected_paths, (str, bytes)):
        raise GitTreePolicyError("Expected paths must be a collection of exact paths")
    try:
        requested = tuple(islice(iter(expected_paths), max_entries + 1))
    except (TypeError, ValueError) as exc:
        raise GitTreePolicyError("Expected paths must be a bounded iterable") from exc
    if not requested or len(requested) > max_entries:
        raise GitTreePolicyError("Expected path count is empty or exceeds its limit")

    allowed: set[str] = set()
    folded: set[str] = set()
    for raw_path in requested:
        try:
            path = _safe_path(raw_path, SnapshotLimits())
        except SnapshotPolicyError as exc:
            raise GitTreePolicyError("Expected path is unsafe") from exc
        if path in allowed or path.casefold() in folded:
            raise GitTreePolicyError("Expected paths contain duplicates or Windows case collisions")
        allowed.add(path)
        folded.add(path.casefold())

    if not output:
        raise GitTreePolicyError("Git tree output is empty")
    if not output.endswith(b"\0"):
        raise GitTreePolicyError("Git tree output is missing its final NUL delimiter")

    records = output[:-1].split(b"\0")
    if len(records) != len(allowed) or len(records) > max_entries:
        raise GitTreePolicyError("Git tree entry count does not match the exact allowlist")

    parsed: dict[str, PinnedTreeObject] = {}
    folded_seen: set[str] = set()
    total = 0
    for record in records:
        if not record or b"\t" not in record:
            raise GitTreePolicyError("Git tree record is malformed")
        header, raw_path = record.split(b"\t", 1)
        try:
            mode_b, type_b, oid_b, size_b = header.split(b" ")
            path = raw_path.decode("utf-8", errors="strict")
            mode = mode_b.decode("ascii")
            object_type = type_b.decode("ascii")
            object_id = oid_b.decode("ascii")
            size_text = size_b.decode("ascii")
        except (ValueError, UnicodeDecodeError) as exc:
            raise GitTreePolicyError("Git tree record has invalid fields or encoding") from exc

        try:
            path = _safe_path(path, SnapshotLimits())
        except SnapshotPolicyError as exc:
            raise GitTreePolicyError("Git tree contains an unsafe path") from exc
        if mode not in ("100644", "100755") or object_type != "blob":
            raise GitTreePolicyError("Only regular Git file blobs are accepted")
        if not re.fullmatch(rf"[0-9a-f]{{{oid_length}}}", object_id):
            raise GitTreePolicyError("Git tree object ID does not match repository object format")
        if not re.fullmatch(r"(?:0|[1-9][0-9]*)", size_text):
            raise GitTreePolicyError("Git tree blob size is malformed")
        size = int(size_text)
        if size > 2_000_000:
            raise GitTreePolicyError("Git tree file exceeds the per-file size limit")
        if path not in allowed:
            raise GitTreePolicyError("Git tree contains a path outside the exact allowlist")
        if path in parsed or path.casefold() in folded_seen:
            raise GitTreePolicyError("Git tree contains duplicate or Windows case-colliding paths")
        parsed[path] = PinnedTreeObject(path, mode, object_type, object_id, size)
        folded_seen.add(path.casefold())
        total += size
        if total > max_total_bytes:
            raise GitTreePolicyError("Git tree total file size exceeds its limit")

    if set(parsed) != allowed:
        raise GitTreePolicyError("Git tree is missing one or more expected paths")
    ordered = tuple(parsed[path] for path in sorted(parsed))
    return PinnedTreeMetadata(object_format, ordered, total)
