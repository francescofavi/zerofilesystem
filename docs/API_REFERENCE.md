# API Reference - zerofilesystem

## Purpose

Detailed documentation of all public functions, classes, parameters, and return types in the zerofilesystem library.

## Scope

Covers all symbols exported in `zerofilesystem.__all__`. For a high-level overview, see the [README](../README.md). For architecture details, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Table of Contents

- [Global Concepts](#global-concepts)
- [Basic I/O](#basic-io)
- [JSON Operations](#json-operations)
- [Gzip Compression](#gzip-compression)
- [File Discovery](#file-discovery)
- [Finder (Fluent API)](#finder-fluent-api)
- [File Locking](#file-locking)
- [File Hashing](#file-hashing)
- [File Metadata](#file-metadata)
- [File Utilities](#file-utilities)
- [Path Utilities](#path-utilities)
- [File Permissions](#file-permissions)
- [File Cleanup](#file-cleanup)
- [File Synchronization](#file-synchronization)
- [Directory Operations](#directory-operations)
- [Integrity Checking](#integrity-checking)
- [File Transactions](#file-transactions)
- [Secure Operations](#secure-operations)
- [Archive Handling](#archive-handling)
- [File Watching](#file-watching)
- [Watcher (Fluent API)](#watcher-fluent-api)
- [Exceptions](#exceptions)

---

## Global Concepts

### Pathish Type

All functions accepting file paths accept both `str` and `pathlib.Path` objects:

```python
Pathish = str | Path
```

### Platform Constants

```python
import zerofilesystem as zfs

zfs.IS_WINDOWS  # True on Windows
zfs.IS_MACOS    # True on macOS
zfs.IS_LINUX    # True on Linux
zfs.IS_UNIX     # True on macOS or Linux
```

### Atomic Operations

Many write operations support an `atomic` parameter. When `True` (default), writes use a temp-file-plus-rename pattern:
1. Write to a temporary file in the same directory
2. Use `os.replace()` to atomically rename to the target

This ensures that on crash, files are either fully written or untouched.

---

## Basic I/O

### read_text

```python
read_text(path: Pathish, encoding: str = "utf-8") -> str
```

Read entire text file contents.

**Parameters:**
- `path` (required): File path to read
- `encoding` (optional): Text encoding, default `"utf-8"`

**Returns:** File contents as string

**Raises:** `FileNotFoundError` if file doesn't exist

**Examples:**

```python
# Basic usage
content = zfs.read_text("config.txt")

# With specific encoding
content = zfs.read_text("legacy.txt", encoding="latin-1")

# Read from Path object
from pathlib import Path
content = zfs.read_text(Path.home() / "document.txt")
```

---

### write_text

```python
write_text(
    path: Pathish,
    data: str,
    encoding: str = "utf-8",
    create_dirs: bool = True,
    atomic: bool = True,
) -> Path
```

Write text to file with atomic write support.

**Parameters:**
- `path` (required): Destination file path
- `data` (required): Text content to write
- `encoding` (optional): Text encoding, default `"utf-8"`
- `create_dirs` (optional): Create parent directories if missing, default `True`
- `atomic` (optional): Use atomic write pattern, default `True`

**Returns:** `Path` to the written file

**Side Effects:** Creates parent directories if `create_dirs=True`

**Examples:**

```python
# Basic atomic write
zfs.write_text("output.txt", "Hello World")

# Write without creating directories (must exist)
zfs.write_text("existing_dir/file.txt", content, create_dirs=False)

# Non-atomic write for performance (less safe)
zfs.write_text("temp.txt", data, atomic=False)

# UTF-16 encoding
zfs.write_text("unicode.txt", text, encoding="utf-16")
```

---

### read_bytes

```python
read_bytes(path: Pathish) -> bytes
```

Read entire binary file contents.

**Parameters:**
- `path` (required): File path to read

**Returns:** File contents as bytes

**Raises:** `FileNotFoundError` if file doesn't exist

**Examples:**

```python
# Read binary file
data = zfs.read_bytes("image.png")

# Read and process
content = zfs.read_bytes("archive.bin")
checksum = hashlib.md5(content).hexdigest()
```

---

### write_bytes

```python
write_bytes(
    path: Pathish,
    data: bytes,
    create_dirs: bool = True,
    atomic: bool = True,
) -> Path
```

Write binary data to file with atomic write support.

**Parameters:**
- `path` (required): Destination file path
- `data` (required): Binary content to write
- `create_dirs` (optional): Create parent directories if missing, default `True`
- `atomic` (optional): Use atomic write pattern, default `True`

**Returns:** `Path` to the written file

**Examples:**

```python
# Write binary data
zfs.write_bytes("output.bin", b"\x00\x01\x02\x03")

# Write downloaded content
zfs.write_bytes("download/file.zip", response.content)
```

---

## JSON Operations

### read_json

```python
read_json(path: Pathish, encoding: str = "utf-8") -> Any
```

Read and parse JSON file.

**Parameters:**
- `path` (required): JSON file path
- `encoding` (optional): Text encoding, default `"utf-8"`

**Returns:** Parsed JSON value (dict, list, str, int, float, bool, or None)

**Raises:**
- `FileNotFoundError` if file doesn't exist
- `json.JSONDecodeError` if JSON is invalid

**Examples:**

```python
# Read configuration
config = zfs.read_json("settings.json")
db_host = config["database"]["host"]

# Read list data
users = zfs.read_json("users.json")
for user in users:
    print(user["name"])
```

---

### write_json

```python
write_json(
    path: Pathish,
    obj: Any,
    *,
    encoding: str = "utf-8",
    indent: int = 2,
    create_dirs: bool = True,
    atomic: bool = True,
) -> Path
```

Write object as JSON file.

**Parameters:**
- `path` (required): Destination file path
- `obj` (required): Object to serialize (must be JSON-serializable)
- `encoding` (optional): Text encoding, default `"utf-8"`
- `indent` (optional): Indentation spaces, default `2`
- `create_dirs` (optional): Create parent directories, default `True`
- `atomic` (optional): Use atomic write, default `True`

**Returns:** `Path` to the written file

**Examples:**

```python
# Write configuration
zfs.write_json("config.json", {"debug": True, "port": 8080})

# Write with custom indent
zfs.write_json("data.json", large_object, indent=4)

# Compact JSON (no indent)
zfs.write_json("compact.json", data, indent=0)
```

---

## Gzip Compression

### gzip_compress

```python
gzip_compress(
    src: Pathish,
    dst: Pathish | None = None,
    level: int = 6,
    atomic: bool = True,
) -> Path
```

Compress file to gzip format.

**Parameters:**
- `src` (required): Source file path
- `dst` (optional): Destination path, default adds `.gz` extension
- `level` (optional): Compression level 1-9, default `6`
- `atomic` (optional): Use atomic write, default `True`

**Returns:** `Path` to compressed file

**Examples:**

```python
# Default compression
zfs.gzip_compress("data.txt")  # Creates data.txt.gz

# Custom destination
zfs.gzip_compress("log.txt", "archive/log.gz")

# Maximum compression
zfs.gzip_compress("large.csv", level=9)
```

---

### gzip_decompress

```python
gzip_decompress(
    src_gz: Pathish,
    dst: Pathish | None = None,
    atomic: bool = True,
) -> Path
```

Decompress gzip file.

**Parameters:**
- `src_gz` (required): Source gzip file
- `dst` (optional): Destination path, default removes `.gz` extension
- `atomic` (optional): Use atomic write, default `True`

**Returns:** `Path` to decompressed file

**Examples:**

```python
# Default decompression
zfs.gzip_decompress("data.txt.gz")  # Creates data.txt

# Custom destination
zfs.gzip_decompress("archive.gz", "output/data.txt")
```

---

## File Discovery

### find_files

```python
find_files(
    base_dir: Pathish,
    pattern: str = "**/*",
    filter_fn: Callable[[Path], bool] | None = None,
    recursive: bool = True,
    absolute: bool = True,
    max_results: int | None = None,
) -> list[Path]
```

Find files matching glob pattern with optional custom filter.

**Parameters:**
- `base_dir` (required): Directory to search in
- `pattern` (optional): Glob pattern, default `"**/*"` (all files)
- `filter_fn` (optional): Custom filter function `(Path) -> bool`
- `recursive` (optional): Search subdirectories, default `True`
- `absolute` (optional): Return absolute paths, default `True`
- `max_results` (optional): Stop after N results, default unlimited

**Returns:** List of matching `Path` objects

**Examples:**

```python
# All Python files
py_files = zfs.find_files("./src", pattern="*.py")

# Non-recursive search
top_level = zfs.find_files("./", pattern="*.txt", recursive=False)

# Custom filter: files larger than 1MB
large_files = zfs.find_files(
    "./data",
    filter_fn=lambda p: p.stat().st_size > 1024 * 1024
)

# Combine pattern and filter
test_files = zfs.find_files(
    "./tests",
    pattern="test_*.py",
    filter_fn=lambda p: "integration" not in p.name
)

# Limit results
first_10 = zfs.find_files("./logs", pattern="*.log", max_results=10)
```

---

### walk_files

```python
walk_files(
    base_dir: Pathish,
    pattern: str = "**/*",
    filter_fn: Callable[[Path], bool] | None = None,
    recursive: bool = True,
    absolute: bool = True,
) -> Iterator[Path]
```

Generator version of `find_files` for memory efficiency.

**Parameters:** Same as `find_files` except no `max_results`

**Yields:** Matching `Path` objects one at a time

**Examples:**

```python
# Process large directory without loading all paths
for path in zfs.walk_files("/var/log", pattern="*.log"):
    process_log(path)

# Count files without building list
count = sum(1 for _ in zfs.walk_files("./data"))
```

---

### is_hidden

```python
is_hidden(path: Pathish) -> bool
```

Check if file or directory is hidden.

**Parameters:**
- `path` (required): Path to check

**Returns:** `True` if hidden

**Platform behavior:**
- Unix/macOS: Files starting with `.`
- Windows: Files with `FILE_ATTRIBUTE_HIDDEN` flag

**Examples:**

```python
zfs.is_hidden(".gitignore")  # True on Unix
zfs.is_hidden("normal.txt")  # False
```

---

## Finder (Fluent API)

The `Finder` class provides a powerful, fluent API for file discovery with extensive filtering capabilities.

### Finder

```python
class Finder:
    def __init__(self, base_dir: Pathish = ".")
```

Powerful file finder with fluent builder API.

**Parameters:**
- `base_dir` (optional): Directory to search in, default current directory

**Returns self for chaining on all filter methods.**

### Pattern Methods

```python
# Add glob patterns to match
.patterns(*patterns: str) -> Finder
.pattern(pattern: str) -> Finder  # Alias

# Add patterns to exclude
.exclude(*patterns: str) -> Finder
```

**Examples:**

```python
from zerofilesystem import Finder

# Single pattern
files = Finder("./src").patterns("*.py").find()

# Multiple patterns
files = Finder("./data").patterns("*.csv", "*.json", "*.xml").find()

# With exclusions
files = (Finder("./project")
    .patterns("*.py")
    .exclude("__pycache__", "*.pyc", ".git")
    .find())
```

### Recursion and Depth

```python
.recursive(recursive: bool = True) -> Finder
.non_recursive() -> Finder
.max_depth(depth: int) -> Finder
```

**Examples:**

```python
# Non-recursive (top-level only)
files = Finder("./").patterns("*.txt").non_recursive().find()

# Limited depth (1 = immediate children)
files = Finder("./project").patterns("*.py").max_depth(2).find()
```

### Size Filters

```python
.size_min(size: int | str) -> Finder
.size_max(size: int | str) -> Finder
.size_between(min_size, max_size) -> Finder
```

Size can be specified as bytes (int) or with units (str): `"1KB"`, `"5MB"`, `"1.5GB"`, `"1TB"`

**Examples:**

```python
# Files larger than 1MB
large = Finder("./data").size_min("1MB").find()

# Files between 100KB and 10MB
medium = Finder("./logs").size_between("100KB", "10MB").find()

# Small files under 1KB
small = Finder("./config").size_max(1024).find()
```

### Date Filters

```python
# Modification time
.modified_after(dt: datetime | str | timedelta) -> Finder
.modified_before(dt: datetime | str | timedelta) -> Finder
.modified_between(after, before) -> Finder
.modified_today() -> Finder
.modified_last_days(days: int) -> Finder
.modified_last_hours(hours: int) -> Finder

# Creation time
.created_after(dt) -> Finder
.created_before(dt) -> Finder

# Access time
.accessed_after(dt) -> Finder
.accessed_before(dt) -> Finder
```

Date can be: `datetime` object, ISO string `"2024-01-01"`, or `timedelta` (relative to now).

**Examples:**

```python
from datetime import datetime, timedelta

# Modified in last 7 days
recent = Finder("./src").modified_last_days(7).find()

# Modified after specific date
new_files = Finder("./data").modified_after("2024-06-01").find()

# Modified in last 2 hours
very_recent = Finder("./logs").modified_last_hours(2).find()

# Using timedelta
recent = Finder("./").modified_after(timedelta(hours=24)).find()
```

### Attribute Filters

```python
.hidden() -> Finder          # Only hidden files
.not_hidden() -> Finder      # Exclude hidden files
.empty() -> Finder           # Only empty files (size=0)
.not_empty() -> Finder       # Exclude empty files
.follow_symlinks(follow: bool = True) -> Finder
.no_symlinks() -> Finder     # Don't follow symlinks
.readable() -> Finder        # Only readable files
.writable() -> Finder        # Only writable files
.executable() -> Finder      # Only executable files
```

**Examples:**

```python
# Find non-empty, non-hidden Python files
files = (Finder("./src")
    .patterns("*.py")
    .not_hidden()
    .not_empty()
    .find())

# Find executable scripts
scripts = Finder("./bin").executable().find()
```

### Type Filters

```python
.files_only() -> Finder      # Only files (default)
.dirs_only() -> Finder       # Only directories
.files_and_dirs() -> Finder  # Both files and directories
```

**Examples:**

```python
# Find directories only
dirs = Finder("./project").dirs_only().find()

# Find both files and directories
all_items = Finder("./").files_and_dirs().find()
```

### Output Options

```python
.absolute(absolute: bool = True) -> Finder  # Return absolute paths (default)
.relative() -> Finder                        # Return relative paths
.limit(max_results: int) -> Finder          # Limit number of results
.first(n: int = 1) -> Finder                # Return first N results
```

**Examples:**

```python
# Get first 10 matches
first_10 = Finder("./logs").patterns("*.log").first(10).find()

# Get relative paths
rel_paths = Finder("./src").patterns("*.py").relative().find()
```

### Custom Filters

```python
.filter(fn: Callable[[Path], bool]) -> Finder
.where(fn: Callable[[Path], bool]) -> Finder  # Alias
```

**Examples:**

```python
# Custom filter: files with "test" in name
test_files = (Finder("./")
    .patterns("*.py")
    .filter(lambda p: "test" in p.name.lower())
    .find())

# Multiple custom filters
files = (Finder("./data")
    .filter(lambda p: p.stat().st_nlink == 1)  # No hardlinks
    .filter(lambda p: len(p.stem) > 5)          # Name length > 5
    .find())
```

### Execution Methods

```python
.find() -> list[Path]              # Execute and return list
.walk() -> Iterator[Path]          # Execute and yield (memory efficient)
.count() -> int                    # Count matches without building list
.exists() -> bool                  # Check if any match exists
.first_match() -> Path | None      # Return first match or None
```

**Examples:**

```python
# Standard execution
files = Finder("./src").patterns("*.py").find()

# Memory-efficient iteration
for path in Finder("./huge_directory").patterns("*.log").walk():
    process_file(path)

# Count without loading
count = Finder("./data").patterns("*.csv").count()

# Check existence
has_tests = Finder("./").patterns("test_*.py").exists()

# Get first match
config = Finder("./").patterns("config.*").first_match()
```

### Iteration Support

```python
# Direct iteration
for f in Finder("./src").patterns("*.py"):
    print(f)

# Length
n = len(Finder("./src").patterns("*.py"))
```

### Complete Example

```python
from zerofilesystem import Finder
from datetime import timedelta

# Find large Python files modified recently, excluding tests and cache
files = (Finder("./project")
    .patterns("*.py", "*.pyx")
    .exclude("__pycache__", "*.pyc", "test_*", ".git", ".venv")
    .recursive()
    .not_hidden()
    .not_empty()
    .size_min("1KB")
    .modified_last_days(30)
    .max_depth(5)
    .limit(100)
    .find())

print(f"Found {len(files)} files")
for f in files:
    print(f"  {f.name}: {f.stat().st_size} bytes")
```

---

## File Locking

### FileLock

```python
class FileLock:
    def __init__(
        self,
        lock_path: Pathish,
        timeout: float | None = None
    )
```

Cross-platform advisory file lock using `fcntl` (Unix) or `msvcrt` (Windows).

**Parameters:**
- `lock_path` (required): Path to lock file (created if doesn't exist)
- `timeout` (optional): Max seconds to wait, `None` for blocking

**Methods:**
- `acquire()`: Acquire the lock
- `release()`: Release the lock

**Raises:** `TimeoutError` if timeout exceeded

**Context Manager:** Yes

**Examples:**

```python
# Blocking lock
with zfs.FileLock("/tmp/myapp.lock"):
    do_exclusive_work()

# With timeout
try:
    with zfs.FileLock("/tmp/myapp.lock", timeout=5.0):
        do_work()
except TimeoutError:
    print("Lock busy")

# Manual control
lock = zfs.FileLock("/tmp/task.lock")
lock.acquire()
try:
    do_work()
finally:
    lock.release()
```

---

## File Hashing

### file_hash

```python
file_hash(
    path: Pathish,
    algo: Literal["md5", "sha1", "sha256", "sha512"] = "sha256",
    chunk: int = 1024 * 1024,
    progress_callback: Callable[[int, int], None] | None = None,
) -> str
```

Compute file hash using streaming (memory efficient).

**Parameters:**
- `path` (required): File path
- `algo` (optional): Hash algorithm, default `"sha256"`
- `chunk` (optional): Read chunk size in bytes, default 1MB
- `progress_callback` (optional): Callback `(bytes_processed, total_bytes)`

**Returns:** Hexadecimal hash string

**Examples:**

```python
# SHA-256 hash
sha = zfs.file_hash("document.pdf")

# MD5 for compatibility
md5 = zfs.file_hash("file.zip", algo="md5")

# With progress
def show_progress(done, total):
    print(f"\r{done * 100 // total}%", end="")

hash_val = zfs.file_hash("large.iso", progress_callback=show_progress)
```

---

## File Metadata

### ensure_dir

```python
ensure_dir(path: Pathish) -> Path
```

Create directory and parents if not exists.

**Parameters:**
- `path` (required): Directory path

**Returns:** `Path` to directory

**Examples:**

```python
zfs.ensure_dir("output/reports/2024")
```

---

### touch

```python
touch(path: Pathish, exist_ok: bool = True) -> Path
```

Create empty file (and parent directories).

**Parameters:**
- `path` (required): File path
- `exist_ok` (optional): Don't error if exists, default `True`

**Returns:** `Path` to file

**Examples:**

```python
zfs.touch("logs/app.log")
zfs.touch("marker.txt", exist_ok=False)  # Raises if exists
```

---

### file_size

```python
file_size(path: Pathish) -> int
```

Get file size in bytes.

**Parameters:**
- `path` (required): File path

**Returns:** Size in bytes

---

### disk_usage

```python
disk_usage(path: Pathish) -> tuple[int, int, int]
```

Get disk usage for filesystem containing path.

**Parameters:**
- `path` (required): Any path on the filesystem

**Returns:** Tuple of `(total_bytes, used_bytes, free_bytes)`

**Examples:**

```python
total, used, free = zfs.disk_usage("/home")
print(f"Free space: {free // (1024**3)} GB")
```

---

## File Utilities

### safe_filename

```python
safe_filename(name: str, replacement: str = "_") -> str
```

Sanitize filename by removing/replacing illegal characters.

**Parameters:**
- `name` (required): Original filename
- `replacement` (optional): Replacement character, default `"_"`

**Returns:** Safe filename string

**Handles:**
- Illegal characters: `< > : " / \ | ? *`
- Control characters
- Windows reserved names (CON, PRN, etc.)

**Examples:**

```python
zfs.safe_filename("file:name*.txt")  # "file_name_.txt"
zfs.safe_filename("CON.txt")         # "_CON.txt" on Windows
zfs.safe_filename("my/path/file")    # "my_path_file"
```

---

### atomic_write

```python
@contextmanager
atomic_write(
    path: Pathish,
    mode: str = "w",
    encoding: str = "utf-8",
) -> Generator[IO, None, None]
```

Context manager for atomic file writes.

**Parameters:**
- `path` (required): Destination path
- `mode` (optional): File mode `"w"` or `"wb"`, default `"w"`
- `encoding` (optional): Text encoding (for text mode)

**Yields:** File handle

**Examples:**

```python
# Text file
with zfs.atomic_write("config.json") as f:
    json.dump(data, f)

# Binary file
with zfs.atomic_write("data.bin", mode="wb") as f:
    f.write(binary_data)
```

---

## Path Utilities

### normalize_path

```python
normalize_path(path: Pathish) -> Path
```

Normalize path by resolving `.` and `..` components.

**Examples:**

```python
zfs.normalize_path("./foo/../bar/./baz")  # Path("bar/baz")
```

---

### to_absolute

```python
to_absolute(path: Pathish, base: Pathish | None = None) -> Path
```

Convert to absolute path.

**Parameters:**
- `path` (required): Path to convert
- `base` (optional): Base for relative paths, default current directory

**Examples:**

```python
zfs.to_absolute("file.txt")  # /current/working/dir/file.txt
zfs.to_absolute("file.txt", base="/home/user")  # /home/user/file.txt
```

---

### to_relative

```python
to_relative(path: Pathish, base: Pathish | None = None) -> Path
```

Convert to relative path.

**Parameters:**
- `path` (required): Path to convert
- `base` (optional): Base directory, default current directory

**Examples:**

```python
zfs.to_relative("/home/user/docs/file.txt", base="/home/user")  # docs/file.txt
```

---

### to_posix

```python
to_posix(path: Pathish) -> str
```

Convert path to POSIX format (forward slashes).

**Examples:**

```python
zfs.to_posix("C:\\Users\\foo\\bar")  # "C:/Users/foo/bar"
```

---

### expand_path

```python
expand_path(path: Pathish) -> Path
```

Expand `~` and environment variables.

**Examples:**

```python
zfs.expand_path("~/documents")      # /home/user/documents
zfs.expand_path("$HOME/docs")       # /home/user/docs
zfs.expand_path("~/docs/$PROJECT")  # Both expanded
```

---

### is_subpath

```python
is_subpath(path: Pathish, parent: Pathish) -> bool
```

Check if path is under parent directory.

**Examples:**

```python
zfs.is_subpath("/foo/bar/baz", "/foo/bar")  # True
zfs.is_subpath("/foo/bar", "/foo/bar/baz")  # False
```

---

### common_path

```python
common_path(*paths: Pathish) -> Path | None
```

Find common ancestor of multiple paths.

**Returns:** Common `Path` or `None` if none exists

**Examples:**

```python
zfs.common_path("/home/user/a", "/home/user/b")  # Path("/home/user")
```

---

### validate_path

```python
validate_path(
    path: Pathish,
    must_exist: bool = False,
    must_be_file: bool = False,
    must_be_dir: bool = False,
) -> Path
```

Validate path and return `Path` object.

**Parameters:**
- `path` (required): Path to validate
- `must_exist` (optional): Raise if doesn't exist
- `must_be_file` (optional): Raise if not a file
- `must_be_dir` (optional): Raise if not a directory

**Raises:** `InvalidPathError` if validation fails

**Examples:**

```python
path = zfs.validate_path("config.json", must_exist=True, must_be_file=True)
```

---

## File Permissions

### get_metadata

```python
get_metadata(path: Pathish) -> FileMetadata
```

Get extended file metadata.

**Returns:** `FileMetadata` dataclass with fields:
- `path`: Path object
- `size`: Size in bytes
- `created`: Creation datetime
- `modified`: Modification datetime
- `accessed`: Access datetime
- `is_file`, `is_dir`, `is_symlink`: Type flags
- `is_hidden`, `is_readonly`, `is_executable`: Attribute flags
- `owner`, `group`: Owner/group names (Unix only)
- `mode`: Numeric permission mode

**Examples:**

```python
meta = zfs.get_metadata("document.txt")
print(f"Size: {meta.size}, Modified: {meta.modified}")
print(f"Owner: {meta.owner}, Readonly: {meta.is_readonly}")
```

---

### set_readonly

```python
set_readonly(path: Pathish, readonly: bool = True) -> None
```

Set or clear read-only attribute.

**Platform behavior:**
- Unix: Removes/adds write permissions
- Windows: Sets/clears `FILE_ATTRIBUTE_READONLY`

---

### set_hidden

```python
set_hidden(path: Pathish, hidden: bool = True) -> None
```

Set hidden attribute (Windows only).

**Raises:** `NotImplementedError` on Unix (use `.` prefix instead)

---

### set_executable

```python
set_executable(path: Pathish, executable: bool = True) -> None
```

Set executable permission (Unix only, no-op on Windows).

---

### set_permissions

```python
set_permissions(path: Pathish, mode: int) -> None
```

Set permissions using numeric mode.

**Examples:**

```python
zfs.set_permissions("script.sh", 0o755)  # rwxr-xr-x
zfs.set_permissions("private.txt", 0o600)  # rw-------
```

---

### copy_permissions

```python
copy_permissions(src: Pathish, dst: Pathish) -> None
```

Copy permissions from source to destination.

---

### set_timestamps

```python
set_timestamps(
    path: Pathish,
    modified: datetime | None = None,
    accessed: datetime | None = None,
) -> None
```

Set file timestamps.

---

### mode_to_string / string_to_mode

```python
mode_to_string(mode: int) -> str
string_to_mode(s: str) -> int
```

Convert between numeric mode and string representation.

**Examples:**

```python
zfs.mode_to_string(0o755)  # "rwxr-xr-x"
zfs.string_to_mode("rwxr-xr-x")  # 0o755
zfs.string_to_mode("755")  # 0o755
```

---

## File Cleanup

### delete_files

```python
delete_files(paths: Iterable[Pathish]) -> dict[str, list]
```

Delete multiple files with detailed error reporting.

**Parameters:**
- `paths` (required): Iterable of file paths to delete

**Returns:** Dictionary with categorized results:
- `"succeeded"`: list of deleted path strings
- `"not_found"`: list of `(path, "File not found")` tuples
- `"not_file"`: list of `(path, "Not a file")` tuples
- `"failed"`: list of `(path, error_message)` tuples

**Examples:**

```python
result = zfs.delete_files(["old1.txt", "old2.txt", "missing.txt"])
print(f"Deleted: {len(result['succeeded'])}")
print(f"Not found: {len(result['not_found'])}")
print(f"Failed: {len(result['failed'])}")

# Delete files found by pattern
py_cache = zfs.find_files("./src", pattern="*.pyc")
zfs.delete_files(py_cache)
```

---

### delete_empty_dirs

```python
delete_empty_dirs(root: Pathish, remove_root: bool = False) -> list[Path]
```

Remove empty directories recursively (bottom-up traversal).

**Parameters:**
- `root` (required): Root directory to scan
- `remove_root` (optional): Also remove root directory if empty, default `False`

**Returns:** List of removed directory `Path` objects

**Examples:**

```python
# Clean up empty dirs after file deletion
removed = zfs.delete_empty_dirs("./output")
print(f"Removed {len(removed)} empty directories")

# Include root directory
removed = zfs.delete_empty_dirs("./temp", remove_root=True)
```

---

## File Synchronization

### copy_if_newer

```python
copy_if_newer(
    src: Pathish,
    dst: Pathish,
    create_dirs: bool = True,
) -> bool
```

Copy file only if source is newer than destination.

**Returns:** `True` if copied, `False` if skipped

---

### move_if_absent

```python
move_if_absent(
    src: Pathish,
    dst_dir: Pathish,
    create_dirs: bool = True,
    on_conflict: Literal["skip", "rename", "error"] = "skip",
) -> tuple[bool, Path | None]
```

Move file to directory if destination doesn't exist.

**Parameters:**
- `on_conflict`: Behavior when destination exists
  - `"skip"`: Don't move, return `(False, None)`
  - `"rename"`: Add suffix `_1`, `_2`, etc.
  - `"error"`: Raise `FileExistsError`

**Returns:** Tuple of `(moved: bool, final_path: Path | None)`

---

## Directory Operations

### copy_tree

```python
copy_tree(
    src: Pathish,
    dst: Pathish,
    *,
    filter_fn: Callable[[Path], bool] | None = None,
    on_conflict: Literal["overwrite", "skip", "only_if_newer"] = "overwrite",
    preserve_metadata: bool = True,
    follow_symlinks: bool = True,
) -> SyncResult
```

Recursively copy directory tree.

**Returns:** `SyncResult` with fields:
- `copied`: List of newly copied files
- `updated`: List of overwritten files
- `skipped`: List of skipped files
- `errors`: List of `(path, error_message)` tuples

**Examples:**

```python
result = zfs.copy_tree("./src", "./backup")
print(f"Copied: {len(result.copied)}, Errors: {len(result.errors)}")

# Only copy Python files
result = zfs.copy_tree(
    "./project",
    "./py_backup",
    filter_fn=lambda p: p.suffix == ".py" or p.is_dir()
)

# Smart sync
result = zfs.copy_tree("./new", "./deploy", on_conflict="only_if_newer")
```

---

### move_tree

```python
move_tree(
    src: Pathish,
    dst: Pathish,
    *,
    filter_fn: Callable[[Path], bool] | None = None,
    on_conflict: Literal["overwrite", "skip", "error"] = "error",
) -> SyncResult
```

Recursively move directory tree.

---

### sync_dirs

```python
sync_dirs(
    src: Pathish,
    dst: Pathish,
    *,
    delete_extra: bool = False,
    filter_fn: Callable[[Path], bool] | None = None,
    dry_run: bool = False,
) -> SyncResult
```

Synchronize destination with source (mirror).

**Parameters:**
- `delete_extra`: Delete files in dst not in src
- `dry_run`: Report what would happen without doing it

**Examples:**

```python
# One-way sync
result = zfs.sync_dirs("./source", "./mirror")

# Full mirror with deletion
result = zfs.sync_dirs("./source", "./mirror", delete_extra=True)

# Preview changes
result = zfs.sync_dirs("./src", "./dst", dry_run=True)
print(f"Would copy: {result.copied}, delete: {result.deleted}")
```

---

### temp_directory

```python
@contextmanager
temp_directory(
    prefix: str = "zerofilesystem_",
    suffix: str = "",
    parent: Pathish | None = None,
    cleanup: bool = True,
) -> Generator[Path, None, None]
```

Context manager for temporary directory with auto-cleanup.

**Examples:**

```python
with zfs.temp_directory() as tmp:
    (tmp / "file.txt").write_text("temporary content")
# Directory and contents deleted on exit

# Keep directory after exit
with zfs.temp_directory(cleanup=False) as tmp:
    print(f"Temp dir at: {tmp}")
```

---

### tree_size

```python
tree_size(path: Pathish, follow_symlinks: bool = False) -> int
```

Calculate total size of directory tree in bytes.

---

### tree_file_count

```python
tree_file_count(path: Pathish, follow_symlinks: bool = False) -> int
```

Count files in directory tree.

---

### flatten_tree

```python
flatten_tree(
    src: Pathish,
    dst: Pathish,
    *,
    separator: str = "_",
    on_conflict: Literal["overwrite", "skip", "rename"] = "rename",
) -> SyncResult
```

Copy all files to single flat directory.

**Examples:**

```python
# a/b/c.txt -> a_b_c.txt
zfs.flatten_tree("./nested", "./flat")
```

---

## Integrity Checking

### directory_hash

```python
directory_hash(
    path: Pathish,
    algorithm: Literal["md5", "sha1", "sha256", "sha512"] = "sha256",
    filter_fn: Callable[[Path], bool] | None = None,
) -> str
```

Calculate hash representing entire directory state.

**Examples:**

```python
# Detect any changes
before = zfs.directory_hash("./config")
make_changes()
after = zfs.directory_hash("./config")
if before != after:
    print("Configuration modified!")
```

---

### create_manifest

```python
create_manifest(
    path: Pathish,
    algorithm: Literal["md5", "sha1", "sha256", "sha512"] = "sha256",
    filter_fn: Callable[[Path], bool] | None = None,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> dict[str, ManifestEntry]
```

Create manifest of all files with hashes.

**Returns:** Dict mapping relative paths to `ManifestEntry` objects

---

### save_manifest / load_manifest

```python
save_manifest(
    manifest: dict[str, ManifestEntry],
    output_path: Pathish,
    algorithm: str = "sha256",
) -> Path

load_manifest(manifest_path: Pathish) -> tuple[dict[str, ManifestEntry], str]
```

Save/load manifest to/from JSON file.

---

### verify_manifest

```python
verify_manifest(
    directory: Pathish,
    manifest: dict[str, ManifestEntry],
    algorithm: Literal["md5", "sha1", "sha256", "sha512"] = "sha256",
    check_extra: bool = True,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> VerificationResult
```

Verify directory against manifest.

**Returns:** `VerificationResult` with:
- `valid`: Files matching manifest
- `missing`: Files in manifest but not on disk
- `extra`: Files on disk but not in manifest
- `modified`: Files with different hashes
- `errors`: Files that couldn't be checked
- `is_valid`: Property, `True` if no issues

---

### verify_file

```python
verify_file(
    path: Pathish,
    expected_hash: str,
    algorithm: Literal["md5", "sha1", "sha256", "sha512"] = "sha256",
) -> bool
```

Verify single file against expected hash.

**Raises:** `HashMismatchError` if hash doesn't match

---

### compare_directories

```python
compare_directories(
    dir1: Pathish,
    dir2: Pathish,
    algorithm: Literal["md5", "sha1", "sha256", "sha512"] = "sha256",
) -> VerificationResult
```

Compare two directories for differences.

---

### snapshot_hash

```python
snapshot_hash(
    path: Pathish,
    algorithm: Literal["md5", "sha1", "sha256", "sha512"] = "sha256",
) -> str
```

Quick hash using paths, sizes, and mtimes (no content reading).

Faster than `directory_hash` but less accurate.

---

## File Transactions

### FileTransaction

```python
class FileTransaction:
    def __init__(self, temp_dir: Pathish | None = None)
```

Pseudo-transactional file operations with atomic commit and rollback.

**Methods:**
- `write_text(path, content, encoding="utf-8")`: Schedule text write
- `write_bytes(path, content)`: Schedule binary write
- `copy_file(src, dst)`: Schedule file copy
- `delete_file(path)`: Schedule file deletion
- `commit()`: Apply all operations atomically
- `rollback()`: Discard all pending operations

**Context Manager:** Yes (auto-commits on success, rollback on exception)

**Examples:**

```python
# Context manager (recommended)
with zfs.FileTransaction() as tx:
    tx.write_text("config.json", new_config)
    tx.write_text("state.json", new_state)
    tx.delete_file("old_config.json")
# All applied atomically or all rolled back

# Manual control
tx = zfs.FileTransaction()
try:
    tx.write_text("a.txt", "content a")
    tx.copy_file("template.txt", "b.txt")
    validate_something()  # May raise
    tx.commit()
except Exception:
    tx.rollback()
    raise
```

---

## Secure Operations

### secure_delete

```python
secure_delete(
    path: Pathish,
    passes: int = 3,
    random_data: bool = True,
) -> None
```

Securely delete file by overwriting before deletion.

**Parameters:**
- `passes`: Number of overwrite passes
- `random_data`: Use random bytes (`True`) or zeros (`False`)

**Note:** Best-effort on modern SSDs. Use full-disk encryption for true security.

---

### secure_delete_directory

```python
secure_delete_directory(
    path: Pathish,
    passes: int = 3,
    random_data: bool = True,
) -> None
```

Securely delete directory and all contents.

---

### private_directory

```python
@contextmanager
private_directory(
    prefix: str = "private_",
    parent: Pathish | None = None,
    cleanup: bool = True,
    secure_cleanup: bool = False,
) -> Generator[Path, None, None]
```

Create temporary directory with restricted permissions (0o700).

**Parameters:**
- `secure_cleanup`: Use `secure_delete_directory` on cleanup

---

### create_private_file

```python
create_private_file(
    path: Pathish,
    content: bytes | None = None,
    text_content: str | None = None,
    encoding: str = "utf-8",
) -> Path
```

Create file with restricted permissions (0o600).

---

## Archive Handling

### create_tar

```python
create_tar(
    source: Pathish,
    output: Pathish,
    *,
    compression: Literal["none", "gz", "bz2", "xz"] = "none",
    filter_fn: Callable[[Path], bool] | None = None,
    base_dir: str | None = None,
) -> Path
```

Create tar archive.

**Examples:**

```python
zfs.create_tar("./project", "backup.tar")
zfs.create_tar("./data", "archive.tar.gz", compression="gz")
zfs.create_tar("./src", "code.tar.xz", compression="xz")
```

---

### create_zip

```python
create_zip(
    source: Pathish,
    output: Pathish,
    *,
    compression: Literal["stored", "deflated", "bzip2", "lzma"] = "deflated",
    filter_fn: Callable[[Path], bool] | None = None,
    base_dir: str | None = None,
) -> Path
```

Create zip archive.

---

### extract_tar / extract_zip

```python
extract_tar(
    archive: Pathish,
    destination: Pathish,
    *,
    filter_fn: Callable[[str], bool] | None = None,
    strip_components: int = 0,
) -> Path

extract_zip(
    archive: Pathish,
    destination: Pathish,
    *,
    filter_fn: Callable[[str], bool] | None = None,
    strip_components: int = 0,
) -> Path
```

Extract archive to destination.

**Parameters:**
- `filter_fn`: Filter by archive member name
- `strip_components`: Remove N leading path components

**Security:** Path traversal attacks are prevented.

---

### extract

```python
extract(archive: Pathish, destination: Pathish, **kwargs) -> Path
```

Auto-detect archive type and extract.

---

### list_archive

```python
list_archive(archive: Pathish) -> list[str]
```

List archive contents without extracting.

---

## File Watching

### FileWatcher

```python
class FileWatcher:
    def __init__(
        self,
        path: Pathish,
        *,
        recursive: bool = True,
        poll_interval: float = 1.0,
        filter_fn: Callable[[Path], bool] | None = None,
        ignore_hidden: bool = True,
    )
```

Polling-based file system watcher.

**Methods:**
- `on_created(callback)`: Register callback for file creation
- `on_modified(callback)`: Register callback for file modification
- `on_deleted(callback)`: Register callback for file deletion
- `on_any(callback)`: Register callback for any event
- `start(blocking=False)`: Start watching
- `stop()`: Stop watching

**Callback receives:** `WatchEvent` with:
- `type`: `WatchEventType.CREATED`, `MODIFIED`, or `DELETED`
- `path`: Affected `Path`
- `is_directory`: Boolean
- `timestamp`: Event time

**Examples:**

```python
def on_change(event):
    print(f"{event.type.name}: {event.path}")

watcher = zfs.FileWatcher("./watched")
watcher.on_created(on_change)
watcher.on_modified(on_change)
watcher.start()  # Non-blocking, runs in thread

# Later
watcher.stop()

# Context manager
with zfs.FileWatcher("./dir") as watcher:
    watcher.on_any(lambda e: print(e))
    time.sleep(60)
```

---

## Watcher (Fluent API)

The `Watcher` class provides a modern, fluent API for file system monitoring with extensive filtering capabilities and debouncing support.

### Watcher

```python
class Watcher:
    def __init__(self, base_dir: Pathish = ".")
```

File system watcher with fluent builder API.

**Parameters:**
- `base_dir` (optional): Directory to watch, default current directory

**Returns self for chaining on all configuration methods.**

### Event Types and WatchEvent

```python
from zerofilesystem import EventType, WatchEvent

class EventType(Enum):
    CREATED = auto()
    MODIFIED = auto()
    DELETED = auto()

@dataclass
class WatchEvent:
    type: EventType       # Event type
    path: Path            # Affected path
    is_directory: bool    # True if path is directory
    timestamp: float      # Event timestamp
```

### Pattern Methods

```python
.patterns(*patterns: str) -> Watcher
.pattern(pattern: str) -> Watcher  # Alias
.exclude(*patterns: str) -> Watcher
```

**Examples:**

```python
from zerofilesystem import Watcher

# Watch Python files
(Watcher("./src")
    .patterns("*.py")
    .on_any(lambda e: print(e))
    .start())

# Watch multiple patterns, exclude some
(Watcher("./project")
    .patterns("*.py", "*.json", "*.yaml")
    .exclude("__pycache__", "*.pyc", ".git")
    .on_modified(handle_change)
    .start())
```

### Recursion and Depth

```python
.recursive(recursive: bool = True) -> Watcher
.non_recursive() -> Watcher
.max_depth(depth: int) -> Watcher
```

### Poll Interval

```python
.poll_interval(seconds: float) -> Watcher  # Custom interval
.poll_fast() -> Watcher                     # 0.1 seconds
.poll_slow() -> Watcher                     # 5 seconds
```

**Examples:**

```python
# Fast polling for responsive detection
watcher = Watcher("./src").poll_fast().on_any(handle)

# Slow polling for low CPU usage
watcher = Watcher("./logs").poll_slow().on_any(handle)

# Custom interval
watcher = Watcher("./data").poll_interval(2.5).on_any(handle)
```

### Debouncing

Debouncing prevents multiple rapid events from triggering multiple callbacks. Only affects `MODIFIED` events - `CREATED` and `DELETED` events are always emitted immediately.

```python
.debounce(seconds: float) -> Watcher     # Debounce in seconds
.debounce_ms(milliseconds: int) -> Watcher  # Debounce in milliseconds
```

**Examples:**

```python
# Wait 500ms after last modification before emitting
(Watcher("./src")
    .patterns("*.py")
    .debounce(0.5)
    .on_modified(lambda e: print(f"File settled: {e.path}"))
    .start())

# Debounce in milliseconds
(Watcher("./config")
    .debounce_ms(200)
    .on_modified(reload_config)
    .start())
```

### Size Filters

```python
.size_min(size: int | str) -> Watcher
.size_max(size: int | str) -> Watcher
.size_between(min_size, max_size) -> Watcher
```

### Date Filters

```python
.modified_after(dt: datetime | str | timedelta) -> Watcher
.modified_before(dt: datetime | str | timedelta) -> Watcher
.modified_last_days(days: int) -> Watcher
.modified_last_hours(hours: int) -> Watcher
.created_after(dt) -> Watcher
.created_before(dt) -> Watcher
```

### Attribute Filters

```python
.hidden() -> Watcher
.not_hidden() -> Watcher
.empty() -> Watcher
.not_empty() -> Watcher
.follow_symlinks(follow: bool = True) -> Watcher
.no_symlinks() -> Watcher
```

### Type Filters

```python
.files_only() -> Watcher
.dirs_only() -> Watcher
.files_and_dirs() -> Watcher
```

### Custom Filters

```python
.filter(fn: Callable[[Path], bool]) -> Watcher
.where(fn: Callable[[Path], bool]) -> Watcher  # Alias
```

### Event Callbacks

```python
.on_created(callback: Callable[[WatchEvent], None]) -> Watcher
.on_modified(callback: Callable[[WatchEvent], None]) -> Watcher
.on_deleted(callback: Callable[[WatchEvent], None]) -> Watcher
.on_any(callback: Callable[[WatchEvent], None]) -> Watcher
.on_error(callback: Callable[[Path, Exception], None]) -> Watcher
```

**Examples:**

```python
def handle_created(event: WatchEvent):
    print(f"Created: {event.path}")

def handle_modified(event: WatchEvent):
    print(f"Modified: {event.path}")

def handle_deleted(event: WatchEvent):
    print(f"Deleted: {event.path}")

def handle_error(path: Path, error: Exception):
    print(f"Error watching {path}: {error}")

# Register callbacks
(Watcher("./src")
    .patterns("*.py")
    .on_created(handle_created)
    .on_modified(handle_modified)
    .on_deleted(handle_deleted)
    .on_error(handle_error)
    .start())

# Or use on_any for all events
(Watcher("./logs")
    .on_any(lambda e: print(f"{e.type.name}: {e.path}"))
    .start())
```

### Execution

```python
.start(blocking: bool = False) -> Watcher  # Start watching
.stop() -> Watcher                          # Stop watching

@property
def is_running(self) -> bool  # Check if running
```

**Examples:**

```python
# Non-blocking (runs in background thread)
watcher = (Watcher("./src")
    .patterns("*.py")
    .on_any(lambda e: print(e))
    .start())

# Do other work...
time.sleep(60)
watcher.stop()

# Blocking (blocks current thread)
(Watcher("./src")
    .patterns("*.py")
    .on_any(lambda e: print(e))
    .start(blocking=True))  # Blocks until stop() called from callback
```

### Context Manager

```python
with Watcher("./src").patterns("*.py").on_any(print) as w:
    print(f"Watching: {w.is_running}")
    time.sleep(60)
# Automatically stopped on exit
```

### Complete Example

```python
from zerofilesystem import Watcher, EventType, WatchEvent
import time

def on_file_change(event: WatchEvent):
    emoji = {
        EventType.CREATED: "+",
        EventType.MODIFIED: "~",
        EventType.DELETED: "-",
    }[event.type]
    print(f"[{emoji}] {event.path.name}")

# Watch Python files with debouncing
watcher = (Watcher("./project")
    .patterns("*.py", "*.pyx")
    .exclude("__pycache__", ".git", ".venv", "*.pyc")
    .recursive()
    .not_hidden()
    .size_min("1KB")
    .poll_interval(0.5)
    .debounce(0.3)
    .on_created(on_file_change)
    .on_modified(on_file_change)
    .on_deleted(on_file_change)
    .on_error(lambda p, e: print(f"Error: {e}"))
    .start())

print(f"Watching... (press Ctrl+C to stop)")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    watcher.stop()
    print("Stopped")
```

---

## Exceptions

All custom exceptions inherit from `ZeroOSError`:

```python
class ZeroOSError(Exception):
    path: Path | None
    operation: str | None
    cause: Exception | None
```

### Exception Types

- **`FileLockedError`**: File is locked by another process
- **`InvalidPathError`**: Path validation failed
- **`HashMismatchError`**: File hash doesn't match expected value
- **`IntegrityError`**: Integrity verification failed
- **`TransactionError`**: File transaction operation failed
- **`ArchiveError`**: Archive operation failed
- **`PermissionDeniedError`**: Permission denied for operation
- **`SecureDeleteError`**: Secure deletion failed
- **`SyncError`**: Directory sync operation failed
