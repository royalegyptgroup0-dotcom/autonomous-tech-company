# Phase 2D-6.2 — Trusted Git Metadata Acquisition and Blob Verification

## Implemented boundary

\`local_agent/git_acquisition.py\` connects the existing read-only worktree
inspector, pinned-tree parser, snapshot manifest validator and Git blob verifier.

For one already-registered, clean worktree, the acquisition function:

1. Revalidates the source/candidate worktree relationship, exact origin, pinned
   HEAD, registration and clean status through the existing read-only inspector.
2. Resolves the full pinned commit and confirms the repository object format.
3. Uses a fixed \`git ls-tree --full-tree -r -l -z\` command with literal pathspecs
   for the exact configured allowlist.
4. Parses the bounded NUL-delimited output, then independently validates the
   metadata against the snapshot manifest policy.
5. Retrieves each blob by its full object ID using fixed \`git cat-file blob\`
   commands. Each output is capped at the pinned file size plus one byte.
6. Verifies the Git object ID and raw SHA-256 digest against the corresponding
   digest from a separately inspected archive stream.

The default subprocess runner uses argv arrays with \`shell=False\`, no stdin,
a filtered environment, disabled Git prompts, no system/global Git config,
disabled replace refs and lazy fetching, strict per-command timeouts, and
bounded stdout/stderr draining. Proxy environment variables are not inherited.
No remote/network Git subcommand is used.

## Required inputs and trust assumptions

- The source checkout and candidate worktree must already exist and pass the
  registered-worktree inspector.
- The full commit ID and exact origin must be supplied by trusted local config.
- The path allowlist must be exact, bounded and safe.
- The archive SHA-256 mapping must come from a completed bounded archive
  inspection of the same intended snapshot. This module checks exact path-set
  agreement and verifies every acquired blob against those digests.

## Explicitly not implemented

This module does not create a worktree, fetch or clone, write files, build or
extract an archive, launch Windows Sandbox, execute validation commands, apply
patches, modify the runner, or connect to production. It returns verification
metadata only. It is not an OS isolation boundary and does not close filesystem
TOCTOU risks. The snapshot builder and Sandbox executor remain a separate gate.
