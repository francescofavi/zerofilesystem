"""zerofilesystem - Cross-platform file system utilities.

Usage:
    import zerofilesystem as zo

    # Read/write files
    zo.write_text("file.txt", "Hello World")
    content = zo.read_text("file.txt")

    # JSON operations
    zo.write_json("data.json", {"key": "value"})
    data = zo.read_json("data.json")

    # Find files
    py_files = zo.find_files(".", pattern="**/*.py")

    # File locking
    with zo.FileLock("/tmp/my.lock"):
        # Critical section
        pass

    # Transactions
    with zo.FileTransaction() as tx:
        tx.write_text("file1.txt", "content1")
        tx.write_text("file2.txt", "content2")

    # Archives
    zo.create_zip("./src", "backup.zip")
    zo.extract("backup.zip", "./extracted")

Copyright (c) 2025 Francesco Favi
License: MIT
"""

from zerofilesystem._platform import IS_LINUX, IS_MACOS, IS_UNIX, IS_WINDOWS, Pathish
from zerofilesystem.classes import (
    ArchiveError,
    ArchiveHandler,
    DirectoryOps,
    EventType,
    FileCleaner,
    FileFinder,
    FileHasher,
    FileIO,
    FileLock,
    FileLockedError,
    FileMeta,
    FilePermissions,
    FileSync,
    FileTransaction,
    FileUtils,
    FileWatcher,
    Finder,
    GzipHandler,
    HashMismatchError,
    IntegrityChecker,
    IntegrityError,
    InvalidPathError,
    JsonHandler,
    PathUtils,
    PermissionDeniedError,
    SecureDeleteError,
    SecureOps,
    SyncError,
    TransactionError,
    Watcher,
    WatchEvent,
    ZeroOSError,
)
from zerofilesystem.zerofilesystem import ZeroOS

__version__ = "0.1.1"
__author__ = "Francesco Favi"
__email__ = "14098835+francescofavi@users.noreply.github.com"

# =============================================================================
# BASIC I/O
# =============================================================================

read_text = FileIO.read_text
write_text = FileIO.write_text
read_bytes = FileIO.read_bytes
write_bytes = FileIO.write_bytes

# =============================================================================
# JSON
# =============================================================================

read_json = JsonHandler.read_json
write_json = JsonHandler.write_json

# =============================================================================
# GZIP
# =============================================================================

gzip_compress = GzipHandler.compress
gzip_decompress = GzipHandler.decompress

# =============================================================================
# DISCOVERY
# =============================================================================

find_files = FileFinder.find_files
walk_files = FileFinder.walk_files
is_hidden = FileFinder.is_hidden

# =============================================================================
# CLEANUP
# =============================================================================

delete_files = FileCleaner.delete_files
delete_empty_dirs = FileCleaner.delete_empty_dirs

# =============================================================================
# SYNC
# =============================================================================

move_if_absent = FileSync.move_if_absent
copy_if_newer = FileSync.copy_if_newer

# =============================================================================
# HASH
# =============================================================================

file_hash = FileHasher.file_hash

# =============================================================================
# META
# =============================================================================

ensure_dir = FileMeta.ensure_dir
touch = FileMeta.touch
file_size = FileMeta.file_size
disk_usage = FileMeta.disk_usage

# =============================================================================
# UTILS
# =============================================================================

safe_filename = FileUtils.safe_filename
atomic_write = FileUtils.atomic_write

# =============================================================================
# PATH UTILS
# =============================================================================

normalize_path = PathUtils.normalize
to_absolute = PathUtils.to_absolute
to_relative = PathUtils.to_relative
to_posix = PathUtils.to_posix
expand_path = PathUtils.expand
is_subpath = PathUtils.is_subpath
common_path = PathUtils.common_path
validate_path = PathUtils.validate_path

# =============================================================================
# PERMISSIONS
# =============================================================================

get_metadata = FilePermissions.get_metadata
set_readonly = FilePermissions.set_readonly
set_hidden = FilePermissions.set_hidden
set_executable = FilePermissions.set_executable
set_permissions = FilePermissions.set_permissions
copy_permissions = FilePermissions.copy_permissions
set_timestamps = FilePermissions.set_timestamps
mode_to_string = FilePermissions.mode_to_string
string_to_mode = FilePermissions.string_to_mode

