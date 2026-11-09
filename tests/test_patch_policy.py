from __future__ import annotations

import pytest

from local_agent.patch_policy import (
    PatchLimits,
    PatchPolicyError,
    validate_unified_diff,
)


def _patch(path="src/example.py", old="before", new="after"):
    return (
        f"diff --git a/{path} b/{path}\n"
        "index 1111111..2222222\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        "@@ -1 +1 @@\n"
        f"-{old}\n"
        f"+{new}\n"
    )


def test_valid_patch_returns_bounded_summary_and_hash():
    patch = _patch()
    result = validate_unified_diff(patch, allowed_paths={"src/example.py"})
    assert result.total_additions == 1
    assert result.total_deletions == 1
    assert result.files[0].path == "src/example.py"
    assert len(result.sha256) == 64


def test_exact_allowlist_is_required():
    with pytest.raises(PatchPolicyError, match="exact write allowlist"):
        validate_unified_diff(_patch(), allowed_paths={"src/other.py"})


@pytest.mark.parametrize("path", [
    "../outside.py",
    "/absolute.py",
    "C:/outside.py",
    "src\\outside.py",
    "src//double.py",
    "src/./dot.py",
    "src/a b.py",
    ".env.local",
    "config/private.py",
    ".github/workflows/build.yml",
])
def test_rejects_unsafe_or_protected_paths(path):
    with pytest.raises(PatchPolicyError):
        validate_unified_diff(_patch(path), allowed_paths={path})


def test_rejects_renames():
    patch = _patch().replace(
        "diff --git a/src/example.py b/src/example.py",
        "diff --git a/src/example.py b/src/renamed.py",
    )
    with pytest.raises(PatchPolicyError, match="Renames"):
        validate_unified_diff(
            patch,
            allowed_paths={"src/example.py", "src/renamed.py"},
        )


@pytest.mark.parametrize("metadata", [
    "new file mode 100644",
    "deleted file mode 100644",
    "old mode 100644",
    "new mode 100755",
    "similarity index 100%",
    "rename from src/example.py",
    "copy from src/example.py",
    "Subproject commit 1234567",
])
def test_rejects_mode_rename_copy_and_submodule_metadata(metadata):
    patch = _patch().replace(
        "index 1111111..2222222\n",
        f"{metadata}\n",
    )
    with pytest.raises(PatchPolicyError):
        validate_unified_diff(patch, allowed_paths={"src/example.py"})


@pytest.mark.parametrize("patch", [
    "not a diff",
    "diff --git a/src/a.py b/src/a.py\nGIT binary patch\n",
    "diff --git a/src/a.py b/src/a.py\nBinary files a/src/a.py and b/src/a.py differ\n",
    "diff --cc src/a.py\n",
    "diff --git a/src/a.py b/src/a.py\n--- /dev/null\n+++ b/src/a.py\n",
    "diff --git a/src/a.py b/src/a.py\n--- a/src/a.py\n+++ /dev/null\n",
])
def test_rejects_malformed_binary_combined_and_create_delete_patches(patch):
    with pytest.raises(PatchPolicyError):
        validate_unified_diff(patch, allowed_paths={"src/a.py"})


def test_rejects_hunk_count_mismatch():
    patch = _patch().replace("@@ -1 +1 @@", "@@ -1,2 +1 @@")
    with pytest.raises(PatchPolicyError, match="Truncated"):
        validate_unified_diff(patch, allowed_paths={"src/example.py"})


def test_rejects_unexpected_hunk_lines():
    patch = _patch().replace("-before\n", "?before\n")
    with pytest.raises(PatchPolicyError, match="Invalid unified-diff"):
        validate_unified_diff(patch, allowed_paths={"src/example.py"})


def test_rejects_duplicate_file_sections():
    patch = _patch() + _patch()
    with pytest.raises(PatchPolicyError, match="Duplicate"):
        validate_unified_diff(patch, allowed_paths={"src/example.py"})


def test_rejects_empty_allowlist():
    with pytest.raises(PatchPolicyError, match="non-empty"):
        validate_unified_diff(_patch(), allowed_paths=set())


def test_rejects_oversized_patch():
    with pytest.raises(PatchPolicyError, match="total byte limit"):
        validate_unified_diff(
            _patch(old="x" * 200),
            allowed_paths={"src/example.py"},
            limits=PatchLimits(max_patch_bytes=100),
        )


def test_rejects_total_changed_line_limit():
    patch = (
        "diff --git a/src/example.py b/src/example.py\n"
        "--- a/src/example.py\n+++ b/src/example.py\n"
        "@@ -1 +1,4 @@\n-old\n+one\n+two\n+three\n+four\n"
    )
    with pytest.raises(PatchPolicyError, match="changed-line limit"):
        validate_unified_diff(
            patch,
            allowed_paths={"src/example.py"},
            limits=PatchLimits(max_changed_lines=3),
        )


def test_no_newline_marker_is_accepted_after_hunk():
    patch = _patch().rstrip("\n") + "\n\\ No newline at end of file\n"
    result = validate_unified_diff(patch, allowed_paths={"src/example.py"})
    assert result.files[0].hunk_count == 1


def test_rejects_nul_content():
    with pytest.raises(PatchPolicyError, match="NUL"):
        validate_unified_diff(_patch() + "\x00", allowed_paths={"src/example.py"})



def test_accepts_unchanged_regular_file_mode_metadata():
    patch = _patch().replace(
        "index 1111111..2222222\\n",
        "index 1111111..2222222 100644\\n",
    )
    result = validate_unified_diff(patch, allowed_paths={"src/example.py"})
    assert result.files[0].path == "src/example.py"


def test_rejects_symlink_mode_metadata():
    patch = _patch().replace(
        "index 1111111..2222222\\n",
        "index 1111111..2222222 120000\\n",
    )
    with pytest.raises(PatchPolicyError, match="Unsupported diff metadata"):
        validate_unified_diff(patch, allowed_paths={"src/example.py"})


def test_rejects_string_instead_of_allowlist_collection():
    with pytest.raises(PatchPolicyError, match="collection"):
        validate_unified_diff(_patch(), allowed_paths="src/example.py")
