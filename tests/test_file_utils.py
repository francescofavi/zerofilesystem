"""Tests for safe_filename and atomic_write."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import zerofilesystem as zfs


@pytest.mark.parametrize(
    ("raw", "expected_in_result"),
    [
        ("hello.txt", "hello.txt"),
        ("file:name*.txt", "file_name_.txt"),
        ('weird<>:"|?*.txt', "weird"),
        ("with/slash.txt", "with_slash.txt"),
        ("with\\back.txt", "with_back.txt"),
    ],
)
def test_safe_filename_replaces_illegal_characters(raw: str, expected_in_result: str) -> None:
    assert expected_in_result in zfs.safe_filename(raw)


def test_safe_filename_strips_leading_and_trailing_dots_and_spaces() -> None:
    assert zfs.safe_filename(" .hidden.txt ") == "hidden.txt"
    assert zfs.safe_filename("trailing.   ") == "trailing"


def test_safe_filename_replaces_control_characters() -> None:
    assert zfs.safe_filename("a\x00b\x1fc") == "a_b_c"


def test_safe_filename_custom_replacement_character() -> None:
    assert zfs.safe_filename("a:b", replacement="-") == "a-b"


def test_safe_filename_empty_input_falls_back_to_unnamed() -> None:
    assert zfs.safe_filename("") == "unnamed"
    assert zfs.safe_filename("...") == "unnamed"


def test_safe_filename_preserves_unicode() -> None:
    assert "日本" in zfs.safe_filename("日本語.txt")


def test_atomic_write_text_creates_file_with_content(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    with zfs.atomic_write(target) as f:
        f.write("hello")
    assert target.read_text() == "hello"


def test_atomic_write_binary_mode(tmp_path: Path) -> None:
    target = tmp_path / "out.bin"
    payload = b"\x00\x01\x02"
    with zfs.atomic_write(target, mode="wb") as f:
        f.write(payload)
    assert target.read_bytes() == payload


def test_atomic_write_creates_parent_directory(tmp_path: Path) -> None:
    target = tmp_path / "deep" / "nested" / "out.txt"
    with zfs.atomic_write(target) as f:
        f.write("ok")
    assert target.read_text() == "ok"


def test_atomic_write_rolls_back_on_exception(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    with pytest.raises(RuntimeError), zfs.atomic_write(target) as f:
        f.write("partial")
        raise RuntimeError("boom")
    assert not target.exists()
    leftovers = list(tmp_path.glob(".out.txt.*.tmp"))
    assert leftovers == []


def test_atomic_write_does_not_overwrite_until_close(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    target.write_text("original")
    with zfs.atomic_write(target) as f:
        f.write("new")
        # While the context is open, the original file must still hold the
        # original content (writes go to a temp file that is renamed on exit).
        assert target.read_text() == "original"
    assert target.read_text() == "new"


def test_atomic_write_supports_json_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "data.json"
    obj = {"k": [1, 2, 3], "u": "àèì"}
    with zfs.atomic_write(target) as f:
        json.dump(obj, f, ensure_ascii=False)
    assert json.loads(target.read_text(encoding="utf-8")) == obj


def test_atomic_write_overwrites_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    target.write_text("old")
    with zfs.atomic_write(target) as f:
        f.write("new")
    assert target.read_text() == "new"
