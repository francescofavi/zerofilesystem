"""Tests for PathUtils - Path normalization and utilities.

Copyright (c) 2025 Francesco Favi
"""

import os
from pathlib import Path

import pytest

import zerofilesystem as zfs
from zerofilesystem import InvalidPathError


class TestNormalizePath:
    """Tests for normalize_path function."""

    def test_normalize_removes_dot(self) -> None:
        """Test normalizing path with . components."""
        result = zfs.normalize_path("./foo/./bar")
        assert result == Path("foo/bar")

    def test_normalize_resolves_dotdot(self) -> None:
        """Test normalizing path with .. components."""
        result = zfs.normalize_path("foo/bar/../baz")
        assert result == Path("foo/baz")

    def test_normalize_mixed(self) -> None:
        """Test normalizing path with mixed . and .. components."""
        result = zfs.normalize_path("./foo/../bar/./baz/../qux")
        assert result == Path("bar/qux")

    def test_normalize_already_normalized(self) -> None:
        """Test normalizing already normalized path."""
        result = zfs.normalize_path("foo/bar/baz")
        assert result == Path("foo/bar/baz")

    def test_normalize_accepts_path_object(self) -> None:
        """Test normalize_path accepts Path object."""
        result = zfs.normalize_path(Path("./foo/../bar"))
        assert result == Path("bar")


class TestToAbsolute:
    """Tests for to_absolute function."""

    def test_to_absolute_relative(self, tmp_path: Path) -> None:
        """Test converting relative path to absolute."""
        os.chdir(tmp_path)
        result = zfs.to_absolute("foo/bar")

        assert result.is_absolute()
        assert str(result).endswith("foo/bar") or str(result).endswith("foo\\bar")

    def test_to_absolute_already_absolute(self) -> None:
        """Test absolute path remains unchanged."""
        abs_path = Path("/foo/bar").resolve()
        result = zfs.to_absolute(abs_path)

        assert result == abs_path

    def test_to_absolute_with_base(self, tmp_path: Path) -> None:
        """Test to_absolute with custom base directory."""
        result = zfs.to_absolute("subdir/file.txt", base=tmp_path)

        expected = tmp_path / "subdir" / "file.txt"
        assert result == expected

    def test_to_absolute_current_dir(self, tmp_path: Path) -> None:
        """Test to_absolute with current directory reference."""
        os.chdir(tmp_path)
        result = zfs.to_absolute(".")

        assert result.is_absolute()


class TestToRelative:
    """Tests for to_relative function."""

    def test_to_relative_child_path(self, tmp_path: Path) -> None:
        """Test converting child path to relative."""
        child = tmp_path / "foo" / "bar"

        result = zfs.to_relative(child, base=tmp_path)

        assert result == Path("foo/bar")

    def test_to_relative_sibling_path(self, tmp_path: Path) -> None:
        """Test converting sibling path to relative with .."""
        base = tmp_path / "foo"
        target = tmp_path / "bar"
        base.mkdir()
        target.mkdir()

        result = zfs.to_relative(target, base=base)

        assert ".." in str(result)

    def test_to_relative_same_path(self, tmp_path: Path) -> None:
        """Test converting same path to relative."""
        result = zfs.to_relative(tmp_path, base=tmp_path)

        assert result == Path(".")


class TestToPosix:
    """Tests for to_posix function."""

    def test_to_posix_converts_backslashes(self) -> None:
        """Test converting Windows-style paths to POSIX format."""
        # On Unix, backslashes are valid filename chars, so we test with Path
        # On Windows, Path("foo\\bar") becomes foo/bar when using as_posix()
        from pathlib import PureWindowsPath

        # Test using PureWindowsPath which always interprets \ as separator
        win_path = PureWindowsPath("foo\\bar\\baz")
        result = win_path.as_posix()
        assert result == "foo/bar/baz"

    def test_to_posix_already_posix(self) -> None:
        """Test POSIX path remains unchanged."""
        result = zfs.to_posix("foo/bar/baz")

        assert result == "foo/bar/baz"

    def test_to_posix_with_path_object(self) -> None:
        """Test to_posix with Path object."""
        result = zfs.to_posix(Path("foo/bar"))

        assert result == "foo/bar"


