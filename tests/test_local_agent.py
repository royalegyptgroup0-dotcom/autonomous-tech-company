import json
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest

from local_agent.engine import (
    AgentError, PROJECT_ID, _NoRedirectHandler, _git_readonly, _open_local_ollama, collect_snapshot, load_config,
    local_ollama_base_url, safe_read,
)


def test_project_id_validation():
    assert PROJECT_ID.fullmatch("octopusa")
    assert PROJECT_ID.fullmatch("royal-media-player")
    assert not PROJECT_ID.fullmatch("../octopusa")
    assert not PROJECT_ID.fullmatch("A project")


def test_safe_read_allows_bounded_text(tmp_path: Path):
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    assert safe_read(tmp_path, "README.md") == "hello"


def test_safe_read_rejects_parent_traversal(tmp_path: Path):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("do not read", encoding="utf-8")
    assert safe_read(tmp_path, "../outside.txt") == ""


def test_safe_read_skips_secret_names(tmp_path: Path):
    (tmp_path / ".env").write_text("SECRET=value", encoding="utf-8")
    assert safe_read(tmp_path, ".env") == ""


def test_safe_read_rejects_absolute_path(tmp_path: Path):
    assert safe_read(tmp_path, str((tmp_path / "README.md").resolve())) == ""



def test_ollama_url_accepts_loopback_addresses():
    assert local_ollama_base_url("http://127.0.0.1:11434/") == "http://127.0.0.1:11434"
    assert local_ollama_base_url("http://[::1]:11434") == "http://[::1]:11434"


@pytest.mark.parametrize("url", [
    "https://127.0.0.1:11434",
    "http://localhost:11434",
    "http://192.0.2.10:11434",
    "http://user:pass@127.0.0.1:11434",
    "http://127.0.0.1:11434/api",
    "http://127.0.0.1:11434/?target=remote",
])
def test_ollama_url_rejects_non_loopback_or_ambiguous_urls(url):
    with pytest.raises(AgentError):
        local_ollama_base_url(url)



def test_local_ollama_opener_disables_environment_proxies(monkeypatch):
    captured = {}

    class DummyOpener:
        def open(self, request, timeout):
            captured["timeout"] = timeout
            return "opened"

    def fake_build_opener(*handlers):
        captured["handlers"] = handlers
        return DummyOpener()

    monkeypatch.setattr(urllib.request, "build_opener", fake_build_opener)
    assert _open_local_ollama("http://127.0.0.1:11434/api/tags", 8) == "opened"
    proxies = [h for h in captured["handlers"] if isinstance(h, urllib.request.ProxyHandler)]
    redirects = [h for h in captured["handlers"] if isinstance(h, urllib.request.HTTPRedirectHandler)]
    assert len(proxies) == 1
    assert proxies[0].proxies == {}
    assert len(redirects) == 1
    assert isinstance(redirects[0], _NoRedirectHandler)
    assert redirects[0].redirect_request(None, None, 302, "Found", {}, "http://203.0.113.10/") is None


def _write_agent_config(tmp_path: Path, workspace: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    root.mkdir()
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({
        "workspace": str(workspace),
        "projects": [{"id": "sample-repo", "path": str(root), "enabled": True}],
    }), encoding="utf-8")
    return config_path, root


def test_config_rejects_workspace_equal_to_repository(tmp_path, monkeypatch):
    config_path, root = _write_agent_config(tmp_path, tmp_path / "repo")
    monkeypatch.setattr(
        "local_agent.engine.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout=str(root)),
    )
    with pytest.raises(AgentError, match="repository root or its parent"):
        load_config(config_path)


def test_config_rejects_workspace_parent_of_repository(tmp_path, monkeypatch):
    config_path, root = _write_agent_config(tmp_path, tmp_path)
    monkeypatch.setattr(
        "local_agent.engine.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout=str(root)),
    )
    with pytest.raises(AgentError, match="repository root or its parent"):
        load_config(config_path)


