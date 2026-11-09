from __future__ import annotations

from pathlib import Path

import pytest

from local_agent.git_inspector import (
    GitInspectionError,
    inspect_registered_worktree,
)


ORIGIN = "https://github.com/example/project.git"
HEAD = "a" * 40


def _fixture(tmp_path, monkeypatch, *, dirty="", origin=ORIGIN, registered=True, head=HEAD):
    source = tmp_path / "source"
    candidate = tmp_path / "candidate"
    common = tmp_path / "shared.git"
    source.mkdir()
    candidate.mkdir()
    common.mkdir()
    monkeypatch.setattr("local_agent.git_inspector.shutil.which", lambda name: "/usr/bin/git")

    def runner(argv, cwd, env, timeout):
        args = argv[3:]
        if args == ["rev-parse", "--show-toplevel"]:
            return str(cwd)
        if args == ["config", "--get", "remote.origin.url"]:
            return origin
        if args == ["rev-parse", "--git-common-dir"]:
            return str(common)
        if args == ["worktree", "list", "--porcelain"]:
            paths = [source]
            if registered:
                paths.append(candidate)
            return "\n\n".join(f"worktree {p}\nHEAD {HEAD}" for p in paths)
        if args == ["rev-parse", "--verify", "HEAD"]:
            return head
        if args == ["status", "--porcelain=v1", "--untracked-files=all", "--ignore-submodules=none"]:
            return dirty
        raise AssertionError(f"Unexpected Git command: {args!r}")

    return source, candidate, runner


def _inspect(source, candidate, runner, **kwargs):
    return inspect_registered_worktree(
        source,
        candidate,
        expected_origin=ORIGIN,
        pinned_commit=HEAD,
        _runner=runner,
        **kwargs,
    )


def test_accepts_registered_clean_worktree_with_exact_identity(tmp_path, monkeypatch):
    source, candidate, runner = _fixture(tmp_path, monkeypatch)
    result = _inspect(source, candidate, runner)
    assert result.clean is True
    assert result.registered is True
    assert result.pinned_commit == HEAD
    assert result.expected_origin == ORIGIN


def test_rejects_wrong_source_origin(tmp_path, monkeypatch):
    source, candidate, runner = _fixture(tmp_path, monkeypatch, origin="https://wrong.invalid/repo.git")
    with pytest.raises(GitInspectionError, match="origin"):
        _inspect(source, candidate, runner)


def test_rejects_unregistered_candidate(tmp_path, monkeypatch):
    source, candidate, runner = _fixture(tmp_path, monkeypatch, registered=False)
    with pytest.raises(GitInspectionError, match="not registered"):
        _inspect(source, candidate, runner)


def test_rejects_wrong_pinned_head(tmp_path, monkeypatch):
    source, candidate, runner = _fixture(tmp_path, monkeypatch, head="b" * 40)
    with pytest.raises(GitInspectionError, match="pinned commit"):
        _inspect(source, candidate, runner)


def test_rejects_dirty_worktree_including_untracked(tmp_path, monkeypatch):
    source, candidate, runner = _fixture(tmp_path, monkeypatch, dirty="?? untracked.txt")
    with pytest.raises(GitInspectionError, match="not clean"):
        _inspect(source, candidate, runner)


def test_rejects_nested_roots_before_git_invocation(tmp_path, monkeypatch):
    source, candidate, runner = _fixture(tmp_path, monkeypatch)
    nested = source / "nested"
    nested.mkdir()
    with pytest.raises(GitInspectionError, match="separate sibling"):
        _inspect(source, nested, runner)


@pytest.mark.parametrize("origin,head,timeout", [
    ("", HEAD, 10),
    (ORIGIN, "not-a-full-sha", 10),
    (ORIGIN, HEAD, 0),
    (ORIGIN, HEAD, 31),
])
def test_rejects_invalid_identity_or_timeout(tmp_path, monkeypatch, origin, head, timeout):
    source, candidate, runner = _fixture(tmp_path, monkeypatch)
    with pytest.raises(GitInspectionError):
        inspect_registered_worktree(
            source, candidate, expected_origin=origin, pinned_commit=head,
            timeout_seconds=timeout, _runner=runner,
        )


def test_never_accepts_arbitrary_command_from_caller(tmp_path, monkeypatch):
    source, candidate, runner = _fixture(tmp_path, monkeypatch)
    seen = []

    def recording_runner(argv, cwd, env, timeout):
        seen.append(argv[3:])
        return runner(argv, cwd, env, timeout)

    _inspect(source, candidate, recording_runner)
    assert all(args[0] in {"rev-parse", "config", "worktree", "status"} for args in seen)
    assert all("fetch" not in args and "checkout" not in args and "reset" not in args for args in seen)