# =============================================================================
# DIRECTORY OPS
# =============================================================================

copy_tree = DirectoryOps.copy_tree
move_tree = DirectoryOps.move_tree
sync_dirs = DirectoryOps.sync
temp_directory = DirectoryOps.temp_directory
tree_size = DirectoryOps.tree_size
tree_file_count = DirectoryOps.tree_file_count
flatten_tree = DirectoryOps.flatten

# =============================================================================
# INTEGRITY
# =============================================================================

directory_hash = IntegrityChecker.directory_hash
create_manifest = IntegrityChecker.create_manifest
save_manifest = IntegrityChecker.save_manifest
load_manifest = IntegrityChecker.load_manifest
verify_manifest = IntegrityChecker.verify_manifest
verify_file = IntegrityChecker.verify_file
compare_directories = IntegrityChecker.compare_directories
snapshot_hash = IntegrityChecker.snapshot_hash

# =============================================================================
# SECURE
# =============================================================================

secure_delete = SecureOps.secure_delete
secure_delete_directory = SecureOps.secure_delete_directory
private_directory = SecureOps.private_directory
create_private_file = SecureOps.create_private_file

# =============================================================================
# ARCHIVE
# =============================================================================

create_tar = ArchiveHandler.create_tar
create_zip = ArchiveHandler.create_zip
extract_tar = ArchiveHandler.extract_tar
extract_zip = ArchiveHandler.extract_zip
extract = ArchiveHandler.extract
list_archive = ArchiveHandler.list_archive

# =============================================================================
# __all__
# =============================================================================

__all__ = [
    # Facade class
    "ZeroOS",
    # Platform constants
    "IS_WINDOWS",
    "IS_MACOS",
    "IS_LINUX",
    "IS_UNIX",
    "Pathish",
    # Classes (for advanced usage)
    "Finder",
    "Watcher",
    "WatchEvent",
    "EventType",
    "FileLock",
    "FileTransaction",
    "FileWatcher",  # Legacy
    # Exceptions
    "ZeroOSError",
    "FileLockedError",
    "InvalidPathError",
    "HashMismatchError",
    "IntegrityError",
    "TransactionError",
    "ArchiveError",
    "PermissionDeniedError",
    "SecureDeleteError",
    "SyncError",
    # Basic I/O
    "read_text",
    "write_text",
    "read_bytes",
    "write_bytes",
    # JSON
    "read_json",
    "write_json",
    # Gzip
    "gzip_compress",
    "gzip_decompress",
    # Discovery
    "find_files",
    "walk_files",
    "is_hidden",
    # Cleanup
    "delete_files",
    "delete_empty_dirs",
    # Sync
    "move_if_absent",
    "copy_if_newer",
    # Hash
    "file_hash",
    # Meta
    "ensure_dir",
    "touch",
    "file_size",
    "disk_usage",
    # Utils
    "safe_filename",
    "atomic_write",
    # Path utils
    "normalize_path",
    "to_absolute",
    "to_relative",
    "to_posix",
    "expand_path",
    "is_subpath",
    "common_path",
    "validate_path",
    # Permissions
    "get_metadata",
    "set_readonly",
    "set_hidden",
    "set_executable",
    "set_permissions",
    "copy_permissions",
    "set_timestamps",
    "mode_to_string",
    "string_to_mode",
    # Directory ops
    "copy_tree",
    "move_tree",
    "sync_dirs",
    "temp_directory",
    "tree_size",
    "tree_file_count",
    "flatten_tree",
    # Integrity
    "directory_hash",
    "create_manifest",
    "save_manifest",
    "load_manifest",
    "verify_manifest",
    "verify_file",
    "compare_directories",
    "snapshot_hash",
    # Secure
    "secure_delete",
    "secure_delete_directory",
    "private_directory",
    "create_private_file",
    # Archive
    "create_tar",
    "create_zip",
    "extract_tar",
    "extract_zip",
    "extract",
    "list_archive",
]