def test_config_allows_dedicated_local_agent_workspace(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    workspace = root / ".local-agent"
    config_path, root = _write_agent_config(tmp_path, workspace)
    monkeypatch.setattr(
        "local_agent.engine.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout=str(root)),
    )
    config = load_config(config_path)
    assert config["workspace_path"] == workspace.resolve()



def test_example_config_does_not_enable_unverified_paths():
    example_path = Path(__file__).resolve().parents[1] / "config" / "agent.example.json"
    example = json.loads(example_path.read_text(encoding="utf-8"))
    assert example["projects"]
    assert all(project["enabled"] is False for project in example["projects"])
    assert all(project["path"] == "" for project in example["projects"])



def test_config_rejects_invalid_review_file_allowlist(tmp_path, monkeypatch):
    config_path, root = _write_agent_config(tmp_path, tmp_path / "outside")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["projects"][0]["review_files"] = "src/main.py"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setattr(
        "local_agent.engine.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout=str(root)),
    )
    with pytest.raises(AgentError, match="review_files"):
        load_config(config_path)



def test_config_rejects_more_than_50_review_files(tmp_path, monkeypatch):
    config_path, root = _write_agent_config(tmp_path, tmp_path / "outside")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["projects"][0]["review_files"] = [f"src/file_{i}.py" for i in range(51)]
    config_path.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setattr(
        "local_agent.engine.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout=str(root)),
    )
    with pytest.raises(AgentError, match="at most 50"):
        load_config(config_path)


def test_snapshot_is_bounded_and_does_not_collect_untracked_file_list(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("R" * 20000, encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs" / "ROADMAP.md").write_text("D" * 20000, encoding="utf-8")
    calls = []

    def fake_git(root_arg, *arguments, **kwargs):
        calls.append(arguments)
        output = "S" * 12000 if arguments[0] == "status" else "H" * 3000
        return SimpleNamespace(stdout=output)

    monkeypatch.setattr("local_agent.engine._git_readonly", fake_git)
    snapshot = collect_snapshot({
        "id": "sample-repo",
        "resolved_path": root,
        "review_files": [],
    })
    assert len(snapshot) <= 40000
    assert "\\nGIT STATUS:\\n" in snapshot
    assert "\\n\\nSOURCE FILES:\\n" in snapshot
    assert any("--untracked-files=no" in args for args in calls)


def test_snapshot_includes_only_explicitly_allowlisted_source_contents(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    source_dir = root / "src"
    source_dir.mkdir(parents=True)
    (source_dir / "allowed.py").write_text("SAFE_REVIEW_CONTENT = 42", encoding="utf-8")
    (source_dir / "not_allowed.py").write_text("DO_NOT_INCLUDE_THIS_CONTENT", encoding="utf-8")
    monkeypatch.setattr(
        "local_agent.engine.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout="mocked git output"),
    )
    snapshot = collect_snapshot({
        "id": "sample-repo",
        "resolved_path": root,
        "review_files": ["src/allowed.py"],
    })
    assert "SAFE_REVIEW_CONTENT = 42" in snapshot
    assert "DO_NOT_INCLUDE_THIS_CONTENT" not in snapshot


def test_config_defaults_to_installed_small_local_model_and_bounded_context(tmp_path, monkeypatch):
    config_path, root = _write_agent_config(tmp_path, tmp_path / "outside")
    monkeypatch.setattr(
        "local_agent.engine.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout=str(root)),
    )
    config = load_config(config_path)
    assert config["ollama"]["model"] == "qwen2.5:3b"
    assert config["ollama"]["context_length"] == 4096
    assert config["ollama"]["timeout_seconds"] == 300


@pytest.mark.parametrize("context_length", [0, 1024, 8192 + 1, "not-a-number"])
def test_config_rejects_unsafe_context_lengths(tmp_path, monkeypatch, context_length):
    config_path, root = _write_agent_config(tmp_path, tmp_path / "outside")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["ollama"] = {"context_length": context_length}
    config_path.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setattr(
        "local_agent.engine.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout=str(root)),
    )
    with pytest.raises(AgentError, match="context_length"):
        load_config(config_path)



def test_config_accepts_utf8_bom_from_windows_powershell(tmp_path, monkeypatch):
    config_path, root = _write_agent_config(tmp_path, tmp_path / "outside")
    config_path.write_text(
        json.dumps({
            "workspace": str(tmp_path / "outside"),
            "projects": [{"id": "sample-repo", "path": str(root), "enabled": True}],
        }),
        encoding="utf-8-sig",
    )
    monkeypatch.setattr(
        "local_agent.engine.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout=str(root)),
    )
    config = load_config(config_path)
    assert config["enabled_projects"][0]["id"] == "sample-repo"


def test_safe_read_blocks_git_metadata_and_common_credential_files(tmp_path: Path):
    for relative in (
        ".git/config",
        ".git/hooks/pre-commit",
        ".env.production",
        "certs/private.pem",
        "keys/signing.key",
        ".npmrc",
        ".netrc",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("sensitive material", encoding="utf-8")
        assert safe_read(tmp_path, relative) == ""


def test_git_readonly_disables_fsmonitor_and_strips_inherited_git_overrides(tmp_path, monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs["env"]
        return SimpleNamespace(stdout=str(tmp_path))

    monkeypatch.setenv("GIT_DIR", str(tmp_path / "attacker.git"))
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.fsmonitor")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "malicious-hook")
    monkeypatch.setattr("local_agent.engine.subprocess.run", fake_run)

    _git_readonly(tmp_path, "status", "--short", "--branch")

    assert captured["command"][:7] == [
        "git", "-c", "core.fsmonitor=false",
        "-c", "core.untrackedCache=false", "-C", str(tmp_path),
    ]
    assert captured["env"]["GIT_CONFIG_NOSYSTEM"] == "1"
    assert captured["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert not any(key.upper().startswith("GIT_") and key != "GIT_CONFIG_NOSYSTEM"
                   and key != "GIT_TERMINAL_PROMPT" for key in captured["env"])


def test_safe_read_rejects_symlink_escape(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside secret", encoding="utf-8")
    link = root / "linked.txt"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is not permitted on this host")
    assert safe_read(root, "linked.txt") == ""

def test_safe_read_rejects_symlink_directory_escape(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "private.txt").write_text("outside directory secret", encoding="utf-8")
    link = root / "linked-dir"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Directory symlink creation is not permitted on this host")
    assert safe_read(root, "linked-dir/private.txt") == ""
