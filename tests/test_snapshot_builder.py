from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from local_agent.git_acquisition import GitAcquisitionResult, VerifiedBlobContent
from local_agent.git_blob_policy import GitBlobVerification
from local_agent.git_tree_policy import PinnedTreeMetadata, PinnedTreeObject
from local_agent.snapshot_builder import (
    SnapshotBuildError,
    SnapshotBuildResult,
    build_disposable_snapshot,
    cleanup_disposable_snapshot,
)


COMMIT = "a" * 40
CONTENT = b"snapshot-safe-content"
OID = hashlib.sha1(b"blob " + str(len(CONTENT)).encode("ascii") + b"\0" + CONTENT).hexdigest()
SHA = hashlib.sha256(CONTENT).hexdigest()
MANIFEST = "b" * 64


def acquisition():
    entry = PinnedTreeObject("src/app.py", "100644", "blob", OID, len(CONTENT))
    tree = PinnedTreeMetadata("sha1", (entry,), len(CONTENT))
    verification = GitBlobVerification("src/app.py", len(CONTENT), "sha1", OID, SHA, len(CONTENT))
    blob = VerifiedBlobContent("src/app.py", CONTENT, len(CONTENT), OID, "sha1", SHA)
    return GitAcquisitionResult(SimpleNamespace(), tree, (verification,), COMMIT, MANIFEST, (blob,))


def test_builds_exact_snapshot_and_cleanup_removes_only_owned_tree(tmp_path):
    source = tmp_path / "source"
    parent = tmp_path / "validation"
    source.mkdir()
    parent.mkdir()
    result = build_disposable_snapshot(acquisition(), validation_parent=parent, source_checkout=source)
    assert result.path.parent == parent
    assert (result.path / "src" / "app.py").read_bytes() == CONTENT
    assert (result.path / ".agent-snapshot-owner.json").is_file()
    cleanup_disposable_snapshot(result)
    assert not result.path.exists()
    assert source.is_dir()


def test_rejects_source_checkout_as_validation_parent(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(SnapshotBuildError, match="disjoint"):
        build_disposable_snapshot(acquisition(), validation_parent=source, source_checkout=source)


def test_rejects_relative_validation_parent(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(SnapshotBuildError, match="absolute"):
        build_disposable_snapshot(acquisition(), validation_parent="relative/path", source_checkout=source)


def test_rejects_symlinked_validation_parent(tmp_path):
    source = tmp_path / "source"
    real = tmp_path / "real"
    source.mkdir()
    real.mkdir()
    link = tmp_path / "linked"
    try:
        link.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is unavailable")
    with pytest.raises(SnapshotBuildError, match="symlink or reparse"):
        build_disposable_snapshot(acquisition(), validation_parent=link, source_checkout=source)


def test_rejects_tampered_blob_before_creating_directory(tmp_path):
    source = tmp_path / "source"
    parent = tmp_path / "validation"
    source.mkdir()
    parent.mkdir()
    original = acquisition()
    bad_blob = VerifiedBlobContent("src/app.py", CONTENT + b"x", len(CONTENT) + 1, OID, "sha1", SHA)
    bad = GitAcquisitionResult(original.inspection, original.tree, original.blob_verifications,
                               original.pinned_commit, original.manifest_sha256, (bad_blob,))
    with pytest.raises(SnapshotBuildError, match="digest verification"):
        build_disposable_snapshot(bad, validation_parent=parent, source_checkout=source)
    assert list(parent.iterdir()) == []


def test_cleanup_refuses_unexpected_files_and_preserves_directory(tmp_path):
    source = tmp_path / "source"
    parent = tmp_path / "validation"
    source.mkdir()
    parent.mkdir()
    result = build_disposable_snapshot(acquisition(), validation_parent=parent, source_checkout=source)
    (result.path / "unexpected.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(SnapshotBuildError, match="unexpected entries"):
        cleanup_disposable_snapshot(result)
    assert (result.path / "unexpected.txt").read_text(encoding="utf-8") == "keep"


def test_cleanup_requires_matching_ownership_receipt(tmp_path):
    source = tmp_path / "source"
    parent = tmp_path / "validation"
    source.mkdir()
    parent.mkdir()
    result = build_disposable_snapshot(acquisition(), validation_parent=parent, source_checkout=source)
    forged = SnapshotBuildResult(result.path, result.commit, result.manifest_sha256, "0" * 64, result.files)
    with pytest.raises(SnapshotBuildError, match="does not match"):
        cleanup_disposable_snapshot(forged)
    assert result.path.exists()
    cleanup_disposable_snapshot(result)


def test_rejects_unsafe_cleanup_receipt_path(tmp_path):
    source = tmp_path / "source"
    parent = tmp_path / "validation"
    source.mkdir()
    parent.mkdir()
    result = build_disposable_snapshot(acquisition(), validation_parent=parent, source_checkout=source)
    forged = SnapshotBuildResult(result.path, result.commit, result.manifest_sha256,
                                 result.owner_token, ("../outside.txt",))
    with pytest.raises(ValueError):
        cleanup_disposable_snapshot(forged)
    cleanup_disposable_snapshot(result)
