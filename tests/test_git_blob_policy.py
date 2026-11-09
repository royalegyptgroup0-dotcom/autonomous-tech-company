from __future__ import annotations

import hashlib
import io

import pytest

from local_agent.git_blob_policy import GitBlobPolicyError, verify_git_blob_stream


CONTENT = b"hello world"


def _git_oid(content: bytes, algorithm: str) -> str:
    header = f"blob {len(content)}".encode("ascii") + bytes((0,))
    return hashlib.new(algorithm, header + content).hexdigest()


def _verify(content=CONTENT, *, algorithm="sha1", **overrides):
    values = {
        "path": "src/app.py",
        "expected_size": len(content),
        "expected_git_oid": _git_oid(content, algorithm),
        "expected_sha256": hashlib.sha256(content).hexdigest(),
        "object_format": algorithm,
    }
    values.update(overrides)
    return verify_git_blob_stream(io.BytesIO(content), **values)


@pytest.mark.parametrize("algorithm", ["sha1", "sha256"])
def test_verifies_git_blob_oid_and_archive_sha256(algorithm):
    result = _verify(algorithm=algorithm)
    assert result.path == "src/app.py"
    assert result.size_bytes == len(CONTENT)
    assert result.git_object_id == _git_oid(CONTENT, algorithm)
    assert result.sha256 == hashlib.sha256(CONTENT).hexdigest()
    assert result.bytes_read == len(CONTENT)


def test_rejects_git_oid_mismatch():
    with pytest.raises(GitBlobPolicyError, match="object ID"):
        _verify(expected_git_oid="0" * 40)


def test_rejects_archive_digest_mismatch():
    with pytest.raises(GitBlobPolicyError, match="archive SHA-256"):
        _verify(expected_sha256="0" * 64)


def test_rejects_truncated_and_oversized_streams():
    with pytest.raises(GitBlobPolicyError, match="ended"):
        _verify(
            content=CONTENT[:-1],
            expected_size=len(CONTENT),
            expected_git_oid=_git_oid(CONTENT, "sha1"),
            expected_sha256=hashlib.sha256(CONTENT).hexdigest(),
        )
    with pytest.raises(GitBlobPolicyError, match="beyond"):
        _verify(content=CONTENT + b"x")


@pytest.mark.parametrize(("algorithm", "oid"), [
    ("sha1", "0" * 64), ("sha256", "0" * 40), ("md5", "0" * 32),
])
def test_rejects_wrong_object_format_or_oid_length(algorithm, oid):
    with pytest.raises(GitBlobPolicyError):
        _verify(object_format=algorithm, expected_git_oid=oid)


@pytest.mark.parametrize("path", ["../outside.py", "src\\outside.py", ".env", "src/CON"])
def test_rejects_unsafe_paths(path):
    with pytest.raises(GitBlobPolicyError, match="Unsafe"):
        _verify(path=path)


@pytest.mark.parametrize("kwargs", [
    {"expected_size": True},
    {"expected_size": -1},
    {"max_chunk_bytes": 0},
    {"max_chunk_bytes": 65_537},
    {"max_file_bytes": 2_000_001},
])
def test_rejects_invalid_limits(kwargs):
    with pytest.raises(GitBlobPolicyError):
        _verify(**kwargs)


def test_rejects_non_binary_stream():
    class TextStream:
        def read(self, size=-1):
            return "hello"
    with pytest.raises(GitBlobPolicyError, match="return bytes"):
        verify_git_blob_stream(
            TextStream(), path="src/app.py", expected_size=len(CONTENT),
            expected_git_oid=_git_oid(CONTENT, "sha1"),
            expected_sha256=hashlib.sha256(CONTENT).hexdigest(),
            object_format="sha1",
        )

def test_accepts_empty_git_blob():
    empty = b""
    result = _verify(
        content=empty,
        expected_git_oid=_git_oid(empty, "sha1"),
        expected_sha256=hashlib.sha256(empty).hexdigest(),
    )
    assert result.bytes_read == 0
    assert result.size_bytes == 0
