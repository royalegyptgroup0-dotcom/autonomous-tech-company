"""Build a restrictive Windows Sandbox profile for a disposable snapshot.

This module only validates paths and returns XML. It never writes a .wsb file,
launches Windows Sandbox, copies source files, applies patches, or executes tests.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import stat
import xml.etree.ElementTree as ET


class SandboxPolicyError(ValueError):
    """Raised when a validation snapshot is unsafe to expose to a sandbox."""


@dataclass(frozen=True)
class SandboxProfile:
    host_snapshot: Path
    sandbox_folder: str
    xml: str
    networking: str = "Disable"
    clipboard_redirection: str = "Disable"
    protected_client: str = "Enable"


_SANDBOX_FOLDER = r"C:\Validation"


def _absolute_existing_directory(value: str | os.PathLike[str], label: str) -> Path:
    try:
        raw = Path(os.fspath(value))
    except (TypeError, ValueError, OSError) as exc:
        raise SandboxPolicyError(f"{label} must be a valid path") from exc
    if not raw.is_absolute():
        raise SandboxPolicyError(f"{label} must be absolute")
    if any(part == ".." for part in raw.parts):
        raise SandboxPolicyError(f"{label} cannot contain parent-directory traversal")
    candidate = Path(os.path.normpath(os.fspath(raw)))

    current = Path(candidate.anchor)
    for part in candidate.parts[1:]:
        current = current / part
        try:
            mode = current.lstat().st_mode
        except OSError as exc:
            raise SandboxPolicyError(f"{label} contains a missing or inaccessible component") from exc
        if stat.S_ISLNK(mode):
            raise SandboxPolicyError(f"{label} cannot contain symlink components")

    if not candidate.is_dir():
        raise SandboxPolicyError(f"{label} must be an existing directory")
    return candidate


def _overlaps(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def build_windows_sandbox_profile(
    validation_snapshot: str | os.PathLike[str],
    source_checkout: str | os.PathLike[str],
) -> SandboxProfile:
    """Return a no-network, no-clipboard, single-folder Sandbox XML profile.

    The only host folder exposed is the disposable validation snapshot, mapped
    writable so test tools can create temporary outputs. The source checkout
    and all other host paths are excluded. The caller must create the snapshot
    independently and must never pass the user's source checkout here.
    """
    snapshot = _absolute_existing_directory(validation_snapshot, "Validation snapshot")
    source = _absolute_existing_directory(source_checkout, "Source checkout")
    if _overlaps(snapshot, source):
        raise SandboxPolicyError("Validation snapshot and source checkout must be disjoint trees")

    root = ET.Element("Configuration")
    for tag, value in (
        ("VGpu", "Disable"),
        ("Networking", "Disable"),
        ("ClipboardRedirection", "Disable"),
        ("PrinterRedirection", "Disable"),
        ("AudioInput", "Disable"),
        ("VideoInput", "Disable"),
        ("ProtectedClient", "Enable"),
    ):
        ET.SubElement(root, tag).text = value

    mapped = ET.SubElement(root, "MappedFolders")
    folder = ET.SubElement(mapped, "MappedFolder")
    ET.SubElement(folder, "HostFolder").text = str(snapshot)
    ET.SubElement(folder, "SandboxFolder").text = _SANDBOX_FOLDER
    ET.SubElement(folder, "ReadOnly").text = "false"

    xml = ET.tostring(root, encoding="unicode", short_empty_elements=True)
    return SandboxProfile(
        host_snapshot=snapshot,
        sandbox_folder=_SANDBOX_FOLDER,
        xml=xml,
    )
