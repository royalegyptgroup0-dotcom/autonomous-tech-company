# Phase 2A — Static Patch Policy

## Scope

`local_agent.patch_policy.validate_unified_diff` validates a proposed unified diff as inert text and returns a small summary plus a SHA-256 digest. It does not read the repository, invoke Git, write files, run tests, or apply a patch.

## Default limits

- 256,000 UTF-8 bytes per patch.
- 20 file sections.
- 64,000 bytes per file section.
- 2,000 changed lines across the complete patch.
- 240 characters per path.

Callers may lower limits. They must not raise them without a separate security review.

## Accepted patch shape

- Git unified-diff file headers.
- Existing-file modifications only.
- Exact same source and destination path.
- Text hunks whose declared old/new line counts match the actual content.
- Paths must be canonical, relative POSIX paths and must appear in the caller's exact allowlist.

## Rejected by default

- Empty or missing allowlists.
- Absolute paths, drive paths, backslashes, whitespace, NUL, repeated separators, dot segments, and parent traversal.
- Environment files, Git metadata, common credential paths, private-key formats, dependency manifests/lockfiles, and protected paths such as `.github/`, `config/`, `infra/`, and `deploy/`. Caller-supplied protected paths can add restrictions but cannot remove built-in protections.
- New files, deleted files, renames, copies, binary/combined diffs, submodules, mode changes, duplicate file sections, malformed hunks, and oversized patches.

## Important limitation

A text parser cannot prove whether an existing path in a particular Git tree is a symlink. Before any future application stage, the pinned base worktree must independently inspect every target path using filesystem metadata, reject symlinks and non-regular files, and repeat validation immediately before any write. This parser is not an authorization to apply a patch.

## Required tests

`tests/test_patch_policy.py` covers valid summaries, exact allowlists, traversal and protected paths, rename/mode/submodule/binary rejection, create/delete rejection, malformed hunks, duplicate paths, empty allowlists, size limits, no-newline markers, and NUL content.

## Activation state

Phase 2A is a standalone validation primitive only. It is not imported by the Phase 1 runner and is not connected to patch application, worktree creation, test execution, branch creation, or deployment. Phase 2 remains disabled pending the remaining gates and a separate review.
