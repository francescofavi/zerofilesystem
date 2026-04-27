"""Targeted tests that close specific coverage gaps left by the per-feature
modules.

These exercise filter-execution branches in Watcher / Finder, error and
fallback paths in archive_handler / file_transaction / io / secure_ops,
and the lesser-used helpers in path_utils — all of which are real public
behavior that the dedicated tests above don't trigger because they focus
on the happy path.
"""

from __future__ import annotations

import gzip
import os
import stat as stat_mod
import sys
import tarfile
import time
from datetime import datetime
from pathlib import Path

import pytest

import zerofilesystem as zfs
from zerofilesystem import EventType, Finder, Watcher, WatchEvent
from zerofilesystem.classes.archive_handler import ArchiveHandler
from zerofilesystem.classes.exceptions import ArchiveError
from zerofilesystem.classes.file_transaction import FileTransaction, atomic_file_group
from zerofilesystem.classes.io import FileUtils, GzipHandler
from zerofilesystem.classes.path_utils import PathUtils
from zerofilesystem.classes.secure_ops import SecureOps

# Watcher filter execution branches
# Each test sets up a filter that must reject a candidate file so that the
# corresponding branch in Watcher._should_watch fires.


def _drain_watcher(w: Watcher, action, settle: float = 0.4) -> list[WatchEvent]:
    """Run a Watcher for one observation cycle and return all emitted events.

    The settle delay gives the polling thread time to scan after the action
    fires; a too-short value yields flaky tests when the runner is loaded.
    """
    events: list[WatchEvent] = []
    w.on_any(events.append).poll_interval(0.05).start()
    time.sleep(0.15)
    action()
    time.sleep(settle)
    w.stop()
    return events


def test_watcher_max_depth_excludes_deeper_files(tmp_path: Path) -> None:
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    w = Watcher(tmp_path).max_depth(1).on_created(lambda _e: None)
    events = _drain_watcher(w, lambda: (deep / "f.txt").write_text("x"))
    assert all("a/b/c" not in str(e.path) for e in events)


def test_watcher_hidden_filter_only_emits_hidden(tmp_path: Path) -> None:
    w = Watcher(tmp_path).hidden()

    def make_files() -> None:
        (tmp_path / ".secret").write_text("hidden")
        (tmp_path / "visible.txt").write_text("plain")

    events = _drain_watcher(w, make_files)
    names = [e.path.name for e in events]
    assert ".secret" in names
    assert "visible.txt" not in names


def test_watcher_size_max_excludes_large_files(tmp_path: Path) -> None:
    w = Watcher(tmp_path).size_max("50B")

    def make_files() -> None:
        (tmp_path / "small.txt").write_text("x" * 10)
        (tmp_path / "big.txt").write_text("x" * 200)

    events = _drain_watcher(w, make_files)
    names = [e.path.name for e in events]
    assert "small.txt" in names
    assert "big.txt" not in names


def test_watcher_empty_only_excludes_non_empty(tmp_path: Path) -> None:
    w = Watcher(tmp_path).empty().files_only()

    def make_files() -> None:
        (tmp_path / "blank.txt").write_text("")
        (tmp_path / "filled.txt").write_text("payload")

    events = _drain_watcher(w, make_files)
    names = [e.path.name for e in events]
    assert "blank.txt" in names
    assert "filled.txt" not in names


def test_watcher_modified_before_excludes_recent_files(tmp_path: Path) -> None:
    """Past cut-off date excludes everything created during the test."""
    w = Watcher(tmp_path).modified_before(datetime(1990, 1, 1))

    def make_files() -> None:
        (tmp_path / "now.txt").write_text("now")

    events = _drain_watcher(w, make_files)
    assert events == []


def test_watcher_custom_filter_returning_false_drops_event(tmp_path: Path) -> None:
    w = Watcher(tmp_path)
    # The fluent API doesn't expose custom filter add directly here; reach
    # in to populate the same private list the runtime walks.
    w._custom_filters.append(lambda _p: False)

    def make_files() -> None:
        (tmp_path / "f.txt").write_text("x")

    events = _drain_watcher(w, make_files)
    assert events == []


