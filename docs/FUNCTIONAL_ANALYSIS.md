# Functional Analysis - zerofilesystem

## Purpose

High-level view of the system's purpose, process flows, feature mapping, and configuration impact.

## Scope

Covers functional behavior of all public features. Does not cover internal implementation details (see [ARCHITECTURE.md](ARCHITECTURE.md)) or parameter-level API documentation (see [API_REFERENCE.md](API_REFERENCE.md)).

---

## 3.1 Overview

**zerofilesystem** is a cross-platform file system utilities library for Python 3.12+. It provides a unified API for common file operations that typically require combining multiple standard library modules with careful attention to platform differences and error handling.

**Problem Domain**: File system operations in software development and operations contexts, including configuration management, backup systems, deployment automation, data processing pipelines, and any application requiring reliable file handling.

**Main Problems Solved**:
- Inconsistent behavior across Windows, Linux, and macOS for file operations
- Risk of data corruption from non-atomic writes during crashes or interruptions
- Complexity of implementing proper file locking across platforms
- Lack of transactional semantics for multi-file operations
- Difficulty in verifying file integrity across distributed systems

**Context of Use**: The library is designed for use in Python applications that need reliable, cross-platform file operations. Typical use cases include build tools, deployment scripts, backup utilities, configuration managers, data processing systems, and any software that must handle files safely.

**Main Goals**:
- **Reliability**: Atomic operations prevent partial writes and data corruption
- **Simplicity**: Single import provides access to all file operations
- **Cross-platform**: Consistent behavior on Windows, macOS, and Linux
- **Safety**: Secure deletion, private files, and integrity verification built-in

---

## 3.2 Glossary

| Term | Definition |
|------|------------|
| **Atomic write** | File write operation that either completes fully or leaves the original file unchanged |
| **Manifest** | JSON file containing hashes and metadata for a set of files, used for integrity verification |
| **Advisory lock** | File lock that cooperating processes respect but doesn't prevent other access |
| **Transaction** | Group of file operations that succeed or fail together with rollback capability |
| **Pathish** | Type accepting both string paths and `pathlib.Path` objects |

---

## 3.3 Process Flows

### FLOW-001: Atomic File Write

**Trigger**: Application calls `write_text()` or `write_bytes()` with `atomic=True` (default)

**Input**: Target file path and content to write

**Steps**:
1. Parent directory is created if `create_dirs=True` (default)
2. Content is written to a temporary file in the same directory as the target
3. Temporary file name includes process ID and thread ID for uniqueness
4. `os.replace()` atomically renames temporary file to target path
5. If any step fails, temporary file is removed

**Output**: File at target path with guaranteed complete content

**Synchronous**: Yes, blocking until complete

---

### FLOW-002: File Discovery

**Trigger**: Application calls `find_files()` or `walk_files()`

**Input**: Base directory, glob pattern, optional filter function, search options

**Steps**:
1. Base directory existence is verified
2. Glob pattern is normalized for recursive/non-recursive mode
3. Files matching pattern are enumerated using `pathlib.glob()` or `pathlib.rglob()`
4. Each file is passed through optional custom filter function
5. Paths are converted to absolute or relative as requested
6. Results are collected (list) or yielded (generator)
7. If `max_results` specified, enumeration stops early

**Output**: List or iterator of matching `Path` objects

**Synchronous**: Yes for `find_files()`, lazy evaluation for `walk_files()`

---

### FLOW-002b: Fluent File Discovery (Finder)

**Trigger**: Application creates `Finder` instance and calls `.find()` or `.walk()`

**Input**: Base directory, fluent configuration of patterns, filters, and options

**Steps**:
1. Finder is configured using fluent method chaining
2. Multiple patterns are combined (OR logic)
3. Exclusion patterns are checked (filename, path, and parent directories)
4. Files are enumerated via `rglob()` or `glob()` based on recursion setting
5. Depth limit is enforced if `max_depth()` specified
6. Type filters applied (files_only, dirs_only, or both)
7. Size filters applied (min, max, or range)
8. Date filters applied (modified, created, accessed - before/after)
9. Attribute filters applied (hidden, empty, symlinks, permissions)
10. Custom filter functions executed
11. Deduplication ensures each path appears once
12. Results limited if `limit()` specified
13. Paths returned as absolute or relative based on configuration

