"""Bounded, read-only inspection of a tar snapshot against a pinned manifest.

No extraction, filesystem writes, Git invocation, or process execution occurs.
Only uncompressed tar streams containing regular files and expected parent
directories are accepted. This is an inspection primitive, not a snapshot builder.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import tarfile
from typing import BinaryIO

from .snapshot_policy import SnapshotManifest, SnapshotPolicyError, _safe_path


class ArchivePolicyError(ValueError):
    """Raised when an archive cannot be reconciled with its expected manifest."""


@dataclass(frozen=True)
class ArchiveLimits:
    max_archive_bytes: int = 32_000_000
    max_chunk_bytes: int = 65_536


@dataclass(frozen=True)
class ArchiveFileDigest:
    path: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class ArchiveInspection:
    commit: str
    manifest_sha256: str
    bytes_read: int
    total_file_bytes: int
    files: tuple[ArchiveFileDigest, ...]


class _BoundedReader:
    """Read-only adapter that caps bytes consumed from the supplied stream."""

    def __init__(self, source: BinaryIO, maximum: int) -> None:
        self._source = source
        self._maximum = maximum
        self.bytes_read = 0

    def read(self, size: int = -1) -> bytes:
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ArchivePolicyError("Archive reader requires bounded positive read sizes")
        if size == 0:
            return b""
        remaining = self._maximum - self.bytes_read
        if remaining <= 0:
            probe = self._source.read(1)
            if probe:
                raise ArchivePolicyError("Archive byte limit exceeded")
            return b""
        data = self._source.read(min(size, remaining + 1))
        if not isinstance(data, bytes):
            raise ArchivePolicyError("Archive source must be a binary stream")
        if len(data) > remaining:
            raise ArchivePolicyError("Archive byte limit exceeded")
        self.bytes_read += len(data)
        return data


def _expected_directories(paths: set[str]) -> set[str]:
    directories: set[str] = set()
    for path in paths:
        parts = path.split("/")
        for index in range(1, len(parts)):
            directories.add("/".join(parts[:index]))
    return directories


def inspect_tar_stream(
    source: BinaryIO,
    manifest: SnapshotManifest,
    *,
    limits: ArchiveLimits = ArchiveLimits(),
) -> ArchiveInspection:
    """Inspect and hash a tar stream without extracting or writing any files.

    The archive must contain exactly the manifest's regular files, plus only
    their required parent directories. Symlinks, hardlinks, devices, sparse
    entries, PAX metadata, unexpected paths, duplicate members and compressed
    archives are rejected. Content SHA-256 values are returned for later
    comparison with independently obtained Git blob contents.
    """
    if not isinstance(manifest, SnapshotManifest) or not manifest.entries:
        raise ArchivePolicyError("A non-empty validated snapshot manifest is required")
    if not isinstance(limits, ArchiveLimits):
        raise ArchivePolicyError("limits must be an ArchiveLimits value")
    if (
        not isinstance(limits.max_archive_bytes, int)
        or isinstance(limits.max_archive_bytes, bool)
        or not 1 <= limits.max_archive_bytes <= 32_000_000
        or not isinstance(limits.max_chunk_bytes, int)
        or isinstance(limits.max_chunk_bytes, bool)
        or not 1 <= limits.max_chunk_bytes <= 65_536
    ):
        raise ArchivePolicyError("Archive limits exceed safe defaults")

    expected = {entry.path: entry for entry in manifest.entries}
    if len(expected) != len(manifest.entries):
        raise ArchivePolicyError("Manifest contains duplicate paths")
    expected_dirs = _expected_directories(set(expected))
    seen_files: set[str] = set()
    seen_dirs: set[str] = set()
    digests: list[ArchiveFileDigest] = []
    total = 0
    reader = _BoundedReader(source, limits.max_archive_bytes)

    try:
        with tarfile.open(fileobj=reader, mode="r|") as archive:
            for member in archive:
                if member.pax_headers or archive.pax_headers:
                    raise ArchivePolicyError("PAX metadata is not accepted")
                name = member.name
                is_dir = member.type == tarfile.DIRTYPE
                if is_dir and name.endswith("/"):
                    name = name[:-1]
                try:
                    path = _safe_path(name, _manifest_path_limits())
                except SnapshotPolicyError as exc:
                    raise ArchivePolicyError(f"Unsafe archive member path: {name!r}") from exc

                if is_dir:
                    if member.size != 0 or path not in expected_dirs or path in seen_dirs:
                        raise ArchivePolicyError("Unexpected, duplicate or malformed directory entry")
                    seen_dirs.add(path)
                    continue

                if member.type not in (tarfile.REGTYPE, tarfile.AREGTYPE):
                    raise ArchivePolicyError("Only regular archive files are accepted")
                if path not in expected or path in seen_files:
                    raise ArchivePolicyError("Unexpected or duplicate archive file")
                expected_entry = expected[path]
                if member.size != expected_entry.size_bytes:
                    raise ArchivePolicyError(f"Archive size does not match manifest: {path}")
                if member.size < 0:
                    raise ArchivePolicyError("Negative archive member size")

                stream = archive.extractfile(member)
                if stream is None:
                    raise ArchivePolicyError("Archive member content is unavailable")
                digest = hashlib.sha256()
                remaining = member.size
                actual = 0
                while remaining:
                    chunk = stream.read(min(limits.max_chunk_bytes, remaining))
                    if not chunk:
                        raise ArchivePolicyError(f"Truncated archive member: {path}")
                    if len(chunk) > remaining:
                        raise ArchivePolicyError(f"Archive member exceeded declared size: {path}")
                    digest.update(chunk)
                    actual += len(chunk)
                    remaining -= len(chunk)
                if stream.read(1):
                    raise ArchivePolicyError(f"Archive member contains excess data: {path}")
                if actual != expected_entry.size_bytes:
                    raise ArchivePolicyError(f"Archive content size mismatch: {path}")
                total += actual
                if total > manifest.total_bytes:
                    raise ArchivePolicyError("Archive content exceeds manifest total")
                seen_files.add(path)
                digests.append(ArchiveFileDigest(path, actual, digest.hexdigest()))

        if seen_files != set(expected):
            raise ArchivePolicyError("Archive is missing one or more manifest files")
        if total != manifest.total_bytes:
            raise ArchivePolicyError("Archive total size does not match manifest")
    except ArchivePolicyError:
        raise
    except (tarfile.TarError, OSError, EOFError, ValueError) as exc:
        raise ArchivePolicyError("Malformed or unsupported tar stream") from exc

    return ArchiveInspection(
        commit=manifest.commit,
        manifest_sha256=manifest.sha256,
        bytes_read=reader.bytes_read,
        total_file_bytes=total,
        files=tuple(sorted(digests, key=lambda item: item.path)),
    )


def _manifest_path_limits():
    # The upstream manifest already enforces these conservative path bounds.
    from .snapshot_policy import SnapshotLimits
    return SnapshotLimits()
