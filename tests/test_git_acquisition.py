from __future__ import annotations

import hashlib
import sys
from types import SimpleNamespace

import pytest

from local_agent.archive_policy import ArchiveFileDigest, ArchiveInspection
from local_agent.snapshot_policy import validate_snapshot_manifest
import local_agent.git_acquisition as acquisition
from local_agent.git_acquisition import (
    GitAcquisitionError,
    _run_git_bounded,
    acquire_and_verify_pinned_blobs,
)


COMMIT = "a" * 40
CONTENT = b"hello pinned"
BLOB_OID = hashlib.sha1(b"blob " + str(len(CONTENT)).encode() + b"\0" + CONTENT).hexdigest()
TREE = (
    f"100644 blob {BLOB_OID} {len(CONTENT)}\tsrc/app.py".encode("ascii") + b"\0"
)
ARCHIVE_SHA256 = hashlib.sha256(CONTENT).hexdigest()
MANIFEST = validate_snapshot_manifest(
    commit=COMMIT,
    tree_entries=[{"path": "src/app.py", "mode": "100644", "type": "blob", "size": len(CONTENT)}],
    allowed_paths=["src/app.py"],
)


def _archive(*, sha256=ARCHIVE_SHA256, commit=COMMIT, manifest_sha256=MANIFEST.sha256, size=len(CONTENT), files=None):
    return ArchiveInspection(
        commit=commit,
        manifest_sha256=manifest_sha256,
        bytes_read=1024,
        total_file_bytes=size,
        files=tuple(files) if files is not None else (ArchiveFileDigest("src/app.py", size, sha256),),
    )


def _run_fake(argv, cwd, env, timeout, limit):
    args = argv[3:]
    if args[:2] == ["rev-parse", "--verify"]:
        return (COMMIT + "\n").encode()
    if args[:2] == ["rev-parse", "--show-object-format"]:
        return b"sha1\n"
    if args[:4] == ["ls-tree", "--full-tree", "-r", "-l"]:
        assert ":(literal)src/app.py" in args
        return TREE
    if args[:2] == ["cat-file", "blob"]:
        assert args[2] == BLOB_OID
        return CONTENT
    raise AssertionError(f"Unexpected Git command: {args!r}")


@pytest.fixture
def verified_inspection(monkeypatch, tmp_path):
    monkeypatch.setattr(acquisition.shutil, "which", lambda name: "git.exe")
    monkeypatch.setattr(
        acquisition,
        "inspect_registered_worktree",
        lambda *args, **kwargs: SimpleNamespace(
            worktree_root=tmp_path,
            pinned_commit=COMMIT,
            clean=True,
            registered=True,
        ),
    )


def _acquire(**overrides):
    args = {
        "source_checkout": ".",
        "candidate_worktree": ".",
        "expected_origin": "https://github.com/example/project.git",
        "pinned_commit": COMMIT,
        "allowed_paths": ["src/app.py"],
        "archive_inspection": _archive(),
        "_runner": _run_fake,
    }
    args.update(overrides)
    return acquire_and_verify_pinned_blobs(**args)


def test_acquires_exact_pinned_tree_and_verifies_blob(verified_inspection):
    result = _acquire()
    assert result.tree.entries[0].object_id == BLOB_OID
    assert result.tree.entries[0].size_bytes == len(CONTENT)
    assert result.blob_verifications[0].path == "src/app.py"
    assert result.blob_verifications[0].sha256 == ARCHIVE_SHA256
    assert result.blob_verifications[0].git_object_id == BLOB_OID


def test_rejects_archive_digest_mismatch(verified_inspection):
    with pytest.raises(GitAcquisitionError, match="verification failed"):
        _acquire(archive_inspection=_archive(sha256="0" * 64))


def test_rejects_archive_digest_path_set_mismatch_before_git(verified_inspection):
    with pytest.raises(GitAcquisitionError, match="exactly match"):
        _acquire(archive_inspection=_archive(files=()))


def test_rejects_invalid_pinned_commit_before_git(verified_inspection):
    with pytest.raises(GitAcquisitionError, match="full lowercase"):
        _acquire(pinned_commit="HEAD")


def test_rejects_invalid_timeout(verified_inspection):
    with pytest.raises(GitAcquisitionError, match="between 1 and 30"):
        _acquire(timeout_seconds=31)


def test_rejects_non_sha256_archive_digest(verified_inspection):
    with pytest.raises(GitAcquisitionError, match="full lowercase SHA-256"):
        _acquire(archive_inspection=_archive(sha256="not-a-digest"))


def test_rejects_archive_file_size_mismatch(verified_inspection):
    with pytest.raises(GitAcquisitionError, match="byte total"):
        _acquire(archive_inspection=_archive(size=len(CONTENT) + 1))


def test_rejects_unsafe_archive_inspection_path(verified_inspection):
    bad_file = ArchiveFileDigest("../outside.py", len(CONTENT), ARCHIVE_SHA256)
    with pytest.raises(GitAcquisitionError, match="unsafe path"):
        _acquire(archive_inspection=_archive(files=(bad_file,)))


def test_rejects_archive_inspection_for_different_commit(verified_inspection):
    with pytest.raises(GitAcquisitionError, match="differs"):
        _acquire(archive_inspection=_archive(commit="b" * 40))


def test_rejects_wrong_archive_manifest_digest(verified_inspection):
    with pytest.raises(GitAcquisitionError, match="manifest digest"):
        _acquire(archive_inspection=_archive(manifest_sha256="0" * 64))


def test_rejects_wrong_resolved_commit(verified_inspection):
    def wrong_commit(argv, cwd, env, timeout, limit):
        if argv[3:5] == ["rev-parse", "--verify"]:
            return (("b" * 40) + "\n").encode()
        return _run_fake(argv, cwd, env, timeout, limit)

    with pytest.raises(GitAcquisitionError, match="differs"):
        _acquire(_runner=wrong_commit)


def test_rejects_unexpected_git_object_format(verified_inspection):
    def wrong_format(argv, cwd, env, timeout, limit):
        if argv[3:5] == ["rev-parse", "--show-object-format"]:
            return b"sha512\n"
        return _run_fake(argv, cwd, env, timeout, limit)

    with pytest.raises(GitAcquisitionError, match="unsupported"):
        _acquire(_runner=wrong_format)


def test_bounded_runner_returns_small_stdout_without_shell(tmp_path):
    result = _run_git_bounded(
        [sys.executable, "-c", "print('bounded')"],
        tmp_path,
        {},
        3,
        100,
    )
    assert result.replace(b"\r\n", b"\n") == b"bounded\n"


def test_bounded_runner_rejects_stdout_overflow(tmp_path):
    with pytest.raises(GitAcquisitionError, match="output limit"):
        _run_git_bounded(
            [sys.executable, "-c", "print('x' * 10000)"],
            tmp_path,
            {},
            3,
            100,
        )


def test_bounded_runner_kills_timed_out_process(tmp_path):
    with pytest.raises(GitAcquisitionError, match="time limit"):
        _run_git_bounded(
            [sys.executable, "-c", "import time; time.sleep(3)"],
            tmp_path,
            {},
            1,
            100,
        )