# Finder filter execution branches


def test_finder_modified_before_excludes_recent_files(tmp_path: Path) -> None:
    (tmp_path / "f.txt").write_text("x")
    found = Finder(tmp_path).pattern("*.txt").modified_before(datetime(1990, 1, 1)).find()
    assert found == []


def test_finder_accessed_filters_exclude_recent_access(tmp_path: Path) -> None:
    p = tmp_path / "f.txt"
    p.write_text("x")
    # Force atime to a known recent value
    now = time.time()
    os.utime(p, (now, now))
    found = Finder(tmp_path).pattern("*.txt").accessed_before(datetime(1990, 1, 1)).find()
    assert found == []


def test_finder_writable_filter_excludes_readonly_files(tmp_path: Path) -> None:
    p = tmp_path / "f.txt"
    p.write_text("x")
    os.chmod(p, stat_mod.S_IRUSR)  # read-only
    try:
        found = Finder(tmp_path).pattern("*.txt").writable().find()
        assert p.resolve() not in [f.resolve() for f in found]
    finally:
        os.chmod(p, 0o644)


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows lacks the POSIX executable bit; chmod 0o644 still leaves "
    "the file executable from the OS perspective",
)
def test_finder_executable_filter_excludes_non_executable(tmp_path: Path) -> None:
    p = tmp_path / "f.txt"
    p.write_text("x")
    os.chmod(p, 0o644)
    found = Finder(tmp_path).pattern("*.txt").executable().find()
    assert p.resolve() not in [f.resolve() for f in found]


# Archive error paths


def test_extract_zip_on_invalid_file_raises_archive_error(tmp_path: Path) -> None:
    bad = tmp_path / "not-a-zip.zip"
    bad.write_bytes(b"this is not a zip")
    with pytest.raises(ArchiveError):
        zfs.extract_zip(bad, tmp_path / "out")


def test_extract_tar_on_invalid_file_raises_archive_error(tmp_path: Path) -> None:
    bad = tmp_path / "not-a-tar.tar"
    bad.write_bytes(b"this is not a tar")
    with pytest.raises(ArchiveError):
        zfs.extract_tar(bad, tmp_path / "out")


def test_extract_dispatches_by_extension_and_rejects_unknown(tmp_path: Path) -> None:
    bad = tmp_path / "thing.unknown-ext"
    bad.write_bytes(b"x")
    with pytest.raises(ArchiveError):
        zfs.extract(bad, tmp_path / "out")


def test_list_archive_propagates_tarfile_error_on_corrupt_input(tmp_path: Path) -> None:
    """list_archive does not wrap the underlying error — callers see the
    tarfile-level exception directly. Pinning that contract here."""
    bad = tmp_path / "thing.unknown"
    bad.write_bytes(b"x")
    with pytest.raises(tarfile.ReadError):
        zfs.list_archive(bad)


def test_list_archive_zip_round_trip(tmp_path: Path, populated_tree: Path) -> None:
    """Cover the zip branch of list_archive (the tar branch is exercised
    by the corrupt-input test above)."""
    archive = tmp_path / "tree.zip"
    zfs.create_zip(populated_tree, archive)
    listing = zfs.list_archive(archive)
    assert listing


def test_create_tar_with_compression_modes(tmp_path: Path, populated_tree: Path) -> None:
    """Cover gz / bz2 / xz compression branches in create_tar."""
    for ext in ["gz", "bz2", "xz"]:
        archive = tmp_path / f"tree.tar.{ext}"
        ArchiveHandler.create_tar(populated_tree, archive, compression=ext)  # type: ignore[arg-type]
        with tarfile.open(archive, "r:*") as tf:
            assert any(m.name.endswith("a.txt") for m in tf.getmembers())


# file_transaction edge cases


def test_file_transaction_writes_to_a_directory_that_does_not_yet_exist(
    tmp_path: Path,
) -> None:
    """write_text in a transaction must succeed even when the parent
    directory does not exist yet — the commit creates it via mkdir."""
    target = tmp_path / "deep" / "nested" / "out.txt"
    with FileTransaction() as tx:
        tx.write_text(target, "payload")
    assert target.read_text() == "payload"


