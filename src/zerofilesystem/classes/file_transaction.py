"""Pseudo-transactional file operations with rollback."""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Generator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from zerofilesystem._platform import Pathish
from zerofilesystem.classes.exceptions import TransactionError


@dataclass
class PendingWrite:
    """A pending write operation in a transaction."""

    target: Path
    temp_path: Path | None  # None for delete operations
    original_existed: bool
    original_backup: Path | None = None


class FileTransaction:
    """
    Pseudo-transactional file operations with atomic commit and rollback.

    Example:
        with FileTransaction() as tx:
            tx.write_text("config.json", '{"key": "value"}')
            tx.write_text("data.txt", "hello world")
            # Both files written atomically on exit

        # Or with explicit commit/rollback:
        tx = FileTransaction()
        try:
            tx.write_text("file1.txt", "content1")
            tx.write_text("file2.txt", "content2")
            tx.commit()
        except Exception:
            tx.rollback()
    """

    def __init__(self, temp_dir: Pathish | None = None):
        """
        Initialize transaction.

        Args:
            temp_dir: Directory for temp files (default: system temp)
        """
        self._temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir())
        self._pending: list[PendingWrite] = []
        self._committed = False
        self._rolled_back = False
        self._tx_temp_dir: Path | None = None

    def _get_tx_temp_dir(self) -> Path:
        """Get or create transaction temp directory."""
        if self._tx_temp_dir is None:
            self._tx_temp_dir = Path(
                tempfile.mkdtemp(prefix="zerofilesystem_tx_", dir=self._temp_dir)
            )
        return self._tx_temp_dir

    def _create_temp_file(self) -> Path:
        """Create a temp file for pending write."""
        fd, path = tempfile.mkstemp(dir=self._get_tx_temp_dir())
        os.close(fd)
        return Path(path)

    def write_text(
        self,
        path: Pathish,
        content: str,
        encoding: str = "utf-8",
    ) -> None:
        """
        Schedule a text file write.

        Args:
            path: Target file path
            content: Text content
            encoding: Text encoding
        """
        self._check_state()

        target = Path(path).resolve()
        temp_path = self._create_temp_file()

        # Write to temp file
        temp_path.write_text(content, encoding=encoding)

        # Backup original if exists
        original_backup = None
        existed = target.exists()
        if existed:
            original_backup = self._create_temp_file()
            shutil.copy2(target, original_backup)

        self._pending.append(
            PendingWrite(
                target=target,
                temp_path=temp_path,
                original_existed=existed,
                original_backup=original_backup,
            )
        )

    def write_bytes(self, path: Pathish, content: bytes) -> None:
        """
        Schedule a binary file write.

        Args:
            path: Target file path
            content: Binary content
        """
        self._check_state()

        target = Path(path).resolve()
        temp_path = self._create_temp_file()

        temp_path.write_bytes(content)

        original_backup = None
        existed = target.exists()
        if existed:
            original_backup = self._create_temp_file()
            shutil.copy2(target, original_backup)

        self._pending.append(
            PendingWrite(
                target=target,
                temp_path=temp_path,
                original_existed=existed,
                original_backup=original_backup,
            )
        )

    def copy_file(self, src: Pathish, dst: Pathish) -> None:
        """
        Schedule a file copy.

        Args:
            src: Source file path
            dst: Destination file path
        """
        self._check_state()

        src_p = Path(src)
        target = Path(dst).resolve()
        temp_path = self._create_temp_file()

        shutil.copy2(src_p, temp_path)

        original_backup = None
        existed = target.exists()
        if existed:
            original_backup = self._create_temp_file()
            shutil.copy2(target, original_backup)

        self._pending.append(
            PendingWrite(
                target=target,
                temp_path=temp_path,
                original_existed=existed,
                original_backup=original_backup,
            )
        )

    def delete_file(self, path: Pathish) -> None:
        """
        Schedule a file deletion.

        Args:
            path: File path to delete
        """
        self._check_state()

        target = Path(path).resolve()

        if not target.exists():
            return

        # Backup original
        original_backup = self._create_temp_file()
        shutil.copy2(target, original_backup)

        # Schedule deletion (temp_path is None for deletes)
        self._pending.append(
            PendingWrite(
                target=target,
                temp_path=None,
                original_existed=True,
                original_backup=original_backup,
            )
        )

    def commit(self) -> None:
        """
        Commit all pending operations atomically.

        Raises:
            TransactionError: If commit fails
        """
        self._check_state()

        if not self._pending:
            self._committed = True
            return

        committed_ops: list[PendingWrite] = []

        try:
            for op in self._pending:
                # Ensure parent directory exists
                op.target.parent.mkdir(parents=True, exist_ok=True)

                if op.temp_path is None:
                    # Delete operation
                    op.target.unlink()
                else:
                    # Write/copy operation - atomic replace
                    os.replace(op.temp_path, op.target)

                committed_ops.append(op)

            self._committed = True

        except Exception as e:
            # Rollback committed operations
            for op in reversed(committed_ops):
                try:
                    if op.original_backup:
                        os.replace(op.original_backup, op.target)
                    elif not op.original_existed:
                        op.target.unlink(missing_ok=True)
                except Exception:
                    pass

            raise TransactionError(
                f"Commit failed: {e}",
                rollback_success=True,
                cause=e,
            ) from e

        finally:
            self._cleanup_temps()

    def rollback(self) -> None:
        """
        Rollback all pending operations.

        Discards all pending writes without applying them.
        """
        if self._committed:
            raise TransactionError("Cannot rollback committed transaction")

        self._rolled_back = True
        self._cleanup_temps()

    def _check_state(self) -> None:
        """Check transaction state."""
        if self._committed:
            raise TransactionError("Transaction already committed")
        if self._rolled_back:
            raise TransactionError("Transaction already rolled back")

    def _cleanup_temps(self) -> None:
        """Clean up temporary files."""
        for op in self._pending:
            try:
                if op.temp_path and op.temp_path.exists():
                    op.temp_path.unlink()
            except Exception:
                pass
            try:
                if op.original_backup and op.original_backup.exists():
                    op.original_backup.unlink()
            except Exception:
                pass

        self._pending.clear()

        # Remove transaction temp directory
        if self._tx_temp_dir and self._tx_temp_dir.exists():
            with suppress(Exception):
                shutil.rmtree(self._tx_temp_dir)
            self._tx_temp_dir = None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, _exc_val: BaseException | None, _exc_tb: object
    ) -> None:
        if exc_type is not None:
            # Exception occurred - rollback
            self.rollback()
            return

        # No exception - commit
        if not self._committed and not self._rolled_back:
            self.commit()

    def __del__(self) -> None:
        """Cleanup on garbage collection."""
        if not self._committed and not self._rolled_back:
            with suppress(Exception):
                self.rollback()


