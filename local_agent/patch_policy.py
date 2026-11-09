"""Fail-closed validation for model-proposed unified diffs.

This module only parses and validates patch text. It never reads or writes the
filesystem, invokes Git, or applies a patch.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Iterable


class PatchPolicyError(ValueError):
    """Raised when a proposed patch violates the static patch policy."""


@dataclass(frozen=True)
class PatchLimits:
    max_patch_bytes: int = 256_000
    max_files: int = 20
    max_file_bytes: int = 64_000
    max_changed_lines: int = 2_000
    max_path_length: int = 240


@dataclass(frozen=True)
class FilePatch:
    path: str
    additions: int
    deletions: int
    hunk_count: int


@dataclass(frozen=True)
class PatchSummary:
    files: tuple[FilePatch, ...]
    total_additions: int
    total_deletions: int
    sha256: str


DEFAULT_PROTECTED_PATHS = (
    ".github/",
    ".git/",
    ".ssh/",
    ".env",
    "secrets/",
    "credentials/",
    "config/",
    "infra/",
    "deploy/",
    "wrangler.toml",
    "Dockerfile",
    "docker-compose.yml",
    "pyproject.toml",
    "requirements.txt",
)

_DIFF_HEADER = re.compile(r"^diff --git a/(.+) b/(.+)$")
_HUNK_HEADER = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?$"
)
_INDEX_LINE = re.compile(r"^index [0-9a-fA-F]+\.\.[0-9a-fA-F]+$")


def _validate_path(path: str, limits: PatchLimits) -> str:
    if not isinstance(path, str) or not path:
        raise PatchPolicyError("Patch contains an empty path")
    if len(path) > limits.max_path_length:
        raise PatchPolicyError("Patch path exceeds the maximum length")
    if (
        path.startswith("/")
        or path.startswith("~")
        or "\\" in path
        or ":" in path
        or any(ch.isspace() for ch in path)
        or "\x00" in path
        or "//" in path
    ):
        raise PatchPolicyError(f"Unsafe or ambiguous patch path: {path!r}")
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise PatchPolicyError(f"Path traversal or non-canonical path: {path!r}")
    blocked_names = {".git", ".ssh", ".npmrc", ".pypirc", ".netrc", "id_rsa", "id_ed25519"}
    if any(
        part.casefold() in blocked_names
        or part.casefold().startswith(".env")
        or part.casefold().endswith((".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"))
        for part in parts
    ):
        raise PatchPolicyError("Credential and private-key paths are protected")
    return path


def _is_protected(path: str, protected_paths: Iterable[str]) -> bool:
    candidate = path.casefold()
    for item in protected_paths:
        rule = item.casefold()
        if rule.endswith("/"):
            if candidate.startswith(rule):
                return True
        elif candidate == rule or candidate.startswith(rule + "/"):
            return True
    return False


def validate_unified_diff(
    patch: str,
    *,
    allowed_paths: Iterable[str],
    protected_paths: Iterable[str] = DEFAULT_PROTECTED_PATHS,
    limits: PatchLimits = PatchLimits(),
) -> PatchSummary:
    """Validate a text-only, modification-only unified diff without applying it.

    The allowlist is exact (not glob-based). New/deleted files, renames,
    copies, binary patches, mode changes, submodules, and protected paths
    are rejected. A caller must separately verify base-tree symlink status.
    """
    if not isinstance(patch, str) or not patch:
        raise PatchPolicyError("Patch must be a non-empty string")
    try:
        encoded = patch.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise PatchPolicyError("Patch must be valid UTF-8 text") from exc
    if len(encoded) > limits.max_patch_bytes:
        raise PatchPolicyError("Patch exceeds the total byte limit")
    if "\x00" in patch:
        raise PatchPolicyError("Binary or NUL-containing patch content is not allowed")

    allow = {
        _validate_path(item, limits)
        for item in allowed_paths
    }
    if not allow:
        raise PatchPolicyError("An explicit, non-empty exact-path allowlist is required")
    protected = tuple(protected_paths)

    lines = patch.splitlines()
    if not lines or not lines[0].startswith("diff --git "):
        raise PatchPolicyError("Patch must use git unified-diff file headers")
    if any(
        line.startswith(("GIT binary patch", "Binary files ", "diff --cc ", "diff --combined "))
        for line in lines
    ):
        raise PatchPolicyError("Binary and combined diffs are not supported")

    blocks: list[list[str]] = []
    for line in lines:
        if line.startswith("diff --git "):
            blocks.append([line])
        elif not blocks:
            raise PatchPolicyError("Unexpected content before the first file header")
        else:
            blocks[-1].append(line)

    if len(blocks) > limits.max_files:
        raise PatchPolicyError("Patch changes more files than the configured limit")

    parsed: list[FilePatch] = []
    seen: set[str] = set()
    total_additions = 0
    total_deletions = 0

    for block in blocks:
        match = _DIFF_HEADER.fullmatch(block[0])
        if not match:
            raise PatchPolicyError("Malformed or quoted Git diff path header")
        old_path = _validate_path(match.group(1), limits)
        new_path = _validate_path(match.group(2), limits)
        if old_path != new_path:
            raise PatchPolicyError("Renames and cross-path patches are not allowed")
        path = old_path
        if path in seen:
            raise PatchPolicyError(f"Duplicate patch section for {path!r}")
        seen.add(path)
        if path not in allow:
            raise PatchPolicyError(f"Path is not in the exact write allowlist: {path}")
        if _is_protected(path, protected):
            raise PatchPolicyError(f"Protected path cannot be changed: {path}")

        old_header = f"--- a/{path}"
        new_header = f"+++ b/{path}"
        try:
            old_index = block.index(old_header)
            new_index = block.index(new_header, old_index + 1)
        except ValueError as exc:
            raise PatchPolicyError("File creation/deletion or malformed file headers are not allowed") from exc
        if new_index != old_index + 1:
            raise PatchPolicyError("Unexpected metadata between old and new file headers")

        metadata = block[1:old_index]
        for line in metadata:
            if _INDEX_LINE.fullmatch(line):
                continue
            if line.startswith((
                "old mode ", "new mode ", "new file mode ", "deleted file mode ",
                "similarity index ", "dissimilarity index ", "rename from ",
                "rename to ", "copy from ", "copy to ", "Subproject commit ",
            )):
                raise PatchPolicyError("Mode changes, renames, copies, and submodules are not allowed")
            raise PatchPolicyError(f"Unsupported diff metadata: {line[:120]!r}")

        additions = 0
        deletions = 0
        hunk_count = 0
        index = new_index + 1
        if index >= len(block):
            raise PatchPolicyError("File patch contains no hunks")

        while index < len(block):
            hunk_match = _HUNK_HEADER.fullmatch(block[index])
            if not hunk_match:
                raise PatchPolicyError("Unexpected content outside a unified-diff hunk")
            old_remaining = int(hunk_match.group(2) or "1")
            new_remaining = int(hunk_match.group(4) or "1")
            hunk_count += 1
            index += 1
            while old_remaining or new_remaining:
                if index >= len(block):
                    raise PatchPolicyError("Truncated unified-diff hunk")
                line = block[index]
                if not line:
                    raise PatchPolicyError("Malformed empty diff line")
                marker = line[0]
                if marker == " ":
                    old_remaining -= 1
                    new_remaining -= 1
                elif marker == "+":
                    new_remaining -= 1
                    additions += 1
                elif marker == "-":
                    old_remaining -= 1
                    deletions += 1
                else:
                    raise PatchPolicyError("Invalid unified-diff hunk line")
                if old_remaining < 0 or new_remaining < 0:
                    raise PatchPolicyError("Hunk line counts exceed the declared ranges")
                index += 1
            no_newline_markers = 0
            while index < len(block) and block[index].startswith("\\ No newline at end of file"):
                no_newline_markers += 1
                if no_newline_markers > 2:
                    raise PatchPolicyError("Too many no-newline markers")
                index += 1
            if additions + deletions > limits.max_changed_lines:
                raise PatchPolicyError("Per-file changed-line limit exceeded")

        file_bytes = sum(len(line.encode("utf-8")) + 1 for line in block)
        if file_bytes > limits.max_file_bytes:
            raise PatchPolicyError(f"Patch section for {path!r} exceeds the per-file byte limit")
        total_additions += additions
        total_deletions += deletions
        parsed.append(FilePatch(path, additions, deletions, hunk_count))

    if total_additions + total_deletions == 0:
        raise PatchPolicyError("Patch must contain at least one changed line")
    if total_additions + total_deletions > limits.max_changed_lines:
        raise PatchPolicyError("Total changed-line limit exceeded")
    return PatchSummary(
        files=tuple(parsed),
        total_additions=total_additions,
        total_deletions=total_deletions,
        sha256=hashlib.sha256(encoded).hexdigest(),
    )
