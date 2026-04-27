"""File-level operations: metadata, hashing, sync, cleanup, and discovery.

Consolidates: FileMeta, FileHasher, FileSync, FileCleaner, FileFinder.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from collections.abc import Callable, Iterable, Iterator
from contextlib import suppress
from pathlib import Path
from typing import Literal

from zerofilesystem._platform import IS_WINDOWS, Pathish
from zerofilesystem.classes._internal import (
    FILE_ATTRIBUTE_HIDDEN,
    HASH_CHUNK_SIZE,
    MAX_RENAME_CONFLICTS,
)

# FileMeta — File and directory metadata


class FileMeta:
    """File and directory metadata operations."""

    @staticmethod
    def ensure_dir(path: Pathish) -> Path:
        """Create directory if not exists (including parents)."""
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @staticmethod
    def touch(path: Pathish, exist_ok: bool = True) -> Path:
        """Create empty file (and parent directories)."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch(exist_ok=exist_ok)
        return p

    @staticmethod
    def file_size(path: Pathish) -> int:
        """Get file size in bytes."""
        return Path(path).stat().st_size

    @staticmethod
    def disk_usage(path: Pathish) -> tuple[int, int, int]:
        """Get disk usage for filesystem containing path.

        Args:
            path: Any path on the filesystem

        Returns:
            Tuple of (total_bytes, used_bytes, free_bytes)
        """
        usage = shutil.disk_usage(str(Path(path)))
        return usage.total, usage.used, usage.free


# FileHasher — File hashing


