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

## Findings from the official Windows interfaces

Microsoft documents two relevant command paths:

- The native Windows Sandbox CLI (`wsb`) can execute a command and return its
  exit code. It supports `ExistingLogin` and `System` run-as contexts. However,
  its documentation explicitly says process I/O is not supported, so command
  stdout/stderr cannot be retrieved through that interface. An active user
  session is required for `ExistingLogin`. See
  [Windows Sandbox command-line interface](https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-cli).
- The Microsoft `winapp` Sandbox workflow can forward guest process streams,
  but its documentation says apps and workflows share the same guest user,
  desktop, registry, packages, runtimes and network access and can interfere
  with each other. Its preparation also adds shared bootstrap folders, a guest
  agent, Developer Mode and an inbound firewall rule. That is not an acceptable
  default trust boundary for mutually untrusted test code in this project.
  See [Windows Sandbox execution](https://learn.microsoft.com/en-us/windows/apps/dev-tools/winapp-cli/sandbox-execution).

Microsoft also warns that changes to host folders mapped with write permission
persist after the Sandbox is disposed, and documents that LogonCommand runs
under the Sandbox container user, which should be an administrator account.
See [Use and configure Windows Sandbox](https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-configure-using-wsb-file).

## Candidate narrow result channel — not yet approved

The native `wsb exec` exit code may provide a limited pass/fail signal without
returning stdout/stderr. A possible design to investigate is:

1. Launch a fixed, trusted guest bootstrap as `System` through `wsb exec`.
2. Keep the pinned source snapshot read-only.
3. Run the untrusted test workload under a separately restricted guest token,
   not as the bootstrap's `System` identity.
4. Have the bootstrap return only a bounded exit status to the native CLI.
5. If diagnostic logs are required, use a separate host output directory whose
   ACLs are proven inaccessible to the test token; never trust a guest-writable
   report file merely because it has a checksum or nonce.

This is only a research hypothesis. The docs do not establish that the proposed
privilege separation, mapped-folder ACL behavior, bootstrap integrity, or
process-tree containment will work as required. Each must be proven on the
supported host. If those properties cannot be demonstrated, do not treat the
exit code or any guest-written report as authenticated evidence.

## Critical result-channel problem

A writable mapped output directory is not, by itself, trustworthy: the code
under test runs inside the same guest and could write, replace, or forge the
report. A report file, marker, JSON schema, checksum, or random nonce stored in
that same writable mapping does not solve this problem if the guest workload can
read or alter it.

Likewise, a successful launch of WindowsSandbox.exe is not evidence that a
validation command ran or passed. The host must distinguish the trusted
bootstrap's exit code from any value produced by the untrusted workload.

Therefore, no host-side patch decision, automatic approval, or success claim may
be based solely on an untrusted guest-writable report.

## Required design gates before execution

1. **Read-only input:** map the verified source snapshot read-only. Do not let
   test code modify the host snapshot or its ownership marker.
2. **Separate scratch:** keep temporary files and caches inside the guest's
   disposable local filesystem wherever possible.
3. **Authenticated result channel:** independently prove that the trusted
   bootstrap's exit status cannot be forged or bypassed by the test workload.
   Prove any separate output directory's ACLs from inside the actual guest.
4. **Least privilege:** run the test workload with fewer guest privileges than
   the trusted bootstrap and result collector, and prove that it cannot alter
   the collector, its process, its output channel, or its credentials.
5. **Fixed commands only:** select exact argv vectors from the trusted local
   validation registry. No model-generated shell strings, command interpolation,
   or arbitrary LogonCommand values.
6. **Process containment:** prove that timeout stops the exact Sandbox instance
   and all guest child processes. A timeout, guest crash, malformed response,
   missing completion marker, or host shutdown is always a failure.
7. **Fail-closed host lifecycle:** launch only after explicit local opt-in;
   verify the exact profile and snapshot identity before launch; never fall back
   to ordinary host subprocess execution; clean up only with the existing
   ownership receipt and exact-tree reconciliation.
8. **Actual-host validation:** verify feature availability and a successful
   launch/exec/stop cycle on the user's Windows machine before enabling any
   execution path. Hosted CI unit tests cannot prove this.

## Explicit non-goals

This design does not authorize Sandbox launch, test execution, patch application,
commit, push, merge, deployment, scheduled operation, or production changes.
It does not assume Windows Sandbox provides a guest attestation API.

## Decision rule

If the result channel and privilege separation cannot be demonstrated with
supported, free, locally available Windows features, retain Phase 2 in disabled
mode and report guest test output as untrusted advisory evidence only.
