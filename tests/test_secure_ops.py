"""Tests for secure_delete, secure_delete_directory, private_directory and
create_private_file.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

import zerofilesystem as zfs
from zerofilesystem.classes.exceptions import SecureDeleteError
from zerofilesystem.classes.secure_ops import SecureOps


def test_secure_delete_removes_file(sample_file: Path) -> None:
    zfs.secure_delete(sample_file)
    assert not sample_file.exists()


def test_secure_delete_missing_file_is_noop(tmp_path: Path) -> None:
    zfs.secure_delete(tmp_path / "ghost")  # must not raise


def test_secure_delete_rejects_directory(tmp_path: Path) -> None:
    d = tmp_path / "subdir"
    d.mkdir()
    with pytest.raises(SecureDeleteError):
        zfs.secure_delete(d)


def test_secure_delete_with_zeros_overwrites_before_delete(tmp_path: Path) -> None:
    p = tmp_path / "data.bin"
    p.write_bytes(b"\xff" * 1024)
    zfs.secure_delete(p, passes=1, random_data=False)
    assert not p.exists()


def test_secure_delete_with_random_data_passes(tmp_path: Path) -> None:
    p = tmp_path / "data.bin"
    p.write_bytes(b"\xff" * 1024)
    zfs.secure_delete(p, passes=2, random_data=True)
    assert not p.exists()


def test_secure_delete_against_readonly_file_succeeds(tmp_path: Path) -> None:
    """secure_delete chmods +w on a readonly file before overwriting; the
    file should be gone afterwards even if the user tried to protect it."""
    p = tmp_path / "ro.bin"
    p.write_bytes(b"x" * 32)
    os.chmod(p, stat.S_IRUSR)
    zfs.secure_delete(p)
    assert not p.exists()


def test_secure_delete_directory_removes_tree(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    (root / "sub").mkdir(parents=True)
    (root / "a.txt").write_text("alpha")
    (root / "sub" / "b.txt").write_text("bravo")
    zfs.secure_delete_directory(root, passes=1, random_data=False)
    assert not root.exists()


def test_secure_delete_directory_missing_is_noop(tmp_path: Path) -> None:
    zfs.secure_delete_directory(tmp_path / "ghost")  # must not raise


def test_secure_delete_directory_falls_back_to_secure_delete_for_files(
    tmp_path: Path,
) -> None:
    p = tmp_path / "file.txt"
    p.write_text("alpha")
    zfs.secure_delete_directory(p, passes=1, random_data=False)
    assert not p.exists()


def test_private_directory_yields_existing_directory(tmp_path: Path) -> None:
    with zfs.private_directory(parent=tmp_path) as d:
        assert d.is_dir()
        (d / "secret.txt").write_text("classified")
    assert not d.exists()


def test_private_directory_no_cleanup_keeps_directory(tmp_path: Path) -> None:
    with zfs.private_directory(parent=tmp_path, cleanup=False) as d:
        captured = d
    assert captured.exists()


def test_private_directory_uses_prefix(tmp_path: Path) -> None:
    with zfs.private_directory(prefix="locked_", parent=tmp_path) as d:
        assert d.name.startswith("locked_")


def test_private_directory_has_owner_only_permissions(tmp_path: Path) -> None:
    """Private directories must be 0o700 — owner-only access is the whole
    point of using ``private_directory`` over ``temp_directory``."""
    with zfs.private_directory(parent=tmp_path) as d:
        assert (d.stat().st_mode & 0o777) == 0o700


def test_private_directory_secure_cleanup_removes_directory(tmp_path: Path) -> None:
    with zfs.private_directory(parent=tmp_path, secure_cleanup=True) as d:
        (d / "x.txt").write_text("y")
        captured = d
    assert not captured.exists()


def test_create_private_file_with_text_content(tmp_path: Path) -> None:
    target = tmp_path / "secret.txt"
    p = zfs.create_private_file(target, text_content="ssh-key")
    assert p == target
    assert target.read_text() == "ssh-key"


def test_create_private_file_with_binary_content(tmp_path: Path) -> None:
    target = tmp_path / "secret.bin"
    payload = b"\x00\x01\x02\xff"
    zfs.create_private_file(target, content=payload)
    assert target.read_bytes() == payload


def test_create_private_file_no_content_creates_empty_file(tmp_path: Path) -> None:
    target = tmp_path / "blank.txt"
    zfs.create_private_file(target)
    assert target.exists()
    assert target.read_bytes() == b""


def test_create_private_file_creates_parent_directory(tmp_path: Path) -> None:
    target = tmp_path / "deep" / "nested" / "secret.txt"
    zfs.create_private_file(target, text_content="x")
    assert target.exists()


def test_create_private_file_has_owner_only_permissions(tmp_path: Path) -> None:
    """Private files must be 0o600 — same security guarantee as
    ``private_directory``, applied at file granularity."""
    target = tmp_path / "secret.txt"
    zfs.create_private_file(target, text_content="x")
    assert (target.stat().st_mode & 0o777) == 0o600


def test_create_private_file_overwrites_existing(tmp_path: Path) -> None:
    target = tmp_path / "f.txt"
    target.write_text("OLD")
    zfs.create_private_file(target, text_content="NEW")
    assert target.read_text() == "NEW"


def test_set_private_permissions_uses_0o600_for_file_and_0o700_for_directory(
    tmp_path: Path,
) -> None:
    f = tmp_path / "f.txt"
    f.write_text("x")
    SecureOps.set_private_permissions(f)
    assert (f.stat().st_mode & 0o777) == 0o600

    d = tmp_path / "subdir"
    d.mkdir()
    SecureOps.set_private_permissions(d)
    assert (d.stat().st_mode & 0o777) == 0o700


def test_generate_random_filename_respects_length_and_extension() -> None:
    plain = SecureOps.generate_random_filename()
    assert len(plain) == 16

    custom = SecureOps.generate_random_filename(length=8, extension=".bin")
    assert custom.endswith(".bin")
    assert len(custom) == 8 + len(".bin")
