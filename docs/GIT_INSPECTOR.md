# Phase 2C — Read-only Git Worktree Inspector

## Scope

`local_agent.git_inspector.inspect_registered_worktree` verifies an already-existing candidate worktree without changing repository state. It checks:

- Both configured paths resolve to distinct, non-overlapping repository roots.
- Git reports the exact configured top-level paths.
- Source and candidate `remote.origin.url` values exactly match a locally configured expected identity.
- Both worktrees share the same Git common directory.
- The candidate is registered in the source repository's `git worktree list --porcelain`.
- Candidate HEAD equals a full pinned object ID.
- Candidate status is clean, including untracked files and submodule state.

## Command and process restrictions

The module uses a fixed set of read-only commands: `rev-parse`, `config --get`, `worktree list --porcelain`, and `status --porcelain`. It never accepts a command string from a model or caller. It invokes Git with an argument array, `shell=False`, no stdin, a bounded timeout, bounded stdout, and a filtered environment that removes inherited Git, proxy, SSH, and credential variables. Git terminal prompts, optional index locks, system/global config, filesystem monitor and LFS smudging are disabled for the inspection process.

No fetch, pull, checkout, switch, reset, clean, add, commit, push, worktree add/remove, test execution, or patch application is performed.

## Limitations

- The expected origin and pinned commit must be supplied by trusted local configuration, not model output.
- The origin is compared as an exact configured string; no network connection or remote authenticity check is made.
- The inspector is not an OS sandbox and does not prevent concurrent filesystem changes (TOCTOU).
- The injectable runner is intended only for unit tests; production callers must use the default subprocess runner.
- This module is not connected to the Phase 1 runner and cannot enable Phase 2 by itself.

## Tests

`tests/test_git_inspector.py` covers successful verification, origin mismatch, unregistered worktrees, wrong HEAD, dirty/untracked files, overlapping roots, invalid identity/timeout values, and the fixed-command boundary.

## Activation state

Phase 2 remains disabled. This inspector is a standalone read-only verification primitive. Worktree creation, isolated test execution, patch application, rollback, audit integration, and end-to-end activation remain separate gated work.
