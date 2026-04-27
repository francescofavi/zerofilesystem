"""Helper classes for file operations."""

from zerofilesystem.classes.archive_handler import ArchiveHandler
from zerofilesystem.classes.change_detector import ChangeDetector, ChangeSummary
from zerofilesystem.classes.directory_ops import DirectoryOps
from zerofilesystem.classes.exceptions import (
    ArchiveError,
    FileLockedError,
    HashMismatchError,
    IntegrityError,
    InvalidPathError,
    PermissionDeniedError,
    SecureDeleteError,
    SyncError,
    TransactionError,
    ZeroFSError,
)
from zerofilesystem.classes.file_lock import FileLock
from zerofilesystem.classes.file_permissions import FilePermissions
from zerofilesystem.classes.file_transaction import FileTransaction
from zerofilesystem.classes.files import FileCleaner, FileFinder, FileHasher, FileMeta, FileSync
from zerofilesystem.classes.finder import Finder
from zerofilesystem.classes.integrity_checker import IntegrityChecker
from zerofilesystem.classes.io import FileIO, FileUtils, GzipHandler, JsonHandler
from zerofilesystem.classes.manifest_cache import ManifestCache
from zerofilesystem.classes.path_utils import PathUtils
from zerofilesystem.classes.secure_ops import SecureOps
from zerofilesystem.classes.watcher import (
    EventType,
    FileWatcher,
    Watcher,
    WatchEvent,
    WatchEventType,
)

# Legacy alias
WatchEventOld = WatchEvent

__all__ = [
    # Change detection
    "ChangeDetector",
    "ChangeSummary",
    # Core I/O
    "FileIO",
    "JsonHandler",
    "GzipHandler",
    "FileUtils",
    # Discovery and cleanup
    "Finder",
    "FileFinder",
    "FileCleaner",
    # Sync and file operations
    "FileSync",
    "FileHasher",
    "FileMeta",
    "FileLock",
    # Path utilities
    "PathUtils",
    # Permissions and metadata
    "FilePermissions",
    # Directory operations
    "DirectoryOps",
    # Integrity verification
    "IntegrityChecker",
    "ManifestCache",
    # Transactions
    "FileTransaction",
    # Security
    "SecureOps",
    # Archives
    "ArchiveHandler",
    # File watching
    "Watcher",
    "WatchEvent",
    "EventType",
    "FileWatcher",  # Legacy
    "WatchEventType",  # Legacy alias
    "WatchEventOld",  # Legacy alias
    # Exceptions
    "ZeroFSError",
    "FileLockedError",
    "InvalidPathError",
    "HashMismatchError",
    "IntegrityError",
    "TransactionError",
    "ArchiveError",
    "PermissionDeniedError",
    "SecureDeleteError",
    "SyncError",
]
