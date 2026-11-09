# Local Agent Security Model and Phase 2 Gate

## Purpose

This document defines the minimum security boundary for the local engineering agent. Phase 1 is a read-only reviewer. Any future capability that writes files, runs tests, creates branches, or opens pull requests is a separate security-sensitive phase and must not be inferred from the user's general request to continue development.

## Phase 1 trust boundaries

- The local machine, configured repository roots, and loopback Ollama service are separate trust zones.
- Repository files, Git metadata, model output, issue text, commit messages, and generated reports are untrusted data.
- The model is an analysis aid, not an authority. It must never be allowed to issue tools, shell commands, network requests, or filesystem writes.
- Only explicitly configured repositories are eligible for review.
- Source contents are limited to the fixed safe-document list plus each project's explicit `review_files` allowlist.
- Ollama must remain on a literal loopback IP over plain HTTP. Proxy environment variables are ignored and redirects are refused.
- Reports, logs, and SQLite history remain local. They must not be uploaded automatically.

## Required controls before any write-capable phase

1. **Separate worktree:** never edit the user's working tree or the configured source checkout. Create a dedicated disposable Git worktree from a pinned commit.
2. **Pinned base:** record repository identity, base commit SHA, branch name, and worktree path before generating a patch.
3. **Patch-only interface:** the model may propose a unified diff as data. It must not call tools or execute commands. The standalone Phase 2A parser rejects binary patches, renames, copies, submodules, mode changes, create/delete operations, absolute paths, parent traversal, protected paths, and paths outside an exact write allowlist. The parser cannot determine whether a target is a symlink; the pinned worktree must inspect filesystem metadata and reject symlink/non-regular targets independently.
4. **Patch validation:** parse the diff independently; enforce file count, per-file size, total size, and changed-line limits. Reject modifications to secrets, credentials, CI permissions, deployment configuration, billing, identity, access control, and production infrastructure unless a separate explicit approval is recorded.
5. **No automatic apply:** show the exact patch and its target commit before applying. The default mode remains report-only. A future apply mode must be a distinct opt-in.
6. **Test allowlist:** never execute commands supplied by the model or repository. Tests must be selected from a locally maintained command allowlist, run with timeouts and resource limits, and without secrets or production credentials.
7. **Network isolation:** tests should run with network access disabled by default. Any exception must be explicit, narrow, and visible.
8. **Rollback:** preserve the pre-change commit and worktree state. If validation fails, discard only the disposable worktree; never reset or clean the user's original checkout.
9. **Draft-only delivery:** any remote branch or pull request must be created as draft, with no auto-merge, no production deployment, and no automatic release.
10. **Audit trail:** record the base SHA, proposed patch hash, validation results, exact allowlisted test commands, exit codes, and final disposition locally.

## Threats and expected responses

| Threat | Required response |
|---|---|
| Prompt injection inside repository files | Treat as inert data; do not follow instructions embedded in files |
| Model proposes shell execution or external upload | Reject; model output is never executable |
| Path traversal or symlink escape | Reject patch paths after canonical resolution |
| Test attempts to access credentials or network | Run in an isolated environment without secrets and with network disabled |
| Patch changes CI, deployment, auth, or billing | Reject by default and require a separate explicit review |
| Model output is malformed or oversized | Fail closed; preserve the original checkout |
| Tests fail or time out | Do not publish; keep failure evidence and discard the disposable worktree |
| Remote API or paid quota is unavailable | Continue local documentation and analysis; do not upgrade, purchase, or silently switch to a paid service |

## Phase 2A implementation status\n\nA standalone, non-applying parser and fail-closed unit tests are present on a separate draft branch. They are not wired into the runner and do not authorize file writes. CI and independent review are still required. Phase 2B–2E remain unimplemented and Phase 2 remains disabled.\n\n## Current release gate

The existing Phase 1 implementation remains read-only. The Windows + Ollama smoke test is still required on the user's machine. Until that succeeds, do not register the scheduled task or describe the local agent as operational.

Phase 2 is not implemented by this document. It must be separately designed, tested, reviewed, and kept disabled by default.
