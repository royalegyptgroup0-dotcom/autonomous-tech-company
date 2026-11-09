"""Verify streamed file content against independently obtained Git blob IDs.

Pure streaming verification only: no Git invocation, filesystem access, extraction,
or process execution. Expected object IDs must come from trusted pinned-tree data.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import BinaryIO

from .snapshot_policy import SnapshotLimits, SnapshotPolicyError, _safe_path


class GitBlobPolicyError(ValueError):
    """Raised when streamed content does not match trusted Git blob metadata."""


@dataclass(frozen=True)
class GitBlobVerification:
    path: str
    size_bytes: int
    object_format: str
    git_object_id: str
    sha256: str
    bytes_read: int


def verify_git_blob_stream(
    source: BinaryIO,
    *,
    path: str,
    expected_size: int,
    expected_git_oid: str,
    expected_sha256: str,
    object_format: str,
    max_chunk_bytes: int = 65_536,
    max_file_bytes: int = 2_000_000,
) -> GitBlobVerification:
    """Hash one bounded stream as both raw content and a Git blob object.

    Git blob IDs hash the exact header blob <size> followed by a NUL byte
    and then the content. The caller supplies the expected blob ID from
    independently inspected pinned-tree data and the archive SHA-256 digest.
    """
    try:
        safe_path = _safe_path(path, SnapshotLimits())
    except SnapshotPolicyError as exc:
        raise GitBlobPolicyError("Unsafe Git blob path") from exc

    if object_format not in ("sha1", "sha256"):
        raise GitBlobPolicyError("Git object format must be sha1 or sha256")
    oid_length = 40 if object_format == "sha1" else 64
    if not isinstance(expected_git_oid, str) or not re.fullmatch(
        rf"[0-9a-f]{{{oid_length}}}", expected_git_oid
    ):
        raise GitBlobPolicyError("Git blob object ID does not match repository object format")
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise GitBlobPolicyError("Expected archive SHA-256 must be a full lowercase digest")
    for name, value, upper in (
        ("expected_size", expected_size, max_file_bytes),
        ("max_chunk_bytes", max_chunk_bytes, 65_536),
        ("max_file_bytes", max_file_bytes, 2_000_000),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value < 1 or value > upper:
            raise GitBlobPolicyError(f"{name} is outside its safe bound")
    if expected_size > max_file_bytes:
        raise GitBlobPolicyError("Git blob exceeds the configured file-size limit")
    if not hasattr(source, "read") or not callable(source.read):
        raise GitBlobPolicyError("A readable binary stream is required")

    git_hash = hashlib.new(object_format)
    content_hash = hashlib.sha256()
    git_hash.update(f"blob {expected_size}\\0".encode("ascii"))
    remaining = expected_size
    while remaining:
        chunk = source.read(min(max_chunk_bytes, remaining))
        if not isinstance(chunk, bytes):
            raise GitBlobPolicyError("Git blob source must return bytes")
        if not chunk:
            raise GitBlobPolicyError("Git blob stream ended before its declared size")
        if len(chunk) > remaining:
            raise GitBlobPolicyError("Git blob stream exceeded its declared size")
        git_hash.update(chunk)
        content_hash.update(chunk)
        remaining -= len(chunk)

    extra = source.read(1)
    if not isinstance(extra, bytes):
        raise GitBlobPolicyError("Git blob source must return bytes")
    if extra:
        raise GitBlobPolicyError("Git blob stream contains bytes beyond its declared size")

    actual_oid = git_hash.hexdigest()
    actual_sha256 = content_hash.hexdigest()
    if actual_oid != expected_git_oid:
        raise GitBlobPolicyError("Git blob object ID does not match pinned tree metadata")
    if actual_sha256 != expected_sha256:
        raise GitBlobPolicyError("Git blob content does not match inspected archive SHA-256")

    return GitBlobVerification(
        path=safe_path,
        size_bytes=expected_size,
        object_format=object_format,
        git_object_id=actual_oid,
        sha256=actual_sha256,
        bytes_read=expected_size,
    )
