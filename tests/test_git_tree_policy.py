from __future__ import annotations

import pytest

from local_agent.git_tree_policy import GitTreePolicyError, parse_ls_tree_output


OID1 = "a" * 40
OID2 = "b" * 64


def _record(path="src/app.py", *, mode="100644", kind="blob", oid=OID1, size="12"):
    return f"{mode} {kind} {oid} {size}\t{path}".encode("utf-8") + b"\0"


def _parse(data=None, *, paths=("src/app.py",), algorithm="sha1", **kwargs):
    return parse_ls_tree_output(
        data if data is not None else _record(),
        expected_paths=paths,
        object_format=algorithm,
        **kwargs,
    )


def test_parses_exact_pinned_blob_metadata():
    result = _parse()
    item = result.entries[0]
    assert item.path == "src/app.py"
    assert item.mode == "100644"
    assert item.object_type == "blob"
    assert item.object_id == OID1
    assert item.size_bytes == 12
    assert result.total_bytes == 12
    assert result.snapshot_entries == ({
        "path": "src/app.py", "mode": "100644", "type": "blob", "size": 12
    },)


def test_accepts_sha256_repository_object_ids():
    result = _parse(_record(oid=OID2), algorithm="sha256")
    assert result.entries[0].object_id == OID2


def test_parses_multiple_records_and_sorts_paths():
    data = _record("src/z.py", size="3") + _record("src/a.py", size="4", oid="c" * 40)
    result = _parse(data, paths=("src/a.py", "src/z.py"))
    assert [item.path for item in result.entries] == ["src/a.py", "src/z.py"]
    assert result.total_bytes == 7


@pytest.mark.parametrize("record", [
    b"",
    b"100644 blob " + OID1.encode() + b" 12\tsrc/app.py",
    b"100644 blob " + OID1.encode() + b" 12 src/app.py\0",
    b"100644 blob " + OID1.encode() + b" 12\tsrc/app.py\0\0",
    b"100644 blob " + OID1.encode() + b" 12\tsrc/app.py\n\0",
    b"100644 blob " + OID1.encode() + b" 12\tbad-\xff.py\0",
])
def test_rejects_malformed_or_invalidly_encoded_records(record):
    with pytest.raises(GitTreePolicyError):
        _parse(record)


@pytest.mark.parametrize(("mode", "kind", "size"), [
    ("120000", "blob", "5"),
    ("160000", "commit", "-"),
    ("040000", "tree", "-"),
    ("100644", "tree", "-"),
])
def test_rejects_symlinks_submodules_and_trees(mode, kind, size):
    with pytest.raises(GitTreePolicyError, match="regular Git file blobs"):
        _parse(_record(mode=mode, kind=kind, size=size))


def test_rejects_wrong_oid_for_repository_format():
    with pytest.raises(GitTreePolicyError, match="object ID"):
        _parse(_record(oid="a" * 64))


@pytest.mark.parametrize("size", ["-1", "+1", "01", "1.0", "x", "2000001"])
def test_rejects_malformed_or_oversized_blob_sizes(size):
    with pytest.raises(GitTreePolicyError):
        _parse(_record(size=size))


def test_rejects_unexpected_missing_and_duplicate_paths():
    with pytest.raises(GitTreePolicyError, match="outside"):
        _parse(_record("src/other.py"))
    with pytest.raises(GitTreePolicyError, match="count"):
        _parse(_record(), paths=("src/app.py", "src/other.py"))
    with pytest.raises(GitTreePolicyError, match="count"):
        _parse(_record() + _record(), paths=("src/app.py",))


def test_rejects_case_collisions_and_unsafe_paths():
    with pytest.raises(GitTreePolicyError, match="case collisions"):
        _parse(paths=("src/App.py", "src/app.py"))
    with pytest.raises(GitTreePolicyError, match="unsafe"):
        _parse(_record("../outside.py"), paths=("../outside.py",))


def test_enforces_output_entry_and_total_byte_limits():
    with pytest.raises(GitTreePolicyError, match="byte limit"):
        _parse(max_output_bytes=8)
    with pytest.raises(GitTreePolicyError, match="entry limit"):
        _parse(max_entries=0)
    data = _record(size="12") + _record("src/other.py", size="12", oid="c" * 40)
    with pytest.raises(GitTreePolicyError, match="total file size"):
        _parse(data, paths=("src/app.py", "src/other.py"), max_total_bytes=20)


@pytest.mark.parametrize("value", ["sha1", ""])
def test_rejects_string_as_expected_path_collection(value):
    with pytest.raises(GitTreePolicyError, match="collection"):
        _parse(expected_paths=value)


def test_rejects_non_bytes_output_and_invalid_object_format():
    with pytest.raises(GitTreePolicyError, match="must be bytes"):
        _parse("not bytes")
    with pytest.raises(GitTreePolicyError, match="object format"):
        _parse(algorithm="md5")
