"""Tests for platform constants and the Pathish type alias."""

from __future__ import annotations

import sys
from pathlib import Path

from zerofilesystem._platform import IS_LINUX, IS_MACOS, Pathish


def test_exactly_one_of_linux_macos_is_true() -> None:
    """zerofilesystem is POSIX-only; Linux + macOS are mutually exclusive,
    so on a supported platform exactly one of the two must be True."""
    assert IS_LINUX != IS_MACOS
    assert IS_LINUX or IS_MACOS, f"unsupported platform: {sys.platform}"


def test_pathish_accepts_str_and_path() -> None:
    """Documented contract: any Pathish-typed parameter accepts both str and
    pathlib.Path uniformly."""

    def take_path(p: Pathish) -> str:
        return str(Path(p))

    assert take_path("/tmp/foo") == take_path(Path("/tmp/foo"))
