import xml.etree.ElementTree as ET

import pytest

from local_agent.sandbox_policy import (
    SandboxPolicyError,
    build_windows_sandbox_profile,
)


def test_profile_disables_network_and_host_redirections(tmp_path):
    source = tmp_path / "source"
    snapshot = tmp_path / "validation-snapshot"
    source.mkdir()
    snapshot.mkdir()

    profile = build_windows_sandbox_profile(snapshot, source)
    root = ET.fromstring(profile.xml)

    assert root.findtext("Networking") == "Disable"
    assert root.findtext("ClipboardRedirection") == "Disable"
    assert root.findtext("PrinterRedirection") == "Disable"
    assert root.findtext("AudioInput") == "Disable"
    assert root.findtext("VideoInput") == "Disable"
    assert root.findtext("vGPU") == "Disable"
    assert root.findtext("ProtectedClient") == "Enable"
    mapped = root.findall("./MappedFolders/MappedFolder")
    assert len(mapped) == 1
    assert mapped[0].findtext("HostFolder") == str(snapshot)
    assert mapped[0].findtext("SandboxFolder") == r"C:\Validation"
    assert mapped[0].findtext("ReadOnly") == "false"
    assert root.find("LogonCommand") is None


def test_rejects_same_source_and_snapshot(tmp_path):
    source = tmp_path / "repo"
    source.mkdir()
    with pytest.raises(SandboxPolicyError, match="disjoint"):
        build_windows_sandbox_profile(source, source)


def test_rejects_snapshot_nested_inside_source(tmp_path):
    source = tmp_path / "repo"
    snapshot = source / ".validation"
    snapshot.mkdir(parents=True)
    with pytest.raises(SandboxPolicyError, match="disjoint"):
        build_windows_sandbox_profile(snapshot, source)


def test_rejects_source_nested_inside_snapshot(tmp_path):
    snapshot = tmp_path / "validation"
    source = snapshot / "source"
    source.mkdir(parents=True)
    with pytest.raises(SandboxPolicyError, match="disjoint"):
        build_windows_sandbox_profile(snapshot, source)


def test_rejects_missing_or_relative_paths(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(SandboxPolicyError, match="existing directory"):
        build_windows_sandbox_profile(tmp_path / "missing", source)
    with pytest.raises(SandboxPolicyError, match="absolute"):
        build_windows_sandbox_profile("relative-snapshot", source)


def test_rejects_symlinked_snapshot_component(tmp_path):
    source = tmp_path / "source"
    actual = tmp_path / "actual"
    link = tmp_path / "linked"
    source.mkdir()
    actual.mkdir()
    try:
        link.symlink_to(actual, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Directory symlinks are unavailable in this environment")
    with pytest.raises(SandboxPolicyError, match="symlink"):
        build_windows_sandbox_profile(link, source)
