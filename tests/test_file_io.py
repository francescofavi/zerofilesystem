"""Tests for FileIO - Basic file I/O operations.

Copyright (c) 2025 Francesco Favi
"""

from pathlib import Path

import pytest

import zerofilesystem as zo


class TestReadText:
    """Tests for read_text function."""

    def test_read_text_basic(self, tmp_path: Path) -> None:
        """Test basic text file reading."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Hello World", encoding="utf-8")

        content = zo.read_text(file_path)
        assert content == "Hello World"

    def test_read_text_with_encoding(self, tmp_path: Path) -> None:
        """Test reading text file with specific encoding."""
        file_path = tmp_path / "test_utf16.txt"
        file_path.write_text("Ciao àèìòù", encoding="utf-16")

        content = zo.read_text(file_path, encoding="utf-16")
        assert content == "Ciao àèìòù"

    def test_read_text_multiline(self, tmp_path: Path) -> None:
        """Test reading multiline text file."""
        file_path = tmp_path / "multiline.txt"
        expected = "Line 1\nLine 2\nLine 3"
        file_path.write_text(expected, encoding="utf-8")

        content = zo.read_text(file_path)
        assert content == expected

    def test_read_text_unicode(self, tmp_path: Path) -> None:
        """Test reading file with unicode characters."""
        file_path = tmp_path / "unicode.txt"
        expected = "日本語 中文 한국어 العربية"
        file_path.write_text(expected, encoding="utf-8")

        content = zo.read_text(file_path)
        assert content == expected

    def test_read_text_nonexistent_raises(self, tmp_path: Path) -> None:
        """Test reading non-existent file raises FileNotFoundError."""
        file_path = tmp_path / "nonexistent.txt"

        with pytest.raises(FileNotFoundError):
            zo.read_text(file_path)


class TestWriteText:
    """Tests for write_text function."""

    def test_write_text_basic(self, tmp_path: Path) -> None:
        """Test basic text file writing."""
        file_path = tmp_path / "output.txt"

        result = zo.write_text(file_path, "Hello World")

        assert result == file_path
        assert file_path.read_text() == "Hello World"

    def test_write_text_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Test that write_text creates parent directories."""
        file_path = tmp_path / "deep" / "nested" / "dir" / "file.txt"

        zo.write_text(file_path, "Content")

        assert file_path.exists()
        assert file_path.read_text() == "Content"

    def test_write_text_no_create_dirs(self, tmp_path: Path) -> None:
        """Test write_text fails when parent dir doesn't exist and create_dirs=False."""
        file_path = tmp_path / "nonexistent" / "file.txt"

        with pytest.raises(FileNotFoundError):
            zo.write_text(file_path, "Content", create_dirs=False)

    def test_write_text_atomic(self, tmp_path: Path) -> None:
        """Test atomic write doesn't leave partial files."""
        file_path = tmp_path / "atomic.txt"
        zo.write_text(file_path, "Original")

        # Atomic write
        zo.write_text(file_path, "Updated", atomic=True)

        assert file_path.read_text() == "Updated"
        # No temp files should remain
        temp_files = list(tmp_path.glob(".*tmp"))
        assert len(temp_files) == 0

    def test_write_text_non_atomic(self, tmp_path: Path) -> None:
        """Test non-atomic write."""
        file_path = tmp_path / "non_atomic.txt"

        zo.write_text(file_path, "Content", atomic=False)

        assert file_path.read_text() == "Content"

    def test_write_text_overwrites_existing(self, tmp_path: Path) -> None:
        """Test that write_text overwrites existing file."""
        file_path = tmp_path / "existing.txt"
        file_path.write_text("Original")

        zo.write_text(file_path, "New Content")

        assert file_path.read_text() == "New Content"


class TestReadBytes:
    """Tests for read_bytes function."""

    def test_read_bytes_basic(self, tmp_path: Path) -> None:
        """Test basic binary file reading."""
        file_path = tmp_path / "binary.bin"
        file_path.write_bytes(b"\x00\x01\x02\xff")

        content = zo.read_bytes(file_path)
        assert content == b"\x00\x01\x02\xff"

    def test_read_bytes_image_like(self, tmp_path: Path) -> None:
        """Test reading binary data (simulated image header)."""
        file_path = tmp_path / "fake_png.bin"
        png_header = b"\x89PNG\r\n\x1a\n"  # PNG magic bytes
        file_path.write_bytes(png_header)

        content = zo.read_bytes(file_path)
        assert content == png_header

    def test_read_bytes_nonexistent_raises(self, tmp_path: Path) -> None:
        """Test reading non-existent binary file raises FileNotFoundError."""
        file_path = tmp_path / "nonexistent.bin"

        with pytest.raises(FileNotFoundError):
            zo.read_bytes(file_path)


class TestWriteBytes:
    """Tests for write_bytes function."""

    def test_write_bytes_basic(self, tmp_path: Path) -> None:
        """Test basic binary file writing."""
        file_path = tmp_path / "output.bin"

        result = zo.write_bytes(file_path, b"\x00\x01\x02\xff")

        assert result == file_path
        assert file_path.read_bytes() == b"\x00\x01\x02\xff"

    def test_write_bytes_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Test that write_bytes creates parent directories."""
        file_path = tmp_path / "deep" / "path" / "data.bin"

        zo.write_bytes(file_path, b"binary data")

        assert file_path.exists()
        assert file_path.read_bytes() == b"binary data"

    def test_write_bytes_atomic(self, tmp_path: Path) -> None:
        """Test atomic binary write."""
        file_path = tmp_path / "atomic.bin"
        zo.write_bytes(file_path, b"original")

        zo.write_bytes(file_path, b"updated", atomic=True)

        assert file_path.read_bytes() == b"updated"


class TestAcceptsBothPathTypes:
    """Tests that functions accept both str and Path."""

    def test_read_text_str_path(self, tmp_path: Path) -> None:
        """Test read_text accepts string path."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("content")

        content = zo.read_text(str(file_path))
        assert content == "content"

    def test_write_text_str_path(self, tmp_path: Path) -> None:
        """Test write_text accepts string path."""
        file_path = str(tmp_path / "test.txt")

        zo.write_text(file_path, "content")

        assert Path(file_path).read_text() == "content"

    def test_read_bytes_str_path(self, tmp_path: Path) -> None:
        """Test read_bytes accepts string path."""
        file_path = tmp_path / "test.bin"
        file_path.write_bytes(b"data")

        content = zo.read_bytes(str(file_path))
        assert content == b"data"

    def test_write_bytes_str_path(self, tmp_path: Path) -> None:
        """Test write_bytes accepts string path."""
        file_path = str(tmp_path / "test.bin")

        zo.write_bytes(file_path, b"data")

        assert Path(file_path).read_bytes() == b"data"
