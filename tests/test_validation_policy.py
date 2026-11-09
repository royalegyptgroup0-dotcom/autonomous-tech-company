import pytest

from local_agent.validation_policy import (
    ValidationPolicyError,
    build_validation_plan,
)


REGISTRY = [
    {
        "name": "python-tests",
        "argv": ["python", "-m", "pytest", "-q"],
        "timeout_seconds": 180,
        "max_output_bytes": 250_000,
    },
    {
        "name": "web-tests",
        "argv": ["node", "--test", "tests/navigation.test.cjs"],
        "timeout_seconds": 60,
        "max_output_bytes": 100_000,
    },
]


def test_selects_exact_registered_argv_and_stays_disabled():
    plan = build_validation_plan(REGISTRY, ["python-tests", "web-tests"])
    assert plan.commands[0].argv == ("python", "-m", "pytest", "-q")
    assert plan.commands[1].argv == ("node", "--test", "tests/navigation.test.cjs")
    assert plan.execution_enabled is False


def test_selection_order_is_preserved():
    plan = build_validation_plan(REGISTRY, ["web-tests", "python-tests"])
    assert [item.name for item in plan.commands] == ["web-tests", "python-tests"]


def test_rejects_unknown_or_model_invented_command():
    with pytest.raises(ValidationPolicyError, match="not present"):
        build_validation_plan(REGISTRY, ["python-tests", "curl-anything"])


def test_rejects_duplicate_registry_names():
    with pytest.raises(ValidationPolicyError, match="Duplicate"):
        build_validation_plan(REGISTRY + [REGISTRY[0]], ["python-tests"])


def test_rejects_extra_registry_keys():
    bad = [{**REGISTRY[0], "shell": True}]
    with pytest.raises(ValidationPolicyError, match="exact supported schema"):
        build_validation_plan(bad, ["python-tests"])


@pytest.mark.parametrize("argv", [
    [],
    ["python", "bad\\nargument"],
    ["python", "x" * 4097],
    ["python", *([ "x" ] * 64)],
])
def test_rejects_malformed_or_oversized_argv(argv):
    bad = [{**REGISTRY[0], "argv": argv}]
    with pytest.raises(ValidationPolicyError):
        build_validation_plan(bad, ["python-tests"])


@pytest.mark.parametrize("timeout", [0, 301, True, 1.5])
def test_rejects_unbounded_or_invalid_timeout(timeout):
    bad = [{**REGISTRY[0], "timeout_seconds": timeout}]
    with pytest.raises(ValidationPolicyError):
        build_validation_plan(bad, ["python-tests"])


@pytest.mark.parametrize("limit", [0, 1_000_001, True, 10.5])
def test_rejects_unbounded_or_invalid_output_limit(limit):
    bad = [{**REGISTRY[0], "max_output_bytes": limit}]
    with pytest.raises(ValidationPolicyError):
        build_validation_plan(bad, ["python-tests"])


def test_rejects_empty_or_duplicate_selection():
    with pytest.raises(ValidationPolicyError):
        build_validation_plan(REGISTRY, [])
    with pytest.raises(ValidationPolicyError, match="unique"):
        build_validation_plan(REGISTRY, ["python-tests", "python-tests"])


def test_rejects_string_instead_of_name_collection():
    with pytest.raises(ValidationPolicyError):
        build_validation_plan(REGISTRY, "python-tests")


def test_bounds_consumption_of_unbounded_iterable():
    def endless_names():
        while True:
            yield "python-tests"

    with pytest.raises(ValidationPolicyError, match="between 1 and 20"):
        build_validation_plan(REGISTRY, endless_names())
