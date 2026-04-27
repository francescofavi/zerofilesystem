"""Shared pytest fixtures for the zerofilesystem test suite.

All fixtures are function-scoped — no I/O at import time, no shared mutable state.
Tests rely on these instead of inlining repeated setup, but each function still
gets its own freshly created temporary tree.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from zerofilesystem._platform import IS_WINDOWS

SAMPLE_TEXT = "Hello, world!\nLine 2\nUnicode: àèìòù 日本 🚀\n"
SAMPLE_BYTES = b"\x00\x01\x02\x03\xff\xfe\xfd"


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    """A file with deterministic UTF-8 content."""
    p = tmp_path / "sample.txt"
    p.write_text(SAMPLE_TEXT, encoding="utf-8")
    return p


@pytest.fixture
def sample_bytes_file(tmp_path: Path) -> Path:
    """A file with deterministic binary content."""
    p = tmp_path / "sample.bin"
    p.write_bytes(SAMPLE_BYTES)
    return p


@pytest.fixture
def populated_tree(tmp_path: Path) -> Path:
    """A small directory tree useful for finder/walker/copy/sync tests.

    Layout::

        tmp_path/tree/
        ├── a.txt          (10 bytes)
        ├── b.log          (20 bytes)
        ├── .hidden        (5 bytes, hidden by Unix convention)
        └── sub/
            ├── c.txt      (15 bytes)
            ├── d.py       (30 bytes)
            └── deep/
                └── e.txt  (5 bytes)
    """
    root = tmp_path / "tree"
    root.mkdir()
    (root / "a.txt").write_text("0123456789")
    (root / "b.log").write_text("01234567890123456789")
    (root / ".hidden").write_text("hello")
    sub = root / "sub"
    sub.mkdir()
    (sub / "c.txt").write_text("012345678901234")
    (sub / "d.py").write_text("0123456789012345678901234567890"[:30])
    deep = sub / "deep"
    deep.mkdir()
    (deep / "e.txt").write_text("01234")
    return root


@pytest.fixture
def empty_dir(tmp_path: Path) -> Path:
    """An empty directory inside tmp_path."""
    d = tmp_path / "empty"
    d.mkdir()
    return d


@pytest.fixture
def skip_on_windows() -> None:
    """Skip the test when running on Windows (POSIX-only behavior)."""
    if IS_WINDOWS:
        pytest.skip("POSIX-only behavior")


@pytest.fixture
def skip_on_posix() -> None:
    """Skip the test when running on POSIX (Windows-only behavior)."""
    if not IS_WINDOWS:
        pytest.skip("Windows-only behavior")
