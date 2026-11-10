# Phase 2D-6.3b — Windows Sandbox Executor Design

## Status
Design contract only. The executor is NOT implemented or enabled. No Sandbox is launched, no command is run, and no host checkout is modified by this document.

## Purpose
Define the safe bridge between the verified disposable snapshot (2D-6.3a), the restrictive Windows Sandbox profile, and the trusted local validation-command registry. The executor must fail closed; isolation failure must never fall back to host subprocess execution.

## Required inputs
- A live in-memory SnapshotBuildResult receipt from the snapshot builder.
- The source checkout path, used only for disjointness checks.
- A ValidationPlan created from trusted local configuration.
- Explicit bounded execution deadline and output budgets.

It must not accept model-generated shell text, arbitrary argv, arbitrary environment variables, caller-selected host folders, or user-supplied Sandbox profiles.

## Mandatory preflight gates
1. Host OS is Windows and Windows Sandbox is available and enabled.
2. The Sandbox executable resolves to the expected Windows system location; reject PATH-only or caller-overridden executables.
3. The snapshot receipt is valid; root and descendants are regular files/directories, contain no links or reparse points, and remain disjoint from the source checkout.
4. The snapshot ownership marker exactly matches the in-memory receipt. Reject any tree change since creation.
5. The validation plan is policy-produced, contains 1–20 registered commands, and has bounded aggregate time and output budgets.
6. The generated profile disables networking, clipboard, printer, audio and video redirection; enables ProtectedClient; and contains exactly one mapped folder.
7. The only mapped host folder is the disposable snapshot. Never map the source checkout, home directory, temp root, credentials, package cache, or other host folders.
8. The .wsb file is created exclusively in a private temporary directory with restrictive ACLs and removed only after Sandbox exits.

## Snapshot integrity prerequisite — blocking gap
The current snapshot receipt records the pinned commit, manifest digest, owner token and file paths, but does not expose a per-file size/SHA-256 inventory that a later executor can independently re-check. The current ownership marker likewise records paths but not per-file content digests. The snapshot builder verifies source blob bytes before writing and checks the resulting directory/file set, but that is not proof that the snapshot remains unchanged after creation.

Therefore, **do not implement or enable Sandbox launch against the current path-only profile API**. Before executor implementation:
- Extend the immutable snapshot receipt and ownership marker with the exact per-file relative path, byte size and SHA-256 digest inventory derived from verified Git blobs.
- Add a non-destructive verifier that validates the receipt schema, ownership marker, exact directory/file set, rejects links/reparse points and recomputes every file size and SHA-256 digest.
- Bind profile creation to the validated receipt rather than accepting an arbitrary snapshot path; revalidate immediately before creating/launching the profile to reduce time-of-check/time-of-use exposure.
- Add adversarial tests for modified bytes, same-size replacement, missing/extra files, forged marker, forged receipt, links/reparse points and source/snapshot overlap.
- Keep the executor disabled until this prerequisite and its tests are complete.

## Execution contract
- Commands run only inside Sandbox from a fixed in-sandbox bootstrap. The host never concatenates model text into a command line.
- The bootstrap resolves command names against the exact trusted registry payload and executes registered argv without a shell.
- Networking remains disabled. No package installation or dependency download is permitted during validation.
- Stdout/stderr are streamed through per-command and aggregate byte caps. Exceeding a cap terminates the run.
- Every command has a hard timeout and the run has a global deadline.
- Timeout, cancellation, output overflow, malformed result, unexpected file, process crash, or Sandbox exit without a complete verified result is failure.
- The host verifies run identifier, snapshot commit, manifest digest, command names, exit codes and output digests.
- Timeout/cancellation must terminate Sandbox as a process tree. If reliable process-tree termination cannot be demonstrated, keep the executor disabled.
- No direct host-side subprocess fallback is permitted for validation commands.

## Result and audit contract
Persist a bounded local audit record containing pinned commit, manifest digest, snapshot receipt identity (never the secret owner token), selected command names, timestamps, exit codes, timeout/overflow flags, and output hashes. Do not store environment secrets or unbounded raw output.

A successful executor result means only that selected validation commands completed in the disposable Sandbox. It does not authorize patch application, merge, release, deployment, or production writes.

## Required test matrix
### Pure unit tests (all platforms)
- Reject non-Windows host and invalid/missing Sandbox executable.
- Reject malformed, forged, expired or cleaned-up snapshot receipts.
- Reject modified snapshot files, unexpected files, links and reparse points.
- Reject source/snapshot overlap and any additional mapped folder.
- Reject arbitrary command argv and plans not produced by validation policy.
- Verify XML escaping and exact security settings.
- Verify output caps, aggregate budgets, timeout arithmetic and result schema.
- Verify every failure path returns failure and never invokes a host command.

### Windows integration tests (real Windows Sandbox required)
- Disabled feature, missing executable, and insufficient permissions fail closed.
- A benign deterministic command runs only inside Sandbox and returns verifiable output.
- Networking and clipboard are unavailable inside Sandbox.
- The source checkout and user profile are not visible inside Sandbox.
- Host snapshot remains limited to expected files plus declared outputs.
- Timeout/cancellation terminate Sandbox and all descendants.
- Sandbox crash, malformed result, output overflow and cleanup failure are handled safely.
- No ordinary host subprocess fallback occurs in any failure scenario.

## Enablement criteria
Do not connect the executor to the agent engine or enable unattended operation until implementation and adversarial unit tests pass; the full integration matrix passes on a real supported Windows machine; process-tree termination and private .wsb handling receive separate review; a local human-readable report is produced and reviewed; and Phase 2E patch application remains separately disabled pending its own review.

## Explicit non-goals
This phase does not apply patches, mutate worktrees, commit changes, create pull requests automatically, merge, release, deploy, access production systems, or perform unattended continuous operation.
