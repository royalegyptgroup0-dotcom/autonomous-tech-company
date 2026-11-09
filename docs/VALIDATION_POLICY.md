# Phase 2D — Validation Plan Policy (planning-only)

## Purpose

Create a bounded validation plan from a trusted, local command registry. A model
or caller may select registered command names, but cannot provide or modify
command arguments. The policy copies the exact configured argument vector.

## Enforced limits

- At most 20 registered or selected commands.
- Exact registry schema: `name`, `argv`, `timeout_seconds`, `max_output_bytes`.
- Unique canonical names and unique requested selections.
- Argument vectors only; no shell field or shell command string.
- At most 64 arguments per command, 4,096 characters per argument and 16 KiB
  total UTF-8 argument data.
- Timeout between 1 and 300 seconds.
- Output limit between 1 byte and 1,000,000 bytes.
- Unknown names, malformed data, control characters and extra schema keys fail closed.

## Critical limitation

This is a planning and policy primitive only. It does **not** launch processes,
create a sandbox, block network access, remove secrets from an operating-system
process token, cap real process output, or provide a race-free filesystem view.
Every returned plan has `execution_enabled=False`.

No validation command may be executed until a separate Windows execution
boundary has been implemented and independently tested. That boundary must
demonstrate OS-enforced network denial, a minimal environment with no inherited
credentials, process-tree termination on timeout, bounded streaming output,
restricted filesystem access, and cleanup of only the disposable worktree.
A Python flag or caller-provided boolean is not proof of isolation.

## Tests

`tests/test_validation_policy.py` verifies exact argv selection, order
preservation, disabled execution, unknown command rejection, strict schema,
argument bounds, timeout/output limits and duplicate rejection.

## Activation state

Phase 2 remains disabled. This module is not connected to the Phase 1 runner,
does not execute tests and cannot authorize patch application or delivery.
