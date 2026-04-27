"""Advanced directory operations."""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Callable, Generator
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from zerofilesystem._platform import Pathish
from zerofilesystem.classes._internal import MAX_RENAME_CONFLICTS
from zerofilesystem.classes.exceptions import SyncError


@dataclass
class SyncResult:
    """Result of a sync/mirror operation."""

    copied: list[Path] = field(default_factory=list)
    updated: list[Path] = field(default_factory=list)
    deleted: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)
    errors: list[tuple[Path, str]] = field(default_factory=list)

    @property
    def total_operations(self) -> int:
        return len(self.copied) + len(self.updated) + len(self.deleted)

    def __str__(self) -> str:
        return (
            f"SyncResult(copied={len(self.copied)}, "
            f"updated={len(self.updated)}, "
            f"deleted={len(self.deleted)}, "
            f"skipped={len(self.skipped)}, "
            f"errors={len(self.errors)})"
        )


class DirectoryOps:
    """Advanced directory operations."""

    @staticmethod
    def copy_tree(
        src: Pathish,
        dst: Pathish,
        *,
        filter_fn: Callable[[Path], bool] | None = None,
        on_conflict: Literal["overwrite", "skip", "only_if_newer"] = "overwrite",
        preserve_metadata: bool = True,
        follow_symlinks: bool = True,
    ) -> SyncResult:
        """
        Recursively copy a directory tree with filtering and conflict options.

        Args:
            src: Source directory
            dst: Destination directory
            filter_fn: Optional filter function (path) -> bool (True to include)
            on_conflict: Behavior when destination exists
            preserve_metadata: Preserve file timestamps and permissions
            follow_symlinks: Follow symbolic links

        Returns:
            SyncResult with details of operations performed
        """
        src_p = Path(src)
        dst_p = Path(dst)
        result = SyncResult()

        if not src_p.is_dir():
            raise SyncError(f"Source is not a directory: {src}", source=src)

        dst_p.mkdir(parents=True, exist_ok=True)

        for root, dirs, files in os.walk(src_p, followlinks=follow_symlinks):
            root_path = Path(root)
            rel_root = root_path.relative_to(src_p)
            dst_root = dst_p / rel_root

            # Create directories
            for d in dirs:
                src_dir = root_path / d
                if filter_fn and not filter_fn(src_dir):
                    continue
                (dst_root / d).mkdir(exist_ok=True)

            # Copy files
            for f in files:
                src_file = root_path / f
                dst_file = dst_root / f

                if filter_fn and not filter_fn(src_file):
                    result.skipped.append(src_file)
                    continue

                try:
                    should_copy = True
                    existed_before = dst_file.exists()

                    if existed_before:
                        if on_conflict == "skip":
                            result.skipped.append(src_file)
                            should_copy = False
                        elif on_conflict == "only_if_newer":
                            src_mtime = src_file.stat().st_mtime
                            dst_mtime = dst_file.stat().st_mtime
                            if src_mtime <= dst_mtime:
                                result.skipped.append(src_file)
                                should_copy = False
                        # overwrite: should_copy stays True

                    if should_copy:
                        if preserve_metadata:
                            shutil.copy2(src_file, dst_file)
                        else:
                            shutil.copy(src_file, dst_file)

                        if existed_before:
                            result.updated.append(dst_file)
                        else:
                            result.copied.append(dst_file)

                except Exception as e:  # pragma: no cover -- defensive: capture per-file error and continue the walk
                    result.errors.append((src_file, str(e)))

        return result

    @staticmethod
    def move_tree(
        src: Pathish,
        dst: Pathish,
        *,
        filter_fn: Callable[[Path], bool] | None = None,
        on_conflict: Literal["overwrite", "skip", "error"] = "error",
    ) -> SyncResult:
        """
        Recursively move a directory tree.

        Args:
            src: Source directory
            dst: Destination directory
            filter_fn: Optional filter function
            on_conflict: Behavior when destination exists

        Returns:
            SyncResult with details
        """
        src_p = Path(src)
        dst_p = Path(dst)
        result = SyncResult()

        if not src_p.is_dir():
            raise SyncError(f"Source is not a directory: {src}", source=src)

        # If no filter and destination doesn't exist, use efficient shutil.move
        if filter_fn is None and not dst_p.exists():
            shutil.move(str(src_p), str(dst_p))
            result.copied.append(dst_p)
            return result

        dst_p.mkdir(parents=True, exist_ok=True)

        for root, _dirs, files in os.walk(src_p, topdown=False):
            root_path = Path(root)
            rel_root = root_path.relative_to(src_p)
            dst_root = dst_p / rel_root

            # parents=True is required: topdown=False visits deepest paths first,
            # so dst_root may sit several levels below the still-uncreated dst_p
            dst_root.mkdir(parents=True, exist_ok=True)

            # Move files
            for f in files:
                src_file = root_path / f
                dst_file = dst_root / f

                if filter_fn and not filter_fn(src_file):
                    result.skipped.append(src_file)
                    continue

                try:
                    if dst_file.exists():
                        if on_conflict == "skip":
                            result.skipped.append(src_file)
                            continue
                        elif on_conflict == "error":
                            raise FileExistsError(f"Destination exists: {dst_file}")
                        else:  # overwrite
                            dst_file.unlink()

                    shutil.move(str(src_file), str(dst_file))
                    result.copied.append(dst_file)

                except Exception as e:
                    result.errors.append((src_file, str(e)))

            # Remove empty source directories
            with suppress(OSError):
                root_path.rmdir()

        return result

    @staticmethod
    def sync(
        src: Pathish,
        dst: Pathish,
        *,
        delete_extra: bool = False,
        filter_fn: Callable[[Path], bool] | None = None,
        dry_run: bool = False,
    ) -> SyncResult:
        """
        Synchronize destination directory with source (mirror).

        Args:
            src: Source directory
            dst: Destination directory
            delete_extra: Delete files in dst not in src
            filter_fn: Optional filter function
            dry_run: If True, don't actually perform operations

        Returns:
            SyncResult with operations (performed or planned if dry_run)
        """
        src_p = Path(src)
        dst_p = Path(dst)
        result = SyncResult()

        if not src_p.is_dir():
            raise SyncError(f"Source is not a directory: {src}", source=src)

        if not dry_run:
            dst_p.mkdir(parents=True, exist_ok=True)

        # Build set of source files (relative paths)
        src_files: set[Path] = set()
        for root, dirs, files in os.walk(src_p):
            root_path = Path(root)
            rel_root = root_path.relative_to(src_p)

            for f in files:
                src_file = root_path / f
                if filter_fn and not filter_fn(src_file):
                    continue
                src_files.add(rel_root / f)

            # Filter directories - iterate over copy to allow safe removal
            for d in dirs[:]:
                src_dir = root_path / d
                if filter_fn and not filter_fn(src_dir):
                    dirs.remove(d)

        # Copy/update files from source
        for rel_path in src_files:
            src_file = src_p / rel_path
            dst_file = dst_p / rel_path

            try:
                if dst_file.exists():
                    # Check if update needed
                    src_mtime = src_file.stat().st_mtime
                    dst_mtime = dst_file.stat().st_mtime

                    if src_mtime > dst_mtime:
                        if not dry_run:
                            dst_file.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(src_file, dst_file)
                        result.updated.append(dst_file)
                    else:
                        result.skipped.append(dst_file)
                else:
                    if not dry_run:
                        dst_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src_file, dst_file)
                    result.copied.append(dst_file)

            except Exception as e:
                result.errors.append((src_file, str(e)))

        # Delete extra files in destination
        if delete_extra and dst_p.exists():
            for root, _dirs, files in os.walk(dst_p):
                root_path = Path(root)
                rel_root = root_path.relative_to(dst_p)

                for f in files:
                    rel_path = rel_root / f
                    if rel_path not in src_files:
                        dst_file = dst_p / rel_path
                        try:
                            if not dry_run:
                                dst_file.unlink()
                            result.deleted.append(dst_file)
                        except (
                            Exception
                        ) as e:  # pragma: no cover -- defensive: capture per-file delete error
                            result.errors.append((dst_file, str(e)))

            # Clean up empty directories
            if not dry_run:
                for root, _dirs, _files in os.walk(dst_p, topdown=False):
                    root_path = Path(root)
                    if root_path != dst_p:
                        with suppress(OSError):
                            root_path.rmdir()

        return result

    @staticmethod
    @contextmanager
    def temp_directory(
        prefix: str = "zerofilesystem_",
        suffix: str = "",
        parent: Pathish | None = None,
        cleanup: bool = True,
    ) -> Generator[Path, None, None]:
        """
        Context manager for temporary directory with auto-cleanup.

        Args:
            prefix: Prefix for temp directory name
            suffix: Suffix for temp directory name
            parent: Parent directory (default: system temp)
            cleanup: Auto-cleanup on exit (default: True)

        Yields:
            Path to temporary directory

        Example:
            with DirectoryOps.temp_directory() as tmp:
                (tmp / "file.txt").write_text("hello")
                # Directory and contents deleted on exit
        """
        parent_dir = Path(parent) if parent else None
        tmp_dir = tempfile.mkdtemp(prefix=prefix, suffix=suffix, dir=parent_dir)
        tmp_path = Path(tmp_dir)

        try:
            yield tmp_path
        finally:
            if cleanup:
                with suppress(Exception):
                    shutil.rmtree(tmp_path)

    @staticmethod
    def tree_size(path: Pathish, follow_symlinks: bool = False) -> int:
        """
        Calculate total size of directory tree.

        Args:
            path: Directory path
            follow_symlinks: Follow symbolic links

        Returns:
            Total size in bytes
        """
        total = 0
        p = Path(path)

        if p.is_file():
            return p.stat().st_size

        for root, _dirs, files in os.walk(p, followlinks=follow_symlinks):
            for f in files:
                file_path = Path(root) / f
                with suppress(OSError):
                    total += file_path.stat().st_size

        return total

    @staticmethod
    def tree_file_count(path: Pathish, follow_symlinks: bool = False) -> int:
        """
        Count files in directory tree.

        Args:
            path: Directory path
            follow_symlinks: Follow symbolic links

        Returns:
            Number of files
        """
        count = 0
        for _root, _dirs, files in os.walk(Path(path), followlinks=follow_symlinks):
            count += len(files)
        return count

    @staticmethod
    def flatten(
        src: Pathish,
        dst: Pathish,
        *,
        separator: str = "_",
        on_conflict: Literal["overwrite", "skip", "rename"] = "rename",
    ) -> SyncResult:
        """
        Flatten a directory tree by copying all files to a single directory.

        Args:
            src: Source directory
            dst: Destination directory (flat)
            separator: Separator for path components in filename
            on_conflict: Behavior when destination filename exists

        Returns:
            SyncResult
        """
        src_p = Path(src)
        dst_p = Path(dst)
        result = SyncResult()

        dst_p.mkdir(parents=True, exist_ok=True)

        for root, _dirs, files in os.walk(src_p):
            root_path = Path(root)
            rel_root = root_path.relative_to(src_p)

            for f in files:
                src_file = root_path / f

                # Create flattened filename
                if rel_root == Path("."):
                    flat_name = f
                else:
                    flat_name = separator.join(rel_root.parts) + separator + f

                dst_file = dst_p / flat_name

                try:
                    if dst_file.exists():
                        if on_conflict == "skip":
                            result.skipped.append(src_file)
                            continue
                        elif on_conflict == "rename":
                            counter = 1
                            stem = dst_file.stem
                            suffix = dst_file.suffix
                            while dst_file.exists():
                                dst_file = dst_p / f"{stem}_{counter}{suffix}"
                                counter += 1
                                if counter > MAX_RENAME_CONFLICTS:
                                    raise RuntimeError(f"Too many conflicting files: {stem}")

                    shutil.copy2(src_file, dst_file)
                    result.copied.append(dst_file)

                except Exception as e:
                    result.errors.append((src_file, str(e)))

        return result
