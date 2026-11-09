from pathlib import Path

import pytest

from local_agent.engine import AgentError, PROJECT_ID, local_ollama_base_url, safe_read


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
