"""Tests for the small private helpers in classes._internal.

The module is internal but feeds Watcher and Finder, so its parsing helpers
need clear contracts.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from zerofilesystem.classes._internal import parse_datetime, parse_size


def test_parse_size_passes_int_through() -> None:
    assert parse_size(1024) == 1024


def test_parse_size_handles_known_units() -> None:
    assert parse_size("1KB") == 1024
    assert parse_size("2MB") == 2 * 1024 * 1024
    assert parse_size("1.5GB") == int(1.5 * 1024 * 1024 * 1024)


def test_parse_size_default_unit_is_bytes() -> None:
    assert parse_size("512") == 512


def test_parse_size_rejects_malformed_input() -> None:
    with pytest.raises(ValueError):
        parse_size("not-a-size")


def test_parse_size_rejects_unknown_unit() -> None:
    with pytest.raises(ValueError):
        parse_size("5 ZB")


def test_parse_datetime_passes_datetime_through() -> None:
    dt = datetime(2024, 6, 1, 10, 0, 0)
    assert parse_datetime(dt) is dt


def test_parse_datetime_treats_timedelta_as_relative_to_now() -> None:
    delta = timedelta(days=1)
    result = parse_datetime(delta)
    assert (datetime.now() - result) >= delta - timedelta(seconds=1)


def test_parse_datetime_rejects_unparseable_string() -> None:
    with pytest.raises(ValueError):
        parse_datetime("not-a-date-at-all")
