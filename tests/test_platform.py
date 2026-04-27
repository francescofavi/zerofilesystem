"""Tests for platform constants and the Pathish type alias."""

from __future__ import annotations

from pathlib import Path

from zerofilesystem._platform import IS_LINUX, IS_MACOS, IS_UNIX, IS_WINDOWS, Pathish


def test_exactly_one_primary_platform_is_true() -> None:
    """Sanity check that platform detection is mutually exclusive.

    On any supported runner — Windows, macOS, Linux — exactly one of the
    three primary flags is True. If this fires the package is running on
    a platform it doesn't classify yet (e.g. FreeBSD, AIX)."""
    assert sum(int(flag) for flag in (IS_WINDOWS, IS_MACOS, IS_LINUX)) == 1


def test_unix_flag_is_macos_or_linux_and_never_overlaps_windows() -> None:
    """IS_UNIX is the convenience union of macOS + Linux; it never overlaps
    with Windows. Code that needs a single POSIX/non-POSIX branch can rely
    on this invariant."""
    assert (IS_MACOS or IS_LINUX) == IS_UNIX
    assert IS_UNIX != IS_WINDOWS


def test_pathish_accepts_str_and_path() -> None:
    """Documented contract: any ``Pathish``-typed parameter accepts both
    ``str`` and ``pathlib.Path`` uniformly."""

    def take_path(p: Pathish) -> str:
        return str(Path(p))

    assert take_path("/tmp/foo") == take_path(Path("/tmp/foo"))
