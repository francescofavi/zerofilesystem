"""Tests for move_if_absent and copy_if_newer."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import zerofilesystem as zfs


def _make_file(p: Path, content: str = "x") -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


def test_move_if_absent_moves_when_target_missing(tmp_path: Path) -> None:
    src = _make_file(tmp_path / "src.txt", "payload")
    dst_dir = tmp_path / "dst"
    moved, final = zfs.move_if_absent(src, dst_dir)
    assert moved is True
    assert final == dst_dir / "src.txt"
    assert (dst_dir / "src.txt").read_text() == "payload"
    assert not src.exists()


def test_move_if_absent_skips_when_target_exists(tmp_path: Path) -> None:
    src = _make_file(tmp_path / "src.txt", "fresh")
    dst_dir = tmp_path / "dst"
    _make_file(dst_dir / "src.txt", "old")
    moved, final = zfs.move_if_absent(src, dst_dir)
    assert moved is False
    assert final is None
    assert (dst_dir / "src.txt").read_text() == "old"
    assert src.exists()


def test_move_if_absent_renames_on_conflict(tmp_path: Path) -> None:
    src = _make_file(tmp_path / "src.txt", "fresh")
    dst_dir = tmp_path / "dst"
    _make_file(dst_dir / "src.txt", "old")
    moved, final = zfs.move_if_absent(src, dst_dir, on_conflict="rename")
    assert moved is True
    assert final is not None
    assert final.parent == dst_dir
    assert final.name == "src_1.txt"
    assert final.read_text() == "fresh"
    assert (dst_dir / "src.txt").read_text() == "old"


def test_move_if_absent_rename_increments_until_unique(tmp_path: Path) -> None:
    src = _make_file(tmp_path / "src.txt", "new")
    dst_dir = tmp_path / "dst"
    _make_file(dst_dir / "src.txt", "v0")
    _make_file(dst_dir / "src_1.txt", "v1")
    _make_file(dst_dir / "src_2.txt", "v2")
    moved, final = zfs.move_if_absent(src, dst_dir, on_conflict="rename")
    assert moved is True
    assert final is not None
    assert final.name == "src_3.txt"


def test_move_if_absent_error_raises_on_conflict(tmp_path: Path) -> None:
    src = _make_file(tmp_path / "src.txt", "fresh")
    dst_dir = tmp_path / "dst"
    _make_file(dst_dir / "src.txt", "old")
    with pytest.raises(FileExistsError):
        zfs.move_if_absent(src, dst_dir, on_conflict="error")


def test_move_if_absent_creates_destination_directory(tmp_path: Path) -> None:
    src = _make_file(tmp_path / "src.txt")
    dst_dir = tmp_path / "deep" / "nested"
    moved, final = zfs.move_if_absent(src, dst_dir)
    assert moved is True
    assert final is not None
    assert dst_dir.is_dir()


def test_move_if_absent_no_create_dirs_raises_when_missing(tmp_path: Path) -> None:
    src = _make_file(tmp_path / "src.txt")
    dst_dir = tmp_path / "missing"
    with pytest.raises(RuntimeError):
        zfs.move_if_absent(src, dst_dir, create_dirs=False)


def test_copy_if_newer_copies_when_destination_absent(tmp_path: Path) -> None:
    src = _make_file(tmp_path / "src.txt", "data")
    dst = tmp_path / "dst.txt"
    copied = zfs.copy_if_newer(src, dst)
    assert copied is True
    assert dst.read_text() == "data"


def test_copy_if_newer_skips_when_destination_is_newer(tmp_path: Path) -> None:
    src = _make_file(tmp_path / "src.txt", "old")
    dst = _make_file(tmp_path / "dst.txt", "newer")
    src_stat = src.stat()
    os.utime(src, (src_stat.st_atime - 1000, src_stat.st_mtime - 1000))
    copied = zfs.copy_if_newer(src, dst)
    assert copied is False
    assert dst.read_text() == "newer"


def test_copy_if_newer_copies_when_source_is_newer(tmp_path: Path) -> None:
    src = _make_file(tmp_path / "src.txt", "new")
    dst = _make_file(tmp_path / "dst.txt", "old")
    dst_stat = dst.stat()
    os.utime(dst, (dst_stat.st_atime - 1000, dst_stat.st_mtime - 1000))
    copied = zfs.copy_if_newer(src, dst)
    assert copied is True
    assert dst.read_text() == "new"


def test_copy_if_newer_preserves_mtime(tmp_path: Path) -> None:
    src = _make_file(tmp_path / "src.txt", "x")
    src_stat = src.stat()
    os.utime(src, (src_stat.st_atime - 5000, src_stat.st_mtime - 5000))
    expected_mtime = src.stat().st_mtime
    dst = tmp_path / "dst.txt"
    zfs.copy_if_newer(src, dst)
    assert abs(dst.stat().st_mtime - expected_mtime) <= 1.5


def test_copy_if_newer_creates_destination_directory(tmp_path: Path) -> None:
    src = _make_file(tmp_path / "src.txt", "x")
    dst = tmp_path / "deep" / "nested" / "dst.txt"
    copied = zfs.copy_if_newer(src, dst)
    assert copied is True
    assert dst.exists()


def test_copy_if_newer_missing_source_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        zfs.copy_if_newer(tmp_path / "nope.txt", tmp_path / "dst.txt")
