# Phase 2B — Disposable Worktree Preflight

## Scope

`local_agent.worktree_policy.validate_disposable_worktree` is a filesystem-only preflight for an already-created candidate worktree. It verifies that the candidate and configured source checkout are separate trees, that every exact allowlisted target exists as a regular file, and that no path component or target is a symlink.

It does not create or remove a worktree, invoke Git, inspect HEAD, establish a clean status, execute tests, write files, or apply patches.

## Required runner responsibilities (not implemented here)

Before a candidate can be used, a future runner must independently:

1. Resolve and pin the expected repository identity and base commit SHA.
2. Create the worktree in a dedicated parent directory outside the configured source checkout.
3. Verify Git reports the expected worktree path and exact pinned HEAD.
4. Verify the new worktree is clean, including untracked files.
5. Verify the worktree's Git administrative pointer belongs to the expected repository/worktree registration.
6. Run this filesystem preflight against every exact patch target.
7. Repeat filesystem checks immediately before any future write to reduce time-of-check/time-of-use risk.
8. Discard only the disposable worktree on failure; never clean, reset, or remove the user's source checkout.

## Limits and safety

- Existing regular files only; symlinks, missing paths, directories, special files, non-canonical paths and overlapping checkout roots are rejected.
- The allowlist must be non-empty and exact.
- This preflight is not a sandbox and does not provide OS-level isolation.
- It does not protect against concurrent filesystem changes after validation.
- No worktree creation, patch application, test execution, branch creation, or runner integration is enabled by this module.

## Tests

`tests/test_worktree_policy.py` covers valid sibling roots, overlapping roots, malformed paths, missing/non-regular targets, symlink targets, symlinked parent directories and empty allowlists.

## Activation state

Phase 2 remains disabled. Phase 2B is only a standalone preflight primitive; Git identity, pinned HEAD, clean-state checks, race-resistant use, isolation, audit and rollback remain future work.
