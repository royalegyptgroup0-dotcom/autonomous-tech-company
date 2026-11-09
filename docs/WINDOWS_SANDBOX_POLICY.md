# Phase 2D-2 — Windows Sandbox profile policy

## Implemented

`local_agent/sandbox_policy.py` validates two existing, absolute, non-symlink
(or Windows reparse-point-free) directory trees and returns a restrictive
Windows Sandbox (`.wsb`) XML profile. The source checkout and validation
snapshot must be disjoint. Exactly one host folder is mapped: the disposable
validation snapshot. The guest mapping is fixed at `C:\\Validation`.

The profile disables networking, clipboard redirection, printer redirection,
audio input, video input and vGPU, and enables Protected Client. The mapping is
writable only because test tools may need temporary files and caches. No source
checkout, home directory, credential folder, or other host path is mapped.
No logon command or arbitrary command string is embedded.

The read-only prerequisite script,
`scripts/Test-LocalAgentPrerequisites.ps1`, now reports Windows edition,
hypervisor presence, firmware virtualization and the Windows Sandbox optional
feature state when the relevant Windows query commands are available. It never
enables a feature or changes system settings.

## Important limits

This is a profile builder and capability preflight only. It does not create a
validation snapshot, copy files, apply patches, write a `.wsb` file, launch
Windows Sandbox, execute commands, enforce cleanup, or prove the host can
successfully start Sandbox. Feature-state queries can be unavailable or require
elevation; an unknown result is not a pass. Protected Client compatibility must
be checked on the actual Windows host before use. A generated profile is not
evidence that the sandbox successfully started or that a test passed.

The future executor must:
1. Create a fresh disposable snapshot from a pinned revision without copying
   credentials, Git hooks, local configuration, or unrelated host files.
2. Verify the snapshot is outside and disjoint from the source checkout.
3. Generate and inspect this profile, then launch Sandbox only after a separate
   explicit enablement gate.
4. Run only exact command vectors selected by `validation_policy.py`, with
   bounded streaming output and a process-tree timeout.
5. Treat every sandbox exit, timeout, malformed result, or missing completion
   marker as failure; never infer success from process launch.
6. Close the sandbox and delete only the uniquely-created disposable snapshot
   after verifying its exact path and ownership.

Windows Sandbox is optional and may be unavailable on Windows Home or on hosts
without the required virtualization support. If unavailable, fail closed; do
not silently fall back to ordinary subprocess execution or a paid service.

## Tests

`tests/test_sandbox_policy.py` checks the XML policy, single-folder mapping,
disabled host redirections, source/snapshot separation, missing paths, relative
paths, parent traversal and symlink rejection. These are unit tests; they do
not start Sandbox. CI validates the PowerShell script syntax on Windows.