@contextmanager
def atomic_file_group(*paths: Pathish) -> Generator[list[Path], None, None]:
    """
    Context manager for writing multiple files atomically.

    All files are written to temp files first, then all renamed atomically.
    If any rename fails, all are rolled back.

    Args:
        *paths: File paths to write to

    Yields:
        List of temp file paths to write to

    Example:
        with atomic_file_group("a.txt", "b.txt") as temps:
            temps[0].write_text("content a")
            temps[1].write_text("content b")
        # Both files atomically written on exit
    """
    targets = [Path(p).resolve() for p in paths]
    temps: list[Path] = []
    backups: list[Path | None] = []

    tx_dir = Path(tempfile.mkdtemp(prefix="zerofilesystem_atomic_"))

    try:
        # Create temp files
        for i, target in enumerate(targets):
            temp = tx_dir / f"temp_{i}"
            temps.append(temp)

            # Backup existing
            if target.exists():
                backup = tx_dir / f"backup_{i}"
                shutil.copy2(target, backup)
                backups.append(backup)
            else:
                backups.append(None)

        yield temps

        # Commit - rename all temps to targets
        for temp, target in zip(temps, targets, strict=False):
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temp, target)

    except Exception:
        # Rollback - restore backups
        for target, backup_file in zip(targets, backups, strict=False):
            try:
                if backup_file and backup_file.exists():
                    os.replace(backup_file, target)
                elif target.exists():
                    target.unlink()
            except Exception:
                pass
        raise

    finally:
        # Cleanup
        with suppress(Exception):
            shutil.rmtree(tx_dir)