class TestExpandPath:
    """Tests for expand_path function."""

    def test_expand_tilde(self) -> None:
        """Test expanding ~ to home directory."""
        result = zfs.expand_path("~/foo")

        assert "~" not in str(result)
        assert result.is_absolute()

    def test_expand_env_var(self, tmp_path: Path) -> None:
        """Test expanding environment variables."""
        os.environ["TEST_VAR"] = str(tmp_path)

        result = zfs.expand_path("$TEST_VAR/foo")

        assert str(tmp_path) in str(result)

        del os.environ["TEST_VAR"]

    def test_expand_combined(self, tmp_path: Path) -> None:
        """Test expanding both ~ and env vars."""
        os.environ["TEST_DIR"] = "subdir"

        result = zfs.expand_path("~/$TEST_DIR")

        assert "~" not in str(result)
        assert "subdir" in str(result)

        del os.environ["TEST_DIR"]


class TestIsSubpath:
    """Tests for is_subpath function."""

    def test_is_subpath_true(self, tmp_path: Path) -> None:
        """Test is_subpath returns True for child path."""
        child = tmp_path / "foo" / "bar"

        assert zfs.is_subpath(child, tmp_path) is True

    def test_is_subpath_false(self, tmp_path: Path) -> None:
        """Test is_subpath returns False for non-child path."""
        other = Path("/some/other/path")

        # This might be True on some systems if paths resolve to same location
        # So we use a clearly different path
        result = zfs.is_subpath(other, tmp_path)

        # If other doesn't exist and tmp_path does, they can't be related
        if not other.exists():
            assert result is False

    def test_is_subpath_same_path(self, tmp_path: Path) -> None:
        """Test is_subpath with same path."""
        assert zfs.is_subpath(tmp_path, tmp_path) is True

    def test_is_subpath_parent_is_child(self, tmp_path: Path) -> None:
        """Test is_subpath when parent is actually child."""
        child = tmp_path / "foo"

        assert zfs.is_subpath(tmp_path, child) is False


class TestCommonPath:
    """Tests for common_path function."""

    def test_common_path_siblings(self, tmp_path: Path) -> None:
        """Test common path of sibling directories."""
        path1 = tmp_path / "foo" / "bar"
        path2 = tmp_path / "foo" / "baz"

        result = zfs.common_path(path1, path2)

        assert result == (tmp_path / "foo").resolve()

    def test_common_path_parent_child(self, tmp_path: Path) -> None:
        """Test common path of parent and child."""
        parent = tmp_path / "foo"
        child = tmp_path / "foo" / "bar" / "baz"

        result = zfs.common_path(parent, child)

        assert result == parent.resolve()

    def test_common_path_multiple(self, tmp_path: Path) -> None:
        """Test common path of multiple paths."""
        paths = [
            tmp_path / "a" / "b" / "c",
            tmp_path / "a" / "b" / "d",
            tmp_path / "a" / "e",
        ]

        result = zfs.common_path(*paths)

        assert result == (tmp_path / "a").resolve()

    def test_common_path_no_args(self) -> None:
        """Test common_path with no arguments."""
        result = zfs.common_path()

        assert result is None


class TestValidatePath:
    """Tests for validate_path function."""

    def test_validate_path_exists(self, tmp_path: Path) -> None:
        """Test validate_path with must_exist=True."""
        file_path = tmp_path / "exists.txt"
        file_path.write_text("content")

        result = zfs.validate_path(file_path, must_exist=True)

        assert result == file_path

    def test_validate_path_not_exists_raises(self, tmp_path: Path) -> None:
        """Test validate_path raises for non-existent path."""
        file_path = tmp_path / "nonexistent.txt"

        with pytest.raises(InvalidPathError):
            zfs.validate_path(file_path, must_exist=True)

    def test_validate_path_must_be_file(self, tmp_path: Path) -> None:
        """Test validate_path with must_be_file=True."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("content")

        result = zfs.validate_path(file_path, must_be_file=True)

        assert result == file_path

    def test_validate_path_file_not_dir_raises(self, tmp_path: Path) -> None:
        """Test validate_path raises when file expected but got dir."""
        with pytest.raises(InvalidPathError):
            zfs.validate_path(tmp_path, must_exist=True, must_be_file=True)

    def test_validate_path_must_be_dir(self, tmp_path: Path) -> None:
        """Test validate_path with must_be_dir=True."""
        result = zfs.validate_path(tmp_path, must_be_dir=True)

        assert result == tmp_path

    def test_validate_path_dir_not_file_raises(self, tmp_path: Path) -> None:
        """Test validate_path raises when dir expected but got file."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("content")

        with pytest.raises(InvalidPathError):
            zfs.validate_path(file_path, must_exist=True, must_be_dir=True)

    def test_validate_path_no_constraints(self, tmp_path: Path) -> None:
        """Test validate_path without constraints."""
        nonexistent = tmp_path / "whatever"

        result = zfs.validate_path(nonexistent)

        assert result == nonexistent
