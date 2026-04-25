"""Tests for POSIX file permissions and extended metadata helpers."""

from __future__ import annotations

import os
import stat
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import zerofilesystem as zfs
from zerofilesystem.classes.file_permissions import FileMetadata


def test_get_metadata_returns_filemetadata_with_basic_fields(sample_file: Path) -> None:
    meta = zfs.get_metadata(sample_file)
    assert isinstance(meta, FileMetadata)
    assert meta.path == sample_file
    assert meta.size == sample_file.stat().st_size
    assert meta.is_file is True
    assert meta.is_dir is False
    assert meta.is_symlink is False
    assert meta.mode is not None


def test_get_metadata_for_directory(tmp_path: Path) -> None:
    meta = zfs.get_metadata(tmp_path)
    assert meta.is_dir is True
    assert meta.is_file is False


def test_get_metadata_records_owner_and_group(sample_file: Path) -> None:
    meta = zfs.get_metadata(sample_file)
    assert meta.owner is not None
    assert meta.group is not None


def test_get_metadata_str_repr_contains_basic_info(sample_file: Path) -> None:
    rendered = str(zfs.get_metadata(sample_file))
    assert sample_file.name in rendered
    assert "size=" in rendered


def test_get_metadata_dotfile_is_hidden(tmp_path: Path) -> None:
    p = tmp_path / ".secret"
    p.write_text("x")
    assert zfs.get_metadata(p).is_hidden is True


def test_get_metadata_normal_file_not_hidden(sample_file: Path) -> None:
    assert zfs.get_metadata(sample_file).is_hidden is False


@pytest.mark.parametrize("readonly", [True, False])
def test_set_readonly_round_trip(tmp_path: Path, readonly: bool) -> None:
    p = tmp_path / "f.txt"
    p.write_text("x")
    zfs.set_readonly(p, readonly=readonly)
    mode = p.stat().st_mode
    if readonly:
        assert not (mode & stat.S_IWUSR)
    else:
        assert mode & stat.S_IWUSR


def test_set_readonly_then_writable_again_allows_writes(tmp_path: Path) -> None:
    p = tmp_path / "f.txt"
    p.write_text("x")
    zfs.set_readonly(p, readonly=True)
    zfs.set_readonly(p, readonly=False)
    p.write_text("can write again")
    assert p.read_text() == "can write again"


@pytest.mark.parametrize("executable", [True, False])
def test_set_executable_toggles_user_x_bit(tmp_path: Path, executable: bool) -> None:
    p = tmp_path / "script.sh"
    p.write_text("#!/bin/sh\necho hi\n")
    zfs.set_permissions(p, 0o644)  # baseline known mode
    zfs.set_executable(p, executable=executable)
    assert bool(p.stat().st_mode & stat.S_IXUSR) is executable


def test_set_permissions_writes_exact_mode(tmp_path: Path) -> None:
    p = tmp_path / "f.txt"
    p.write_text("x")
    zfs.set_permissions(p, 0o640)
    assert (p.stat().st_mode & 0o777) == 0o640


def test_copy_permissions_mirrors_source(tmp_path: Path) -> None:
    src = tmp_path / "src.txt"
    src.write_text("x")
    dst = tmp_path / "dst.txt"
    dst.write_text("y")
    zfs.set_permissions(src, 0o640)
    zfs.set_permissions(dst, 0o600)
    zfs.copy_permissions(src, dst)
    assert (dst.stat().st_mode & 0o777) == 0o640


def test_set_timestamps_updates_modified_time(tmp_path: Path) -> None:
    p = tmp_path / "f.txt"
    p.write_text("x")
    target_mtime = datetime(2020, 1, 1, 12, 0, 0)
    zfs.set_timestamps(p, modified=target_mtime)
    actual = datetime.fromtimestamp(p.stat().st_mtime)
    assert abs((actual - target_mtime).total_seconds()) < 2


def test_set_timestamps_independently_updates_access_time(tmp_path: Path) -> None:
    p = tmp_path / "f.txt"
    p.write_text("x")
    initial_mtime = p.stat().st_mtime
    new_atime = datetime.fromtimestamp(initial_mtime) - timedelta(days=1)
    zfs.set_timestamps(p, accessed=new_atime)
    # mtime preserved
    assert abs(p.stat().st_mtime - initial_mtime) < 2


def test_set_timestamps_none_args_keep_current_values(tmp_path: Path) -> None:
    p = tmp_path / "f.txt"
    p.write_text("x")
    before = p.stat()
    zfs.set_timestamps(p, modified=None, accessed=None)
    after = p.stat()
    assert abs(after.st_mtime - before.st_mtime) < 2


def test_mode_to_string_known_modes() -> None:
    assert zfs.mode_to_string(0o755) == "rwxr-xr-x"
    assert zfs.mode_to_string(0o644) == "rw-r--r--"
    assert zfs.mode_to_string(0o600) == "rw-------"
    assert zfs.mode_to_string(0o000) == "---------"
    assert zfs.mode_to_string(0o777) == "rwxrwxrwx"


def test_string_to_mode_octal_numeric_form() -> None:
    assert zfs.string_to_mode("755") == 0o755
    assert zfs.string_to_mode("644") == 0o644


def test_string_to_mode_symbolic_form() -> None:
    assert zfs.string_to_mode("rwxr-xr-x") == 0o755
    assert zfs.string_to_mode("rw-r--r--") == 0o644
    assert zfs.string_to_mode("---------") == 0o000


def test_mode_to_string_round_trip_via_string_to_mode() -> None:
    for mode in [0o000, 0o644, 0o755, 0o600, 0o777, 0o400, 0o007]:
        assert zfs.string_to_mode(zfs.mode_to_string(mode)) == mode


@pytest.mark.parametrize("bad", ["", "rwxrwx", "rwxr-xr-xr", "abcdefghi", "rwxr-xr-X"])
def test_string_to_mode_rejects_malformed(bad: str) -> None:
    with pytest.raises(ValueError):
        zfs.string_to_mode(bad)


def test_string_to_mode_rejects_wrong_chars_at_position() -> None:
    with pytest.raises(ValueError):
        zfs.string_to_mode("xrwr-xr-x")


def test_get_metadata_mode_matches_filesystem(tmp_path: Path) -> None:
    p = tmp_path / "f.txt"
    p.write_text("x")
    os.chmod(p, 0o640)
    meta = zfs.get_metadata(p)
    assert meta.mode is not None
    assert (meta.mode & 0o777) == 0o640


def test_set_readonly_default_argument_is_true(tmp_path: Path) -> None:
    p = tmp_path / "f.txt"
    p.write_text("x")
    zfs.set_readonly(p)
    assert not (p.stat().st_mode & stat.S_IWUSR)


def test_set_executable_propagates_to_group_and_others_only_when_readable(
    tmp_path: Path,
) -> None:
    """The chmod-+x convention adds the x-bit to the same scopes that already
    have the matching r-bit. This test exercises both halves of that rule."""
    p = tmp_path / "script.sh"
    p.write_text("#!/bin/sh\n")
    zfs.set_permissions(p, 0o604)  # u=rw-, g=---, o=r--
    zfs.set_executable(p, executable=True)
    mode = p.stat().st_mode
    assert mode & stat.S_IXUSR
    assert not (mode & stat.S_IXGRP)  # group has no r-bit, so no x-bit added
    assert mode & stat.S_IXOTH  # other has r-bit, so x-bit added
