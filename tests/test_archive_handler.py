"""Tests for ArchiveHandler - ZIP and TAR archive operations.

Copyright (c) 2025 Francesco Favi
"""

from pathlib import Path

import pytest

import zerofilesystem as zfs


@pytest.fixture
def sample_files(tmp_path: Path) -> Path:
    """Create sample files for archiving."""
    src = tmp_path / "source"
    src.mkdir()

    # Create files
    (src / "file1.txt").write_text("Content of file 1")
    (src / "file2.txt").write_text("Content of file 2")

    # Create subdirectory
    subdir = src / "subdir"
    subdir.mkdir()
    (subdir / "nested.txt").write_text("Nested content")

    return src


class TestCreateZip:
    """Tests for create_zip function."""

    def test_create_zip_basic(self, sample_files: Path, tmp_path: Path) -> None:
        """Test basic ZIP creation."""
        archive = tmp_path / "archive.zip"

        result = zfs.create_zip(sample_files, archive)

        assert result == archive
        assert archive.exists()
        assert archive.stat().st_size > 0

    def test_create_zip_contents(self, sample_files: Path, tmp_path: Path) -> None:
        """Test that ZIP contains expected files."""
        archive = tmp_path / "archive.zip"

        zfs.create_zip(sample_files, archive)

        # List archive contents
        contents = zfs.list_archive(archive)

        assert len(contents) >= 3
        assert any("file1.txt" in c for c in contents)
        assert any("file2.txt" in c for c in contents)
        assert any("nested.txt" in c for c in contents)

    def test_create_zip_with_filter(self, sample_files: Path, tmp_path: Path) -> None:
        """Test ZIP creation with file filter."""
        archive = tmp_path / "filtered.zip"

        # Only include file1.txt
        zfs.create_zip(
            sample_files,
            archive,
            filter_fn=lambda p: p.name == "file1.txt",
        )

        contents = zfs.list_archive(archive)

        assert len(contents) == 1
        assert "file1.txt" in contents[0]

    def test_create_zip_compression_stored(self, sample_files: Path, tmp_path: Path) -> None:
        """Test ZIP with no compression (stored)."""
        archive = tmp_path / "stored.zip"

        zfs.create_zip(sample_files, archive, compression="stored")

        assert archive.exists()

    def test_create_zip_compression_deflated(self, sample_files: Path, tmp_path: Path) -> None:
        """Test ZIP with deflate compression."""
        archive = tmp_path / "deflated.zip"

        zfs.create_zip(sample_files, archive, compression="deflated")

        assert archive.exists()


class TestExtractZip:
    """Tests for extract_zip function."""

    def test_extract_zip_basic(self, sample_files: Path, tmp_path: Path) -> None:
        """Test basic ZIP extraction."""
        archive = tmp_path / "archive.zip"
        extract_dir = tmp_path / "extracted"

        zfs.create_zip(sample_files, archive)
        result = zfs.extract_zip(archive, extract_dir)

        assert result == extract_dir
        assert extract_dir.exists()

    def test_extract_zip_preserves_structure(self, sample_files: Path, tmp_path: Path) -> None:
        """Test that extraction preserves directory structure."""
        archive = tmp_path / "archive.zip"
        extract_dir = tmp_path / "extracted"

        zfs.create_zip(sample_files, archive)
        zfs.extract_zip(archive, extract_dir)

        # Check files exist
        files = list(extract_dir.rglob("*"))
        file_names = [f.name for f in files if f.is_file()]

        assert "file1.txt" in file_names
        assert "file2.txt" in file_names
        assert "nested.txt" in file_names

    def test_extract_zip_with_filter(self, sample_files: Path, tmp_path: Path) -> None:
        """Test ZIP extraction with filter."""
        archive = tmp_path / "archive.zip"
        extract_dir = tmp_path / "extracted"

        zfs.create_zip(sample_files, archive)
        zfs.extract_zip(archive, extract_dir, filter_fn=lambda name: "file1" in name)

        files = list(extract_dir.rglob("*.txt"))
        file_names = [f.name for f in files]

        assert "file1.txt" in file_names
        assert "file2.txt" not in file_names


class TestCreateTar:
    """Tests for create_tar function."""

    def test_create_tar_basic(self, sample_files: Path, tmp_path: Path) -> None:
        """Test basic TAR creation."""
        archive = tmp_path / "archive.tar"

        result = zfs.create_tar(sample_files, archive)

        assert result == archive
        assert archive.exists()

    def test_create_tar_gzip(self, sample_files: Path, tmp_path: Path) -> None:
        """Test TAR with gzip compression."""
        archive = tmp_path / "archive.tar.gz"

        zfs.create_tar(sample_files, archive, compression="gz")

        assert archive.exists()
        assert archive.stat().st_size > 0

    def test_create_tar_bzip2(self, sample_files: Path, tmp_path: Path) -> None:
        """Test TAR with bzip2 compression."""
        archive = tmp_path / "archive.tar.bz2"

        zfs.create_tar(sample_files, archive, compression="bz2")

        assert archive.exists()

    def test_create_tar_xz(self, sample_files: Path, tmp_path: Path) -> None:
        """Test TAR with xz compression."""
        archive = tmp_path / "archive.tar.xz"

        zfs.create_tar(sample_files, archive, compression="xz")

        assert archive.exists()

    def test_create_tar_contents(self, sample_files: Path, tmp_path: Path) -> None:
        """Test that TAR contains expected files."""
        archive = tmp_path / "archive.tar"

        zfs.create_tar(sample_files, archive)

        contents = zfs.list_archive(archive)

        assert any("file1.txt" in c for c in contents)
        assert any("nested.txt" in c for c in contents)


