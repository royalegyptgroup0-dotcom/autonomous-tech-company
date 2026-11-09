"""Read-only verification of a registered disposable Git worktree.

No Git command in this module creates, removes, fetches, checks out, resets,
or writes to a repository. The caller must supply an exact expected remote
identity and pinned commit. This is a preflight, not an OS sandbox.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Callable


class GitInspectionError(ValueError):
    """Raised when repository identity or worktree state is not trustworthy."""


@dataclass(frozen=True)
class GitInspection:
    source_root: Path
    worktree_root: Path
    expected_origin: str
    pinned_commit: str
    common_git_dir: Path
    clean: bool
    registered: bool


Runner = Callable[[list[str], Path, dict[str, str], int], str]
_SHA = re.compile(r"^[0-9a-f]{40,64}$")


def _run_git(argv: list[str], cwd: Path, env: dict[str, str], timeout: int) -> str:
    """Run one fixed read-only Git command without a shell or inherited secrets."""
    try:
        result = subprocess.run(
            argv,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitInspectionError(f"Git inspection command could not complete: {type(exc).__name__}") from exc
    if result.returncode != 0:
        # Do not include stderr: repository config may contain sensitive strings.
        raise GitInspectionError(f"Read-only Git command failed ({result.returncode})")
    if len(result.stdout.encode("utf-8")) > 1_000_000:
        raise GitInspectionError("Git output exceeded the one-megabyte limit")
    return result.stdout.strip()


def _safe_environment() -> dict[str, str]:
    # Keep only variables required to locate Git and run it on Windows.
    allowed = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE")
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    env.update({
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_LFS_SKIP_SMUDGE": "1",
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "core.fsmonitor",
        "GIT_CONFIG_VALUE_0": "false",
    })
    return env


def _absolute_directory(value: str | os.PathLike[str]) -> Path:
    try:
        path = Path(value).expanduser().resolve(strict=True)
    except (OSError, RuntimeError, TypeError) as exc:
        raise GitInspectionError("Repository path is missing or cannot be resolved") from exc
    if not path.is_dir():
        raise GitInspectionError("Repository path must be an existing directory")
    return path


def _parse_worktree_records(output: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in output.splitlines():
        if not line:
            if current:
                records.append(current)
                current = {}
            continue
        key, separator, value = line.partition(" ")
        if not separator:
            continue
        current[key] = value
    if current:
        records.append(current)
    return records


def inspect_registered_worktree(
    source_checkout: str | os.PathLike[str],
    candidate_worktree: str | os.PathLike[str],
    *,
    expected_origin: str,
    pinned_commit: str,
    timeout_seconds: int = 10,
    _runner: Runner | None = None,
) -> GitInspection:
    """Verify origin, common Git directory, registration, pinned HEAD and clean state.

    The optional runner exists solely for deterministic unit tests. Production
    callers must not provide it. Commands are fixed below; no user/model command
    string is accepted. No network-capable Git subcommand is used.
    """
    if not isinstance(expected_origin, str) or not expected_origin or expected_origin.strip() != expected_origin:
        raise GitInspectionError("An exact, non-empty expected origin is required")
    if not isinstance(pinned_commit, str) or not _SHA.fullmatch(pinned_commit):
        raise GitInspectionError("Pinned commit must be a full hexadecimal Git object ID")
    if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool) or not 1 <= timeout_seconds <= 30:
        raise GitInspectionError("Timeout must be an integer between 1 and 30 seconds")

    source = _absolute_directory(source_checkout)
    candidate = _absolute_directory(candidate_worktree)
    if source == candidate or source in candidate.parents or candidate in source.parents:
        raise GitInspectionError("Source checkout and candidate worktree must be separate sibling trees")

    git = shutil.which("git")
    if not git:
        raise GitInspectionError("Git executable was not found")
    env = _safe_environment()
    run = _runner or _run_git

    def command(root: Path, *args: str) -> str:
        return run([git, "-C", str(root), *args], root, env, timeout_seconds)

    source_top = Path(command(source, "rev-parse", "--show-toplevel")).resolve(strict=True)
    candidate_top = Path(command(candidate, "rev-parse", "--show-toplevel")).resolve(strict=True)
    if source_top != source or candidate_top != candidate:
        raise GitInspectionError("Git reported a repository root different from the configured path")

    source_origin = command(source, "config", "--get", "remote.origin.url")
    candidate_origin = command(candidate, "config", "--get", "remote.origin.url")
    if source_origin != expected_origin or candidate_origin != expected_origin:
        raise GitInspectionError("Repository origin does not match the configured identity")

    source_common = Path(command(source, "rev-parse", "--git-common-dir"))
    candidate_common = Path(command(candidate, "rev-parse", "--git-common-dir"))
    if not source_common.is_absolute():
        source_common = (source / source_common).resolve(strict=True)
    else:
        source_common = source_common.resolve(strict=True)
    if not candidate_common.is_absolute():
        candidate_common = (candidate / candidate_common).resolve(strict=True)
    else:
        candidate_common = candidate_common.resolve(strict=True)
    if source_common != candidate_common:
        raise GitInspectionError("Candidate is not attached to the source repository's common Git directory")

    records = _parse_worktree_records(command(source, "worktree", "list", "--porcelain"))
    registered_paths = set()
    for record in records:
        raw_path = record.get("worktree")
        if raw_path:
            try:
                registered_paths.add(Path(raw_path).resolve(strict=True))
            except (OSError, RuntimeError):
                continue
    if candidate not in registered_paths:
        raise GitInspectionError("Candidate path is not registered as a worktree of the source repository")

    actual_head = command(candidate, "rev-parse", "--verify", "HEAD")
    if actual_head != pinned_commit:
        raise GitInspectionError("Candidate HEAD does not match the pinned commit")

    status = command(candidate, "status", "--porcelain=v1", "--untracked-files=all", "--ignore-submodules=none")
    if status:
        raise GitInspectionError("Candidate worktree is not clean")

    return GitInspection(
        source_root=source,
        worktree_root=candidate,
        expected_origin=expected_origin,
        pinned_commit=pinned_commit,
        common_git_dir=source_common,
        clean=True,
        registered=True,
    )
