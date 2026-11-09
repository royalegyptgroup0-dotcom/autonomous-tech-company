# Phase 2D-3 — Snapshot Manifest Policy (merged; CI passed)

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

## Limits

This is a pure metadata validator. It does not invoke Git, verify that metadata
truly came from the named commit, read file contents, create a snapshot, extract
an archive, copy files, or prove that a later filesystem operation is race-free.
A digest of metadata is not a digest of file contents and is not proof of
snapshot integrity.

## Phase 2D-4 — Read-only archive inspection (implementation in review)

local_agent/archive_policy.py inspects an uncompressed tar stream without
extracting it or writing to disk. It reconciles the archive against the pinned
manifest, permits only expected regular files and their parent directories,
rejects links, devices, PAX metadata, unsafe paths, duplicate/unexpected/missing
members, size mismatches, truncation, compression and archives exceeding the
configured byte cap. It computes SHA-256 for each file's content and returns
those digests for later comparison with independently obtained Git blob data.

This is not an extractor or snapshot builder. It does not create directories,
write files, invoke Git, execute tests, launch Windows Sandbox, or connect to
the runner. The archive content digests alone do not prove correspondence to
the source commit until compared with independently obtained trusted content
hashes.

## Required next gates

1. Independently obtain and compare Git blob content hashes for the pinned
   commit; verify archive file digests against them.
2. Implement race-resistant extraction into a fresh, uniquely-owned disposable
   directory outside and disjoint from the source checkout.
3. Independently reconcile every created file, path, mode, size and hash;
   reject reparse points and path-following writes.
4. Verify Windows Sandbox capability and successful launch on the actual
   Windows machine.
5. Enforce exact registered commands, bounded output, process-tree timeout,
   and a fail-closed completion protocol inside the sandbox.

Until all gates are independently tested, these modules remain disconnected
from the runner. No ordinary subprocess fallback and no paid-service fallback
if Windows Sandbox is unavailable.
