"""Tests for gzip_compress / gzip_decompress."""

from __future__ import annotations

import gzip
from pathlib import Path

import pytest

import zerofilesystem as zfs


def test_compress_creates_default_dotgz_path(sample_file: Path) -> None:
    out = zfs.gzip_compress(sample_file)
    assert out == sample_file.with_suffix(sample_file.suffix + ".gz")
    assert out.exists()
    assert out.stat().st_size > 0


def test_compress_to_explicit_destination(sample_file: Path, tmp_path: Path) -> None:
    dst = tmp_path / "out" / "blob.gz"
    out = zfs.gzip_compress(sample_file, dst=dst)
    assert out == dst
    assert dst.exists()


def test_compress_creates_destination_parents(sample_file: Path, tmp_path: Path) -> None:
    dst = tmp_path / "deep" / "nested" / "blob.gz"
    zfs.gzip_compress(sample_file, dst=dst)
    assert dst.exists()


def test_decompress_default_strips_dotgz(sample_file: Path) -> None:
    compressed = zfs.gzip_compress(sample_file)
    sample_file.unlink()
    out = zfs.gzip_decompress(compressed)
    assert out == sample_file
    assert out.exists()


def test_decompress_without_dotgz_appends_decompressed_suffix(
    sample_file: Path, tmp_path: Path
) -> None:
    fake = tmp_path / "file.bin"
    with gzip.open(fake, "wb") as f:
        f.write(b"payload")
    out = zfs.gzip_decompress(fake)
    assert out.name == "file.bin.decompressed"
    assert out.read_bytes() == b"payload"


def test_roundtrip_preserves_text_content(sample_file: Path, tmp_path: Path) -> None:
    original = sample_file.read_text(encoding="utf-8")
    compressed = zfs.gzip_compress(sample_file, dst=tmp_path / "c.gz")
    restored = zfs.gzip_decompress(compressed, dst=tmp_path / "restored.txt")
    assert restored.read_text(encoding="utf-8") == original


def test_roundtrip_preserves_binary_content(sample_bytes_file: Path, tmp_path: Path) -> None:
    original = sample_bytes_file.read_bytes()
    compressed = zfs.gzip_compress(sample_bytes_file, dst=tmp_path / "c.gz")
    restored = zfs.gzip_decompress(compressed, dst=tmp_path / "restored.bin")
    assert restored.read_bytes() == original


@pytest.mark.parametrize("level", [1, 6, 9])
def test_compress_levels_all_produce_decompressible_output(
    sample_file: Path, tmp_path: Path, level: int
) -> None:
    compressed = zfs.gzip_compress(sample_file, dst=tmp_path / f"c-{level}.gz", level=level)
    restored = zfs.gzip_decompress(compressed, dst=tmp_path / f"r-{level}.txt")
    assert restored.read_text(encoding="utf-8") == sample_file.read_text(encoding="utf-8")


def test_compress_non_atomic_does_not_leave_tmp_file(sample_file: Path, tmp_path: Path) -> None:
    dst = tmp_path / "blob.gz"
    zfs.gzip_compress(sample_file, dst=dst, atomic=False)
    leftovers = list(tmp_path.glob(".blob.gz.*.tmp"))
    assert leftovers == []


def test_compress_missing_source_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        zfs.gzip_compress(tmp_path / "does-not-exist.txt")


def test_decompress_corrupt_input_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.gz"
    bad.write_bytes(b"not a gzip stream")
    with pytest.raises((OSError, gzip.BadGzipFile)):
        zfs.gzip_decompress(bad, dst=tmp_path / "out.bin")


def test_compress_empty_file_roundtrips(tmp_path: Path) -> None:
    empty = tmp_path / "empty.txt"
    empty.write_text("")
    compressed = zfs.gzip_compress(empty)
    restored = zfs.gzip_decompress(compressed, dst=tmp_path / "restored.txt")
    assert restored.read_text() == ""
