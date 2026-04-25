"""Tests for the ZeroFS facade class.

The facade is a thin re-export of every top-level helper, plus three
constructor-style methods (``file_lock``, ``file_transaction``, ``file_watcher``)
that return instances rather than aliasing static methods. Per-feature behavior
lives in the dedicated test modules; this file only defends the wiring so
that a forgotten re-export shows up as a build-time failure instead of as
a confused user.
"""

from __future__ import annotations

from pathlib import Path

import zerofilesystem as zfs
from zerofilesystem import ZeroFS
from zerofilesystem._platform import IS_LINUX, IS_MACOS, IS_UNIX, IS_WINDOWS

# Every helper that should be reachable as both ``zerofilesystem.<name>``
# (top-level alias) and ``ZeroFS.<name>`` (facade method). Constructors are
# listed separately because they wrap the underlying class rather than
# aliasing it.
ALIASED_METHODS = [
    "read_text",
    "write_text",
    "read_bytes",
    "write_bytes",
    "read_json",
    "write_json",
    "gzip_compress",
    "gzip_decompress",
    "find_files",
    "walk_files",
    "is_hidden",
    "delete_files",
    "delete_empty_dirs",
    "move_if_absent",
    "copy_if_newer",
    "file_hash",
    "ensure_dir",
    "touch",
    "file_size",
    "disk_usage",
    "safe_filename",
    "atomic_write",
    "normalize_path",
    "to_absolute",
    "to_relative",
    "to_posix",
    "expand_path",
    "is_subpath",
    "common_path",
    "validate_path",
    "get_metadata",
    "set_readonly",
    "set_hidden",
    "set_executable",
    "set_permissions",
    "copy_permissions",
    "set_timestamps",
    "mode_to_string",
    "string_to_mode",
    "copy_tree",
    "move_tree",
    "sync_dirs",
    "temp_directory",
    "tree_size",
    "tree_file_count",
    "flatten_tree",
    "directory_hash",
    "create_manifest",
    "save_manifest",
    "load_manifest",
    "verify_manifest",
    "verify_file",
    "compare_directories",
    "snapshot_hash",
    "secure_delete",
    "secure_delete_directory",
    "private_directory",
    "create_private_file",
    "create_tar",
    "create_zip",
    "extract_tar",
    "extract_zip",
    "extract",
    "list_archive",
]


def test_zerofs_class_attributes_match_module_constants() -> None:
    assert ZeroFS.IS_WINDOWS is IS_WINDOWS
    assert ZeroFS.IS_MACOS is IS_MACOS
    assert ZeroFS.IS_LINUX is IS_LINUX
    assert ZeroFS.IS_UNIX is IS_UNIX


def test_facade_exposes_every_top_level_helper() -> None:
    """If a new public helper is added at the module level but forgotten on
    the ZeroFS class (or vice versa), users would have to switch styles to
    reach it. This test pins the parity. The facade methods are independent
    wrappers, not direct aliases, so we check name presence — semantic
    equivalence is exercised transitively by the per-feature test modules
    (and per-platform by the CI matrix)."""
    missing_on_facade = [name for name in ALIASED_METHODS if not hasattr(ZeroFS, name)]
    missing_at_module = [name for name in ALIASED_METHODS if not hasattr(zfs, name)]
    assert missing_on_facade == [], f"facade is missing: {missing_on_facade}"
    assert missing_at_module == [], f"module is missing: {missing_at_module}"


def test_facade_file_lock_constructs_filelock(tmp_path: Path) -> None:
    """file_lock is one of the three non-aliased methods — it constructs
    a FileLock bound to the given path."""
    lock = ZeroFS.file_lock(tmp_path / "x.lock", timeout=0.5)
    assert isinstance(lock, zfs.FileLock)
    assert lock.lock_path == tmp_path / "x.lock"
    assert lock.timeout == 0.5


def test_facade_file_transaction_constructs_filetransaction(tmp_path: Path) -> None:
    tx = ZeroFS.file_transaction(temp_dir=tmp_path)
    assert isinstance(tx, zfs.FileTransaction)


def test_facade_file_watcher_constructs_filewatcher(tmp_path: Path) -> None:
    w = ZeroFS.file_watcher(tmp_path)
    assert isinstance(w, zfs.FileWatcher)
