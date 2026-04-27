"""Tests for ChangeDetector.

Copyright (c) 2026 Francesco Favi
License: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest

from zerofilesystem import ChangeDetector


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    d = tmp_path / "repo"
    d.mkdir()
    (d / "a.py").write_text("def foo(): pass\n", encoding="utf-8")
    (d / "b.py").write_text("def bar(): pass\n", encoding="utf-8")
    return d


def test_first_scan_marks_all_files_as_new(repo: Path) -> None:
    detector = ChangeDetector(extensions={".py"})
    summary = detector.scan(repo)
    assert summary.has_changes
    assert len(summary.new) == 2
    assert summary.modified == []
    assert summary.deleted == []


def test_second_scan_without_changes_is_clean(repo: Path) -> None:
    detector = ChangeDetector(extensions={".py"})
    detector.scan(repo)
    summary = detector.scan(repo)
    assert not summary.has_changes


def test_new_file_detected(repo: Path) -> None:
    detector = ChangeDetector(extensions={".py"})
    detector.scan(repo)
    (repo / "c.py").write_text("x = 1\n", encoding="utf-8")
    summary = detector.scan(repo)
    assert len(summary.new) == 1
    assert summary.modified == []
    assert summary.deleted == []


def test_modified_file_detected(repo: Path) -> None:
    detector = ChangeDetector(extensions={".py"})
    detector.scan(repo)
    (repo / "a.py").write_text("def foo(): return 42\n", encoding="utf-8")
    summary = detector.scan(repo)
    assert len(summary.modified) == 1
    assert summary.new == []
    assert summary.deleted == []


def test_deleted_file_detected(repo: Path) -> None:
    detector = ChangeDetector(extensions={".py"})
    detector.scan(repo)
    (repo / "b.py").unlink()
    summary = detector.scan(repo)
    assert len(summary.deleted) == 1
    assert summary.new == []
    assert summary.modified == []


def test_reset_clears_state(repo: Path) -> None:
    detector = ChangeDetector(extensions={".py"})
    detector.scan(repo)
    detector.reset()
    summary = detector.scan(repo)
    # After reset, first scan marks all as new again
    assert len(summary.new) == 2


def test_non_matching_extensions_ignored(repo: Path) -> None:
    (repo / "notes.txt").write_text("hello", encoding="utf-8")
    detector = ChangeDetector(extensions={".py"})
    detector.scan(repo)
    (repo / "notes.txt").write_text("changed", encoding="utf-8")
    summary = detector.scan(repo)
    assert not summary.has_changes


def test_has_changes_false_on_empty_summary() -> None:
    from zerofilesystem import ChangeSummary

    assert not ChangeSummary().has_changes
