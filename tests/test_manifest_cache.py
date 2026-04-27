"""Tests for ManifestCache.

Copyright (c) 2026 Francesco Favi
License: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest

from zerofilesystem import ManifestCache


@pytest.fixture
def source_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("def foo(): pass\n", encoding="utf-8")
    (repo / "b.py").write_text("def bar(): pass\n", encoding="utf-8")
    return repo


@pytest.fixture
def cache(tmp_path: Path) -> ManifestCache:
    return ManifestCache(tmp_path / "cache")


def test_load_returns_none_when_no_snapshot(cache: ManifestCache, source_repo: Path) -> None:
    assert cache.load(source_repo) is None


def test_save_then_load_returns_data(cache: ManifestCache, source_repo: Path) -> None:
    data = {"key": "value", "nums": [1, 2, 3]}
    cache.save(source_repo, data)
    assert cache.load(source_repo) == data


def test_load_returns_none_after_file_modified(cache: ManifestCache, source_repo: Path) -> None:
    cache.save(source_repo, {"ok": True})
    (source_repo / "a.py").write_text("def foo(): return 42\n", encoding="utf-8")
    assert cache.load(source_repo) is None


def test_load_returns_none_after_file_added(cache: ManifestCache, source_repo: Path) -> None:
    cache.save(source_repo, {"ok": True})
    (source_repo / "new.py").write_text("x = 1\n", encoding="utf-8")
    assert cache.load(source_repo) is None


def test_load_returns_none_after_file_deleted(cache: ManifestCache, source_repo: Path) -> None:
    cache.save(source_repo, {"ok": True})
    (source_repo / "b.py").unlink()
    assert cache.load(source_repo) is None


def test_filter_fn_ignores_untracked_extra_files(cache: ManifestCache, source_repo: Path) -> None:
    only_py = lambda p: p.suffix == ".py"  # noqa: E731
    cache.save(source_repo, {"ok": True}, filter_fn=only_py)
    (source_repo / "README.md").write_text("docs", encoding="utf-8")
    # .md files are not tracked → should NOT bust the cache
    assert cache.load(source_repo, filter_fn=only_py) == {"ok": True}


def test_filter_fn_tracked_new_file_busts_cache(cache: ManifestCache, source_repo: Path) -> None:
    only_py = lambda p: p.suffix == ".py"  # noqa: E731
    cache.save(source_repo, {"ok": True}, filter_fn=only_py)
    (source_repo / "c.py").write_text("z = 0\n", encoding="utf-8")
    # .py file is tracked → must bust the cache
    assert cache.load(source_repo, filter_fn=only_py) is None


def test_blob_name_is_configurable(cache: ManifestCache, source_repo: Path) -> None:
    cache.save(source_repo, [1, 2], blob_name="graph.json")
    assert cache.load(source_repo, blob_name="graph.json") == [1, 2]
    assert cache.load(source_repo, blob_name="data.json") is None


def test_changed_files_returns_empty_with_no_snapshot(
    cache: ManifestCache, source_repo: Path
) -> None:
    assert cache.changed_files(source_repo) == []


def test_changed_files_returns_modified(cache: ManifestCache, source_repo: Path) -> None:
    cache.save(source_repo, {})
    (source_repo / "a.py").write_text("modified", encoding="utf-8")
    changed = cache.changed_files(source_repo)
    assert any("a.py" in str(p) for p in changed)


def test_changed_files_returns_new_tracked_file(cache: ManifestCache, source_repo: Path) -> None:
    only_py = lambda p: p.suffix == ".py"  # noqa: E731
    cache.save(source_repo, {}, filter_fn=only_py)
    new = source_repo / "c.py"
    new.write_text("x = 1\n", encoding="utf-8")
    changed = cache.changed_files(source_repo, filter_fn=only_py)
    assert new in changed


def test_changed_files_ignores_untracked_new_file(cache: ManifestCache, source_repo: Path) -> None:
    only_py = lambda p: p.suffix == ".py"  # noqa: E731
    cache.save(source_repo, {}, filter_fn=only_py)
    (source_repo / "notes.txt").write_text("...", encoding="utf-8")
    changed = cache.changed_files(source_repo, filter_fn=only_py)
    assert not any("notes.txt" in str(p) for p in changed)


def test_clear_removes_cache_slot(cache: ManifestCache, source_repo: Path) -> None:
    cache.save(source_repo, {"x": 1})
    assert cache.clear(source_repo) is True
    assert cache.load(source_repo) is None


def test_clear_returns_false_when_no_slot(cache: ManifestCache, source_repo: Path) -> None:
    assert cache.clear(source_repo) is False


def test_multiple_source_dirs_are_isolated(tmp_path: Path) -> None:
    cache = ManifestCache(tmp_path / "cache")
    repo1 = tmp_path / "r1"
    repo1.mkdir()
    (repo1 / "f.py").write_text("a", encoding="utf-8")
    repo2 = tmp_path / "r2"
    repo2.mkdir()
    (repo2 / "f.py").write_text("b", encoding="utf-8")

    cache.save(repo1, {"repo": 1})
    cache.save(repo2, {"repo": 2})

    assert cache.load(repo1) == {"repo": 1}
    assert cache.load(repo2) == {"repo": 2}
