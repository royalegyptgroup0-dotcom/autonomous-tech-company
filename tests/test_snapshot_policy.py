from __future__ import annotations
import pytest
from local_agent.snapshot_policy import SnapshotLimits, SnapshotPolicyError, validate_snapshot_manifest

COMMIT = "a" * 40


def _entry(path="src/app.py", size=12, mode="100644", kind="blob"):
    return {"path": path, "mode": mode, "type": kind, "size": size}


def _validate(entries=None, allowed=None, **kwargs):
    return validate_snapshot_manifest(
        commit=COMMIT,
        tree_entries=entries if entries is not None else [_entry()],
        allowed_paths=allowed if allowed is not None else {"src/app.py"},
        **kwargs,
    )


def test_accepts_exact_regular_file_and_returns_stable_digest():
    result = _validate()
    assert result.entries[0].path == "src/app.py"
    assert result.total_bytes == 12
    assert result.sha256 == _validate().sha256
    assert len(result.sha256) == 64


@pytest.mark.parametrize("path", [
    "../outside.py", "/absolute.py", "C:/outside.py", "src\\outside.py",
    "src//double.py", "src/./dot.py", "src/a b.py", "src/CON", "src/nul.txt",
    "src/COM1.log", "src/LPT³", ".env", ".env.local", ".git/config",
    ".ssh/id_rsa", ".aws/credentials", "secrets/key.txt", "config/.netrc",
    "src/private/cert.pem", "src/signing.key", "node_modules/pkg/index.js",
    "src/file.py:stream",
])
def test_rejects_unsafe_or_sensitive_paths(path):
    with pytest.raises(SnapshotPolicyError):
        _validate(entries=[_entry(path)], allowed={path})


@pytest.mark.parametrize(("mode", "kind"), [
    ("120000", "blob"), ("160000", "commit"), ("040000", "tree"),
    ("100644", "tree"), ("100755", "commit"),
])
def test_rejects_symlink_submodule_tree_and_non_blob_entries(mode, kind):
    with pytest.raises(SnapshotPolicyError, match="regular Git file blobs"):
        _validate(entries=[_entry(mode=mode, kind=kind)])


def test_rejects_path_not_in_exact_allowlist():
    with pytest.raises(SnapshotPolicyError, match="outside the exact allowlist"):
        _validate(entries=[_entry("src/other.py")], allowed={"src/app.py"})


def test_rejects_missing_allowlisted_path():
    with pytest.raises(SnapshotPolicyError, match="missing"):
        _validate(entries=[_entry("src/other.py")], allowed={"src/app.py", "src/other.py"})


def test_rejects_duplicate_paths_and_case_collisions():
    with pytest.raises(SnapshotPolicyError, match="Duplicate tree path"):
        _validate(entries=[_entry(), _entry()])
    with pytest.raises(SnapshotPolicyError, match="case-colliding"):
        _validate(entries=[_entry("src/App.py"), _entry("src/app.py")],
                  allowed={"src/App.py", "src/app.py"})


def test_rejects_bad_schema_and_unexpected_metadata():
    bad = {"path": "src/app.py", "mode": "100644", "type": "blob", "size": 1, "extra": True}
    with pytest.raises(SnapshotPolicyError, match="exact metadata schema"):
        _validate(entries=[bad])


@pytest.mark.parametrize("size", [-1, True, "12"])
def test_rejects_invalid_sizes(size):
    with pytest.raises(SnapshotPolicyError, match="non-negative integer"):
        _validate(entries=[_entry(size=size)])


def test_enforces_per_file_and_total_size_limits():
    with pytest.raises(SnapshotPolicyError, match="per-file"):
        _validate(entries=[_entry(size=2_000_001)])
    entries = [_entry("src/a.py", 1_000_000), _entry("src/b.py", 1_000_000)]
    with pytest.raises(SnapshotPolicyError, match="total byte"):
        _validate(entries=entries, allowed={"src/a.py", "src/b.py"},
                  limits=SnapshotLimits(max_total_bytes=1_500_000))


def test_rejects_case_colliding_allowlist():
    with pytest.raises(SnapshotPolicyError, match="case-colliding"):
        _validate(allowed={"src/App.py", "src/app.py"})


@pytest.mark.parametrize("commit", ["", "main", "abc", "g" * 40, "a" * 39])
def test_requires_full_pinned_git_object_id(commit):
    with pytest.raises(SnapshotPolicyError, match="full pinned"):
        validate_snapshot_manifest(commit=commit, tree_entries=[_entry()],
                                    allowed_paths={"src/app.py"})


def test_rejects_unbounded_or_boolean_limits():
    with pytest.raises(SnapshotPolicyError, match="safe default"):
        _validate(limits=SnapshotLimits(max_entries=True))
    with pytest.raises(SnapshotPolicyError, match="safe default"):
        _validate(limits=SnapshotLimits(max_total_bytes=99_000_000))


def test_rejects_string_instead_of_path_collection():
    with pytest.raises(SnapshotPolicyError, match="collection"):
        _validate(allowed="src/app.py")


def test_rejects_empty_manifest():
    with pytest.raises(SnapshotPolicyError, match="empty or exceeds"):
        _validate(entries=[])
