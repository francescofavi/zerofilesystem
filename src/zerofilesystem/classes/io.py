"""File I/O operations: text, bytes, JSON, gzip, and atomic writes.

Consolidates: FileIO, JsonHandler, GzipHandler, FileUtils.
"""

from __future__ import annotations

import gzip
import json
import os
import re
import shutil
import threading
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Any

from zerofilesystem._platform import IS_WINDOWS, Pathish

# Atomic Write Helpers


def _atomic_tmp_path(path: Path) -> Path:
    """Generate thread-safe temp file path for atomic writes."""
    return path.parent / f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp"


def _atomic_write_helper(
    path: Path,
    write_func,
    cleanup_on_error: bool = True,
) -> Path:
    """Atomic write: write to temp file, then rename.

    Uses PID and thread ID for unique temp filename to avoid
    collisions in multi-threaded scenarios.
    """
    tmp = _atomic_tmp_path(path)

    try:
        write_func(tmp)
        os.replace(tmp, path)
        return path
    except Exception:
        if cleanup_on_error and tmp.exists():
            tmp.unlink()
        raise


# FileIO — Basic text/bytes I/O


class FileIO:
    """Basic file I/O operations with atomic write support.

    All methods accept str or Path objects.
    """

    @staticmethod
    def read_text(path: Pathish, encoding: str = "utf-8") -> str:
        """Read text file."""
        return Path(path).read_text(encoding=encoding)

    @staticmethod
    def write_text(
        path: Pathish,
        data: str,
        encoding: str = "utf-8",
        create_dirs: bool = True,
        atomic: bool = True,
    ) -> Path:
        """Write text file.

        Args:
            path: File path
            data: Text content
            encoding: Text encoding
            create_dirs: Create parent directories
            atomic: Use atomic write (temp file + rename)

        Returns:
            Path to written file
        """
        p = Path(path)
        if create_dirs:
            p.parent.mkdir(parents=True, exist_ok=True)

        if not atomic:
            p.write_text(data, encoding=encoding)
            return p

        def _write(tmp: Path) -> None:
            tmp.write_text(data, encoding=encoding)

        return _atomic_write_helper(p, _write)

    @staticmethod
    def read_bytes(path: Pathish) -> bytes:
        """Read binary file."""
        return Path(path).read_bytes()

    @staticmethod
    def write_bytes(
        path: Pathish,
        data: bytes,
        create_dirs: bool = True,
        atomic: bool = True,
    ) -> Path:
        """Write binary file with optional atomic operation."""
        p = Path(path)
        if create_dirs:
            p.parent.mkdir(parents=True, exist_ok=True)

        if not atomic:
            p.write_bytes(data)
            return p

        def _write(tmp: Path) -> None:
            tmp.write_bytes(data)

        return _atomic_write_helper(p, _write)


# JsonHandler — JSON serialization/deserialization


class JsonHandler:
    """JSON file read/write operations."""

    @staticmethod
    def read_json(path: Pathish, encoding: str = "utf-8") -> Any:
        """Read and parse JSON file."""
        return json.loads(FileIO.read_text(path, encoding=encoding))

    @staticmethod
    def write_json(
        path: Pathish,
        obj: Any,
        *,
        encoding: str = "utf-8",
        indent: int = 2,
        create_dirs: bool = True,
        atomic: bool = True,
    ) -> Path:
        """Write object as JSON file.

        Args:
            path: File path
            obj: Object to serialize
            encoding: Text encoding
            indent: JSON indentation
            create_dirs: Create parent directories
            atomic: Use atomic write

        Returns:
            Path to written file
        """
        txt = json.dumps(obj, ensure_ascii=False, indent=indent)
        return FileIO.write_text(
            path, txt, encoding=encoding, create_dirs=create_dirs, atomic=atomic
        )


# GzipHandler — Compression/decompression


