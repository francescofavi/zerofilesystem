"""Tests for FileTransaction - Pseudo-transactional file operations.

Copyright (c) 2025 Francesco Favi
"""

from pathlib import Path

import pytest

import zerofilesystem as zfs
from zerofilesystem import TransactionError


class TestFileTransactionBasic:
    """Basic tests for FileTransaction."""

    def test_transaction_write_text(self, tmp_path: Path) -> None:
        """Test basic text file write in transaction."""
        file_path = tmp_path / "test.txt"

        with zfs.FileTransaction() as tx:
            tx.write_text(file_path, "Hello World")

        assert file_path.read_text() == "Hello World"

    def test_transaction_write_bytes(self, tmp_path: Path) -> None:
        """Test binary file write in transaction."""
        file_path = tmp_path / "test.bin"

        with zfs.FileTransaction() as tx:
            tx.write_bytes(file_path, b"\x00\x01\x02")

        assert file_path.read_bytes() == b"\x00\x01\x02"

    def test_transaction_multiple_files(self, tmp_path: Path) -> None:
        """Test writing multiple files in single transaction."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file3 = tmp_path / "file3.txt"

        with zfs.FileTransaction() as tx:
            tx.write_text(file1, "Content 1")
            tx.write_text(file2, "Content 2")
            tx.write_text(file3, "Content 3")

        assert file1.read_text() == "Content 1"
        assert file2.read_text() == "Content 2"
        assert file3.read_text() == "Content 3"

    def test_transaction_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Test that transaction creates parent directories."""
        file_path = tmp_path / "deep" / "nested" / "file.txt"

        with zfs.FileTransaction() as tx:
            tx.write_text(file_path, "Content")

        assert file_path.exists()
        assert file_path.read_text() == "Content"

    def test_transaction_explicit_commit(self, tmp_path: Path) -> None:
        """Test explicit commit."""
        file_path = tmp_path / "test.txt"

        tx = zfs.FileTransaction()
        tx.write_text(file_path, "Content")
        tx.commit()

        assert file_path.read_text() == "Content"


class TestFileTransactionRollback:
    """Tests for transaction rollback."""

    def test_transaction_rollback_on_exception(self, tmp_path: Path) -> None:
        """Test that transaction rolls back on exception."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"

        with pytest.raises(ValueError), zfs.FileTransaction() as tx:
            tx.write_text(file1, "Content 1")
            tx.write_text(file2, "Content 2")
            raise ValueError("Simulated error")

        # Files should not exist after rollback
        assert not file1.exists()  # type: ignore[unreachable]
        assert not file2.exists()

    def test_transaction_explicit_rollback(self, tmp_path: Path) -> None:
        """Test explicit rollback."""
        file_path = tmp_path / "test.txt"

        tx = zfs.FileTransaction()
        tx.write_text(file_path, "Content")
        tx.rollback()

        assert not file_path.exists()

    def test_transaction_rollback_restores_original(self, tmp_path: Path) -> None:
        """Test that rollback restores original file content."""
        file_path = tmp_path / "existing.txt"
        file_path.write_text("Original Content")

        with pytest.raises(ValueError), zfs.FileTransaction() as tx:
            tx.write_text(file_path, "New Content")
            raise ValueError("Simulated error")

        # Original content should be restored
        assert file_path.read_text() == "Original Content"  # type: ignore[unreachable]

    def test_transaction_rollback_multiple_files(self, tmp_path: Path) -> None:
        """Test rollback restores multiple files."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("Original 1")
        file2.write_text("Original 2")

        with pytest.raises(ValueError), zfs.FileTransaction() as tx:
            tx.write_text(file1, "Modified 1")
            tx.write_text(file2, "Modified 2")
            raise ValueError("Simulated error")

        assert file1.read_text() == "Original 1"  # type: ignore[unreachable]
        assert file2.read_text() == "Original 2"


class TestFileTransactionCopyDelete:
    """Tests for copy and delete operations in transactions."""

    def test_transaction_copy_file(self, tmp_path: Path) -> None:
        """Test file copy in transaction."""
        src = tmp_path / "source.txt"
        dst = tmp_path / "destination.txt"
        src.write_text("Source Content")

        with zfs.FileTransaction() as tx:
            tx.copy_file(src, dst)

        assert dst.read_text() == "Source Content"
        assert src.exists()  # Source still exists

    def test_transaction_delete_file(self, tmp_path: Path) -> None:
        """Test file deletion in transaction."""
        file_path = tmp_path / "to_delete.txt"
        file_path.write_text("Content")

        with zfs.FileTransaction() as tx:
            tx.delete_file(file_path)

        assert not file_path.exists()

    def test_transaction_delete_rollback_restores(self, tmp_path: Path) -> None:
        """Test that deleted file is restored on rollback."""
        file_path = tmp_path / "to_delete.txt"
        file_path.write_text("Important Content")

        with pytest.raises(ValueError), zfs.FileTransaction() as tx:
            tx.delete_file(file_path)
            raise ValueError("Abort!")

        # File should be restored
        assert file_path.exists()  # type: ignore[unreachable]
        assert file_path.read_text() == "Important Content"

    def test_transaction_delete_nonexistent_safe(self, tmp_path: Path) -> None:
        """Test deleting non-existent file is safe."""
        file_path = tmp_path / "nonexistent.txt"

        with zfs.FileTransaction() as tx:
            tx.delete_file(file_path)  # Should not raise


