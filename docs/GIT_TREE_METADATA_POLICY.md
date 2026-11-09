# Phase 2D-6.1 — Pinned Git Tree Metadata Parser

## Implemented primitive

`local_agent/git_tree_policy.py` parses the NUL-delimited output format of a
fixed `git ls-tree -r -l -z` invocation. It preserves each file's path, mode,
type, full object ID and byte size, and exposes the exact metadata schema
accepted by the existing snapshot manifest validator.

The parser requires:
- a full SHA-1 or SHA-256 object ID for every regular file blob;
- exact agreement with a bounded local path allowlist;
- canonical safe paths, unique names and no Windows case collisions;
- regular file modes only (100644 or 100755);
- canonical non-negative sizes, with per-file, total, entry-count and output
  byte limits;
- strict UTF-8 paths and a final NUL delimiter.

It rejects symlinks, submodules, trees, malformed records, unexpected/missing
paths and invalid object formats. It performs no Git invocation, filesystem
access, extraction or process execution.

## Trust boundary and remaining work

This parser does not prove that its input came from the intended repository or
commit. A future acquisition layer must run only fixed Git argv against a
verified repository and full pinned commit, constrain environment and output,
and bind the returned metadata to that commit before passing it here. The
resulting object IDs can then be used by the existing Git blob verifier.

This is a parser primitive only. It does not retrieve blob contents, construct
an archive, create a snapshot, launch Windows Sandbox, execute tests, or connect
to the local agent runner.
