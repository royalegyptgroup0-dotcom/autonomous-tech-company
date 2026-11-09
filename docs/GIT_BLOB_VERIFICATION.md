# Phase 2D-5 — Git Blob Content Verification

## Implemented primitive

local_agent/git_blob_policy.py verifies a bounded binary stream against two
independent expectations:

- The Git blob object ID obtained from trusted metadata for the pinned commit.
- The SHA-256 content digest returned by the read-only archive inspector.

Git blob hashing includes the exact Git object header, blob <size>, a NUL byte,
and then the file bytes. Both repository object formats are supported: SHA-1
(40 hex characters) and SHA-256 (64 hex characters). The raw content SHA-256
is checked separately against the archive inspection result.

The verifier enforces exact byte count, a 2 MB maximum file size, a 64 KiB
maximum read chunk, strict path validation, and fail-closed handling of short,
long, text, malformed, or mismatched input streams.

## Boundaries

This is a pure streaming hash verifier. It does not invoke Git, retrieve tree
metadata or blob contents, inspect repository configuration, create files,
extract archives, launch Windows Sandbox, execute validation commands, or
connect to the agent runner.

The caller must independently obtain and authenticate the pinned commit's
object format, tree entry object IDs and sizes. A matching pair of hashes
proves the supplied stream matches those expectations; it does not establish
that the expectations themselves came from the intended repository unless
the upstream Git inspection is trusted.

No snapshot builder or sandbox executor is implemented by this phase.
