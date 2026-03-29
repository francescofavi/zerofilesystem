# zerofilesystem

[![PyPI version](https://img.shields.io/pypi/v/zerofilesystem?cacheSeconds=0)](https://pypi.org/project/zerofilesystem/)
[![Python versions](https://img.shields.io/pypi/pyversions/zerofilesystem?cacheSeconds=0)](https://pypi.org/project/zerofilesystem/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?cacheSeconds=0)](https://github.com/francescofavi/zerofilesystem/blob/main/LICENSE)

Cross-platform file system utilities for Python 3.12+

## Why This Project Exists

Working with files in Python often requires combining multiple standard library modules (`os`, `shutil`, `pathlib`, `json`, `gzip`, `tarfile`, `zipfile`) with careful attention to platform differences, atomic operations, and error handling. **zerofilesystem** consolidates these operations into a single, cohesive library that handles the complexity for you.

The library solves common pain points: ensuring atomic writes don't corrupt files on crash, managing cross-platform file locking, handling path normalization across Windows and Unix, and providing transactional file operations with automatic rollback. Whether you're building a configuration manager, a backup utility, or any application that needs reliable file operations, zerofilesystem provides battle-tested primitives that work consistently across platforms.

## Technical Choices and Design

zerofilesystem uses **only the Python standard library** with no external dependencies. This deliberate choice ensures maximum compatibility, minimal installation footprint, and no dependency conflicts.

The library is organized around single-responsibility classes, each handling one category of file operations. All public functions accept both `str` and `pathlib.Path` objects via the `Pathish` type alias. Atomic operations use the temp-file-plus-rename pattern to ensure crash safety on POSIX-compliant filesystems.

Platform-specific behavior (file locking via `fcntl`/`msvcrt`, hidden file attributes, executable permissions) is abstracted behind unified APIs that do the right thing on each platform.

## High-Level Component Overview

The library is structured into functional modules:

- **Basic I/O** (`FileIO`, `JsonHandler`, `GzipHandler`) - Text and binary file reading/writing with atomic support, JSON serialization, and gzip compression
- **File Discovery** (`FileFinder`, `Finder`) - Glob-based file search with custom filters and lazy iteration; `Finder` provides a fluent builder API
- **File Operations** (`FileSync`, `FileHasher`, `FileMeta`, `FileUtils`) - Conditional copy/move, cryptographic hashing, metadata access, and filename sanitization
- **Path Utilities** (`PathUtils`) - Cross-platform path normalization, expansion, and validation
- **Permissions** (`FilePermissions`) - Read/write/execute attributes and timestamp manipulation
- **Directory Operations** (`DirectoryOps`) - Tree copy, move, sync, and temporary directories
- **Integrity** (`IntegrityChecker`) - Directory hashing, manifest creation, and verification
- **Transactions** (`FileTransaction`) - Multi-file atomic operations with rollback
- **Security** (`SecureOps`) - Secure file deletion and private directory creation
- **Archives** (`ArchiveHandler`) - Tar and zip creation/extraction with filtering
- **File Watching** (`FileWatcher`, `Watcher`) - Polling-based filesystem monitoring; `Watcher` provides a fluent builder API with debouncing
- **Locking** (`FileLock`) - Cross-platform advisory file locking

## Meaningful Usage Example

Here's a realistic example showing how zerofilesystem components work together to create a simple backup system with integrity verification:

```python
import zerofilesystem as zo

# Create a backup of a project directory
source_dir = "./my_project"
backup_dir = "./backups"

# Create timestamped backup archive
zo.ensure_dir(backup_dir)
archive_path = zo.create_zip(
    source_dir,
    f"{backup_dir}/backup_2024.zip",
    filter_fn=lambda p: not p.name.startswith("."),  # Exclude hidden files
    compression="deflated"
)

# Generate integrity manifest for verification
manifest = zo.create_manifest(source_dir, algorithm="sha256")
zo.save_manifest(manifest, f"{backup_dir}/backup_2024.manifest")

# Later: verify the backup matches the manifest
loaded_manifest, algo = zo.load_manifest(f"{backup_dir}/backup_2024.manifest")
result = zo.verify_manifest(source_dir, loaded_manifest, algorithm=algo)

if result.is_valid:
    print("Backup integrity verified!")
else:
    print(f"Modified: {result.modified}, Missing: {result.missing}")

# Use transactions for multi-file config updates
with zo.FileTransaction() as tx:
    tx.write_text("config/app.json", '{"version": 2}')
    tx.write_text("config/db.json", '{"host": "localhost"}')
    # Both files written atomically, or neither if an error occurs
```

## Installation

```bash
pip install zerofilesystem
```

Or install from source:

```bash
git clone https://github.com/francescofavi/zerofilesystem.git
cd zerofilesystem
pip install -e .
```

### Requirements

- **Python 3.12+**
- **No external dependencies** - uses only the Python standard library

## Main Functions and APIs

### File I/O

**`read_text(path, encoding="utf-8")`** - Read text file contents.
```python
# Simple
content = zo.read_text("config.txt")

# With encoding
content = zo.read_text("data.txt", encoding="latin-1")
```

**`write_text(path, data, atomic=True, create_dirs=True)`** - Write text with atomic safety.
```python
# Simple
zo.write_text("output.txt", "Hello World")

# Non-atomic write to existing directory
zo.write_text("logs/app.log", log_data, atomic=False, create_dirs=False)
```

**`read_json(path)` / `write_json(path, obj)`** - JSON file operations.
```python
# Simple
config = zo.read_json("settings.json")

# Write with custom formatting
zo.write_json("data.json", {"users": users}, indent=4, atomic=True)
```

### File Discovery

**`find_files(base_dir, pattern, filter_fn, recursive, max_results)`** - Find files matching criteria.
```python
# Simple - find all Python files
py_files = zo.find_files("./src", pattern="*.py")

# Complex - find large log files, limit results
large_logs = zo.find_files(
    "./logs",
    pattern="*.log",
    filter_fn=lambda p: p.stat().st_size > 1024 * 1024,
    recursive=True,
    max_results=100
)
```

**`walk_files(base_dir, pattern)`** - Memory-efficient generator for large directories.
```python
# Process millions of files without loading all paths
for path in zo.walk_files("/data", pattern="*.csv"):
    process_file(path)
```

### Finder (Fluent API)

**`Finder(base_dir)`** - Powerful file finder with fluent builder API.
```python
from zerofilesystem import Finder

# Find Python files modified in last 7 days
files = (Finder("./src")
    .patterns("*.py")
    .modified_last_days(7)
    .not_hidden()
    .find())

# Complex search with multiple filters
files = (Finder("./project")
    .patterns("*.py", "*.json")
    .exclude("__pycache__", ".git", "*.pyc")
    .size_min("1KB")
    .size_max("10MB")
    .not_empty()
    .max_depth(5)
    .limit(100)
    .find())

# Memory-efficient iteration
for path in Finder("./logs").patterns("*.log").walk():
    process_log(path)

# Quick checks
count = Finder("./src").patterns("*.py").count()
has_tests = Finder("./tests").patterns("test_*.py").exists()
```

### Watcher (Fluent API)

**`Watcher(base_dir)`** - File system watcher with fluent builder API and debouncing.
```python
from zerofilesystem import Watcher, EventType

# Simple watch
watcher = (Watcher("./src")
    .patterns("*.py")
    .on_any(lambda e: print(f"{e.type.name}: {e.path}"))
    .start())

# Watch with filtering and debouncing
watcher = (Watcher("./project")
    .patterns("*.py", "*.json")
    .exclude("__pycache__", ".git")
    .not_hidden()
    .poll_fast()           # 0.1 second polling
    .debounce(0.5)         # Wait 500ms after last change
    .on_created(handle_new)
    .on_modified(handle_change)
    .on_deleted(handle_remove)
    .start())

# Context manager
with Watcher("./config").patterns("*.yaml").on_any(reload) as w:
    run_server()  # Watcher stops automatically on exit
```

### File Locking

**`FileLock(path, timeout)`** - Cross-platform advisory file lock.
```python
# Simple - blocking lock
with zo.FileLock("/tmp/myapp.lock"):
    do_critical_work()

# With timeout
try:
    with zo.FileLock("/tmp/myapp.lock", timeout=5.0):
        do_critical_work()
except TimeoutError:
    print("Could not acquire lock")
```

### Transactions

**`FileTransaction()`** - Atomic multi-file operations with rollback.
```python
# Simple
with zo.FileTransaction() as tx:
    tx.write_text("a.txt", "content a")
    tx.write_text("b.txt", "content b")

# With explicit control
tx = zo.FileTransaction()
try:
    tx.write_text("config.json", new_config)
    tx.copy_file("template.txt", "output.txt")
    tx.commit()
except Exception:
    tx.rollback()
```

### Archives

**`create_zip(source, output)` / `create_tar(source, output)`** - Create archives.
```python
# Simple
zo.create_zip("./project", "backup.zip")

# With compression and filtering
zo.create_tar(
    "./data",
    "archive.tar.gz",
    compression="gz",
    filter_fn=lambda p: p.suffix != ".tmp"
)
```

**`extract(archive, destination)`** - Auto-detect and extract archives.
```python
# Auto-detects format
zo.extract("backup.zip", "./restored")
zo.extract("archive.tar.gz", "./restored")
```

### Integrity Checking

**`file_hash(path, algo)`** - Compute file hash.
```python
# Simple
sha = zo.file_hash("document.pdf")

# With progress callback for large files
def progress(done, total):
    print(f"\r{done}/{total} bytes", end="")

sha = zo.file_hash("large.iso", algo="sha256", progress_callback=progress)
```

**`directory_hash(path)`** - Hash entire directory tree.
```python
# Detect any changes in a directory
before = zo.directory_hash("./config")
# ... operations ...
after = zo.directory_hash("./config")
if before != after:
    print("Configuration changed!")
```

### Directory Operations

**`copy_tree(src, dst)` / `move_tree(src, dst)`** - Recursive directory operations.
```python
# Simple copy
result = zo.copy_tree("./src", "./backup")
print(f"Copied {len(result.copied)} files")

# Sync with conflict handling
result = zo.copy_tree(
    "./new_version",
    "./deploy",
    on_conflict="only_if_newer",
    preserve_metadata=True
)
```

**`sync_dirs(src, dst, delete_extra)`** - Mirror directories.
```python
# One-way sync, optionally delete extra files in destination
result = zo.sync_dirs("./source", "./mirror", delete_extra=True)
```

### Secure Operations

**`secure_delete(path, passes)`** - Overwrite before deletion.
```python
# Simple
zo.secure_delete("sensitive.txt")

# Multiple passes with random data
zo.secure_delete("credentials.json", passes=7, random_data=True)
```

## Development

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Linting and formatting
uv run ruff check .
uv run ruff format .

# Type checking
uv run mypy src
```

## Further Documentation

- [Full API Reference](https://github.com/francescofavi/zerofilesystem/blob/main/docs/API_REFERENCE.md) - Detailed documentation of all public functions, parameters, and return types
- [Architecture](https://github.com/francescofavi/zerofilesystem/blob/main/docs/ARCHITECTURE.md) - Internal structure, module organization, dependency graph, and design decisions
- [Functional Analysis](https://github.com/francescofavi/zerofilesystem/blob/main/docs/FUNCTIONAL_ANALYSIS.md) - High-level view of processes, flows, and feature mapping

## License

[MIT License](https://github.com/francescofavi/zerofilesystem/blob/main/LICENSE)
