"""Tests for file_hash."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

import pytest

import zerofilesystem as zfs

HashAlgo = Literal["md5", "sha1", "sha256", "sha512"]


def _expected_hash(data: bytes, algo: str) -> str:
    h = hashlib.new(algo)
    h.update(data)
    return h.hexdigest()


@pytest.mark.parametrize("algo", ["md5", "sha1", "sha256", "sha512"])
def test_file_hash_matches_hashlib_reference(tmp_path: Path, algo: HashAlgo) -> None:
    payload = b"the quick brown fox jumps over the lazy dog\n" * 100
    target = tmp_path / "data.bin"
    target.write_bytes(payload)
    assert zfs.file_hash(target, algo=algo) == _expected_hash(payload, algo)


def test_file_hash_default_algorithm_is_sha256(tmp_path: Path) -> None:
    target = tmp_path / "x.bin"
    target.write_bytes(b"abc")
    assert zfs.file_hash(target) == _expected_hash(b"abc", "sha256")


def test_file_hash_empty_file(tmp_path: Path) -> None:
    target = tmp_path / "empty.bin"
    target.touch()
    assert zfs.file_hash(target) == _expected_hash(b"", "sha256")


def test_file_hash_streaming_with_small_chunk_matches_one_shot(tmp_path: Path) -> None:
    payload = b"a" * (4 * 1024 * 1024)  # 4 MiB, larger than default chunk
    target = tmp_path / "big.bin"
    target.write_bytes(payload)
    streamed = zfs.file_hash(target, chunk=4096)
    one_shot = _expected_hash(payload, "sha256")
    assert streamed == one_shot


def test_file_hash_progress_callback_reports_total_bytes(tmp_path: Path) -> None:
    payload = b"abcdef" * 1000
    target = tmp_path / "data.bin"
    target.write_bytes(payload)
    seen: list[tuple[int, int]] = []

    def record(processed: int, total: int) -> None:
        seen.append((processed, total))

    zfs.file_hash(target, chunk=64, progress_callback=record)
    assert seen, "progress callback was never invoked"
    last_processed, total = seen[-1]
    assert last_processed == len(payload)
    assert total == len(payload)


def test_file_hash_progress_callback_exception_is_swallowed(tmp_path: Path) -> None:
    target = tmp_path / "data.bin"
    target.write_bytes(b"x" * 1000)

    def boom(_processed: int, _total: int) -> None:
        raise RuntimeError("callback raised")

    digest = zfs.file_hash(target, chunk=64, progress_callback=boom)
    assert digest == _expected_hash(b"x" * 1000, "sha256")


def test_file_hash_invalid_algorithm_raises(tmp_path: Path) -> None:
    target = tmp_path / "data.bin"
    target.write_bytes(b"x")
    with pytest.raises(ValueError):
        zfs.file_hash(target, algo="not-an-algo")  # type: ignore[arg-type]


def test_file_hash_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        zfs.file_hash(tmp_path / "nope.bin")
