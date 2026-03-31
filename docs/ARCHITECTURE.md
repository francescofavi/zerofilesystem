# Architecture - zerofilesystem

## Purpose

Describes the internal structure, module organization, dependency graph, and design decisions of the zerofilesystem library.

## Scope

Covers the source code under `src/zerofilesystem/`. Excludes tests, examples, scripts, and build configuration.

---

## 1. High-Level Structure

```
src/zerofilesystem/
├── __init__.py            # Package entry point, flat function exports, __all__
├── _core.py              # ZeroFS facade class (all methods as static)
├── _platform.py           # Platform detection constants, Pathish type alias
└── classes/
    ├── __init__.py         # Re-exports all public classes and exceptions
    ├── _internal.py        # Shared constants and utility functions (non-public)
    ├── exceptions.py       # Exception hierarchy
    ├── io.py               # FileIO, JsonHandler, GzipHandler, FileUtils
    ├── files.py            # FileMeta, FileHasher, FileSync, FileCleaner, FileFinder
    ├── finder.py           # Finder (fluent builder API)
    ├── watcher.py          # Watcher, FileWatcher (legacy), EventType, WatchEvent
    ├── file_lock.py        # FileLock (cross-platform advisory locking)
    ├── file_transaction.py # FileTransaction, atomic_file_group
    ├── path_utils.py       # PathUtils (normalization, validation)
    ├── file_permissions.py # FilePermissions, FileMetadata dataclass
    ├── directory_ops.py    # DirectoryOps, SyncResult dataclass
    ├── integrity_checker.py# IntegrityChecker, ManifestEntry, VerificationResult
    ├── secure_ops.py       # SecureOps (secure delete, private files)
    └── archive_handler.py  # ArchiveHandler (tar, zip)
```

**File count**: 17 source files
**Total LOC**: ~6300

---

## 2. Access Layers

The library provides three access patterns:

### Layer 1: Flat Functions (Primary)

```python
import zerofilesystem as zfs
zfs.write_text("file.txt", "content")
```

Defined in `__init__.py` as class method aliases:

```python
read_text = FileIO.read_text
write_text = FileIO.write_text
```

This is the recommended usage. All public functions are listed in `__all__`.

### Layer 2: ZeroFS Facade Class

```python
from zerofilesystem import ZeroFS
zo = ZeroFS()
zfs.write_text("file.txt", "content")
```

Defined in `_core.py`. All methods are `@staticmethod`, delegating to the corresponding class methods. Provides a single-object interface for IDE discoverability.

### Layer 3: Direct Class Access

```python
from zerofilesystem.classes import FileIO
FileIO.write_text("file.txt", "content")
```

Direct access to the implementation classes. Useful when only a specific feature module is needed.

---

## 3. Module Responsibilities

### Core Modules

| Module | Classes | LOC | Responsibility |
|--------|---------|-----|----------------|
| `_platform.py` | — | 13 | Platform detection (`IS_WINDOWS`, `IS_MACOS`, etc.), `Pathish` type alias |
| `exceptions.py` | 9 exceptions | 164 | Exception hierarchy rooted at `ZeroFSError` |
| `_internal.py` | — | 107 | Shared constants (`HASH_CHUNK_SIZE`, `SIZE_UNITS`), utility functions (`parse_size`, `parse_datetime`, `is_hidden`) |

### Feature Modules

| Module | Classes | LOC | Responsibility |
|--------|---------|-----|----------------|
| `io.py` | `FileIO`, `JsonHandler`, `GzipHandler`, `FileUtils` | 357 | Text/binary I/O, JSON, gzip, atomic writes |
| `files.py` | `FileMeta`, `FileHasher`, `FileSync`, `FileCleaner`, `FileFinder` | 440 | File metadata, hashing, sync, cleanup, discovery |
| `finder.py` | `Finder` | 603 | Fluent builder API for file search |
| `watcher.py` | `Watcher`, `FileWatcher`, `EventType`, `WatchEvent` | 996 | File system monitoring with polling |
| `file_lock.py` | `FileLock` | 171 | Cross-platform advisory file locking |
| `file_transaction.py` | `FileTransaction`, `atomic_file_group` | 375 | Multi-file transactions with rollback |
| `path_utils.py` | `PathUtils` | 301 | Path normalization, validation, expansion |
| `file_permissions.py` | `FilePermissions`, `FileMetadata` | 320 | Permissions, timestamps, extended metadata |
| `directory_ops.py` | `DirectoryOps`, `SyncResult` | 450 | Tree copy/move/sync, temp directories |
| `integrity_checker.py` | `IntegrityChecker`, `ManifestEntry`, `VerificationResult` | 391 | Directory hashing, manifest, verification |
| `secure_ops.py` | `SecureOps` | 255 | Secure delete, private files/directories |
| `archive_handler.py` | `ArchiveHandler` | 348 | Tar and zip creation/extraction |

---

## 4. Dependency Graph

Internal module dependencies (arrows indicate "depends on"):

```
__init__.py ──> _core.py ──> classes/*
                               │
_platform.py <─────────────────┤ (used by all modules)
                               │
exceptions.py <────────────────┤ (used by: file_transaction, path_utils,
                               │  file_permissions, directory_ops,
                               │  integrity_checker, secure_ops, archive_handler)
                               │
_internal.py <─────────────────┤ (used by: files, finder, watcher, file_permissions)
                               │
io.py ─────────────────────────┤ (standalone, uses _platform)
                               │
files.py ──────────────────────┤ (uses _platform, _internal)
    │
    └──> integrity_checker.py  (uses FileHasher from files.py)
```

