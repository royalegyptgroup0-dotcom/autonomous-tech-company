# Phase 2D-6.3b — Windows Sandbox Execution Trust Boundary

## Status

Design gate only. No Sandbox profile is written, no process is launched, no test
command is executed, and no runner integration or unattended activation occurs.

## Existing controls

The current profile policy disables networking, clipboard, printer, audio/video
input and vGPU; enables Protected Client; and maps only one disjoint disposable
snapshot. The snapshot builder creates a unique directory from independently
verified Git blobs, writes an ownership marker, reconciles the exact tree, and
refuses cleanup when it cannot prove exact ownership.

These are useful containment and integrity controls, but they do not establish
that a test result returned by a guest is authentic.

## Critical result-channel problem

A future guest bootstrap needs a way to return command results to the host.
Windows Sandbox currently has no implemented authenticated host/guest result
channel in this project.

A writable mapped output directory is not, by itself, trustworthy: the code
under test runs inside the same guest and could write, replace, or forge the
report. A report file, marker, JSON schema, checksum, or random nonce stored in
that same writable mapping does not solve this problem if the guest workload can
read or alter it.

Likewise, a successful launch of WindowsSandbox.exe is not evidence that a
validation command ran or passed. Closing the Sandbox process is not a
substitute for a verified child-process exit code.

Therefore, no host-side patch decision, automatic approval, or success claim may
be based solely on an untrusted guest-writable report.

## Required design gates before execution

1. **Read-only input:** map the verified source snapshot read-only. Do not let
   test code modify the host snapshot or its ownership marker.
2. **Separate scratch:** keep temporary files and caches inside the guest's
   disposable local filesystem wherever possible.
3. **Authenticated result channel:** design and independently review a host/guest
   result mechanism that test code cannot write, replace, impersonate, or
   bypass. If no defensible channel is available with the supported Windows
   Sandbox interfaces, stop at manual/advisory validation rather than inventing
   an attestation mechanism.
4. **Least privilege:** run the test workload with fewer guest privileges than
   the trusted bootstrap and result collector, and prove that it cannot alter
   the collector, its process, its output channel, or its credentials.
5. **Fixed commands only:** select exact argv vectors from the trusted local
   validation registry. No model-generated shell strings, command interpolation,
   or arbitrary LogonCommand values.
6. **Process containment:** prove that timeout terminates the entire guest test
   process tree and that a timeout, guest crash, malformed response, missing
   completion marker, or host shutdown is always a failure.
7. **Fail-closed host lifecycle:** launch only after explicit local opt-in;
   verify the exact profile and snapshot identity before launch; never fall back
   to ordinary host subprocess execution; clean up only with the existing
   ownership receipt and exact-tree reconciliation.
8. **Actual-host validation:** verify feature availability and a successful
   launch/close cycle on the user's Windows machine before enabling any
   execution path. Hosted CI unit tests cannot prove this.

## Explicit non-goals

This design does not authorize Sandbox launch, test execution, patch application,
commit, push, merge, deployment, scheduled operation, or production changes.
It does not assume Windows Sandbox provides a guest attestation API.

## Decision rule

If the result channel and privilege separation cannot be demonstrated with
supported, free, locally available Windows features, retain Phase 2 in disabled
mode and report guest test output as untrusted advisory evidence only.
