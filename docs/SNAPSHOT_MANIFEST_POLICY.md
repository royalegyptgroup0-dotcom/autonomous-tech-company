# Phase 2D-3 — Snapshot Manifest Policy (planning-only)

## Implemented

The module local_agent/snapshot_policy.py validates metadata for a pinned Git
tree against an exact local file allowlist. It accepts only regular Git blobs
(100644 or 100755), rejects symlinks, submodules, trees and special entries,
rejects sensitive paths and Windows-unsafe names, detects case-collisions, and
enforces entry, per-file and total-size limits. It returns a deterministic
SHA-256 manifest digest tied to the full pinned commit ID.

Each entry must contain exactly path, mode, type and size. Every allowlisted
path must exist exactly once. Unlisted files, missing paths, duplicate paths,
and malformed metadata fail closed.

## Critical limits

This is a pure metadata validator. It does not invoke Git, verify that metadata
truly came from the named commit, read file contents, create a snapshot, extract
an archive, copy files, or prove that a later filesystem operation is race-free.
A digest of metadata is not a digest of file contents and is not proof of
snapshot integrity.

No snapshot may be built until a separate builder safely streams a pinned
archive into a fresh, uniquely-owned empty directory and independently checks
every extracted file against this manifest. The builder must reject links,
special files, path traversal, duplicate/case-colliding paths, unexpected
entries, content-size mismatches, and archive bombs. It must not copy Git
metadata, hooks, ignored/untracked files, local configuration, credentials,
or environment files. It must enforce file and total byte caps while streaming,
not after buffering an unbounded archive.

## Required next gates

1. A bounded archive reader/extractor with no path-following writes and
   race-resistant directory handling.
2. Independent content hashes and exact file-count/size reconciliation.
3. A uniquely-owned temporary destination outside and disjoint from the source
   checkout; cleanup only after verifying ownership and exact path identity.
4. Windows Sandbox host capability verification and successful launch testing
   on the actual Windows machine.
5. Exact registered command selection, bounded streaming output, process-tree
   timeout, and a fail-closed completion protocol inside the sandbox.

Until all gates are independently tested, this module remains disconnected from
the runner. It does not create or remove directories, execute tests, apply
patches, launch Sandbox, or enable Phase 2. If Windows Sandbox is unavailable,
there is no ordinary subprocess fallback and no paid-service fallback.

## Tests

tests/test_snapshot_policy.py covers pinned commit validation, exact allowlists,
missing and duplicate paths, unsafe and sensitive paths, Windows case
collisions, Git object types/modes, metadata schema, and size limits.