**Output**: List or iterator of matching `Path` objects

**Synchronous**: Yes for `.find()`, lazy evaluation for `.walk()`

**Key Differences from FLOW-002**:
- Fluent API allows complex filter combinations without custom functions
- Built-in size parsing ("1KB", "5MB", "1.5GB")
- Built-in date parsing (ISO strings, datetime, timedelta)
- Multiple patterns with automatic deduplication

---

### FLOW-003: File Locking

**Trigger**: Application creates `FileLock` and calls `acquire()` or enters context manager

**Input**: Lock file path, optional timeout

**Steps**:
1. Lock file directory is created if needed
2. Lock file is opened/created with appropriate flags
3. Platform-specific locking is attempted:
   - Unix/macOS: `fcntl.flock()` with `LOCK_EX`
   - Windows: `msvcrt.locking()` with `LK_NBLCK`
4. If lock unavailable and timeout specified:
   - Polling occurs at 50ms intervals
   - `TimeoutError` raised if timeout exceeded
5. If no timeout, blocking wait until lock acquired
6. On release, lock is unlocked and file descriptor closed

**Output**: Lock acquisition status; critical section protection

**Synchronous**: Blocking (with optional timeout)

---

### FLOW-004: File Transaction

**Trigger**: Application creates `FileTransaction` and schedules operations

**Input**: Multiple file write, copy, and delete operations

**Steps**:
1. Transaction temp directory is created
2. For each scheduled operation:
   - New content is written to temp file
   - If target exists, original is backed up to temp file
   - Operation is recorded in pending list
3. On `commit()`:
   - Each pending operation is applied using `os.replace()`
   - If any operation fails, completed operations are rolled back
   - Backups are restored, new files are removed
4. On `rollback()` (explicit or on exception):
   - All pending operations are discarded
   - No changes to target files
5. Temp directory is cleaned up

**Output**: All files atomically updated, or no changes

**Synchronous**: Yes

---

### FLOW-005: Integrity Verification

**Trigger**: Application calls `create_manifest()` and later `verify_manifest()`

**Input**: Directory path, hash algorithm, optional filter

**Steps** (Manifest Creation):
1. Directory tree is enumerated
2. Each file passing filter is hashed using streaming algorithm
3. File metadata (size, mtime) is recorded
4. Manifest dictionary is built with relative paths as keys
5. Manifest can be saved to JSON file

**Steps** (Manifest Verification):
1. Current directory state is scanned
2. For each manifest entry:
   - File existence is checked (records missing if absent)
   - File hash is computed and compared (records modified if different)
3. Files not in manifest are recorded as extra
4. Verification result summarizes all findings

**Output**: `VerificationResult` with valid, missing, extra, modified, and error lists

**Synchronous**: Yes (may be long-running for large directories)

---

### FLOW-006: Directory Synchronization

**Trigger**: Application calls `sync_dirs()`

**Input**: Source directory, destination directory, sync options

**Steps**:
1. Source directory structure is enumerated
2. Filter function applied to exclude unwanted files/directories
3. For each source file:
   - If not in destination: copied
   - If in destination but older: updated
   - If same or newer: skipped
4. If `delete_extra=True`:
   - Files in destination not in source are removed
   - Empty directories are cleaned up
5. Operation details tracked in `SyncResult`

**Output**: `SyncResult` with copied, updated, deleted, skipped, and error lists

**Dry Run**: If `dry_run=True`, no changes made, only reporting

---

### FLOW-007: Archive Operations

**Trigger**: Application calls `create_zip()`, `create_tar()`, or `extract()`

**Input**: Source path/archive path, destination, compression options

**Steps** (Creation):
1. Source file/directory is enumerated
2. Filter function excludes unwanted items
3. Archive is created with specified compression
4. Files are added with paths relative to base directory
5. Archive path is returned

