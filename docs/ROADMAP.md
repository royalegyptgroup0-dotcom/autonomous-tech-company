# Delivery Roadmap

## Gate 0 — Foundation (current)
- Establish independent repository and deployment boundary.
- Confirm company name, ownership and jurisdiction.
- Run scaffold tests and security baseline.

## Gate 1 — First paid offer
- Interview prospective customers.
- Select one narrow workflow with measurable value.
- Write scope, exclusions, delivery plan and support terms.
- Obtain explicit approval for any contract or financial commitment.

## Gate 2 — Repeatable operations
- Build internal CRM, task queue, approval inbox and reporting.
- Automate routine follow-up only after consent and privacy review.
- Add role-based access and audit trails.

## Gate 3 — Company OS
- Introduce agent registry, orchestrator, memory, policy engine and recovery.
- Start in recommendation mode; expand to bounded execution after tests.

## Gate 4 — Productization
- Productize the most repeated paid workflow.
- Add tenant isolation, billing integration only after legal and security review.
- Measure retention and support cost before scaling.

## Engineering autonomy — staged safety gates
- Phase 1 (read-only local review): implementation and cross-platform CI are in place; local Windows + Ollama smoke test remains outstanding.
- Phase 2 (bounded code changes): remains disabled. The component safety gates through 2D-6.3a are implemented and integrated, but no write-capable runner or sandbox execution is enabled. Build and verify each gate in order:
  1. **2A — Patch policy (merged; CI passed):** `local_agent/patch_policy.py` parses unified diffs without filesystem access or writes. It enforces exact allowlists and size/count limits; rejects traversal, absolute/ambiguous paths, credentials, protected paths, renames, copies, binaries, create/delete operations, submodules, mode changes, malformed hunks, Windows reserved device names and control characters. See `docs/PATCH_POLICY.md`.
  2. **2B — Disposable worktree (preflight primitive only):** `local_agent/worktree_policy.py` checks that candidate/source trees do not overlap and exact targets are existing regular files without symlink components. See `docs/WORKTREE_POLICY.md`. Worktree creation and race-resistant use remain unimplemented.
  3. **2C — Read-only Git inspection (merged; CI passed):** `local_agent/git_inspector.py` verifies exact origin identity, shared Git common directory, worktree registration, pinned HEAD and clean status using fixed read-only Git commands. See `docs/GIT_INSPECTOR.md`. It is not connected to the runner and does not create worktrees or execute tests.
  4. **2D-1 — Validation plan policy:** `local_agent/validation_policy.py` permits selecting only exact command vectors from trusted local configuration, with strict argument, timeout and output-limit bounds. See `docs/VALIDATION_POLICY.md`. It is planning-only; execution is always disabled.
  5. **2D-2 — Windows Sandbox profile policy (merged; CI passed):** `local_agent/sandbox_policy.py` builds a no-network, no-clipboard profile mapping only one disjoint disposable validation snapshot. See `docs/WINDOWS_SANDBOX_POLICY.md`. It does not create snapshots, launch Sandbox, or execute commands.
  6. **2D-3 — Snapshot manifest policy (merged; CI passed):** `local_agent/snapshot_policy.py` validates pinned Git-tree metadata against an exact allowlist, rejects links/submodules/sensitive paths and Windows collisions, and enforces file/count/total-size limits. See `docs/SNAPSHOT_MANIFEST_POLICY.md`. Planning-only: it does not build or extract a snapshot.
  7. **2D-4 — Read-only archive inspection (merged; CI passed):** `local_agent/archive_policy.py` inspects a bounded tar stream without extracting or writing files, reconciles exact members against the pinned manifest, rejects links/special entries and unsafe paths, and computes per-file SHA-256 digests. See `docs/SNAPSHOT_MANIFEST_POLICY.md`. It does not verify Git blob hashes or create a snapshot.
  8. **2D-5 — Git blob content verification (merged; CI passed after fixture correction):** `local_agent/git_blob_policy.py` streams each file through Git SHA-1 or SHA-256 object hashing and raw SHA-256 comparison against the archive inspection digest, with strict byte and path bounds. See `docs/GIT_BLOB_VERIFICATION.md`. It does not invoke Git, retrieve trusted blob metadata, extract files, or connect to the runner.
  9. **2D-6.1 — Pinned Git tree metadata parser (merged; Windows + Ubuntu CI passed):** `local_agent/git_tree_policy.py` parses bounded NUL-delimited `git ls-tree` output, retaining full blob object IDs and sizes for an exact allowlist. See `docs/GIT_TREE_METADATA_POLICY.md`. It does not invoke Git or authenticate the source of its input.
  10. **2D-6.2 — Trusted Git metadata acquisition and blob verification (merged; Windows + Ubuntu CI passed):** `local_agent/git_acquisition.py` binds fixed read-only Git commands to the inspected registered worktree and full pinned commit, parses exact tree metadata, retrieves blobs by object ID, and verifies Git object IDs plus archive SHA-256 digests with bounded output and time. It retains only the verified content within the existing 20 MB total cap for the next gate. See `docs/GIT_ACQUISITION.md`.
  11. **2D-6.3a — Disposable snapshot builder (merged; Windows + Ubuntu CI passed):** `local_agent/snapshot_builder.py` independently re-verifies retained blob bytes, writes only into a unique child of an existing dedicated validation parent, uses exclusive file creation and a random ownership marker, reconciles the exact tree, and refuses cleanup if any unexpected entry or link is present. See `docs/SNAPSHOT_BUILDER.md`. It does not launch Sandbox or execute commands.
  12. **2D-6.3b — Sandbox execution trust design (in progress; design-only):** define a trustworthy host/guest result channel and privilege separation before writing an executor. A guest-writable report cannot be treated as authentic when untrusted test code can forge it. See `docs/WINDOWS_SANDBOX_EXECUTOR_TRUST_MODEL.md`. No Sandbox launch or test execution is authorized by this design stage.
  13. **2E — Apply and rollback (not implemented):** keep patch application behind a separate opt-in; independently validate paths immediately before apply; preserve the base SHA; on any failure discard only the disposable worktree. Record patch hash, checks, test commands and exit codes in a local audit record.
  14. **2F — Delivery (not implemented):** publish only a draft branch/PR after all gates pass. No auto-merge, release or deployment. Keep the entire Phase 2 feature disabled by default until end-to-end tests and a separate review pass.
- Phase 3 (continuous operation): do not enable a scheduled task until Phase 1 has passed on the actual Windows machine and the user has reviewed a local report.
- No paid APIs, subscriptions, production writes or external side effects without explicit approval.