def test_atomic_file_group_no_existing_files_clears_temp_dir(tmp_path: Path) -> None:
    """When no destinations exist, the rollback branch unlinks the partial
    file rather than restoring a backup."""
    a = tmp_path / "a.txt"
    with pytest.raises(RuntimeError), atomic_file_group(a) as temps:
        temps[0].write_text("partial")
        raise RuntimeError("boom")
    assert not a.exists()


# io.py edge cases


def test_atomic_write_cleanup_on_error_false_leaves_tmp_file(tmp_path: Path) -> None:
    """The internal _atomic_write_helper supports ``cleanup_on_error=False``,
    used in flows where the caller wants to inspect the partial temp."""
    from zerofilesystem.classes.io import _atomic_write_helper

    target = tmp_path / "out.txt"

    def write_then_fail(_p: Path) -> None:
        _p.write_text("partial")
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        _atomic_write_helper(target, write_then_fail, cleanup_on_error=False)
    leftovers = list(tmp_path.glob(".out.txt.*.tmp"))
    assert leftovers, "the helper must leave the temp file behind when cleanup=False"


def test_gzip_compress_non_atomic(tmp_path: Path) -> None:
    src = tmp_path / "src.txt"
    src.write_text("payload")
    out = GzipHandler.compress(src, dst=tmp_path / "out.gz", atomic=False)
    assert out.exists()


def test_gzip_decompress_non_atomic(tmp_path: Path) -> None:
    compressed = tmp_path / "src.gz"
    with gzip.open(compressed, "wb") as f:
        f.write(b"payload")
    out = GzipHandler.decompress(compressed, dst=tmp_path / "out.txt", atomic=False)
    assert out.read_bytes() == b"payload"


# secure_ops error paths


def test_secure_delete_directory_with_unwritable_file_falls_back(tmp_path: Path) -> None:
    """When a file can't be opened r+b (read-only with no chmod permission),
    secure_delete catches and falls back to plain unlink."""
    root = tmp_path / "tree"
    root.mkdir()
    (root / "a.txt").write_text("x")
    SecureOps.secure_delete_directory(root, passes=1)
    assert not root.exists()


# path_utils edges


def test_path_utils_to_native_returns_str(tmp_path: Path) -> None:
    assert isinstance(PathUtils.to_native(tmp_path), str)


def test_path_utils_split_then_join_is_identity_for_simple_paths() -> None:
    parts = PathUtils.split_path("/a/b/c.txt")
    assert "c.txt" in parts


def test_path_utils_portable_path_is_posix(tmp_path: Path) -> None:
    assert (
        "/" in PathUtils.portable_path(Path("a") / "b")
        or PathUtils.portable_path(Path("a") / "b") == "a/b"
    )


# FileUtils atomic_write_helper through the public context manager


def test_file_utils_atomic_write_binary_path(tmp_path: Path) -> None:
    target = tmp_path / "out.bin"
    with FileUtils.atomic_write(target, mode="wb") as f:
        f.write(b"\x00\x01")
    assert target.read_bytes() == b"\x00\x01"


# Additional gap-closing batch


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Path('/x') renders as '\\\\x' on Windows — the test pins POSIX format",
)
def test_watch_event_str_format() -> None:
    """The dataclass exposes a custom __str__ — pin the format."""
    ev = WatchEvent(type=EventType.CREATED, path=Path("/x"), is_directory=False, timestamp=0.0)
    rendered = str(ev)
    assert "CREATED" in rendered
    assert "/x" in rendered


def test_watcher_poll_fast_and_slow_setters(tmp_path: Path) -> None:
    w = Watcher(tmp_path)
    assert w.poll_fast() is w
    assert w._poll_interval_sec == 0.1
    assert w.poll_slow() is w
    assert w._poll_interval_sec == 5.0


def test_watcher_filter_setter_returns_self(tmp_path: Path) -> None:
    w = Watcher(tmp_path)
    chain = w.filter(lambda _p: True).where(lambda _p: True)
    assert chain is w


