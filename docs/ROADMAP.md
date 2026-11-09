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
- Phase 2 (bounded code changes): remains disabled. Build and verify each gate in this order:
  1. **2A — Patch policy:** implement a standalone, non-applying unified-diff parser. Exact path allowlist; reject traversal, absolute paths, symlinks, renames, binaries, submodules, mode changes, protected paths and oversized patches. Unit tests must prove fail-closed behavior.
  2. **2B — Disposable worktree:** pin repository identity and base SHA; create a dedicated worktree outside the user's checkout; verify its initial clean state; never edit the configured source checkout.
  3. **2C — Isolated validation:** accept only locally configured test commands, never model-provided commands. Require OS-level network isolation, no inherited secrets, strict timeouts and bounded output before any test execution is enabled.
  4. **2D — Apply and rollback:** keep patch application behind a separate opt-in; independently validate paths immediately before apply; preserve the base SHA; on any failure discard only the disposable worktree. Record patch hash, checks, test commands and exit codes in a local audit record.
  5. **2E — Delivery:** publish only a draft branch/PR after all gates pass. No auto-merge, release or deployment. Keep the entire Phase 2 feature disabled by default until end-to-end tests and a separate review pass.
- Phase 3 (continuous operation): do not enable a scheduled task until Phase 1 has passed on the actual Windows machine and the user has reviewed a local report.
- No paid APIs, subscriptions, production writes or external side effects without explicit approval.
