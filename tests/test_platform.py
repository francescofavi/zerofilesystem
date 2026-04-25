"""Tests for platform constants and the Pathish type alias."""

from __future__ import annotations

import sys
from pathlib import Path

import zerofilesystem as zfs
from zerofilesystem._platform import IS_LINUX, IS_MACOS, IS_UNIX, IS_WINDOWS, Pathish


def test_platform_constants_are_exposed_at_top_level() -> None:
    assert zfs.IS_WINDOWS is IS_WINDOWS
    assert zfs.IS_MACOS is IS_MACOS
    assert zfs.IS_LINUX is IS_LINUX
    assert zfs.IS_UNIX is IS_UNIX


def test_exactly_one_of_windows_macos_linux_is_true() -> None:
    primary = (IS_WINDOWS, IS_MACOS, IS_LINUX)
    assert sum(int(flag) for flag in primary) == 1


def test_unix_is_macos_or_linux() -> None:
    assert (IS_MACOS or IS_LINUX) == IS_UNIX
    assert IS_UNIX != IS_WINDOWS


def test_constants_match_sys_platform() -> None:
    assert (sys.platform == "win32") == IS_WINDOWS
    assert (sys.platform == "darwin") == IS_MACOS
    assert sys.platform.startswith("linux") == IS_LINUX


def test_pathish_accepts_str_and_path() -> None:
    """Pathish is `str | Path`. Functions typed as Pathish must accept both."""

    def take_path(p: Pathish) -> str:
        return str(Path(p))

    assert take_path("/tmp/foo") == take_path(Path("/tmp/foo"))


def test_pathish_is_a_union() -> None:
    """Pathish should be the str|Path union, exposed as a typing alias."""
    assert Pathish is not None
    args = getattr(Pathish, "__args__", None)
    assert args is not None
    assert str in args
    assert Path in args