**Steps** (Extraction):
1. Archive format is auto-detected from file signature
2. Archive contents are enumerated
3. Filter function excludes unwanted members
4. Path components can be stripped for flat extraction
5. Path traversal attacks are prevented (paths must stay within destination)
6. Files are extracted to destination

**Output**: Created archive path or extraction directory path

**Synchronous**: Yes

---

### FLOW-008: File Watching (Legacy)

**Trigger**: Application creates `FileWatcher` and calls `start()`

**Input**: Directory to watch, polling interval, event callbacks

**Steps**:
1. Initial directory state is captured (file paths and mtimes)
2. Background thread (or blocking loop) starts
3. At each polling interval:
   - Current directory state is scanned
   - New files trigger `CREATED` events
   - Changed mtimes trigger `MODIFIED` events
   - Missing files trigger `DELETED` events
   - Registered callbacks are invoked for each event
4. Process continues until `stop()` called

**Output**: Event callbacks invoked with `WatchEvent` objects

**Asynchronous**: Yes, background thread by default; callbacks run in watcher thread

---

### FLOW-008b: Fluent File Watching (Watcher)

**Trigger**: Application creates `Watcher` instance and calls `.start()`

**Input**: Base directory, fluent configuration of patterns, filters, callbacks, and options

**Steps**:
1. Watcher is configured using fluent method chaining
2. Pattern filters define which files to watch (glob patterns)
3. Exclusion patterns define which files to ignore
4. Size, date, and attribute filters further refine watched files
5. Initial directory state is captured (mtimes for files, existence for directories)
6. If debouncing enabled, background debounce thread starts
7. Main watch loop starts (background thread or blocking)
8. At each polling interval:
   - Current directory state is scanned
   - Each path is checked against all configured filters
   - New files/directories trigger `CREATED` events (immediate)
   - Changed mtimes trigger `MODIFIED` events (debounced if configured)
   - Missing files/directories trigger `DELETED` events (immediate)
   - Registered callbacks are invoked for matching events
9. For debounced MODIFIED events:
   - Event is queued with timestamp
   - Debounce thread checks queue periodically
   - Event emitted only after debounce period of silence
10. Process continues until `stop()` called

**Output**: Event callbacks invoked with `WatchEvent` objects containing type, path, is_directory, timestamp

**Asynchronous**: Yes, background thread by default; callbacks run in watcher thread

**Key Features**:
- Same fluent API as `Finder` for filtering
- Debouncing for MODIFIED events (reduces noise from rapid saves)
- Configurable poll intervals with presets (fast=0.1s, slow=5s)
- Error callback for handling exceptions in user callbacks
- Context manager support for automatic cleanup

---

### FLOW-009: Secure Deletion

**Trigger**: Application calls `secure_delete()` or `secure_delete_directory()`

**Input**: File/directory path, number of overwrite passes

**Steps**:
1. File existence and type verified
2. File made writable if necessary
3. For each pass:
   - File is overwritten with random data (or zeros)
   - Write is flushed and synced to disk
4. File is truncated to zero size
5. File is deleted

**Output**: File securely removed (best effort on modern storage)

**Note**: True security requires full-disk encryption due to SSD wear leveling

---

## 3.4 Public Entry Points

### Basic I/O Functions

| Entry Point | Type | Purpose | Key Parameters |
|-------------|------|---------|----------------|
| `read_text()` | Function | Read text file | `path`, `encoding` |
| `write_text()` | Function | Write text file atomically | `path`, `data`, `atomic`, `create_dirs` |
| `read_bytes()` | Function | Read binary file | `path` |
| `write_bytes()` | Function | Write binary file atomically | `path`, `data`, `atomic` |
| `read_json()` | Function | Read and parse JSON | `path` |
| `write_json()` | Function | Serialize to JSON file | `path`, `obj`, `indent` |

**Effects**: File system read/write; may create directories

---

### File Discovery Functions

| Entry Point | Type | Purpose | Key Parameters |
|-------------|------|---------|----------------|
| `find_files()` | Function | Find files by pattern | `base_dir`, `pattern`, `filter_fn`, `recursive` |
| `walk_files()` | Generator | Memory-efficient file enumeration | Same as `find_files()` |
| `is_hidden()` | Function | Check if file is hidden | `path` |
| `Finder` | Class | Fluent file discovery API | `base_dir` |

