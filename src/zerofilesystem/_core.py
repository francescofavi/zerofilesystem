"""ZeroFS - Cross-platform file system utilities facade class."""

from __future__ import annotations

from collections.abc import Callable, Generator, Iterable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import IO, Any, Literal

from zerofilesystem._platform import IS_LINUX, IS_MACOS, IS_UNIX, IS_WINDOWS, Pathish
from zerofilesystem.classes import (
    ArchiveHandler,
    DirectoryOps,
    FileCleaner,
    FileFinder,
    FileHasher,
    FileIO,
    FileLock,
    FileMeta,
    FilePermissions,
    FileSync,
    FileTransaction,
    FileUtils,
    FileWatcher,
    GzipHandler,
    IntegrityChecker,
    JsonHandler,
    PathUtils,
    SecureOps,
)
from zerofilesystem.classes._internal import HASH_CHUNK_SIZE
from zerofilesystem.classes.directory_ops import SyncResult
from zerofilesystem.classes.file_permissions import FileMetadata
from zerofilesystem.classes.integrity_checker import ManifestEntry, VerificationResult


class ZeroFS:
    """Cross-platform file system utilities - facade class.

    Provides a unified interface to all zerofilesystem functionality.

    Example:
        zo = ZeroFS()
        zfs.write_text("file.txt", "Hello World")
        content = zfs.read_text("file.txt")
    """

    # Platform constants
    IS_WINDOWS = IS_WINDOWS
    IS_MACOS = IS_MACOS
    IS_LINUX = IS_LINUX
    IS_UNIX = IS_UNIX

    # Basic I/O

    @staticmethod
    def read_text(path: Pathish, encoding: str = "utf-8") -> str:
        return FileIO.read_text(path, encoding=encoding)

    @staticmethod
    def write_text(
        path: Pathish,
        data: str,
        encoding: str = "utf-8",
        create_dirs: bool = True,
        atomic: bool = True,
    ) -> Path:
        return FileIO.write_text(
            path, data, encoding=encoding, create_dirs=create_dirs, atomic=atomic
        )

    @staticmethod
    def read_bytes(path: Pathish) -> bytes:
        return FileIO.read_bytes(path)

    @staticmethod
    def write_bytes(
        path: Pathish,
        data: bytes,
        create_dirs: bool = True,
        atomic: bool = True,
    ) -> Path:
        return FileIO.write_bytes(path, data, create_dirs=create_dirs, atomic=atomic)

    # JSON

    @staticmethod
    def read_json(path: Pathish, encoding: str = "utf-8") -> Any:
        return JsonHandler.read_json(path, encoding=encoding)

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
        return JsonHandler.write_json(
            path, obj, encoding=encoding, indent=indent, create_dirs=create_dirs, atomic=atomic
        )

    # Gzip

    @staticmethod
    def gzip_compress(
        src: Pathish,
        dst: Pathish | None = None,
        level: int = 6,
        atomic: bool = True,
    ) -> Path:
        return GzipHandler.compress(src, dst, level=level, atomic=atomic)

    @staticmethod
    def gzip_decompress(
        src_gz: Pathish,
        dst: Pathish | None = None,
        atomic: bool = True,
    ) -> Path:
        return GzipHandler.decompress(src_gz, dst, atomic=atomic)

    # Discovery

    @staticmethod
    def find_files(
        base_dir: Pathish,
        pattern: str = "**/*",
        filter_fn: Callable[[Path], bool] | None = None,
        recursive: bool = True,
        absolute: bool = True,
        max_results: int | None = None,
    ) -> list[Path]:
        return FileFinder.find_files(base_dir, pattern, filter_fn, recursive, absolute, max_results)

    @staticmethod
    def walk_files(
        base_dir: Pathish,
        pattern: str = "**/*",
        filter_fn: Callable[[Path], bool] | None = None,
        recursive: bool = True,
        absolute: bool = True,
    ) -> Iterator[Path]:
        return FileFinder.walk_files(base_dir, pattern, filter_fn, recursive, absolute)

    @staticmethod
    def is_hidden(path: Pathish) -> bool:
        return FileFinder.is_hidden(path)

    # Cleanup

    @staticmethod
    def delete_files(paths: Iterable[Pathish]) -> dict[str, list]:
        return FileCleaner.delete_files(paths)

    @staticmethod
    def delete_empty_dirs(root: Pathish, remove_root: bool = False) -> list[Path]:
        return FileCleaner.delete_empty_dirs(root, remove_root=remove_root)

    # Sync

    @staticmethod
    def move_if_absent(
        src: Pathish,
        dst_dir: Pathish,
        create_dirs: bool = True,
        on_conflict: Literal["skip", "rename", "error"] = "skip",
    ) -> tuple[bool, Path | None]:
        return FileSync.move_if_absent(
            src, dst_dir, create_dirs=create_dirs, on_conflict=on_conflict
        )

    @staticmethod
    def copy_if_newer(
        src: Pathish,
        dst: Pathish,
        create_dirs: bool = True,
    ) -> bool:
        return FileSync.copy_if_newer(src, dst, create_dirs=create_dirs)

    # Hash

    @staticmethod
    def file_hash(
        path: Pathish,
        algo: Literal["md5", "sha1", "sha256", "sha512"] = "sha256",
        chunk: int = HASH_CHUNK_SIZE,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> str:
        return FileHasher.file_hash(
            path, algo=algo, chunk=chunk, progress_callback=progress_callback
        )

    # Meta

    @staticmethod
    def ensure_dir(path: Pathish) -> Path:
        return FileMeta.ensure_dir(path)

    @staticmethod
    def touch(path: Pathish, exist_ok: bool = True) -> Path:
        return FileMeta.touch(path, exist_ok=exist_ok)

    @staticmethod
    def file_size(path: Pathish) -> int:
        return FileMeta.file_size(path)

    @staticmethod
    def disk_usage(path: Pathish) -> tuple[int, int, int]:
        return FileMeta.disk_usage(path)

    # Utils

    @staticmethod
    def safe_filename(name: str, replacement: str = "_") -> str:
        return FileUtils.safe_filename(name, replacement=replacement)

    @staticmethod
    @contextmanager
    def atomic_write(
        path: Pathish,
        mode: str = "w",
        encoding: str = "utf-8",
    ) -> Generator[IO, None, None]:
        with FileUtils.atomic_write(path, mode=mode, encoding=encoding) as f:
            yield f

    # Path Utils

    @staticmethod
    def normalize_path(path: Pathish) -> Path:
        return PathUtils.normalize(path)

    @staticmethod
    def to_absolute(path: Pathish, base: Pathish | None = None) -> Path:
        return PathUtils.to_absolute(path, base=base)

    @staticmethod
    def to_relative(path: Pathish, base: Pathish | None = None) -> Path:
        return PathUtils.to_relative(path, base=base)

    @staticmethod
    def to_posix(path: Pathish) -> str:
        return PathUtils.to_posix(path)

    @staticmethod
    def expand_path(path: Pathish) -> Path:
        return PathUtils.expand(path)

    @staticmethod
    def is_subpath(path: Pathish, parent: Pathish) -> bool:
        return PathUtils.is_subpath(path, parent)

    @staticmethod
    def common_path(*paths: Pathish) -> Path | None:
        return PathUtils.common_path(*paths)

    @staticmethod
    def validate_path(
        path: Pathish,
        must_exist: bool = False,
        must_be_file: bool = False,
        must_be_dir: bool = False,
    ) -> Path:
        return PathUtils.validate_path(
            path, must_exist=must_exist, must_be_file=must_be_file, must_be_dir=must_be_dir
        )

    # Permissions

    @staticmethod
    def get_metadata(path: Pathish) -> FileMetadata:
        return FilePermissions.get_metadata(path)

    @staticmethod
    def set_readonly(path: Pathish, readonly: bool = True) -> None:
        FilePermissions.set_readonly(path, readonly=readonly)

    @staticmethod
    def set_hidden(path: Pathish, hidden: bool = True) -> None:
        FilePermissions.set_hidden(path, hidden=hidden)

    @staticmethod
    def set_executable(path: Pathish, executable: bool = True) -> None:
        FilePermissions.set_executable(path, executable=executable)

    @staticmethod
    def set_permissions(path: Pathish, mode: int) -> None:
        FilePermissions.set_permissions(path, mode)

    @staticmethod
    def copy_permissions(src: Pathish, dst: Pathish) -> None:
        FilePermissions.copy_permissions(src, dst)

    @staticmethod
    def set_timestamps(
        path: Pathish,
        modified: datetime | None = None,
        accessed: datetime | None = None,
    ) -> None:
        FilePermissions.set_timestamps(path, modified=modified, accessed=accessed)

    @staticmethod
    def mode_to_string(mode: int) -> str:
        return FilePermissions.mode_to_string(mode)

    @staticmethod
    def string_to_mode(s: str) -> int:
        return FilePermissions.string_to_mode(s)

    # Directory Ops

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
        return DirectoryOps.copy_tree(
            src,
            dst,
            filter_fn=filter_fn,
            on_conflict=on_conflict,
            preserve_metadata=preserve_metadata,
            follow_symlinks=follow_symlinks,
        )

    @staticmethod
    def move_tree(
        src: Pathish,
        dst: Pathish,
        *,
        filter_fn: Callable[[Path], bool] | None = None,
        on_conflict: Literal["overwrite", "skip", "error"] = "error",
    ) -> SyncResult:
        return DirectoryOps.move_tree(src, dst, filter_fn=filter_fn, on_conflict=on_conflict)

    @staticmethod
    def sync_dirs(
        src: Pathish,
        dst: Pathish,
        *,
        delete_extra: bool = False,
        filter_fn: Callable[[Path], bool] | None = None,
        dry_run: bool = False,
    ) -> SyncResult:
        return DirectoryOps.sync(
            src, dst, delete_extra=delete_extra, filter_fn=filter_fn, dry_run=dry_run
        )

    @staticmethod
    @contextmanager
    def temp_directory(
        prefix: str = "zerofilesystem_",
        suffix: str = "",
        parent: Pathish | None = None,
        cleanup: bool = True,
    ) -> Generator[Path, None, None]:
        with DirectoryOps.temp_directory(
            prefix=prefix, suffix=suffix, parent=parent, cleanup=cleanup
        ) as p:
            yield p

    @staticmethod
    def tree_size(path: Pathish, follow_symlinks: bool = False) -> int:
        return DirectoryOps.tree_size(path, follow_symlinks=follow_symlinks)

    @staticmethod
    def tree_file_count(path: Pathish, follow_symlinks: bool = False) -> int:
        return DirectoryOps.tree_file_count(path, follow_symlinks=follow_symlinks)

    @staticmethod
    def flatten_tree(
        src: Pathish,
        dst: Pathish,
        *,
        separator: str = "_",
        on_conflict: Literal["overwrite", "skip", "rename"] = "rename",
    ) -> SyncResult:
        return DirectoryOps.flatten(src, dst, separator=separator, on_conflict=on_conflict)

    # Integrity

    @staticmethod
    def directory_hash(
        path: Pathish,
        algorithm: Literal["md5", "sha1", "sha256", "sha512"] = "sha256",
        filter_fn: Callable[[Path], bool] | None = None,
    ) -> str:
        return IntegrityChecker.directory_hash(path, algorithm=algorithm, filter_fn=filter_fn)

    @staticmethod
    def create_manifest(
        path: Pathish,
        algorithm: Literal["md5", "sha1", "sha256", "sha512"] = "sha256",
        filter_fn: Callable[[Path], bool] | None = None,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> dict[str, ManifestEntry]:
        return IntegrityChecker.create_manifest(
            path, algorithm=algorithm, filter_fn=filter_fn, progress_callback=progress_callback
        )

    @staticmethod
    def save_manifest(
        manifest: dict[str, ManifestEntry], output_path: Pathish, algorithm: str = "sha256"
    ) -> Path:
        return IntegrityChecker.save_manifest(manifest, output_path, algorithm=algorithm)

    @staticmethod
    def load_manifest(manifest_path: Pathish) -> tuple[dict[str, ManifestEntry], str]:
        return IntegrityChecker.load_manifest(manifest_path)

    @staticmethod
    def verify_manifest(
        directory: Pathish,
        manifest: dict[str, ManifestEntry],
        algorithm: Literal["md5", "sha1", "sha256", "sha512"] = "sha256",
        check_extra: bool = True,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> VerificationResult:
        return IntegrityChecker.verify_manifest(
            directory,
            manifest,
            algorithm=algorithm,
            check_extra=check_extra,
            progress_callback=progress_callback,
        )

    @staticmethod
    def verify_file(
        path: Pathish,
        expected_hash: str,
        algorithm: Literal["md5", "sha1", "sha256", "sha512"] = "sha256",
    ) -> bool:
        return IntegrityChecker.verify_file(path, expected_hash, algorithm=algorithm)

    @staticmethod
    def compare_directories(
        dir1: Pathish,
        dir2: Pathish,
        algorithm: Literal["md5", "sha1", "sha256", "sha512"] = "sha256",
    ) -> VerificationResult:
        return IntegrityChecker.compare_directories(dir1, dir2, algorithm=algorithm)

    @staticmethod
    def snapshot_hash(
        path: Pathish,
        algorithm: Literal["md5", "sha1", "sha256", "sha512"] = "sha256",
    ) -> str:
        return IntegrityChecker.snapshot_hash(path, algorithm=algorithm)

    # Secure

    @staticmethod
    def secure_delete(path: Pathish, passes: int = 3, random_data: bool = True) -> None:
        SecureOps.secure_delete(path, passes=passes, random_data=random_data)

    @staticmethod
    def secure_delete_directory(path: Pathish, passes: int = 3, random_data: bool = True) -> None:
        SecureOps.secure_delete_directory(path, passes=passes, random_data=random_data)

    @staticmethod
    @contextmanager
    def private_directory(
        prefix: str = "private_",
        parent: Pathish | None = None,
        cleanup: bool = True,
        secure_cleanup: bool = False,
    ) -> Generator[Path, None, None]:
        with SecureOps.private_directory(
            prefix=prefix, parent=parent, cleanup=cleanup, secure_cleanup=secure_cleanup
        ) as p:
            yield p

    @staticmethod
    def create_private_file(
        path: Pathish,
        content: bytes | None = None,
        text_content: str | None = None,
        encoding: str = "utf-8",
    ) -> Path:
        return SecureOps.create_private_file(
            path, content=content, text_content=text_content, encoding=encoding
        )

    # Archive

    @staticmethod
    def create_tar(
        source: Pathish,
        output: Pathish,
        *,
        compression: Literal["none", "gz", "bz2", "xz"] = "none",
        filter_fn: Callable[[Path], bool] | None = None,
        base_dir: str | None = None,
    ) -> Path:
        return ArchiveHandler.create_tar(
            source, output, compression=compression, filter_fn=filter_fn, base_dir=base_dir
        )

    @staticmethod
    def create_zip(
        source: Pathish,
        output: Pathish,
        *,
        compression: Literal["stored", "deflated", "bzip2", "lzma"] = "deflated",
        filter_fn: Callable[[Path], bool] | None = None,
        base_dir: str | None = None,
    ) -> Path:
        return ArchiveHandler.create_zip(
            source, output, compression=compression, filter_fn=filter_fn, base_dir=base_dir
        )

    @staticmethod
    def extract_tar(
        archive: Pathish,
        destination: Pathish,
        *,
        filter_fn: Callable[[str], bool] | None = None,
        strip_components: int = 0,
    ) -> Path:
        return ArchiveHandler.extract_tar(
            archive, destination, filter_fn=filter_fn, strip_components=strip_components
        )

    @staticmethod
    def extract_zip(
        archive: Pathish,
        destination: Pathish,
        *,
        filter_fn: Callable[[str], bool] | None = None,
        strip_components: int = 0,
    ) -> Path:
        return ArchiveHandler.extract_zip(
            archive, destination, filter_fn=filter_fn, strip_components=strip_components
        )

    @staticmethod
    def extract(archive: Pathish, destination: Pathish, **kwargs) -> Path:
        return ArchiveHandler.extract(archive, destination, **kwargs)

    @staticmethod
    def list_archive(archive: Pathish) -> list[str]:
        return ArchiveHandler.list_archive(archive)

    # Locking and transactions (return class instances)

    @staticmethod
    def file_lock(lock_path: Pathish, timeout: float | None = None) -> FileLock:
        return FileLock(lock_path, timeout=timeout)

    @staticmethod
    def file_transaction(temp_dir: Pathish | None = None) -> FileTransaction:
        return FileTransaction(temp_dir=temp_dir)

    @staticmethod
    def file_watcher(
        path: Pathish,
        *,
        recursive: bool = True,
        poll_interval: float = 1.0,
        filter_fn: Callable[[Path], bool] | None = None,
        ignore_hidden: bool = True,
    ) -> FileWatcher:
        return FileWatcher(
            path,
            recursive=recursive,
            poll_interval=poll_interval,
            filter_fn=filter_fn,
            ignore_hidden=ignore_hidden,
        )
