"""Tests for file metadata helpers: ensure_dir, touch, file_size, disk_usage."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import zerofilesystem as zfs


def test_ensure_dir_creates_a_new_directory(tmp_path: Path) -> None:
    target = tmp_path / "newdir"
    out = zfs.ensure_dir(target)
    assert out == target
    assert target.is_dir()


def test_ensure_dir_creates_intermediate_parents(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "c"
    zfs.ensure_dir(target)
    assert target.is_dir()


def test_ensure_dir_is_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "stable"
    zfs.ensure_dir(target)
    (target / "marker.txt").write_text("keep me")
    zfs.ensure_dir(target)
    assert (target / "marker.txt").read_text() == "keep me"


def test_ensure_dir_accepts_str_path(tmp_path: Path) -> None:
    target = str(tmp_path / "from-str")
    out = zfs.ensure_dir(target)
    assert out == Path(target)
    assert Path(target).is_dir()


def test_touch_creates_empty_file(tmp_path: Path) -> None:
    target = tmp_path / "blank.txt"
    out = zfs.touch(target)
    assert out == target
    assert target.is_file()
    assert target.read_text() == ""


def test_touch_creates_parent_directories(tmp_path: Path) -> None:
    target = tmp_path / "deep" / "nested" / "blank.txt"
    zfs.touch(target)
    assert target.is_file()


def test_touch_existing_file_does_not_truncate(tmp_path: Path) -> None:
    target = tmp_path / "preserve.txt"
    target.write_text("DO NOT LOSE")
    zfs.touch(target)
    assert target.read_text() == "DO NOT LOSE"


def test_touch_with_exist_ok_false_raises_on_existing(tmp_path: Path) -> None:
    target = tmp_path / "exists.txt"
    target.write_text("present")
    with pytest.raises(FileExistsError):
        zfs.touch(target, exist_ok=False)


def test_file_size_returns_byte_count(tmp_path: Path) -> None:
    target = tmp_path / "sized.bin"
    target.write_bytes(b"x" * 137)
    assert zfs.file_size(target) == 137


def test_file_size_zero_for_empty_file(tmp_path: Path) -> None:
    target = tmp_path / "empty.bin"
    target.touch()
    assert zfs.file_size(target) == 0


def test_file_size_raises_on_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        zfs.file_size(tmp_path / "missing")


def test_disk_usage_returns_three_positive_integers(tmp_path: Path) -> None:
    total, used, free = zfs.disk_usage(tmp_path)
    assert isinstance(total, int) and total > 0
    assert isinstance(used, int) and used >= 0
    assert isinstance(free, int) and free >= 0


def test_disk_usage_components_are_internally_consistent(tmp_path: Path) -> None:
    total, used, free = zfs.disk_usage(tmp_path)
    # used + free can be slightly less than total on some filesystems
    # (reserved blocks), but never larger.
    assert used + free <= total + 1


def test_disk_usage_accepts_str_path(tmp_path: Path) -> None:
    total, _, _ = zfs.disk_usage(str(tmp_path))
    assert total > 0


def test_disk_usage_raises_on_missing_path(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    with pytest.raises((FileNotFoundError, OSError)):
        zfs.disk_usage(missing)


def test_ensure_dir_against_existing_file_raises(tmp_path: Path) -> None:
    target = tmp_path / "f"
    target.write_text("im a file")
    with pytest.raises((FileExistsError, NotADirectoryError, OSError)):
        zfs.ensure_dir(target)


def test_touch_updates_mtime_on_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "tick.txt"
    target.write_text("x")
    old_mtime = target.stat().st_mtime
    os.utime(target, (old_mtime - 100, old_mtime - 100))
    zfs.touch(target)
    assert target.stat().st_mtime > old_mtime - 100
