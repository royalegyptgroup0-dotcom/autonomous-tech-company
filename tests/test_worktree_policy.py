from __future__ import annotations

import pytest

from local_agent.worktree_policy import (
    WorktreePolicyError,
    validate_disposable_worktree,
)


def _layout(tmp_path):
    source = tmp_path / "source"
    worktree = tmp_path / "worktree"
    source.mkdir()
    worktree.mkdir()
    target = worktree / "src" / "module.py"
    target.parent.mkdir()
    target.write_text("safe = True\n", encoding="utf-8")
    return source, worktree, target


def test_accepts_separate_worktree_and_regular_allowlisted_file(tmp_path):
    source, worktree, _ = _layout(tmp_path)
    result = validate_disposable_worktree(
        worktree, source, allowed_paths={"src/module.py"}
    )
    assert result.root == worktree
    assert result.source_checkout == source
    assert result.checked_paths == ("src/module.py",)


@pytest.mark.parametrize("relation", ["same", "inside_source", "source_inside_worktree"])
def test_rejects_overlapping_checkout_roots(tmp_path, relation):
    source, worktree, _ = _layout(tmp_path)
    if relation == "same":
        candidate = source
    elif relation == "inside_source":
        candidate = source / "nested"
        candidate.mkdir()
    else:
        candidate = worktree
        source = worktree / "nested-source"
        source.mkdir()
    with pytest.raises(WorktreePolicyError, match="separate"):
        validate_disposable_worktree(
            candidate, source, allowed_paths={"src/module.py"}
        )


@pytest.mark.parametrize("path", ["../outside.py", "/absolute.py", "src/../outside.py", "src\\module.py", "C:/outside.py"])
def test_rejects_noncanonical_target_paths(tmp_path, path):
    source, worktree, _ = _layout(tmp_path)
    with pytest.raises(WorktreePolicyError):
        validate_disposable_worktree(worktree, source, allowed_paths={path})


def test_rejects_missing_target(tmp_path):
    source, worktree, _ = _layout(tmp_path)
    with pytest.raises(WorktreePolicyError, match="missing"):
        validate_disposable_worktree(
            worktree, source, allowed_paths={"src/missing.py"}
        )


def test_rejects_directory_as_file_target(tmp_path):
    source, worktree, _ = _layout(tmp_path)
    with pytest.raises(WorktreePolicyError, match="regular file"):
        validate_disposable_worktree(
            worktree, source, allowed_paths={"src"}
        )


def test_rejects_symlink_target(tmp_path):
    source, worktree, target = _layout(tmp_path)
    outside = tmp_path / "outside.py"
    outside.write_text("outside = True\n", encoding="utf-8")
    link = worktree / "src" / "linked.py"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is unavailable on this runner")
    with pytest.raises(WorktreePolicyError, match="Symlink"):
        validate_disposable_worktree(
            worktree, source, allowed_paths={"src/linked.py"}
        )


def test_rejects_symlinked_parent_directory(tmp_path):
    source, worktree, _ = _layout(tmp_path)
    outside_dir = tmp_path / "outside-dir"
    outside_dir.mkdir()
    (outside_dir / "module.py").write_text("outside = True\n", encoding="utf-8")
    linked_dir = worktree / "linked"
    try:
        linked_dir.symlink_to(outside_dir, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is unavailable on this runner")
    with pytest.raises(WorktreePolicyError, match="Symlink"):
        validate_disposable_worktree(
            worktree, source, allowed_paths={"linked/module.py"}
        )


def test_requires_nonempty_allowlist(tmp_path):
    source, worktree, _ = _layout(tmp_path)
    with pytest.raises(WorktreePolicyError, match="At least one"):
        validate_disposable_worktree(worktree, source, allowed_paths=set())
