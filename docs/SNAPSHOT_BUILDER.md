# Phase 2D-6.3 — Disposable Snapshot Builder

## Implemented boundary

`local_agent/snapshot_builder.py` writes a bounded, disposable validation
snapshot from immutable blob bytes returned by the trusted Git acquisition
stage. The acquisition result now retains at most the existing 20 MB manifest
limit after each blob has passed both its pinned Git object-ID check and the
independent archive SHA-256 check.

Before writing, the builder independently re-hashes every retained byte string,
checks its size and object format, reconciles the Git verification records and
pinned tree entries, and requires an existing absolute validation parent that
is disjoint from the source checkout. Every existing path component is checked
for symlinks and Windows reparse points.

The builder then:
- creates a unique child directory using exclusive temporary-directory creation;
- writes an exclusive ownership marker containing a random 256-bit receipt token,
  pinned commit, manifest digest and exact file list;
- creates only the required parent directories and regular files;
- opens files with create-exclusive semantics and no-follow where supported;
- streams writes in 64 KiB chunks, flushes and fsyncs, and checks written size
  and SHA-256;
- walks the completed tree without following links and reconciles its exact
  files and directories against the expected manifest.

Cleanup requires the returned in-memory ownership receipt and an exact matching
marker. The token itself is never written to disk. This is an accidental-deletion guard,
not an authentication boundary against a process that can read the in-memory receipt.
It refuses to remove anything if a symlink, reparse point, unexpected
file, unexpected directory or marker mismatch is found. It removes only the
expected files, marker, expected directories and the unique owned root.

## Explicitly not implemented

This stage does not create or modify a Git worktree, invoke Git, unpack an
archive, launch Windows Sandbox, execute validation commands, apply patches,
modify the local agent runner, or deploy anything. It is not an OS isolation
boundary and is not connected to unattended execution.

## Remaining security limits

Portable Python path checks and ordinary filesystem APIs cannot eliminate all
time-of-check/time-of-use races against a hostile process with concurrent write
access to the validation parent. The validation parent must therefore be a
dedicated local directory with restrictive user-only ACLs and no untrusted
writers. Windows-specific handle-relative, reparse-safe operations and a
reviewed Sandbox launch boundary remain required before any untrusted tests run.
The builder fails closed on detected anomalies; if cleanup cannot prove exact
ownership, it intentionally leaves the directory for manual inspection rather
than deleting uncertain content.

## Tests

`tests/test_snapshot_builder.py` covers exact file creation and cleanup,
source/validation overlap, relative paths, symlinked parents, content tampering,
unexpected cleanup entries and forged ownership receipts.