**Key observations:**
- No circular dependencies
- `_platform.py` is the only universal dependency
- `_internal.py` provides shared utilities to avoid duplication between `finder.py`, `watcher.py`, and `files.py`
- `integrity_checker.py` depends on `files.py` (for `FileHasher`)
- All other feature modules are independent of each other

### External Dependencies

**None.** The library uses only the Python standard library:

| stdlib module | Used by | Purpose |
|--------------|---------|---------|
| `pathlib` | All | Path objects |
| `os` | All | OS-level operations |
| `shutil` | io, files, directory_ops, secure_ops, archive_handler, file_transaction | Copy, move, disk usage |
| `json` | io, integrity_checker | JSON serialization |
| `hashlib` | files, integrity_checker | File hashing |
| `gzip` | io | Gzip compression |
| `tarfile` | archive_handler | Tar archives |
| `zipfile` | archive_handler | Zip archives |
| `threading` | io, watcher | Atomic writes, background watching |
| `fcntl` | file_lock | Unix file locking (conditional import) |
| `msvcrt` | file_lock | Windows file locking (conditional import) |
| `ctypes` | file_permissions | Windows file attributes (conditional import) |
| `secrets` | secure_ops | Cryptographically secure random data |
| `tempfile` | file_transaction, directory_ops, secure_ops | Temporary files/directories |
| `fnmatch` | finder, watcher | Pattern matching |
| `stat` | file_permissions | File mode constants |

---

## 5. Design Patterns

### Static Method Classes

All feature classes use `@staticmethod` methods exclusively. No instance state is maintained. This design choice means:
- Classes serve as namespaces grouping related functions
- No instantiation required for the primary API
- Easy to alias as flat functions in `__init__.py`

### Fluent Builder (Finder, Watcher)

`Finder` and `Watcher` use the builder pattern with method chaining. Instance state accumulates filter configuration, and execution is deferred until `.find()`, `.walk()`, or `.start()` is called.

### Atomic Write Pattern

Write operations use a temp-file-plus-rename pattern:
1. Write to `.<filename>.<pid>.<tid>.tmp` (unique per process/thread)
2. `os.replace()` atomically renames to target
3. On failure, temp file is cleaned up

This is implemented in `io.py` as `_atomic_write_helper()` and reused across `FileIO`, `GzipHandler`, and `FileUtils`.

### Transaction with Rollback

`FileTransaction` implements a write-ahead log pattern:
1. New content written to temp files
2. Originals backed up to temp files
3. On commit: `os.replace()` for each operation
4. On failure: backups restored in reverse order

### Platform Abstraction

Platform-specific code is isolated:
- `_platform.py`: Detection constants
- `file_lock.py`: Conditional imports of `fcntl` / `msvcrt`
- `file_permissions.py`: Conditional use of `ctypes` for Windows attributes

---

## 6. Public API Surface

### Exported in `__all__` (zerofilesystem package)

- **1 facade class**: `ZeroFS`
- **4 platform constants**: `IS_WINDOWS`, `IS_MACOS`, `IS_LINUX`, `IS_UNIX`
- **1 type alias**: `Pathish`
- **5 stateful classes**: `Finder`, `Watcher`, `FileLock`, `FileTransaction`, `FileWatcher` (legacy)
- **2 data types**: `WatchEvent`, `EventType`
- **10 exceptions**: `ZeroFSError` + 9 subclasses
- **64 flat functions**: covering I/O, JSON, gzip, discovery, cleanup, sync, hash, metadata, utils, paths, permissions, directories, integrity, security, archives

### Internal (not exported)

- `_internal.py` functions: `parse_size`, `parse_datetime`, `is_hidden`
- `_internal.py` constants: `FILE_ATTRIBUTE_HIDDEN`, `HASH_CHUNK_SIZE`, `SIZE_UNITS`, etc.
- Module-level helpers in `io.py`: `_atomic_tmp_path`, `_atomic_write_helper`
- `atomic_file_group` context manager in `file_transaction.py`
- `PathUtils` methods: `to_native`, `normalize_separators`, `split_path`, `join_path`, `portable_path`, `expand_user`, `expand_vars`
- `SecureOps` methods: `set_private_permissions`, `generate_random_filename`
- `ArchiveHandler.detect_archive_type`

---

## 7. Threading Model

- **Atomic writes**: Thread-safe via unique temp filenames (PID + thread ID)
- **FileLock**: Process-level locking via OS primitives; not designed for intra-process thread locking
- **Watcher/FileWatcher**: Runs background daemon thread; callbacks execute in watcher thread; internal state protected by `threading.Lock`
- **All other operations**: Not thread-safe; external synchronization required for concurrent access to the same files

---

## 8. Error Handling Strategy

All custom exceptions inherit from `ZeroFSError`, which carries optional `path`, `operation`, and `cause` fields:

```
ZeroFSError
├── FileLockedError
├── InvalidPathError
├── HashMismatchError
├── IntegrityError
├── TransactionError
├── ArchiveError
├── PermissionDeniedError
├── SecureDeleteError
└── SyncError
```

Standard library exceptions (`FileNotFoundError`, `PermissionError`, `TimeoutError`, `FileExistsError`) are not wrapped — they propagate directly when the root cause is an OS-level error.

---

## 9. Project Stage

**Beta** (`Development Status :: 4 - Beta` in pyproject.toml).

Current version: `0.1.0`.