**Effects**: File system read (stat calls)

**Finder Methods** (all return self for chaining):
- `.patterns()`, `.exclude()` - Pattern matching
- `.size_min()`, `.size_max()` - Size filtering (supports "1KB", "5MB", etc.)
- `.modified_after()`, `.modified_before()`, `.modified_last_days()` - Date filtering
- `.not_hidden()`, `.not_empty()`, `.files_only()` - Attribute filtering
- `.filter()` - Custom filter functions
- `.find()`, `.walk()`, `.count()`, `.exists()` - Execution

---

### Locking and Transactions

| Entry Point | Type | Purpose | Key Parameters |
|-------------|------|---------|----------------|
| `FileLock` | Class | Cross-platform file locking | `lock_path`, `timeout` |
| `FileTransaction` | Class | Multi-file atomic operations | `temp_dir` |

**Effects**: Creates lock files; creates temp files during transactions

---

### Directory Operations

| Entry Point | Type | Purpose | Key Parameters |
|-------------|------|---------|----------------|
| `copy_tree()` | Function | Recursive directory copy | `src`, `dst`, `on_conflict`, `filter_fn` |
| `move_tree()` | Function | Recursive directory move | `src`, `dst`, `on_conflict` |
| `sync_dirs()` | Function | Directory synchronization | `src`, `dst`, `delete_extra`, `dry_run` |
| `temp_directory()` | Context Manager | Temporary directory | `prefix`, `cleanup` |

**Effects**: Creates/modifies directories and files; may delete files if `delete_extra=True`

---

### Integrity Operations

| Entry Point | Type | Purpose | Key Parameters |
|-------------|------|---------|----------------|
| `file_hash()` | Function | Compute file hash | `path`, `algo` |
| `directory_hash()` | Function | Hash entire directory | `path`, `algo`, `filter_fn` |
| `create_manifest()` | Function | Create integrity manifest | `path`, `algo` |
| `verify_manifest()` | Function | Verify against manifest | `directory`, `manifest` |

**Effects**: File system read (intensive for large directories)

---

### Archive Operations

| Entry Point | Type | Purpose | Key Parameters |
|-------------|------|---------|----------------|
| `create_zip()` | Function | Create ZIP archive | `source`, `output`, `compression` |
| `create_tar()` | Function | Create TAR archive | `source`, `output`, `compression` |
| `extract()` | Function | Auto-extract archive | `archive`, `destination` |
| `list_archive()` | Function | List archive contents | `archive` |

**Effects**: Creates archive files or extracts to destination directory

---

### Security Operations

| Entry Point | Type | Purpose | Key Parameters |
|-------------|------|---------|----------------|
| `secure_delete()` | Function | Overwrite and delete file | `path`, `passes` |
| `secure_delete_directory()` | Function | Securely delete directory | `path`, `passes` |
| `private_directory()` | Context Manager | Create restricted-permission directory | `prefix`, `secure_cleanup` |
| `create_private_file()` | Function | Create restricted-permission file | `path`, `content` |

**Effects**: Modifies/deletes files; sets restrictive permissions

---

### File Watching

| Entry Point | Type | Purpose | Key Parameters |
|-------------|------|---------|----------------|
| `FileWatcher` | Class | Monitor directory for changes (legacy) | `path`, `poll_interval`, `recursive` |
| `Watcher` | Class | Fluent file watching API | `base_dir` |
| `EventType` | Enum | Event type constants | `CREATED`, `MODIFIED`, `DELETED` |
| `WatchEvent` | Dataclass | Event information | `type`, `path`, `is_directory`, `timestamp` |

**Effects**: Runs background thread; invokes callbacks on file changes

**Watcher Methods** (all return self for chaining):
- `.patterns()`, `.exclude()` - Pattern matching (same as Finder)
- `.poll_interval()`, `.poll_fast()`, `.poll_slow()` - Polling configuration
- `.debounce()`, `.debounce_ms()` - Debounce MODIFIED events
- Size, date, attribute filters (same as Finder)
- `.on_created()`, `.on_modified()`, `.on_deleted()`, `.on_any()` - Event callbacks
- `.on_error()` - Error handling callback
- `.start()`, `.stop()` - Execution control