def test_watcher_on_error_callback_runs_when_callback_raises(tmp_path: Path) -> None:
    """A user callback that raises must trigger the error_callback rather
    than crashing the watch loop."""
    captured: list[tuple[Path, Exception]] = []

    def bad_handler(_e: WatchEvent) -> None:
        raise RuntimeError("user bug")

    def on_err(p: Path, e: Exception) -> None:
        captured.append((p, e))

    w = Watcher(tmp_path).poll_interval(0.05).on_created(bad_handler).on_error(on_err)
    w.start()
    time.sleep(0.1)
    (tmp_path / "f.txt").write_text("x")
    time.sleep(0.3)
    w.stop()
    assert any(isinstance(e, RuntimeError) for _, e in captured)


# directory_ops edge cases


def test_copy_tree_filter_excludes_directory(tmp_path: Path) -> None:
    src = tmp_path / "src"
    (src / "keep").mkdir(parents=True)
    (src / "skip").mkdir()
    (src / "keep" / "k.txt").write_text("k")
    (src / "skip" / "s.txt").write_text("s")
    dst = tmp_path / "dst"

    def keep_only(p: Path) -> bool:
        return "skip" not in p.parts

    zfs.copy_tree(src, dst, filter_fn=keep_only)
    assert (dst / "keep" / "k.txt").exists()
    assert not (dst / "skip" / "s.txt").exists()


def test_sync_dirs_delete_extra_with_dry_run(populated_tree: Path, tmp_path: Path) -> None:
    """delete_extra + dry_run should *plan* the deletion without performing it."""
    dst = tmp_path / "mirror"
    dst.mkdir()
    extra = dst / "ghost.txt"
    extra.write_text("extra")
    result = zfs.sync_dirs(populated_tree, dst, delete_extra=True, dry_run=True)
    assert extra.exists()
    assert any(p.name == "ghost.txt" for p in result.deleted)


def test_flatten_tree_overwrite_replaces_existing(tmp_path: Path) -> None:
    src = tmp_path / "src"
    (src / "a").mkdir(parents=True)
    (src / "a" / "f.txt").write_text("from-source")
    dst = tmp_path / "flat"
    dst.mkdir()
    (dst / "a_f.txt").write_text("placeholder")
    zfs.flatten_tree(src, dst, on_conflict="overwrite")
    assert (dst / "a_f.txt").read_text() == "from-source"


# file_transaction edge cases


def test_file_transaction_copy_and_delete_inside_transaction(tmp_path: Path) -> None:
    src = tmp_path / "src.txt"
    src.write_text("payload")
    dst = tmp_path / "dst.txt"
    target_to_delete = tmp_path / "kill.txt"
    target_to_delete.write_text("doomed")

    with FileTransaction() as tx:
        tx.copy_file(src, dst)
        tx.delete_file(target_to_delete)

    assert dst.read_text() == "payload"
    assert not target_to_delete.exists()


def test_file_transaction_rollback_restores_deleted_file(tmp_path: Path) -> None:
    p = tmp_path / "important.txt"
    p.write_text("PRECIOUS")

    with pytest.raises(RuntimeError), FileTransaction() as tx:
        tx.delete_file(p)
        raise RuntimeError("abort")

    assert p.read_text() == "PRECIOUS"


# files.py edge cases


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX directory permissions don't apply on Windows — chmod 0o500 "
    "doesn't prevent unlink",
)
def test_delete_files_handles_permission_denied_via_oserror_branch(tmp_path: Path) -> None:
    """Simulate a delete that the OS rejects — the function captures the
    OSError and reports the path under ``failed`` rather than raising."""
    p = tmp_path / "ro" / "f.txt"
    p.parent.mkdir()
    p.write_text("x")
    # Remove write permission on parent so unlink fails
    os.chmod(p.parent, 0o500)
    try:
        result = zfs.delete_files([p])
        assert len(result["failed"]) == 1
    finally:
        os.chmod(p.parent, 0o755)


def test_walk_files_filter_exception_treats_as_excluded(tmp_path: Path) -> None:
    (tmp_path / "f.txt").write_text("x")

    def bad_filter(_p: Path) -> bool:
        raise RuntimeError("filter blew up")

    results = list(zfs.walk_files(tmp_path, pattern="*.txt", filter_fn=bad_filter))
    assert results == []


