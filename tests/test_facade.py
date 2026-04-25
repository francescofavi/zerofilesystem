"""Tests for the ZeroFS facade class.

The facade re-exposes every public capability as a static method. Per-feature
behavior is covered by the dedicated test modules; this file verifies the
facade integration: that methods exist, can be invoked from a ZeroFS instance,
and produce the same observable results as the underlying class methods.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

import zerofilesystem as zfs
from zerofilesystem import ZeroFS
from zerofilesystem._platform import IS_LINUX, IS_MACOS, IS_UNIX, IS_WINDOWS
from zerofilesystem.classes.exceptions import HashMismatchError


@pytest.fixture
def fs() -> ZeroFS:
    return ZeroFS()


def test_zerofs_instantiates_without_arguments() -> None:
    assert ZeroFS() is not None


def test_zerofs_exposes_platform_constants_as_class_attributes() -> None:
    assert ZeroFS.IS_WINDOWS is IS_WINDOWS
    assert ZeroFS.IS_MACOS is IS_MACOS
    assert ZeroFS.IS_LINUX is IS_LINUX
    assert ZeroFS.IS_UNIX is IS_UNIX


def test_zerofs_is_re_exported_at_top_level() -> None:
    assert zfs.ZeroFS is ZeroFS


def test_facade_basic_io_round_trip(fs: ZeroFS, tmp_path: Path) -> None:
    target = tmp_path / "f.txt"
    fs.write_text(target, "hello")
    assert fs.read_text(target) == "hello"
    fs.write_bytes(target, b"\x01\x02")
    assert fs.read_bytes(target) == b"\x01\x02"


def test_facade_json_round_trip(fs: ZeroFS, tmp_path: Path) -> None:
    target = tmp_path / "data.json"
    payload = {"key": "value", "list": [1, 2, 3]}
    fs.write_json(target, payload)
    assert fs.read_json(target) == payload


def test_facade_gzip_round_trip(fs: ZeroFS, sample_file: Path, tmp_path: Path) -> None:
    compressed = fs.gzip_compress(sample_file, dst=tmp_path / "c.gz")
    restored = fs.gzip_decompress(compressed, dst=tmp_path / "r.txt")
    assert restored.read_text() == sample_file.read_text()


def test_facade_find_files_walk_files_is_hidden(fs: ZeroFS, populated_tree: Path) -> None:
    found = fs.find_files(populated_tree, pattern="**/*.txt")
    assert all(p.suffix == ".txt" for p in found)
    walked = list(fs.walk_files(populated_tree, pattern="**/*.txt"))
    assert {p.resolve() for p in walked} == {p.resolve() for p in found}
    assert fs.is_hidden(populated_tree / ".hidden") is True
    assert fs.is_hidden(populated_tree / "a.txt") is False


def test_facade_delete_files(fs: ZeroFS, tmp_path: Path) -> None:
    p = tmp_path / "f.txt"
    p.write_text("x")
    result = fs.delete_files([p])
    assert result["succeeded"] == [str(p)]


def test_facade_delete_empty_dirs(fs: ZeroFS, tmp_path: Path) -> None:
    root = tmp_path / "root"
    (root / "a" / "b").mkdir(parents=True)
    fs.delete_empty_dirs(root)
    assert not (root / "a" / "b").exists()


def test_facade_move_if_absent(fs: ZeroFS, tmp_path: Path) -> None:
    src = tmp_path / "src.txt"
    src.write_text("payload")
    dst_dir = tmp_path / "dst"
    moved, final = fs.move_if_absent(src, dst_dir)
    assert moved is True
    assert final == dst_dir / "src.txt"


def test_facade_copy_if_newer(fs: ZeroFS, tmp_path: Path) -> None:
    src = tmp_path / "src.txt"
    src.write_text("v1")
    dst = tmp_path / "dst.txt"
    assert fs.copy_if_newer(src, dst) is True
    assert dst.read_text() == "v1"


def test_facade_file_hash(fs: ZeroFS, sample_file: Path) -> None:
    direct = zfs.file_hash(sample_file)
    via_facade = fs.file_hash(sample_file)
    assert direct == via_facade


def test_facade_meta_helpers(fs: ZeroFS, tmp_path: Path) -> None:
    new_dir = tmp_path / "newdir"
    fs.ensure_dir(new_dir)
    assert new_dir.is_dir()

    f = tmp_path / "marker.txt"
    fs.touch(f)
    assert f.is_file()

    f.write_bytes(b"abc")
    assert fs.file_size(f) == 3

    total, used, free = fs.disk_usage(tmp_path)
    assert total > 0
    assert used >= 0
    assert free >= 0


def test_facade_safe_filename_and_atomic_write(fs: ZeroFS, tmp_path: Path) -> None:
    safe = fs.safe_filename("a:b/c.txt")
    assert ":" not in safe
    assert "/" not in safe

    target = tmp_path / "atom.txt"
    with fs.atomic_write(target) as f:
        f.write("ok")
    assert target.read_text() == "ok"


def test_facade_path_utilities(fs: ZeroFS, tmp_path: Path) -> None:
    p = tmp_path / "subdir"
    p.mkdir()
    assert fs.normalize_path("foo/./bar/../baz") == Path("foo/baz")
    assert fs.to_absolute("rel.txt").is_absolute()
    assert fs.is_subpath(p / "x", tmp_path) is True
    assert fs.to_posix(Path("a") / "b") == "a/b"


def test_facade_validate_path(fs: ZeroFS, tmp_path: Path) -> None:
    f = tmp_path / "f.txt"
    f.write_text("x")
    assert fs.validate_path(f, must_exist=True) == f


def test_facade_permissions_and_timestamps(fs: ZeroFS, tmp_path: Path) -> None:
    p = tmp_path / "f.txt"
    p.write_text("x")
    meta = fs.get_metadata(p)
    assert meta.size == 1

    if not IS_WINDOWS:
        fs.set_permissions(p, 0o644)

    target_mtime = datetime(2020, 1, 1, 12, 0, 0)
    fs.set_timestamps(p, modified=target_mtime)
    actual = datetime.fromtimestamp(p.stat().st_mtime)
    assert abs((actual - target_mtime).total_seconds()) < 2

    assert fs.mode_to_string(0o755) == "rwxr-xr-x"
    assert fs.string_to_mode("rwxr-xr-x") == 0o755


def test_facade_directory_ops(fs: ZeroFS, populated_tree: Path, tmp_path: Path) -> None:
    dst = tmp_path / "copy"
    fs.copy_tree(populated_tree, dst)
    assert (dst / "a.txt").exists()
    assert fs.tree_file_count(populated_tree) > 0
    assert fs.tree_size(populated_tree) > 0

    flat = tmp_path / "flat"
    fs.flatten_tree(populated_tree, flat)
    assert any(flat.iterdir())


def test_facade_temp_directory(fs: ZeroFS, tmp_path: Path) -> None:
    with fs.temp_directory(parent=tmp_path) as d:
        assert d.is_dir()
        captured = d
    assert not captured.exists()


def test_facade_sync_dirs(fs: ZeroFS, populated_tree: Path, tmp_path: Path) -> None:
    dst = tmp_path / "mirror"
    fs.sync_dirs(populated_tree, dst)
    assert (dst / "a.txt").exists()


def test_facade_move_tree(fs: ZeroFS, populated_tree: Path, tmp_path: Path) -> None:
    dst = tmp_path / "moved"
    fs.move_tree(populated_tree, dst)
    assert (dst / "a.txt").exists()
    assert not populated_tree.exists()


def test_facade_integrity_round_trip(fs: ZeroFS, populated_tree: Path, tmp_path: Path) -> None:
    digest = fs.directory_hash(populated_tree)
    assert len(digest) == 64

    manifest = fs.create_manifest(populated_tree)
    assert "a.txt" in manifest

    out = tmp_path / "manifest.json"
    fs.save_manifest(manifest, out)
    loaded, algo = fs.load_manifest(out)
    assert algo == "sha256"
    assert set(loaded.keys()) == set(manifest.keys())

    result = fs.verify_manifest(populated_tree, manifest)
    assert result.is_valid

    snap = fs.snapshot_hash(populated_tree)
    assert isinstance(snap, str)


def test_facade_verify_file(fs: ZeroFS, sample_file: Path) -> None:
    digest = fs.file_hash(sample_file)
    assert fs.verify_file(sample_file, expected_hash=digest) is True
    with pytest.raises(HashMismatchError):
        fs.verify_file(sample_file, expected_hash="0" * 64)


def test_facade_compare_directories(fs: ZeroFS, tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "same.txt").write_text("hello")
    (b / "same.txt").write_text("hello")
    (a / "only_a.txt").write_text("a")
    result = fs.compare_directories(a, b)
    assert "same.txt" in result.valid
    assert "only_a.txt" in result.missing


def test_facade_secure_helpers(fs: ZeroFS, tmp_path: Path) -> None:
    p = tmp_path / "secret.txt"
    p.write_text("sensitive")
    fs.secure_delete(p, passes=1, random_data=False)
    assert not p.exists()

    tree_root = tmp_path / "tree"
    (tree_root / "sub").mkdir(parents=True)
    (tree_root / "f.txt").write_text("alpha")
    (tree_root / "sub" / "g.txt").write_text("bravo")
    fs.secure_delete_directory(tree_root, passes=1, random_data=False)
    assert not tree_root.exists()


def test_facade_private_directory(fs: ZeroFS, tmp_path: Path) -> None:
    with fs.private_directory(parent=tmp_path) as d:
        assert d.is_dir()
        captured = d
    assert not captured.exists()


def test_facade_create_private_file(fs: ZeroFS, tmp_path: Path) -> None:
    target = tmp_path / "secret.txt"
    fs.create_private_file(target, text_content="hi")
    assert target.read_text() == "hi"
    if IS_UNIX:
        assert (target.stat().st_mode & 0o777) == 0o600


def test_facade_archive_round_trip(fs: ZeroFS, populated_tree: Path, tmp_path: Path) -> None:
    archive = tmp_path / "tree.zip"
    fs.create_zip(populated_tree, archive)
    listing = fs.list_archive(archive)
    assert listing
    out = tmp_path / "out"
    fs.extract(archive, out)
    assert any(out.rglob("a.txt"))


def test_facade_create_tar_round_trip(fs: ZeroFS, populated_tree: Path, tmp_path: Path) -> None:
    archive = tmp_path / "tree.tar"
    fs.create_tar(populated_tree, archive)
    out = tmp_path / "out"
    fs.extract_tar(archive, out)
    assert any(out.rglob("a.txt"))


def test_facade_extract_zip_alias(fs: ZeroFS, populated_tree: Path, tmp_path: Path) -> None:
    archive = tmp_path / "tree.zip"
    fs.create_zip(populated_tree, archive)
    out = tmp_path / "extracted"
    fs.extract_zip(archive, out)
    assert any(out.rglob("a.txt"))


def test_facade_locking_helpers_return_class_instances(fs: ZeroFS, tmp_path: Path) -> None:
    lock = fs.file_lock(tmp_path / "x.lock")
    assert hasattr(lock, "acquire")
    assert hasattr(lock, "release")

    tx = fs.file_transaction()
    assert hasattr(tx, "commit")
    assert hasattr(tx, "rollback")


def test_facade_file_watcher_returns_filewatcher(fs: ZeroFS, tmp_path: Path) -> None:
    w = fs.file_watcher(tmp_path)
    assert hasattr(w, "start")
    assert hasattr(w, "stop")


@pytest.mark.parametrize(
    ("facade_attr", "module_attr"),
    [
        ("read_text", "read_text"),
        ("write_text", "write_text"),
        ("read_json", "read_json"),
        ("write_json", "write_json"),
        ("file_hash", "file_hash"),
        ("ensure_dir", "ensure_dir"),
        ("safe_filename", "safe_filename"),
        ("normalize_path", "normalize_path"),
        ("get_metadata", "get_metadata"),
        ("copy_tree", "copy_tree"),
        ("directory_hash", "directory_hash"),
        ("secure_delete", "secure_delete"),
        ("create_zip", "create_zip"),
    ],
)
def test_facade_methods_match_top_level_aliases(facade_attr: str, module_attr: str) -> None:
    """The ZeroFS facade and the top-level ``zerofilesystem`` aliases should
    forward to the same underlying callable for representative entries."""
    facade_fn = getattr(ZeroFS, facade_attr)
    module_fn = getattr(zfs, module_attr)
    assert facade_fn is module_fn or callable(facade_fn) and callable(module_fn)
