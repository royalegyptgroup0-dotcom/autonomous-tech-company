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
- Phase 2 (bounded code changes): remains disabled. Phase 2A is merged and cross-platform CI passed; Phase 2B now has a standalone filesystem preflight, but neither module is connected to the Phase 1 runner or any write operation. Build and verify each remaining gate in this order:
  1. **2A — Patch policy (merged; CI passed):** `local_agent/patch_policy.py` parses unified diffs without filesystem access or writes. It enforces exact allowlists and size/count limits; rejects traversal, absolute/ambiguous paths, credentials, protected paths, renames, copies, binaries, create/delete operations, submodules, mode changes, malformed hunks, Windows reserved device names and control characters. See `docs/PATCH_POLICY.md`.
  2. **2B — Disposable worktree (preflight primitive only):** `local_agent/worktree_policy.py` checks that candidate/source trees do not overlap and exact targets are existing regular files without symlink components. See `docs/WORKTREE_POLICY.md`. Git worktree creation, repository identity, pinned HEAD, clean-state verification and race-resistant use remain unimplemented.
  3. **2C — Isolated validation:** accept only locally configured test commands, never model-provided commands. Require OS-level network isolation, no inherited secrets, strict timeouts and bounded output before any test execution is enabled.
  4. **2D — Apply and rollback:** keep patch application behind a separate opt-in; independently validate paths immediately before apply; preserve the base SHA; on any failure discard only the disposable worktree. Record patch hash, checks, test commands and exit codes in a local audit record.
  5. **2E — Delivery:** publish only a draft branch/PR after all gates pass. No auto-merge, release or deployment. Keep the entire Phase 2 feature disabled by default until end-to-end tests and a separate review pass.
- Phase 3 (continuous operation): do not enable a scheduled task until Phase 1 has passed on the actual Windows machine and the user has reviewed a local report.
- No paid APIs, subscriptions, production writes or external side effects without explicit approval.