class TestFileTransactionState:
    """Tests for transaction state management."""

    def test_transaction_cannot_use_after_commit(self, tmp_path: Path) -> None:
        """Test that transaction cannot be used after commit."""
        file_path = tmp_path / "test.txt"

        tx = zfs.FileTransaction()
        tx.write_text(file_path, "Content")
        tx.commit()

        with pytest.raises(TransactionError):
            tx.write_text(file_path, "More content")

    def test_transaction_cannot_use_after_rollback(self, tmp_path: Path) -> None:
        """Test that transaction cannot be used after rollback."""
        tx = zfs.FileTransaction()
        tx.rollback()

        with pytest.raises(TransactionError):
            tx.write_text("file.txt", "Content")

    def test_transaction_cannot_rollback_after_commit(self, tmp_path: Path) -> None:
        """Test that rollback after commit raises error."""
        tx = zfs.FileTransaction()
        tx.commit()

        with pytest.raises(TransactionError):
            tx.rollback()

    def test_transaction_commit_empty_is_ok(self) -> None:
        """Test committing empty transaction is allowed."""
        tx = zfs.FileTransaction()
        tx.commit()  # Should not raise


class TestFileTransactionTempDir:
    """Tests for transaction temp directory."""

    def test_transaction_custom_temp_dir(self, tmp_path: Path) -> None:
        """Test using custom temp directory."""
        custom_temp = tmp_path / "custom_temp"
        custom_temp.mkdir()
        file_path = tmp_path / "output.txt"

        with zfs.FileTransaction(temp_dir=custom_temp) as tx:
            tx.write_text(file_path, "Content")

        assert file_path.read_text() == "Content"

    def test_transaction_cleanup_temp_files(self, tmp_path: Path) -> None:
        """Test that temp files are cleaned up after commit."""
        file_path = tmp_path / "output.txt"

        with zfs.FileTransaction() as tx:
            tx.write_text(file_path, "Content")

        # No temp files should remain in system temp
        # (hard to test precisely, but we can check the target dir)
        temp_files = list(tmp_path.glob("*.tmp"))
        assert len(temp_files) == 0

    def test_transaction_cleanup_on_rollback(self, tmp_path: Path) -> None:
        """Test that temp files are cleaned up on rollback."""
        file_path = tmp_path / "output.txt"

        tx = zfs.FileTransaction()
        tx.write_text(file_path, "Content")
        tx.rollback()

        # Check no leftover files
        assert not file_path.exists()


class TestFileTransactionOverwrite:
    """Tests for overwriting existing files."""

    def test_transaction_overwrite_file(self, tmp_path: Path) -> None:
        """Test overwriting existing file."""
        file_path = tmp_path / "existing.txt"
        file_path.write_text("Old Content")

        with zfs.FileTransaction() as tx:
            tx.write_text(file_path, "New Content")

        assert file_path.read_text() == "New Content"

    def test_transaction_overwrite_multiple_times(self, tmp_path: Path) -> None:
        """Test overwriting same file multiple times in transaction."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Original")

        with zfs.FileTransaction() as tx:
            tx.write_text(file_path, "First Update")
            tx.write_text(file_path, "Second Update")
            tx.write_text(file_path, "Final Update")

        assert file_path.read_text() == "Final Update"


class TestAtomicFileGroup:
    """Tests for the atomic_file_group context manager — write multiple
    files atomically, with backup-on-existing and rollback-on-failure.
    """

    def test_writes_all_files_on_success(self, tmp_path: Path) -> None:
        from zerofilesystem.classes.file_transaction import atomic_file_group

        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        with atomic_file_group(a, b) as temps:
            temps[0].write_text("alpha")
            temps[1].write_text("bravo")
        assert a.read_text() == "alpha"
        assert b.read_text() == "bravo"

    def test_rollback_restores_existing_files_on_exception(self, tmp_path: Path) -> None:
        from zerofilesystem.classes.file_transaction import atomic_file_group

        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.write_text("OLD-A")
        b.write_text("OLD-B")
        with pytest.raises(RuntimeError), atomic_file_group(a, b) as temps:
            temps[0].write_text("new-a")
            temps[1].write_text("new-b")
            raise RuntimeError("boom")
        assert a.read_text() == "OLD-A"
        assert b.read_text() == "OLD-B"

    def test_rollback_unlinks_newly_created_files_on_exception(self, tmp_path: Path) -> None:
        from zerofilesystem.classes.file_transaction import atomic_file_group

        a = tmp_path / "a.txt"
        with pytest.raises(RuntimeError), atomic_file_group(a) as temps:
            temps[0].write_text("partial")
            raise RuntimeError("boom")
        assert not a.exists()

    def test_creates_destination_parents(self, tmp_path: Path) -> None:
        from zerofilesystem.classes.file_transaction import atomic_file_group

        target = tmp_path / "deep" / "nested" / "out.txt"
        with atomic_file_group(target) as temps:
            temps[0].write_text("ok")
        assert target.read_text() == "ok"