---

## 3.5 Configuration with Business Impact

zerofilesystem is primarily a library without external configuration files. Behavior is controlled through function parameters.

### Key Parameters with Business Impact

| Parameter | Location | Business Impact |
|-----------|----------|-----------------|
| `atomic` | Write functions | When `True` (default), prevents data corruption on crash. Setting to `False` improves performance but risks partial writes. |
| `create_dirs` | Write functions | When `True` (default), automatically creates parent directories. Setting to `False` requires pre-existing paths. |
| `timeout` | `FileLock` | Controls how long to wait for locked resources. `None` means indefinite blocking which may cause hangs. |
| `passes` | Secure delete | More passes increase security confidence but take longer. Default of 3 balances security and performance. |
| `poll_interval` | `FileWatcher` | Lower values detect changes faster but use more CPU. Default 1.0 second is reasonable for most use cases. |
| `delete_extra` | `sync_dirs()` | When `True`, removes files from destination that don't exist in source. Critical for true mirroring but destructive. |
| `dry_run` | `sync_dirs()` | When `True`, reports what would happen without making changes. Essential for previewing destructive operations. |

### Platform Constants

The constants `IS_WINDOWS`, `IS_MACOS`, `IS_LINUX`, `IS_UNIX` allow applications to implement platform-specific logic when needed.

---

## 3.6 Feature Map

### FEAT-001 - Atomic File Operations

- **Purpose**: Prevent data corruption from interrupted writes
- **Processes involved**: FLOW-001 (Atomic File Write)
- **Entry points**: `write_text()`, `write_bytes()`, `write_json()`, `atomic_write()`
- **Dependencies**: Requires same-filesystem temp directory for `os.replace()` atomicity

---

### FEAT-002 - Cross-Platform File Locking

- **Purpose**: Coordinate access to shared files across processes
- **Processes involved**: FLOW-003 (File Locking)
- **Entry points**: `FileLock` class
- **Dependencies**: Platform-specific: `fcntl` on Unix, `msvcrt` on Windows

---

### FEAT-003 - Multi-File Transactions

- **Purpose**: Apply multiple file changes atomically with rollback
- **Processes involved**: FLOW-004 (File Transaction)
- **Entry points**: `FileTransaction` class
- **Dependencies**: FEAT-001 (Atomic File Operations) for individual writes

---

### FEAT-004 - Integrity Verification

- **Purpose**: Detect file modifications, additions, or deletions
- **Processes involved**: FLOW-005 (Integrity Verification)
- **Entry points**: `create_manifest()`, `verify_manifest()`, `directory_hash()`, `file_hash()`
- **Dependencies**: Standard library `hashlib`

---

### FEAT-005 - Directory Synchronization

- **Purpose**: Keep directories in sync, support backup and deployment
- **Processes involved**: FLOW-006 (Directory Synchronization)
- **Entry points**: `copy_tree()`, `move_tree()`, `sync_dirs()`
- **Dependencies**: None external

---

### FEAT-006 - Archive Management

- **Purpose**: Create and extract compressed archives
- **Processes involved**: FLOW-007 (Archive Operations)
- **Entry points**: `create_zip()`, `create_tar()`, `extract()`, `list_archive()`
- **Dependencies**: Standard library `tarfile`, `zipfile`

---

### FEAT-007 - File System Monitoring

- **Purpose**: React to file changes in near-real-time
- **Processes involved**: FLOW-008 (File Watching), FLOW-008b (Fluent File Watching)
- **Entry points**: `FileWatcher` class (legacy), `Watcher` class (fluent API)
- **Dependencies**: Standard library `threading`
- **Note**: `Watcher` provides same fluent API as `Finder` plus debouncing support

---

### FEAT-007b - Fluent File Discovery

