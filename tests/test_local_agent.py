import json
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest

from local_agent.engine import (
    AgentError, PROJECT_ID, _open_local_ollama, load_config,
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
    assert len(proxies) == 1
    assert proxies[0].proxies == {}


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