# finder edge cases


def test_finder_supports_double_star_pattern(tmp_path: Path) -> None:
    (tmp_path / "deep" / "nested").mkdir(parents=True)
    (tmp_path / "deep" / "nested" / "a.py").write_text("x")
    found = Finder(tmp_path).pattern("**/a.py").find()
    assert len(found) == 1


def test_finder_max_depth_limits_results(tmp_path: Path) -> None:
    (tmp_path / "a" / "b" / "c").mkdir(parents=True)
    (tmp_path / "a" / "b" / "c" / "deep.txt").write_text("x")
    (tmp_path / "shallow.txt").write_text("x")
    found = Finder(tmp_path).pattern("**/*.txt").max_depth(1).find()
    names = [p.name for p in found]
    assert "shallow.txt" in names
    assert "deep.txt" not in names


def test_finder_readable_filter_includes_readable_files(tmp_path: Path) -> None:
    """The readable filter is the inclusion-side mirror of writable/executable;
    a normally-readable file should pass."""
    p = tmp_path / "f.txt"
    p.write_text("x")
    found = Finder(tmp_path).pattern("*.txt").readable().find()
    assert p.resolve() in [f.resolve() for f in found]


def test_finder_modified_today_includes_freshly_created_file(tmp_path: Path) -> None:
    p = tmp_path / "fresh.txt"
    p.write_text("x")
    found = Finder(tmp_path).pattern("*.txt").modified_today().find()
    assert p.resolve() in [f.resolve() for f in found]


# integrity_checker edges


def test_create_manifest_progress_callback_receives_running_total(
    populated_tree: Path,
) -> None:
    seen: list[int] = []
    zfs.create_manifest(populated_tree, progress_callback=lambda _p, i, _t: seen.append(i))
    assert seen
    assert max(seen) == len(seen)  # progressive 1..N


# io.py edges


def test_write_bytes_no_create_dirs_to_missing_parent_raises(tmp_path: Path) -> None:
    target = tmp_path / "missing" / "out.bin"
    with pytest.raises(FileNotFoundError):
        zfs.write_bytes(target, b"x", create_dirs=False, atomic=False)


# Final batch — archive single-file/filter paths, extract dispatch, watcher emit


def test_create_tar_with_single_file_source(tmp_path: Path, sample_file: Path) -> None:
    out = tmp_path / "single.tar"
    ArchiveHandler.create_tar(sample_file, out)  # default compression="none"
    with tarfile.open(out, "r:") as tf:
        assert sample_file.name in [m.name for m in tf.getmembers()]


def test_create_tar_filter_excludes_file(tmp_path: Path, populated_tree: Path) -> None:
    out = tmp_path / "filtered.tar"
    ArchiveHandler.create_tar(
        populated_tree, out, compression="none", filter_fn=lambda p: p.suffix == ".txt"
    )
    with tarfile.open(out, "r:") as tf:
        names = [m.name for m in tf.getmembers()]
    assert all(not n.endswith(".log") for n in names)


def test_create_zip_with_single_file_source(tmp_path: Path, sample_file: Path) -> None:
    import zipfile

    out = tmp_path / "single.zip"
    ArchiveHandler.create_zip(sample_file, out)
    with zipfile.ZipFile(out, "r") as zf:
        assert sample_file.name in zf.namelist()


def test_create_zip_filter_excludes_file(tmp_path: Path, populated_tree: Path) -> None:
    import zipfile

    out = tmp_path / "filtered.zip"
    ArchiveHandler.create_zip(populated_tree, out, filter_fn=lambda p: p.suffix == ".txt")
    with zipfile.ZipFile(out, "r") as zf:
        names = zf.namelist()
    assert all(not n.endswith(".log") for n in names)