- **Purpose**: Powerful file search with complex filter combinations
- **Processes involved**: FLOW-002b (Fluent File Discovery)
- **Entry points**: `Finder` class
- **Dependencies**: Standard library `fnmatch`, `pathlib`
- **Key capabilities**:
  - Multiple glob patterns with automatic deduplication
  - Size filtering with human-readable units ("1KB", "5MB", "1.5GB")
  - Date filtering with multiple input formats (datetime, ISO strings, timedelta)
  - Attribute filtering (hidden, empty, permissions)
  - Custom filter functions
  - Memory-efficient iteration via `.walk()`

---

### FEAT-007c - Fluent File Watching with Debouncing

- **Purpose**: Monitor file changes with advanced filtering and debouncing
- **Processes involved**: FLOW-008b (Fluent File Watching)
- **Entry points**: `Watcher` class, `EventType` enum, `WatchEvent` dataclass
- **Dependencies**: Standard library `threading`, `fnmatch`
- **Key capabilities**:
  - Same filtering API as `Finder`
  - Debouncing for MODIFIED events (coalesces rapid changes)
  - Configurable poll intervals with presets
  - Separate callbacks per event type
  - Error handling callback for exceptions in user code
  - Context manager support for automatic cleanup

---

### FEAT-008 - Secure Operations

- **Purpose**: Handle sensitive files with enhanced security
- **Processes involved**: FLOW-009 (Secure Deletion)
- **Entry points**: `secure_delete()`, `secure_delete_directory()`, `private_directory()`, `create_private_file()`
- **Dependencies**: Standard library `secrets` for random data

---

### FEAT-009 - Path Utilities

- **Purpose**: Cross-platform path manipulation and validation
- **Processes involved**: Used by all other features
- **Entry points**: `normalize_path()`, `to_absolute()`, `to_relative()`, `expand_path()`, `validate_path()`
- **Dependencies**: Standard library `os.path`, `pathlib`

---

### FEAT-010 - Permissions Management

- **Purpose**: Control file access attributes across platforms
- **Processes involved**: Used by FEAT-008 (Secure Operations)
- **Entry points**: `set_readonly()`, `set_hidden()`, `set_executable()`, `set_permissions()`, `get_metadata()`
- **Dependencies**: Platform-specific: `ctypes` on Windows for attribute flags

---

## 3.7 Limitations and Assumptions

### Known Limitations

1. **Atomic writes**: Only atomic on POSIX-compliant filesystems. Network filesystems (NFS, SMB) may not guarantee atomicity.

2. **Secure deletion**: Best-effort on modern SSDs due to wear leveling and controller-level caching. True security requires full-disk encryption.

3. **File locking**: Advisory locks only; processes not using the lock can still access files. Not effective across network filesystems.

4. **File watching**: Polling-based, not event-based. Detection latency depends on `poll_interval`. May miss rapid changes within poll window.

5. **Archive extraction**: Python 3.14 will require explicit filter argument for tar extraction (deprecation warning present).

6. **Windows hidden files**: Cannot rename files to add/remove `.` prefix for hiding; only Windows hidden attribute is supported.

### Implicit Assumptions

1. **Filesystem behavior**: Assumes standard POSIX or Windows filesystem semantics. May not work correctly on exotic filesystems.

2. **Encoding**: Defaults to UTF-8 for text operations. Files with other encodings must explicitly specify.

3. **Permissions**: Assumes process has appropriate permissions for requested operations.

4. **Disk space**: No built-in disk space checking. Operations may fail mid-way if disk fills.

5. **Concurrent access**: Except for `FileLock`, assumes single-process access or external coordination.

### Handled Edge Cases

1. **Thread safety**: Atomic writes use process ID and thread ID in temp filenames to prevent collisions.

2. **Path traversal**: Archive extraction validates all paths stay within destination directory.

3. **Unicode filenames**: Full Unicode support in filenames across platforms.

4. **Symlinks**: Configurable following/ignoring of symbolic links in directory operations.

5. **Empty directories**: `delete_empty_dirs()` handles cleanup; `sync_dirs()` cleans empty dirs when `delete_extra=True`.

6. **Filter exceptions**: File finder catches and skips files where filter function raises exceptions.
