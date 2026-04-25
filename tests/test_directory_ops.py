"""Tests for the directory-tree operations: copy_tree, move_tree, sync_dirs,
temp_directory, tree_size, tree_file_count, flatten_tree.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import zerofilesystem as zfs
from zerofilesystem.classes.directory_ops import SyncResult
from zerofilesystem.classes.exceptions import SyncError


def _file_set(root: Path) -> set[str]:
    return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}


def test_copy_tree_basic_replicates_layout(populated_tree: Path, tmp_path: Path) -> None:
    dst = tmp_path / "copy"
    result = zfs.copy_tree(populated_tree, dst)
    assert isinstance(result, SyncResult)
    assert _file_set(populated_tree) == _file_set(dst)
    assert len(result.copied) > 0
    assert result.errors == []


def test_copy_tree_filter_excludes_files(populated_tree: Path, tmp_path: Path) -> None:
    dst = tmp_path / "copy"

    def only_txt(p: Path) -> bool:
        return p.is_dir() or p.suffix == ".txt"

    zfs.copy_tree(populated_tree, dst, filter_fn=only_txt)
    actual = _file_set(dst)
    assert all(name.endswith(".txt") for name in actual)
    assert "a.txt" in actual
    assert all(not name.endswith(".log") for name in actual)


def test_copy_tree_skip_on_conflict_preserves_existing(
    populated_tree: Path, tmp_path: Path
) -> None:
    dst = tmp_path / "copy"
    dst.mkdir()
    (dst / "a.txt").write_text("DO NOT OVERWRITE")
    result = zfs.copy_tree(populated_tree, dst, on_conflict="skip")
    assert (dst / "a.txt").read_text() == "DO NOT OVERWRITE"
    assert any(p.name == "a.txt" for p in result.skipped) or len(result.skipped) > 0


def test_copy_tree_only_if_newer_skips_when_destination_is_newer(
    populated_tree: Path, tmp_path: Path
) -> None:
    dst = tmp_path / "copy"
    dst.mkdir()
    target = dst / "a.txt"
    target.write_text("newer")
    src_a = populated_tree / "a.txt"
    src_stat = src_a.stat()
    os.utime(src_a, (src_stat.st_atime - 10000, src_stat.st_mtime - 10000))
    zfs.copy_tree(populated_tree, dst, on_conflict="only_if_newer")
    assert target.read_text() == "newer"


def test_copy_tree_overwrite_replaces_existing(populated_tree: Path, tmp_path: Path) -> None:
    dst = tmp_path / "copy"
    dst.mkdir()
    (dst / "a.txt").write_text("OLD")
    result = zfs.copy_tree(populated_tree, dst, on_conflict="overwrite")
    assert (dst / "a.txt").read_text() == (populated_tree / "a.txt").read_text()
    assert any(p.name == "a.txt" for p in result.updated)


def test_copy_tree_raises_when_source_is_not_dir(tmp_path: Path) -> None:
    p = tmp_path / "f.txt"
    p.write_text("x")
    with pytest.raises(SyncError):
        zfs.copy_tree(p, tmp_path / "dst")


def test_move_tree_full_move_when_destination_absent(populated_tree: Path, tmp_path: Path) -> None:
    dst = tmp_path / "moved"
    expected = _file_set(populated_tree)
    zfs.move_tree(populated_tree, dst)
    assert _file_set(dst) == expected
    assert not populated_tree.exists()


def test_move_tree_with_filter_keeps_unmoved_files(populated_tree: Path, tmp_path: Path) -> None:
    dst = tmp_path / "moved"

    def only_txt(p: Path) -> bool:
        return p.is_dir() or p.suffix == ".txt"

    result = zfs.move_tree(populated_tree, dst, filter_fn=only_txt)
    assert any(name.endswith(".log") for name in _file_set(populated_tree))
    assert all(p.suffix == ".txt" for p in result.copied)


def test_move_tree_error_on_conflict_records_failure_in_result(
    populated_tree: Path, tmp_path: Path
) -> None:
    """move_tree with on_conflict='error' surfaces FileExistsError inside the
    SyncResult.errors list rather than raising — the per-file try/except wraps
    the conflict so the rest of the tree can still be moved."""
    dst = tmp_path / "dst"
    dst.mkdir()
    (dst / "a.txt").write_text("present")

    result = zfs.move_tree(populated_tree, dst, filter_fn=lambda _p: True, on_conflict="error")
    error_paths = [str(path) for path, _msg in result.errors]
    assert any(p.endswith("a.txt") for p in error_paths)
    assert (dst / "a.txt").read_text() == "present"


def test_sync_dirs_copies_missing_files(populated_tree: Path, tmp_path: Path) -> None:
    dst = tmp_path / "mirror"
    zfs.sync_dirs(populated_tree, dst)
    assert _file_set(populated_tree) == _file_set(dst)


def test_sync_dirs_dry_run_makes_no_changes(populated_tree: Path, tmp_path: Path) -> None:
    dst = tmp_path / "mirror"
    result = zfs.sync_dirs(populated_tree, dst, dry_run=True)
    assert not dst.exists()
    assert len(result.copied) > 0


def test_sync_dirs_delete_extra_removes_files_not_in_source(
    populated_tree: Path, tmp_path: Path
) -> None:
    dst = tmp_path / "mirror"
    dst.mkdir()
    (dst / "ghost.txt").write_text("should be deleted")
    result = zfs.sync_dirs(populated_tree, dst, delete_extra=True)
    assert not (dst / "ghost.txt").exists()
    assert any(p.name == "ghost.txt" for p in result.deleted)


def test_sync_dirs_without_delete_extra_keeps_extra_files(
    populated_tree: Path, tmp_path: Path
) -> None:
    dst = tmp_path / "mirror"
    dst.mkdir()
    (dst / "extra.txt").write_text("keep me")
    zfs.sync_dirs(populated_tree, dst, delete_extra=False)
    assert (dst / "extra.txt").exists()


def test_sync_dirs_raises_when_source_is_not_dir(tmp_path: Path) -> None:
    p = tmp_path / "f.txt"
    p.write_text("x")
    with pytest.raises(SyncError):
        zfs.sync_dirs(p, tmp_path / "dst")


def test_temp_directory_yields_existing_path(tmp_path: Path) -> None:
    with zfs.temp_directory(parent=tmp_path) as d:
        assert d.is_dir()
        (d / "marker.txt").write_text("hi")
    assert not d.exists()


def test_temp_directory_no_cleanup_keeps_directory(tmp_path: Path) -> None:
    with zfs.temp_directory(parent=tmp_path, cleanup=False) as d:
        captured = d
    assert captured.exists()


def test_temp_directory_uses_prefix_and_suffix(tmp_path: Path) -> None:
    with zfs.temp_directory(prefix="myprefix_", suffix="_mysfx", parent=tmp_path) as d:
        assert d.name.startswith("myprefix_")
        assert d.name.endswith("_mysfx")


def test_tree_size_counts_all_bytes(populated_tree: Path) -> None:
    expected = sum(p.stat().st_size for p in populated_tree.rglob("*") if p.is_file())
    assert zfs.tree_size(populated_tree) == expected


def test_tree_size_for_single_file_returns_file_size(sample_file: Path) -> None:
    assert zfs.tree_size(sample_file) == sample_file.stat().st_size


def test_tree_size_empty_directory_is_zero(empty_dir: Path) -> None:
    assert zfs.tree_size(empty_dir) == 0


def test_tree_file_count_matches_rglob(populated_tree: Path) -> None:
    expected = sum(1 for p in populated_tree.rglob("*") if p.is_file())
    assert zfs.tree_file_count(populated_tree) == expected


def test_tree_file_count_empty_directory_is_zero(empty_dir: Path) -> None:
    assert zfs.tree_file_count(empty_dir) == 0


def test_flatten_tree_collapses_paths_into_single_directory(
    populated_tree: Path, tmp_path: Path
) -> None:
    dst = tmp_path / "flat"
    result = zfs.flatten_tree(populated_tree, dst)
    flat_files = list(dst.iterdir())
    assert len(flat_files) >= 5
    assert all(p.is_file() for p in flat_files)
    src_count = sum(1 for p in populated_tree.rglob("*") if p.is_file())
    assert len(result.copied) == src_count


def test_flatten_tree_uses_separator_for_nested_paths(populated_tree: Path, tmp_path: Path) -> None:
    dst = tmp_path / "flat"
    zfs.flatten_tree(populated_tree, dst, separator="__")
    nested_names = [p.name for p in dst.iterdir() if "__" in p.name]
    assert nested_names, "expected at least one flattened name to contain the separator"


def test_flatten_tree_rename_resolves_collision(tmp_path: Path) -> None:
    src = tmp_path / "src"
    (src / "a").mkdir(parents=True)
    (src / "b").mkdir()
    (src / "a" / "f.txt").write_text("from a")
    (src / "b" / "f.txt").write_text("from b")
    dst = tmp_path / "flat"
    result = zfs.flatten_tree(src, dst, separator="-", on_conflict="rename")
    names = sorted(p.name for p in dst.iterdir())
    assert len(names) == 2
    assert all(name.endswith(".txt") for name in names)
    assert result.errors == []


def test_flatten_tree_skip_keeps_first_collision_only(tmp_path: Path) -> None:
    src = tmp_path / "src"
    (src / "x").mkdir(parents=True)
    (src / "x" / "f.txt").write_text("real")
    dst = tmp_path / "flat"
    dst.mkdir()
    (dst / "x_f.txt").write_text("placeholder")
    result = zfs.flatten_tree(src, dst, on_conflict="skip")
    assert (dst / "x_f.txt").read_text() == "placeholder"
    assert any(p.name == "f.txt" for p in result.skipped)


def test_sync_result_str_summarises_counts(populated_tree: Path, tmp_path: Path) -> None:
    dst = tmp_path / "copy"
    result = zfs.copy_tree(populated_tree, dst)
    rendered = str(result)
    assert "copied=" in rendered
    assert "skipped=" in rendered
    assert "errors=" in rendered


def test_sync_result_total_operations_property() -> None:
    result = SyncResult(
        copied=[Path("a")],
        updated=[Path("b"), Path("c")],
        deleted=[Path("d")],
        skipped=[Path("e")],
    )
    assert result.total_operations == 4
