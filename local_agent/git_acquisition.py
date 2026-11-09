"""Acquire and verify bounded blob content from one pinned local Git worktree.

Only fixed, read-only Git commands are executed. No network command, checkout,
worktree mutation, extraction, patch application, or runner integration occurs.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import os
from pathlib import Path
import re
import shutil
import subprocess
from threading import Event, Thread
from time import monotonic
from typing import Callable, Mapping, Sequence

from .git_blob_policy import GitBlobVerification, verify_git_blob_stream
from .git_inspector import GitInspection, inspect_registered_worktree
from .git_tree_policy import PinnedTreeMetadata, parse_ls_tree_output
from .snapshot_policy import SnapshotLimits, SnapshotPolicyError, _safe_path, validate_snapshot_manifest


class GitAcquisitionError(ValueError):
    """Raised when trusted pinned Git content cannot be acquired safely."""


@dataclass(frozen=True)
class GitAcquisitionResult:
    inspection: GitInspection
    tree: PinnedTreeMetadata
    blob_verifications: tuple[GitBlobVerification, ...]


Runner = Callable[[list[str], Path, dict[str, str], int, int], bytes]
_HEX_COMMIT = re.compile(r"^[0-9a-f]{40,64}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MAX_TREE_OUTPUT = 2_000_000
_MAX_STDERR_BYTES = 16_384


def _safe_git_environment() -> dict[str, str]:
    """Construct an allowlisted environment; ignore all proxy variables."""
    allowed = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE")
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    env.update({
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_LFS_SKIP_SMUDGE": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "core.fsmonitor",
        "GIT_CONFIG_VALUE_0": "false",
    })
    return env


def _run_git_bounded(
    argv: list[str],
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: int,
    max_output_bytes: int,
) -> bytes:
    """Run fixed Git argv with bounded stdout, timeout and no shell."""
    if not isinstance(max_output_bytes, int) or isinstance(max_output_bytes, bool) or not 1 <= max_output_bytes <= _MAX_TREE_OUTPUT:
        raise GitAcquisitionError("Git output limit is outside its safe bound")
    try:
        process = subprocess.Popen(
            argv,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
    except OSError as exc:
        raise GitAcquisitionError(f"Git command could not start: {type(exc).__name__}") from exc

    assert process.stdout is not None
    assert process.stderr is not None
    output_parts: list[bytes] = []
    stderr_parts: list[bytes] = []
    output_size = 0
    overflow = Event()

    def drain_stdout() -> None:
        nonlocal output_size
        while True:
            chunk = process.stdout.read(min(65_536, max_output_bytes + 1 - output_size))
            if not chunk:
                return
            output_size += len(chunk)
            if output_size > max_output_bytes:
                overflow.set()
                return
            output_parts.append(chunk)

    def drain_stderr() -> None:
        retained = 0
        while True:
            chunk = process.stderr.read(4096)
            if not chunk:
                return
            if retained < _MAX_STDERR_BYTES:
                piece = chunk[: _MAX_STDERR_BYTES - retained]
                stderr_parts.append(piece)
                retained += len(piece)

    out_thread = Thread(target=drain_stdout, daemon=True)
    err_thread = Thread(target=drain_stderr, daemon=True)
    out_thread.start()
    err_thread.start()
    deadline = monotonic() + timeout_seconds
    timed_out = False
    try:
        while process.poll() is None:
            if overflow.is_set():
                process.kill()
                break
            remaining = deadline - monotonic()
            if remaining <= 0:
                timed_out = True
                process.kill()
                break
            try:
                process.wait(timeout=min(0.05, remaining))
            except subprocess.TimeoutExpired:
                continue
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    finally:
        out_thread.join(timeout=2)
        err_thread.join(timeout=2)
        process.stdout.close()
        process.stderr.close()

    if timed_out:
        raise GitAcquisitionError("Git command exceeded its time limit")
    if overflow.is_set() or output_size > max_output_bytes:
        raise GitAcquisitionError("Git command exceeded its output limit")
    if out_thread.is_alive() or err_thread.is_alive():
        raise GitAcquisitionError("Git output streams did not close cleanly")
    if process.returncode != 0:
        raise GitAcquisitionError(f"Read-only Git command failed ({process.returncode})")
    return b"".join(output_parts)


def acquire_and_verify_pinned_blobs(
    source_checkout: str | os.PathLike[str],
    candidate_worktree: str | os.PathLike[str],
    *,
    expected_origin: str,
    pinned_commit: str,
    allowed_paths: Sequence[str],
    archive_sha256_by_path: Mapping[str, str],
    timeout_seconds: int = 10,
    _runner: Runner | None = None,
    _inspection_runner=None,
) -> GitAcquisitionResult:
    """Verify one exact allowlist of archive-inspected files against pinned Git blobs.

    The archive digest mapping must come from a separately completed bounded
    archive inspection of this same pinned snapshot. Test-only runners may be
    injected by unit tests; production callers must use the built-in runner.
    """
    if not isinstance(pinned_commit, str) or not _HEX_COMMIT.fullmatch(pinned_commit):
        raise GitAcquisitionError("A full lowercase pinned commit ID is required")
    if not isinstance(expected_origin, str) or not expected_origin or expected_origin.strip() != expected_origin:
        raise GitAcquisitionError("An exact expected repository origin is required")
    if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool) or not 1 <= timeout_seconds <= 30:
        raise GitAcquisitionError("Git timeout must be between 1 and 30 seconds")
    if not isinstance(allowed_paths, (list, tuple)) or not 1 <= len(allowed_paths) <= 500:
        raise GitAcquisitionError("Allowed paths must be a bounded non-empty list")
    safe_paths: list[str] = []
    folded_paths: set[str] = set()
    for raw_path in allowed_paths:
        try:
            safe_path = _safe_path(raw_path, SnapshotLimits())
        except SnapshotPolicyError as exc:
            raise GitAcquisitionError("Allowed path is unsafe or non-canonical") from exc
        if safe_path.casefold() in folded_paths:
            raise GitAcquisitionError("Allowed paths contain duplicates or Windows case collisions")
        safe_paths.append(safe_path)
        folded_paths.add(safe_path.casefold())
    if not isinstance(archive_sha256_by_path, Mapping):
        raise GitAcquisitionError("Archive SHA-256 values must be a path-to-digest mapping")
    if set(archive_sha256_by_path) != set(safe_paths):
        raise GitAcquisitionError("Archive digest paths must exactly match the requested allowlist")
    if any(not isinstance(value, str) or not _SHA256.fullmatch(value) for value in archive_sha256_by_path.values()):
        raise GitAcquisitionError("Every archive digest must be a full lowercase SHA-256 value")

    inspection = inspect_registered_worktree(
        source_checkout,
        candidate_worktree,
        expected_origin=expected_origin,
        pinned_commit=pinned_commit,
        timeout_seconds=timeout_seconds,
        _runner=_inspection_runner,
    )
    git = shutil.which("git")
    if not git:
        raise GitAcquisitionError("Git executable was not found")
    cwd = inspection.worktree_root
    if inspection.pinned_commit != pinned_commit or not inspection.clean or not inspection.registered:
        raise GitAcquisitionError("Registered worktree inspection did not confirm the pinned clean checkout")
    env = _safe_git_environment()
    run = _runner or _run_git_bounded

    def command(args: Sequence[str], limit: int) -> bytes:
        argv = [git, "-C", str(cwd), *args]
        output = run(argv, cwd, env, timeout_seconds, limit)
        if not isinstance(output, bytes) or len(output) > limit:
            raise GitAcquisitionError("Git command returned invalid or oversized output")
        return output

    try:
        resolved = command(["rev-parse", "--verify", f"{pinned_commit}^{{commit}}"], 128).decode("ascii").strip()
    except (UnicodeDecodeError, AttributeError) as exc:
        raise GitAcquisitionError("Pinned commit resolution returned invalid data") from exc
    if resolved != pinned_commit:
        raise GitAcquisitionError("Resolved commit differs from the requested pinned commit")

    try:
        object_format = command(["rev-parse", "--show-object-format"], 32).decode("ascii").strip()
    except (UnicodeDecodeError, AttributeError) as exc:
        raise GitAcquisitionError("Git object format response is invalid") from exc
    if object_format not in ("sha1", "sha256"):
        raise GitAcquisitionError("Repository uses an unsupported Git object format")
    if len(pinned_commit) != (40 if object_format == "sha1" else 64):
        raise GitAcquisitionError("Pinned commit length does not match the repository object format")

    literal_pathspecs = [f":(literal){path}" for path in safe_paths]
    tree_output = command(
        ["ls-tree", "--full-tree", "-r", "-l", "-z", pinned_commit, "--", *literal_pathspecs],
        _MAX_TREE_OUTPUT,
    )
    tree = parse_ls_tree_output(
        tree_output,
        expected_paths=safe_paths,
        object_format=object_format,
        max_output_bytes=_MAX_TREE_OUTPUT,
    )
    try:
        manifest = validate_snapshot_manifest(
            commit=pinned_commit,
            tree_entries=tree.snapshot_entries,
            allowed_paths=safe_paths,
            limits=SnapshotLimits(),
        )
    except ValueError as exc:
        raise GitAcquisitionError("Pinned tree did not satisfy the snapshot manifest policy") from exc
    if manifest.total_bytes != tree.total_bytes:
        raise GitAcquisitionError("Pinned tree and snapshot manifest byte totals differ")

    verified: list[GitBlobVerification] = []
    for entry in tree.entries:
        blob = command(["cat-file", "blob", entry.object_id], entry.size_bytes + 1)
        if len(blob) > entry.size_bytes:
            raise GitAcquisitionError("Git blob output exceeded its pinned size")
        try:
            result = verify_git_blob_stream(
                BytesIO(blob),
                path=entry.path,
                expected_size=entry.size_bytes,
                expected_git_oid=entry.object_id,
                expected_sha256=archive_sha256_by_path[entry.path],
                object_format=object_format,
            )
        except ValueError as exc:
            raise GitAcquisitionError(f"Pinned Git blob verification failed for {entry.path}") from exc
        verified.append(result)

    return GitAcquisitionResult(inspection, tree, tuple(verified))
