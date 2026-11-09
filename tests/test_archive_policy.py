from __future__ import annotations

import io
import tarfile

import pytest

from local_agent.archive_policy import (
    ArchiveLimits,
    ArchivePolicyError,
    inspect_tar_stream,
)
from local_agent.snapshot_policy import validate_snapshot_manifest


COMMIT = "b" * 40


def _manifest(entries=None, allowed=None):
    return validate_snapshot_manifest(
        commit=COMMIT,
        tree_entries=entries if entries is not None else [
            {"path": "src/app.py", "mode": "100644", "type": "blob", "size": 11}
        ],
        allowed_paths=allowed if allowed is not None else {"src/app.py"},
    )


def _tar(members, *, format=tarfile.USTAR_FORMAT):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=format) as archive:
        for info, content in members:
            if content is None:
                archive.addfile(info)
            else:
                archive.addfile(info, io.BytesIO(content))
    buffer.seek(0)
    return buffer


def _file(name="src/app.py", content=b"hello world"):
    info = tarfile.TarInfo(name)
    info.size = len(content)
    info.mode = 0o644
    return info, content


def _directory(name="src/"):
    info = tarfile.TarInfo(name)
    info.type = tarfile.DIRTYPE
    info.size = 0
    return info, None


def test_inspects_exact_tar_and_returns_content_hash():
    manifest = _manifest()
    result = inspect_tar_stream(_tar([_directory(), _file()]), manifest)
    assert result.commit == COMMIT
    assert result.manifest_sha256 == manifest.sha256
    assert result.total_file_bytes == 11
    assert result.files[0].path == "src/app.py"
    assert result.files[0].sha256 == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    assert result.bytes_read > 0


def test_parent_directories_are_optional():
    result = inspect_tar_stream(_tar([_file()]), _manifest())
    assert len(result.files) == 1


@pytest.mark.parametrize("name", [
    "../escape.py", "/absolute.py", "src/../escape.py", "src\\escape.py",
    "src/CON", "src/file.py:stream", ".env",
])
def test_rejects_unsafe_archive_paths(name):
    manifest = _manifest(entries=[{"path": name, "mode": "100644", "type": "blob", "size": 11}], allowed={name})
    with pytest.raises(ArchivePolicyError):
        inspect_tar_stream(_tar([_file(name)]), manifest)


def test_rejects_unexpected_and_missing_files():
    manifest = _manifest()
    with pytest.raises(ArchivePolicyError, match="Unexpected"):
        inspect_tar_stream(_tar([_file("src/other.py")]), manifest)
    with pytest.raises(ArchivePolicyError, match="missing"):
        inspect_tar_stream(_tar([]), manifest)


def test_rejects_duplicate_files_and_directories():
    manifest = _manifest()
    with pytest.raises(ArchivePolicyError, match="duplicate"):
        inspect_tar_stream(_tar([_file(), _file()]), manifest)
    with pytest.raises(ArchivePolicyError, match="directory"):
        inspect_tar_stream(_tar([_directory(), _directory(), _file()]), manifest)


@pytest.mark.parametrize("kind", [
    tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE,
    tarfile.BLKTYPE, tarfile.FIFOTYPE,
])
def test_rejects_links_and_special_archive_entries(kind):
    info = tarfile.TarInfo("src/app.py")
    info.type = kind
    info.linkname = "target"
    with pytest.raises(ArchivePolicyError, match="regular archive files"):
        inspect_tar_stream(_tar([(info, None)]), _manifest())


def test_rejects_size_mismatch_and_truncated_content():
    manifest = _manifest()
    with pytest.raises(ArchivePolicyError, match="size"):
        inspect_tar_stream(_tar([_file(content=b"short")]), manifest)
    truncated = io.BytesIO(_tar([_file()]).getvalue()[:-1024])
    with pytest.raises(ArchivePolicyError):
        inspect_tar_stream(truncated, manifest)


def test_rejects_pax_metadata():
    info, content = _file()
    info.pax_headers = {"comment": "unexpected"}
    with pytest.raises(ArchivePolicyError, match="PAX"):
        inspect_tar_stream(_tar([(info, content)], format=tarfile.PAX_FORMAT), _manifest())


def test_rejects_compressed_archive():
    import gzip
    raw = _tar([_file()]).getvalue()
    with pytest.raises(ArchivePolicyError):
        inspect_tar_stream(io.BytesIO(gzip.compress(raw)), _manifest())


def test_enforces_archive_byte_limit():
    data = _tar([_file()]).getvalue()
    with pytest.raises(ArchivePolicyError, match="byte limit"):
        inspect_tar_stream(io.BytesIO(data), _manifest(),
                           limits=ArchiveLimits(max_archive_bytes=256))


def test_rejects_invalid_limits():
    with pytest.raises(ArchivePolicyError, match="safe defaults"):
        inspect_tar_stream(_tar([_file()]), _manifest(),
                           limits=ArchiveLimits(max_archive_bytes=99_000_000))
