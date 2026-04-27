"""Tests for delete_files and delete_empty_dirs."""

from __future__ import annotations

from pathlib import Path

import pytest

import zerofilesystem as zfs


def test_delete_files_removes_existing_files(tmp_path: Path) -> None:
    paths = []
    for i in range(3):
        p = tmp_path / f"f{i}.txt"
        p.write_text("x")
        paths.append(p)
    result = zfs.delete_files(paths)
    assert sorted(result["succeeded"]) == sorted(str(p) for p in paths)
    assert result["not_found"] == []
    assert result["not_file"] == []
    assert result["failed"] == []
    for p in paths:
        assert not p.exists()


def test_delete_files_categorises_missing_paths(tmp_path: Path) -> None:
    missing = tmp_path / "ghost.txt"
    result = zfs.delete_files([missing])
    assert result["succeeded"] == []
    assert len(result["not_found"]) == 1
    path_str, reason = result["not_found"][0]
    assert path_str == str(missing)
    assert "not found" in reason.lower()


def test_delete_files_rejects_directories(tmp_path: Path) -> None:
    sub = tmp_path / "subdir"
    sub.mkdir()
    result = zfs.delete_files([sub])
    assert result["succeeded"] == []
    assert len(result["not_file"]) == 1
    assert sub.exists()


def test_delete_files_handles_mixed_input(tmp_path: Path) -> None:
    good = tmp_path / "good.txt"
    good.write_text("x")
    missing = tmp_path / "missing.txt"
    sub = tmp_path / "sub"
    sub.mkdir()
    result = zfs.delete_files([good, missing, sub])
    assert result["succeeded"] == [str(good)]
    assert len(result["not_found"]) == 1
    assert len(result["not_file"]) == 1
    assert result["failed"] == []
    assert not good.exists()


def test_delete_files_accepts_empty_iterable() -> None:
    result = zfs.delete_files([])
    assert result == {
        "succeeded": [],
        "not_found": [],
        "not_file": [],
        "failed": [],
    }


def test_delete_files_accepts_str_paths(tmp_path: Path) -> None:
    p = tmp_path / "f.txt"
    p.write_text("x")
    result = zfs.delete_files([str(p)])
    assert result["succeeded"] == [str(p)]


def test_delete_empty_dirs_removes_only_empty(tmp_path: Path) -> None:
    root = tmp_path / "root"
    (root / "empty1").mkdir(parents=True)
    (root / "empty2" / "nested_empty").mkdir(parents=True)
    populated = root / "populated"
    populated.mkdir()
    (populated / "marker.txt").write_text("x")
    removed = zfs.delete_empty_dirs(root)
    assert (root / "empty1") not in [d for d in [root / "empty1"] if d.exists()]
    assert not (root / "empty1").exists()
    assert not (root / "empty2" / "nested_empty").exists()
    assert not (root / "empty2").exists()
    assert populated.exists()
    assert (populated / "marker.txt").exists()
    assert root in [r.parent for r in removed] or root not in removed


def test_delete_empty_dirs_remove_root_flag(tmp_path: Path) -> None:
    root = tmp_path / "wholly_empty"
    root.mkdir()
    removed = zfs.delete_empty_dirs(root, remove_root=True)
    assert not root.exists()
    assert root in removed


def test_delete_empty_dirs_keeps_root_when_flag_false(tmp_path: Path) -> None:
    root = tmp_path / "wholly_empty"
    root.mkdir()
    removed = zfs.delete_empty_dirs(root, remove_root=False)
    assert root.exists()
    assert root not in removed


def test_delete_empty_dirs_against_non_directory_returns_empty(tmp_path: Path) -> None:
    p = tmp_path / "f.txt"
    p.write_text("x")
    removed = zfs.delete_empty_dirs(p)
    assert removed == []
    assert p.exists()


def test_delete_empty_dirs_missing_path_returns_empty(tmp_path: Path) -> None:
    removed = zfs.delete_empty_dirs(tmp_path / "missing")
    assert removed == []


@pytest.mark.parametrize("count", [1, 5, 25])
def test_delete_empty_dirs_handles_deep_chains(tmp_path: Path, count: int) -> None:
    p = tmp_path / "root"
    p.mkdir()
    cur = p
    for i in range(count):
        cur = cur / f"level_{i}"
        cur.mkdir()
    removed = zfs.delete_empty_dirs(p)
    assert len(removed) == count
    assert p.exists()
    assert not (p / "level_0").exists()