class FileHasher:
    """File hashing operations."""

    @staticmethod
    def file_hash(
        path: Pathish,
        algo: Literal["md5", "sha1", "sha256", "sha512"] = "sha256",
        chunk: int = HASH_CHUNK_SIZE,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> str:
        """Compute file hash using streaming (memory efficient).

        Args:
            path: File path
            algo: Hash algorithm (md5, sha1, sha256, sha512)
            chunk: Chunk size in bytes (default 1MB)
            progress_callback: Optional callback(bytes_processed, total_bytes)

        Returns:
            Hexadecimal hash digest
        """
        h = hashlib.new(algo)
        p = Path(path)
        total_size = p.stat().st_size if progress_callback else 0
        processed = 0

        with open(p, "rb") as f:
            for block in iter(lambda: f.read(chunk), b""):
                h.update(block)

                if progress_callback:
                    processed += len(block)
                    with suppress(Exception):
                        progress_callback(processed, total_size)

        return h.hexdigest()


# FileSync — File move and copy operations


class FileSync:
    """File move and copy operations."""

    @staticmethod
    def move_if_absent(
        src: Pathish,
        dst_dir: Pathish,
        create_dirs: bool = True,
        on_conflict: Literal["skip", "rename", "error"] = "skip",
    ) -> tuple[bool, Path | None]:
        """Move file to directory if destination doesn't exist.

        Args:
            src: Source file path
            dst_dir: Destination directory
            create_dirs: Create destination directory if not exists
            on_conflict: Behavior when destination exists:
                - "skip": Don't move, return (False, None)
                - "rename": Add suffix _1, _2, etc. to find unique name
                - "error": Raise FileExistsError

        Returns:
            Tuple of (moved: bool, final_path: Optional[Path])

        Warning:
            Not atomic! Race condition possible between exists() check and move.
            Use FileLock if you need atomic "move if not exists" across processes.
        """
        src_p = Path(src)
        dst_dir_p = Path(dst_dir)

        if create_dirs:
            dst_dir_p.mkdir(parents=True, exist_ok=True)

        dst = dst_dir_p / src_p.name

        if dst.exists():
            if on_conflict == "skip":
                return (False, None)

            elif on_conflict == "error":
                raise FileExistsError(f"Destination exists: {dst}")

            elif on_conflict == "rename":
                stem = dst.stem
                suffix = dst.suffix
                counter = 1
                while True:
                    dst = dst_dir_p / f"{stem}_{counter}{suffix}"
                    if not dst.exists():
                        break
                    counter += 1
                    if counter > MAX_RENAME_CONFLICTS:  # pragma: no cover -- guard
                        # against pathological collisions (10000 files with the
                        # same name); requires a synthetic test that creates 10k+
                        # files just to fire one branch
                        raise RuntimeError(f"Too many conflicting files: {stem}")

        try:
            shutil.move(str(src_p), str(dst))
            return (True, dst)
        except Exception as e:
            raise RuntimeError(f"Failed to move {src_p} to {dst}: {e}") from e

    @staticmethod
    def copy_if_newer(
        src: Pathish,
        dst: Pathish,
        create_dirs: bool = True,
    ) -> bool:
        """Copy file if source is newer than destination (based on mtime).

        Args:
            src: Source file
            dst: Destination file
            create_dirs: Create destination directory if not exists

        Returns:
            True if file was copied, False if destination is newer/same

        Note:
            Uses 1 second epsilon for filesystem timestamp precision.
        """
        src_p, dst_p = Path(src), Path(dst)

        if create_dirs:
            dst_p.parent.mkdir(parents=True, exist_ok=True)

        src_stat = src_p.stat()

        if dst_p.exists():
            dst_stat = dst_p.stat()
            if src_stat.st_mtime <= dst_stat.st_mtime + 1.0:
                return False

        shutil.copy2(src_p, dst_p)

        try:
            if abs(dst_p.stat().st_mtime - src_stat.st_mtime) > 1.0:
                os.utime(dst_p, (src_stat.st_atime, src_stat.st_mtime))
        except OSError:  # pragma: no cover -- best-effort mtime preservation;
            # if utime fails, the copy still succeeded, so we swallow it
            pass

        return True


# FileCleaner — File and directory cleanup


class FileCleaner:
    """File and directory cleanup operations."""

    @staticmethod
    def delete_files(paths: Iterable[Pathish]) -> dict[str, list]:
        """Delete multiple files with detailed error reporting.

        Args:
            paths: Iterable of file paths to delete

        Returns:
            Dictionary with categorized results:
            {
                "succeeded": [path1, path2, ...],
                "not_found": [(path, "File not found"), ...],
                "not_file": [(path, "Is directory"), ...],
                "failed": [(path, "Permission denied: ..."), ...]
            }
        """
        result: dict[str, list] = {
            "succeeded": [],
            "not_found": [],
            "not_file": [],
            "failed": [],
        }

        for item in paths:
            p = Path(item)

            try:
                if not p.exists():
                    result["not_found"].append((str(p), "File not found"))
                    continue

                if not (p.is_file() or p.is_symlink()):
                    result["not_file"].append((str(p), "Not a file"))
                    continue

                p.unlink()
                result["succeeded"].append(str(p))

            except PermissionError as e:  # pragma: no cover -- defensive: many
                # filesystems return OSError instead of PermissionError; this
                # path requires a non-default ACL to trigger reliably
                result["failed"].append((str(p), f"Permission denied: {e}"))
            except OSError as e:
                result["failed"].append((str(p), f"OS error: {e}"))
            except Exception as e:  # pragma: no cover -- catch-all guard for
                # truly unexpected errors (e.g. broken filesystem driver)
                result["failed"].append((str(p), f"Unexpected error: {e}"))

        return result

    @staticmethod
    def delete_empty_dirs(root: Pathish, remove_root: bool = False) -> list[Path]:
        """Remove empty directories recursively (bottom-up).

        Args:
            root: Root directory to scan
            remove_root: If True, also remove root directory if empty

        Returns:
            List of removed directory paths
        """
        root_p = Path(root)
        if not root_p.is_dir():
            return []

        removed = []

        for dirpath, _dirnames, _filenames in os.walk(root_p, topdown=False):
            dp = Path(dirpath)

            if not remove_root and dp == root_p:
                continue

            try:
                dp.rmdir()
                removed.append(dp)
            except OSError:
                pass

        return removed


# FileFinder — File discovery and searching


class FileFinder:
    """File discovery and searching operations."""

    @staticmethod
    def _prepare_pattern(pattern: str, recursive: bool) -> tuple[str, bool]:
        """Prepare pattern for glob/rglob.

        Returns:
            Tuple of (clean_pattern, use_rglob)
        """
        if recursive:
            if pattern.startswith("**/"):
                return pattern[3:] or "*", True
            elif pattern.startswith("**"):
                return pattern[2:] or "*", True
            else:
                return pattern, True
        else:
            return pattern, False

    @staticmethod
    def find_files(
        base_dir: Pathish,
        pattern: str = "**/*",
        filter_fn: Callable[[Path], bool] | None = None,
        recursive: bool = True,
        absolute: bool = True,
        max_results: int | None = None,
    ) -> list[Path]:
        """Find files using glob pattern with optional custom filter.

        Args:
            base_dir: Base directory to search
            pattern: Glob pattern (e.g., "*.py", "**/*.txt", "test_*.py")
            filter_fn: Optional filter function (path) -> bool
            recursive: Use recursive glob (rglob)
            absolute: Return absolute paths
            max_results: Maximum number of results (early stop)

        Returns:
            List of matching file paths
        """
        base = Path(base_dir)
        if not base.is_dir():
            return []

        results = []
        clean_pattern, use_rglob = FileFinder._prepare_pattern(pattern, recursive)

        glob_iter = base.rglob(clean_pattern) if use_rglob else base.glob(clean_pattern)

        for p in glob_iter:
            if not p.is_file():
                continue

            if filter_fn:
                try:
                    if not filter_fn(p):
                        continue
                except Exception:  # noqa: BLE001  # pragma: no cover -- defensive:
                    # a buggy user filter must not abort the whole walk
                    continue  # nosec B112

            results.append(p.resolve() if absolute else p)

            if max_results and len(results) >= max_results:
                break

        return results

    @staticmethod
    def walk_files(
        base_dir: Pathish,
        pattern: str = "**/*",
        filter_fn: Callable[[Path], bool] | None = None,
        recursive: bool = True,
        absolute: bool = True,
    ) -> Iterator[Path]:
        """Generator version of find_files for memory efficiency.

        Args:
            base_dir: Base directory to search
            pattern: Glob pattern
            filter_fn: Optional filter function
            recursive: Use recursive glob (default: True)
            absolute: Return absolute paths (default: True)

        Yields:
            Matching file paths
        """
        base = Path(base_dir)
        if not base.is_dir():
            return

        clean_pattern, use_rglob = FileFinder._prepare_pattern(pattern, recursive)

        glob_iter = base.rglob(clean_pattern) if use_rglob else base.glob(clean_pattern)

        for p in glob_iter:
            if not p.is_file():
                continue

            if filter_fn:
                try:
                    if not filter_fn(p):
                        continue
                except Exception:  # noqa: BLE001  # pragma: no cover -- defensive:
                    # a buggy user filter must not abort the whole walk
                    continue  # nosec B112

            yield p.resolve() if absolute else p

    @staticmethod
    def is_hidden(path: Pathish) -> bool:
        """Check if file/directory is hidden.

        Args:
            path: File or directory path

        Returns:
            True if hidden

        Platform-specific:
            - Unix/macOS: Starts with .
            - Windows: Has FILE_ATTRIBUTE_HIDDEN flag
        """
        p = Path(path)

        if p.name.startswith("."):
            return True

        if IS_WINDOWS:  # pragma: no cover -- Windows-only, exercised by Windows CI runner
            try:
                attrs = os.stat(p).st_file_attributes  # type: ignore[attr-defined]
                return bool(attrs & FILE_ATTRIBUTE_HIDDEN)
            except (AttributeError, OSError):
                return False

        return False
