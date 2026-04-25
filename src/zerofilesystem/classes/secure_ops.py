"""Secure file operations: secure delete, private directories."""

from __future__ import annotations

import os
import secrets
import shutil
import stat
import tempfile
from collections.abc import Generator
from contextlib import contextmanager, suppress
from pathlib import Path

from zerofilesystem._platform import Pathish
from zerofilesystem.classes.exceptions import SecureDeleteError

SECURE_DELETE_CHUNK_SIZE: int = 65536


class SecureOps:
    """Secure file operations."""

    @staticmethod
    def secure_delete(
        path: Pathish,
        passes: int = 3,
        random_data: bool = True,
    ) -> None:
        """
        Securely delete a file by overwriting before deletion.

        Args:
            path: File path to delete
            passes: Number of overwrite passes (default: 3)
            random_data: Use random data (True) or zeros (False)

        Note:
            This is a best-effort secure delete. Modern SSDs with
            wear leveling, journaling filesystems, and OS caching
            may retain data copies. For true security, use full-disk
            encryption.

        Raises:
            SecureDeleteError: If secure deletion fails
        """
        p = Path(path)

        if not p.exists():
            return

        if not p.is_file():
            raise SecureDeleteError(p, "not a file")

        try:
            file_size = p.stat().st_size

            # Make file writable if needed
            try:
                current_mode = p.stat().st_mode
                if not (current_mode & stat.S_IWUSR):
                    p.chmod(current_mode | stat.S_IWUSR)
            except OSError:  # pragma: no cover -- best-effort chmod, file may be read-only by ACL
                pass

            # Overwrite passes
            with open(p, "r+b") as f:
                for _ in range(passes):
                    f.seek(0)
                    if random_data:
                        # Write random data in chunks
                        remaining = file_size
                        while remaining > 0:
                            chunk_size = min(remaining, SECURE_DELETE_CHUNK_SIZE)
                            f.write(secrets.token_bytes(chunk_size))
                            remaining -= chunk_size
                    else:
                        # Write zeros
                        f.write(b"\x00" * file_size)
                    f.flush()
                    os.fsync(f.fileno())

            # Truncate to zero
            with open(p, "w") as f:
                pass

            # Delete
            p.unlink()

        except Exception as e:
            raise SecureDeleteError(p, f"overwrite failed: {e}", cause=e) from e

    @staticmethod
    def secure_delete_directory(
        path: Pathish,
        passes: int = 3,
        random_data: bool = True,
    ) -> None:
        """
        Securely delete a directory and all its contents.

        Args:
            path: Directory path
            passes: Number of overwrite passes per file
            random_data: Use random data or zeros
        """
        p = Path(path)

        if not p.exists():
            return

        if not p.is_dir():
            SecureOps.secure_delete(p, passes, random_data)
            return

        # Delete files securely
        for root, dirs, files in os.walk(p, topdown=False):
            for f in files:
                file_path = Path(root) / f
                try:
                    SecureOps.secure_delete(file_path, passes, random_data)
                except SecureDeleteError:  # pragma: no cover -- fallback when overwrite fails
                    # Try regular delete as fallback
                    with suppress(OSError):
                        file_path.unlink()

            # Remove directories
            for d in dirs:
                dir_path = Path(root) / d
                with suppress(OSError):
                    dir_path.rmdir()

        # Remove root directory
        with suppress(OSError):
            p.rmdir()

    @staticmethod
    @contextmanager
    def private_directory(
        prefix: str = "private_",
        parent: Pathish | None = None,
        cleanup: bool = True,
        secure_cleanup: bool = False,
    ) -> Generator[Path, None, None]:
        """
        Create a private temporary directory with restricted permissions.

        Args:
            prefix: Directory name prefix
            parent: Parent directory (default: system temp)
            cleanup: Auto-cleanup on exit
            secure_cleanup: Use secure delete on cleanup

        Yields:
            Path to private directory

        Note:
            Directory has permissions 0o700 (owner only).
            Name includes random component for unpredictability.
        """
        parent_dir = Path(parent) if parent else None

        # Create with random suffix for unpredictability
        random_suffix = secrets.token_hex(8)
        tmp_dir = tempfile.mkdtemp(prefix=f"{prefix}{random_suffix}_", dir=parent_dir)
        tmp_path = Path(tmp_dir)

        # Set restrictive permissions (owner only)
        with suppress(OSError):
            tmp_path.chmod(0o700)

        try:
            yield tmp_path
        finally:
            if cleanup:
                try:
                    if secure_cleanup:
                        SecureOps.secure_delete_directory(tmp_path)
                    else:
                        shutil.rmtree(tmp_path)
                except Exception:
                    pass

    @staticmethod
    def create_private_file(
        path: Pathish,
        content: bytes | None = None,
        text_content: str | None = None,
        encoding: str = "utf-8",
    ) -> Path:
        """
        Create a file with restricted permissions.

        Args:
            path: File path
            content: Binary content (mutually exclusive with text_content)
            text_content: Text content
            encoding: Text encoding

        Returns:
            Path to created file

        Note:
            File has permissions 0o600 (owner read/write only).
        """
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)

        # Create file with restrictive permissions
        fd = os.open(p, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)

        try:
            if content is not None:
                os.write(fd, content)
            elif text_content is not None:
                os.write(fd, text_content.encode(encoding))
        finally:
            os.close(fd)

        return p

    @staticmethod
    def set_private_permissions(path: Pathish) -> None:
        """
        Set restrictive permissions on a file or directory.

        Args:
            path: File or directory path

        Note:
            Sets 0o700 for directories, 0o600 for files.
        """
        p = Path(path)

        if p.is_dir():
            p.chmod(0o700)
        else:
            p.chmod(0o600)

    @staticmethod
    def generate_random_filename(
        length: int = 16,
        extension: str = "",
    ) -> str:
        """
        Generate a random filename.

        Args:
            length: Length of random part
            extension: File extension (including dot)

        Returns:
            Random filename string
        """
        name = secrets.token_hex((length + 1) // 2)[:length]
        return f"{name}{extension}"