class GzipHandler:
    """Gzip compression and decompression operations."""

    @staticmethod
    def compress(
        src: Pathish,
        dst: Pathish | None = None,
        level: int = 6,
        atomic: bool = True,
    ) -> Path:
        """Compress file to gzip.

        Args:
            src: Source file
            dst: Destination (default: src + .gz)
            level: Compression level 1-9
            atomic: Use temp file + rename

        Returns:
            Path to compressed file
        """
        src_p = Path(src)
        dst_p = Path(dst) if dst else src_p.with_suffix(src_p.suffix + ".gz")
        dst_p.parent.mkdir(parents=True, exist_ok=True)

        if not atomic:
            with open(src_p, "rb") as f_in, gzip.open(dst_p, "wb", compresslevel=level) as f_out:
                shutil.copyfileobj(f_in, f_out)
            return dst_p

        tmp = _atomic_tmp_path(dst_p)

        try:
            with open(src_p, "rb") as f_in, gzip.open(tmp, "wb", compresslevel=level) as f_out:
                shutil.copyfileobj(f_in, f_out)

            os.replace(tmp, dst_p)
            return dst_p

        except Exception:
            if tmp.exists():
                tmp.unlink()
            raise

    @staticmethod
    def decompress(
        src_gz: Pathish,
        dst: Pathish | None = None,
        atomic: bool = True,
    ) -> Path:
        """Decompress gzip file.

        Args:
            src_gz: Source gzip file
            dst: Destination (default: remove .gz extension)
            atomic: Use temp file + rename

        Returns:
            Path to decompressed file
        """
        src_p = Path(src_gz)

        if dst is None:
            if src_p.suffix == ".gz":
                dst = src_p.with_suffix("")
            else:
                dst = src_p.parent / f"{src_p.name}.decompressed"

        dst_p = Path(dst)
        dst_p.parent.mkdir(parents=True, exist_ok=True)

        if not atomic:
            with gzip.open(src_p, "rb") as f_in, open(dst_p, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
            return dst_p

        tmp = _atomic_tmp_path(dst_p)

        try:
            with gzip.open(src_p, "rb") as f_in, open(tmp, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

            os.replace(tmp, dst_p)
            return dst_p

        except Exception:
            if tmp.exists():
                tmp.unlink()
            raise


# FileUtils — Filename sanitization and atomic write context manager


class FileUtils:
    """Utility functions for file operations."""

    @staticmethod
    def safe_filename(name: str, replacement: str = "_") -> str:
        """Sanitize filename by removing/replacing illegal characters.

        Args:
            name: Original filename
            replacement: Character to replace illegal chars with

        Returns:
            Safe filename

        Platform-specific:
            - Windows: < > : " / \\ | ? *
            - Unix/macOS: Only / is illegal, but we sanitize more for consistency
            - Windows reserved names: CON, PRN, AUX, NUL, COM1-9, LPT1-9

        Example:
            safe_filename("file:name*.txt")  # -> "file_name_.txt"
            safe_filename("CON.txt")         # -> "_CON.txt" (Windows reserved)
        """
        illegal = r'[<>:"/\\|?*]'
        safe = re.sub(illegal, replacement, name)

        # Remove control characters (0x00-0x1F)
        safe = re.sub(r"[\x00-\x1f]", replacement, safe)

        # Strip leading/trailing spaces and dots (Windows issue)
        safe = safe.strip(". ")

        # Windows reserved names
        if IS_WINDOWS:  # pragma: no cover -- Windows-only, exercised by Windows CI runner
            reserved = {
                "CON",
                "PRN",
                "AUX",
                "NUL",
                "COM1",
                "COM2",
                "COM3",
                "COM4",
                "COM5",
                "COM6",
                "COM7",
                "COM8",
                "COM9",
                "LPT1",
                "LPT2",
                "LPT3",
                "LPT4",
                "LPT5",
                "LPT6",
                "LPT7",
                "LPT8",
                "LPT9",
            }
            base_name = safe.split(".")[0].upper()
            if base_name in reserved:
                safe = f"_{safe}"

        return safe or "unnamed"

    @staticmethod
    @contextmanager
    def atomic_write(
        path: Pathish,
        mode: str = "w",
        encoding: str = "utf-8",
    ) -> Generator[IO, None, None]:
        """Context manager for atomic file writes.

        Args:
            path: Destination file path
            mode: File mode ('w' for text, 'wb' for binary)
            encoding: Text encoding (only for text mode)

        Yields:
            File handle

        Example:
            with FileUtils.atomic_write("config.json") as f:
                json.dump(data, f)
        """
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = _atomic_tmp_path(p)

        try:
            if "b" in mode:
                with tmp.open(mode) as f:
                    yield f
            else:
                with tmp.open(mode, encoding=encoding) as f:
                    yield f

            os.replace(tmp, p)

        except Exception:
            if tmp.exists():
                tmp.unlink()
            raise