class TestExtractTar:
    """Tests for extract_tar function."""

    def test_extract_tar_basic(self, sample_files: Path, tmp_path: Path) -> None:
        """Test basic TAR extraction."""
        archive = tmp_path / "archive.tar"
        extract_dir = tmp_path / "extracted"

        zfs.create_tar(sample_files, archive)
        result = zfs.extract_tar(archive, extract_dir)

        assert result == extract_dir
        assert extract_dir.exists()

    def test_extract_tar_gzip(self, sample_files: Path, tmp_path: Path) -> None:
        """Test extracting gzipped TAR."""
        archive = tmp_path / "archive.tar.gz"
        extract_dir = tmp_path / "extracted"

        zfs.create_tar(sample_files, archive, compression="gz")
        zfs.extract_tar(archive, extract_dir)

        files = list(extract_dir.rglob("*.txt"))
        assert len(files) >= 3

    def test_extract_tar_preserves_structure(self, sample_files: Path, tmp_path: Path) -> None:
        """Test that TAR extraction preserves directory structure."""
        archive = tmp_path / "archive.tar"
        extract_dir = tmp_path / "extracted"

        zfs.create_tar(sample_files, archive)
        zfs.extract_tar(archive, extract_dir)

        # Check nested file exists
        nested_files = list(extract_dir.rglob("nested.txt"))
        assert len(nested_files) == 1


class TestGenericExtract:
    """Tests for generic extract function."""

    def test_extract_zip_auto(self, sample_files: Path, tmp_path: Path) -> None:
        """Test auto-detecting ZIP format."""
        archive = tmp_path / "archive.zip"
        extract_dir = tmp_path / "extracted"

        zfs.create_zip(sample_files, archive)
        zfs.extract(archive, extract_dir)

        assert extract_dir.exists()
        files = list(extract_dir.rglob("*.txt"))
        assert len(files) >= 3

    def test_extract_tar_auto(self, sample_files: Path, tmp_path: Path) -> None:
        """Test auto-detecting TAR format."""
        archive = tmp_path / "archive.tar"
        extract_dir = tmp_path / "extracted"

        zfs.create_tar(sample_files, archive)
        zfs.extract(archive, extract_dir)

        assert extract_dir.exists()

    def test_extract_tar_gz_auto(self, sample_files: Path, tmp_path: Path) -> None:
        """Test auto-detecting TAR.GZ format."""
        archive = tmp_path / "archive.tar.gz"
        extract_dir = tmp_path / "extracted"

        zfs.create_tar(sample_files, archive, compression="gz")
        zfs.extract(archive, extract_dir)

        assert extract_dir.exists()


class TestListArchive:
    """Tests for list_archive function."""

    def test_list_zip_archive(self, sample_files: Path, tmp_path: Path) -> None:
        """Test listing ZIP archive contents."""
        archive = tmp_path / "archive.zip"

        zfs.create_zip(sample_files, archive)
        contents = zfs.list_archive(archive)

        assert isinstance(contents, list)
        assert len(contents) >= 3

    def test_list_tar_archive(self, sample_files: Path, tmp_path: Path) -> None:
        """Test listing TAR archive contents."""
        archive = tmp_path / "archive.tar"

        zfs.create_tar(sample_files, archive)
        contents = zfs.list_archive(archive)

        assert isinstance(contents, list)
        assert len(contents) >= 3

    def test_list_tar_gz_archive(self, sample_files: Path, tmp_path: Path) -> None:
        """Test listing TAR.GZ archive contents."""
        archive = tmp_path / "archive.tar.gz"

        zfs.create_tar(sample_files, archive, compression="gz")
        contents = zfs.list_archive(archive)

        assert isinstance(contents, list)


class TestArchiveRoundTrip:
    """Tests for archive create/extract roundtrip."""

    def test_zip_roundtrip_content_preserved(self, sample_files: Path, tmp_path: Path) -> None:
        """Test that ZIP roundtrip preserves file content."""
        archive = tmp_path / "archive.zip"
        extract_dir = tmp_path / "extracted"

        zfs.create_zip(sample_files, archive)
        zfs.extract_zip(archive, extract_dir)

        # Find and check content
        original = (sample_files / "file1.txt").read_text()
        extracted_files = list(extract_dir.rglob("file1.txt"))
        assert len(extracted_files) == 1
        assert extracted_files[0].read_text() == original

    def test_tar_roundtrip_content_preserved(self, sample_files: Path, tmp_path: Path) -> None:
        """Test that TAR roundtrip preserves file content."""
        archive = tmp_path / "archive.tar.gz"
        extract_dir = tmp_path / "extracted"

        zfs.create_tar(sample_files, archive, compression="gz")
        zfs.extract_tar(archive, extract_dir)

        # Find and check content
        original = (sample_files / "file1.txt").read_text()
        extracted_files = list(extract_dir.rglob("file1.txt"))
        assert len(extracted_files) == 1
        assert extracted_files[0].read_text() == original

    def test_unicode_filenames(self, tmp_path: Path) -> None:
        """Test archiving files with unicode names."""
        src = tmp_path / "source"
        src.mkdir()
        (src / "日本語.txt").write_text("Japanese content")
        (src / "émoji.txt").write_text("Accented content")

        archive = tmp_path / "unicode.zip"
        extract_dir = tmp_path / "extracted"

        zfs.create_zip(src, archive)
        zfs.extract_zip(archive, extract_dir)

        files = list(extract_dir.rglob("*.txt"))
        assert len(files) == 2
