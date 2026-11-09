from pathlib import Path

from local_agent.engine import PROJECT_ID, safe_read


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
