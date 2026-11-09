"""Build a bounded validation plan from trusted local configuration only.

This module does not execute commands and cannot enable validation. It rejects
model-supplied command data by accepting only names selected from a local,
explicit command registry and copying the registry's exact argv.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import islice
from typing import Iterable, Mapping, Sequence


class ValidationPolicyError(ValueError):
    """Raised when a local validation plan violates policy."""


@dataclass(frozen=True)
class ValidationCommand:
    name: str
    argv: tuple[str, ...]
    timeout_seconds: int
    max_output_bytes: int


@dataclass(frozen=True)
class ValidationPlan:
    commands: tuple[ValidationCommand, ...]
    execution_enabled: bool = False


_MAX_COMMANDS = 20
_MAX_ARGV_ITEMS = 64
_MAX_ARG_LENGTH = 4096
_MAX_TOTAL_ARG_BYTES = 16_384
_MAX_TIMEOUT_SECONDS = 300
_MAX_OUTPUT_BYTES = 1_000_000


def _validate_argv(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not value or len(value) > _MAX_ARGV_ITEMS:
        raise ValidationPolicyError(f"Command {name!r} must have a bounded, non-empty argv list")
    result: list[str] = []
    total = 0
    for item in value:
        if not isinstance(item, str) or not item or len(item) > _MAX_ARG_LENGTH:
            raise ValidationPolicyError(f"Command {name!r} contains an invalid argument")
        if any(ord(char) < 32 or ord(char) == 127 for char in item):
            raise ValidationPolicyError(f"Command {name!r} contains a control character")
        total += len(item.encode("utf-8"))
        if total > _MAX_TOTAL_ARG_BYTES:
            raise ValidationPolicyError(f"Command {name!r} argv is too large")
        result.append(item)
    return tuple(result)


def build_validation_plan(
    local_registry: Sequence[Mapping[str, object]],
    requested_names: Iterable[str],
) -> ValidationPlan:
    """Select exact preconfigured commands; never accept caller-supplied argv.

    The registry must be loaded from trusted local configuration. The caller
    may request registered names only. Unknown keys, duplicate names, malformed
    argv, unbounded timeouts and output limits fail closed. The returned plan
    is descriptive only: execution_enabled is always False.
    """
    if not isinstance(local_registry, (list, tuple)) or len(local_registry) > _MAX_COMMANDS:
        raise ValidationPolicyError("Local command registry must contain at most 20 entries")
    registry: dict[str, ValidationCommand] = {}
    allowed_keys = {"name", "argv", "timeout_seconds", "max_output_bytes"}

    for entry in local_registry:
        if not isinstance(entry, Mapping) or set(entry) != allowed_keys:
            raise ValidationPolicyError("Each local command must use the exact supported schema")
        name = entry["name"]
        if not isinstance(name, str) or not name or len(name) > 80 or name.strip() != name:
            raise ValidationPolicyError("Command names must be non-empty canonical strings")
        if any(ord(char) < 32 or ord(char) == 127 for char in name):
            raise ValidationPolicyError("Command names cannot contain control characters")
        if name in registry:
            raise ValidationPolicyError(f"Duplicate local command name: {name}")
        argv = _validate_argv(entry["argv"], name)
        timeout = entry["timeout_seconds"]
        output_limit = entry["max_output_bytes"]
        if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= _MAX_TIMEOUT_SECONDS:
            raise ValidationPolicyError(f"Command {name!r} timeout must be between 1 and 300 seconds")
        if not isinstance(output_limit, int) or isinstance(output_limit, bool) or not 1 <= output_limit <= _MAX_OUTPUT_BYTES:
            raise ValidationPolicyError(f"Command {name!r} output limit must be between 1 and 1000000 bytes")
        registry[name] = ValidationCommand(name, argv, timeout, output_limit)

    if isinstance(requested_names, (str, bytes)):
        raise ValidationPolicyError("Requested commands must be a collection of registered names")
    try:
        # Consume at most one item beyond the configured limit. This also
        # prevents an unbounded or infinite caller-supplied iterable.
        names = tuple(islice(iter(requested_names), _MAX_COMMANDS + 1))
    except TypeError as exc:
        raise ValidationPolicyError("Requested commands must be iterable") from exc
    if not names or len(names) > _MAX_COMMANDS:
        raise ValidationPolicyError("Select between 1 and 20 registered commands")
    if any(not isinstance(name, str) or not name for name in names):
        raise ValidationPolicyError("Requested command names must be non-empty strings")
    if len(set(names)) != len(names):
        raise ValidationPolicyError("Requested command names must be unique")
    unknown = [name for name in names if name not in registry]
    if unknown:
        raise ValidationPolicyError("Requested command is not present in the trusted local registry")

    return ValidationPlan(commands=tuple(registry[name] for name in names))