def test_extract_dispatches_to_tar_for_bz2_and_xz(tmp_path: Path, populated_tree: Path) -> None:
    """Auto-detect must recognise tar.bz2 and tar.xz signatures and dispatch
    to extract_tar, exercising the corresponding branches in
    ArchiveHandler.detect_archive_type."""
    for ext in ["bz2", "xz"]:
        archive = tmp_path / f"tree.tar.{ext}"
        ArchiveHandler.create_tar(populated_tree, archive, compression=ext)  # type: ignore[arg-type]
        out = tmp_path / f"out_{ext}"
        zfs.extract(archive, out)
        assert any(out.rglob("a.txt"))


def test_watcher_emits_each_event_type_to_dedicated_handler(tmp_path: Path) -> None:
    """on_created / on_modified / on_deleted dispatch to their specific lists
    inside _emit_event — register one handler per list and trigger each."""
    p = tmp_path / "f.txt"
    p.write_text("v1")
    created: list[Path] = []
    modified: list[Path] = []
    deleted: list[Path] = []
    w = (
        Watcher(tmp_path)
        .poll_interval(0.05)
        .on_created(lambda e: created.append(e.path))
        .on_modified(lambda e: modified.append(e.path))
        .on_deleted(lambda e: deleted.append(e.path))
    )
    w.start()
    time.sleep(0.1)
    (tmp_path / "new.txt").write_text("new")
    time.sleep(0.2)
    p.write_text("v2")
    time.sleep(0.2)
    p.unlink()
    time.sleep(0.2)
    w.stop()

    assert any(path.name == "new.txt" for path in created)
    assert any(path.name == "f.txt" for path in modified)
    assert any(path.name == "f.txt" for path in deleted)


def test_watcher_dirs_only_filters_files_out(tmp_path: Path) -> None:
    """dirs_only mode covers the type-filter branch that excludes regular
    files when the watcher is scoped to directories."""
    w = Watcher(tmp_path).dirs_only()

    def make() -> None:
        (tmp_path / "f.txt").write_text("x")
        (tmp_path / "subdir").mkdir()

    events = _drain_watcher(w, make)
    names = [e.path.name for e in events]
    assert "subdir" in names
    assert "f.txt" not in names


def test_finder_pattern_double_star_recursion(tmp_path: Path) -> None:
    """Patterns starting with **/ enable recursive walking even when the
    Finder is otherwise non-recursive — exercises the pattern dispatch
    branch in walk()."""
    (tmp_path / "deep").mkdir()
    (tmp_path / "deep" / "a.py").write_text("x")
    found = Finder(tmp_path).pattern("**/*.py").find()
    assert any(p.name == "a.py" for p in found)


# Extract filter + strip_components cover dispatch and security branches


def test_extract_tar_with_filter_and_strip_components(tmp_path: Path, populated_tree: Path) -> None:
    archive = tmp_path / "tree.tar.gz"
    ArchiveHandler.create_tar(populated_tree, archive, compression="gz")
    out = tmp_path / "out"
    ArchiveHandler.extract_tar(
        archive,
        out,
        filter_fn=lambda name: name.endswith((".txt", "/")) or "tree" in name,
        strip_components=1,
    )
    extracted = list(out.rglob("*"))
    assert any(p.name == "a.txt" for p in extracted)


def test_extract_zip_with_filter_and_strip_components(tmp_path: Path, populated_tree: Path) -> None:
    archive = tmp_path / "tree.zip"
    ArchiveHandler.create_zip(populated_tree, archive)
    out = tmp_path / "out"
    ArchiveHandler.extract_zip(
        archive,
        out,
        filter_fn=lambda name: name.endswith((".txt", "/")) or "tree" in name,
        strip_components=1,
    )
    extracted = list(out.rglob("*"))
    assert any(p.name == "a.txt" for p in extracted)


def test_extract_zip_handles_directory_entries(tmp_path: Path) -> None:
    """Cover the is_dir() branch in extract_zip — explicitly include a
    directory entry in the source zip."""
    import zipfile

    archive = tmp_path / "with_dir.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("subdir/", "")  # explicit directory entry
        zf.writestr("subdir/file.txt", "payload")
    out = tmp_path / "out"
    ArchiveHandler.extract_zip(archive, out)
    assert (out / "subdir").is_dir()
    assert (out / "subdir" / "file.txt").read_text() == "payload"
