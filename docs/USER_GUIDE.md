# User Guide

## Purpose

Self-sufficient user-facing guide to `zerofilesystem`. A reader with no prior knowledge of the library or its internals should be able to learn what the library does, install it, and use every headline feature from this document alone.

## Scope

Covers the public, user-facing API. Does not cover contributor setup (see [DEVELOPMENT.md](DEVELOPMENT.md)), internal module layout (see [ARCHITECTURE.md](ARCHITECTURE.md)), or the full per-symbol reference (see [API_REFERENCE.md](API_REFERENCE.md)).

---

## 1. Purpose of the project

`zerofilesystem` is a library of cross-platform file system utilities for Python 3.12+. It exists to remove the boilerplate from common file-handling tasks — atomic writes, multi-file transactions, cross-platform locking, integrity verification, archive handling, filtered search, polling monitoring — and to make the safe option the default option.

The target audience is application developers who need reliable file handling on Linux, macOS, and Windows: build tools, deployment scripts, configuration managers, backup utilities, data-processing pipelines.

## 2. Strengths

- **Zero runtime dependencies.** The library uses only the Python standard library; installing it adds nothing to your dependency tree.
- **Atomic by default.** `write_text`, `write_bytes`, `write_json`, `gzip_compress`, and `gzip_decompress` use a temp-file-plus-`os.replace` pattern unless you explicitly pass `atomic=False`.
- **Multi-file transactions.** `FileTransaction` writes everything to temp files, backs up originals, then commits with `os.replace` per target. On any failure the backups are restored in reverse order.
- **One locking interface for every OS.** `FileLock` uses `fcntl.flock` on Unix/macOS and `msvcrt.locking` on Windows behind the same `with FileLock(path, timeout=…):` API.
- **Two readable APIs for the same surface.** A flat function namespace (`zfs.write_text`, `zfs.find_files`) and a `ZeroFS` facade class (`ZeroFS.write_text`) — pick whichever fits your codebase.
- **Fluent finder and watcher.** `Finder(...)` and `Watcher(...)` share the same filter vocabulary (patterns, exclusions, size, date, hidden, depth, custom predicates).
- **Path-traversal protection on archive extraction.** Both `extract_tar` and `extract_zip` verify each member resolves under the destination and silently skip ones that would escape.
- **Typed end-to-end.** Ships a `py.typed` marker, full type hints, modern `str | Path` unions via the `Pathish` alias.

## 3. Known limits and open issues

Same constraints as the README, repeated here so this document is self-sufficient.

- *limit:* `Watcher` / `FileWatcher` are polling-based — events are bounded by the poll interval (default 1.0s); there is no inotify/FSEvents backend.
- *limit:* `secure_delete` is best-effort — SSDs with wear leveling and journaling filesystems may retain copies; for true confidentiality use full-disk encryption.
- *limit:* `move_if_absent` is non-atomic — race window between `exists()` and `shutil.move`; combine with `FileLock` if multiple processes can race.
- *limit:* `copy_if_newer` uses a 1-second epsilon on `st_mtime`; sub-second updates can be missed.
- *limit:* `FilePermissions.set_hidden()` raises `NotImplementedError` on Unix.
- *limit:* archive extraction silently skips path-traversal attempts instead of raising; call `list_archive` first to inspect.
- *open:* `CHANGELOG.md` (`0.1.1`) trails `__version__` (`0.1.3`); the next release should reconcile both via release-please.
- *design:* no `async`/`await` variants — wrap in a thread executor if you need to drive operations from an event loop.

## 4. Main architectural choices (in plain language)

### Two ways to import the same thing

Every operation is exposed in two forms:

```python
# Flat function (recommended for application code)
import zerofilesystem as zfs
zfs.write_text("file.txt", "hello")

# Facade class (recommended when you want a single object to pass around)
from zerofilesystem import ZeroFS
ZeroFS.write_text("file.txt", "hello")
```

Both call the same underlying implementation. Pick one per codebase and stay consistent.

### `Pathish` everywhere

Every public function accepts `str | pathlib.Path`. You never need to wrap your strings in `Path(...)` before calling.

### Atomic writes are the default

Every write helper accepts `atomic: bool = True`. Leave it on for configuration files, manifests, and anything where a half-written file is worse than no update. Turn it off only for append-style logs where you intentionally want streaming behavior.

### Static-method classes

The implementation classes (`FileIO`, `JsonHandler`, `DirectoryOps`, `IntegrityChecker`, `SecureOps`, `ArchiveHandler`, `PathUtils`, `FilePermissions`, `FileMeta`, `FileHasher`, `FileSync`, `FileCleaner`, `FileFinder`, `FileUtils`, `GzipHandler`) are namespaces of `@staticmethod`s. You never instantiate them. The stateful classes — `FileLock`, `FileTransaction`, `Finder`, `Watcher`, `FileWatcher` — are the exceptions.

### One exception hierarchy

All custom exceptions inherit from `ZeroFSError` and carry `path`, `operation`, and `cause` attributes. Standard-library errors (`FileNotFoundError`, `PermissionError`, `TimeoutError`, `FileExistsError`) are not wrapped.

## 5. Getting started

### Install

```bash
pip install zerofilesystem
```

```bash
uv add zerofilesystem
```

### First successful use

```python
import zerofilesystem as zfs

zfs.ensure_dir("./out")
zfs.write_text("./out/hello.txt", "Hello, atomic world.")
print(zfs.read_text("./out/hello.txt"))
```

If the script prints `Hello, atomic world.`, the install is good.

## 6. Common workflows

### 6.1 Read and write text or bytes

```python
zfs.write_text("config.txt", "key=value")
text = zfs.read_text("config.txt", encoding="utf-8")

zfs.write_bytes("data.bin", b"\x00\x01\x02")
blob = zfs.read_bytes("data.bin")
```

`write_text` and `write_bytes` create parent directories by default and write atomically. Pass `atomic=False` for streaming behavior or `create_dirs=False` to require the directory to already exist.

### 6.2 Read and write JSON

```python
zfs.write_json("settings.json", {"theme": "dark", "tabs": 4}, indent=2)
settings = zfs.read_json("settings.json")
```

`write_json` is `write_text` plus `json.dumps(..., ensure_ascii=False)`. The atomic guarantee carries through.

### 6.3 Multi-file transactions

When two or more file changes must succeed together — typical for split configs or paired manifest+payload writes — wrap them in a `FileTransaction`:

```python
with zfs.FileTransaction() as tx:
    tx.write_text("config/app.json", '{"version": 3}')
    tx.write_text("config/db.json", '{"host": "localhost"}')
    tx.copy_file("templates/email.html", "out/email.html")
    tx.delete_file("config/legacy.ini")
```

The `with` block commits on a clean exit, rolls back on any exception. Explicit form:

```python
tx = zfs.FileTransaction()
try:
    tx.write_text("a.txt", "...")
    tx.write_text("b.txt", "...")
    tx.commit()
except Exception:
    tx.rollback()
    raise
```

A committed transaction refuses further operations; same for a rolled-back one.

### 6.4 Cross-platform file locking

```python
with zfs.FileLock("/tmp/myapp.lock"):
    do_critical_work()                  # Blocking — wait forever

try:
    with zfs.FileLock("/tmp/myapp.lock", timeout=5.0):
        do_critical_work()              # Non-blocking — give up after 5s
except TimeoutError:
    print("could not acquire lock")
```

The lock is held by the process, not the thread. Use `threading.Lock` for intra-process coordination.

### 6.5 Find files (flat API)

```python
py_files = zfs.find_files("./src", pattern="**/*.py")

big_logs = zfs.find_files(
    "./logs",
    pattern="*.log",
    filter_fn=lambda p: p.stat().st_size > 1024 * 1024,
    max_results=100,
)

for path in zfs.walk_files("/data", pattern="*.csv"):
    process(path)                       # Memory-efficient generator
```

### 6.6 Find files (fluent `Finder`)

```python
from zerofilesystem import Finder

files = (
    Finder("./project")
    .patterns("*.py", "*.json")
    .exclude("__pycache__", ".git", "*.pyc")
    .size_min("1KB")
    .size_max("10MB")
    .modified_last_days(7)
    .not_hidden()
    .not_empty()
    .max_depth(5)
    .limit(100)
    .find()
)

# Quick checks
count    = Finder("./src").patterns("*.py").count()
has_test = Finder("./tests").patterns("test_*.py").exists()
first    = Finder("./logs").patterns("*.log").first_match()

# Lazy iteration
for path in Finder("./logs").patterns("*.log"):
    process(path)
```

Sizes accept human strings (`"1KB"`, `"10MB"`, `"1.5GB"`). Dates accept ISO strings (`"2024-01-01"`), `datetime` objects, or `timedelta` (interpreted as "now minus delta").

### 6.7 Watch the filesystem

```python
from zerofilesystem import Watcher, EventType

watcher = (
    Watcher("./src")
    .patterns("*.py", "*.json")
    .exclude("__pycache__", ".git")
    .not_hidden()
    .poll_interval(0.5)
    .debounce(0.5)                      # Coalesce bursts of MODIFIED events
    .on_created(lambda e: print("CREATED", e.path))
    .on_modified(lambda e: print("MODIFIED", e.path))
    .on_deleted(lambda e: print("DELETED", e.path))
    .start()
)
# ... do other work ...
watcher.stop()
```

Or as a context manager:

```python
with Watcher("./config").patterns("*.yaml").on_any(reload):
    run_server()                        # Watcher stops on exit
```

The watcher polls; debounce only affects MODIFIED events. CREATED and DELETED fire immediately.

### 6.8 Verify integrity

Quick whole-tree fingerprint:

```python
fingerprint = zfs.directory_hash("./src", algorithm="sha256")
```

Manifest workflow (file-by-file verification):

```python
manifest = zfs.create_manifest("./src", algorithm="sha256")
zfs.save_manifest(manifest, "src.manifest")

# Later, possibly elsewhere
loaded, algo = zfs.load_manifest("src.manifest")
result = zfs.verify_manifest("./src", loaded, algorithm=algo)

if result.is_valid:
    print("OK")
else:
    print("missing:",  result.missing)
    print("modified:", result.modified)
    print("extra:",    result.extra)
```

Compare two trees:

```python
diff = zfs.compare_directories("./expected", "./actual", algorithm="sha256")
```

`snapshot_hash` is a fast variant that only hashes paths, sizes, and mtimes — useful for change detection where you do not need cryptographic strength.

### 6.9 Archives

```python
zfs.create_zip("./project", "backup.zip", compression="deflated")
zfs.create_tar("./data",   "archive.tar.gz", compression="gz")

zfs.extract("backup.zip",     "./restored")     # Auto-detects format
zfs.extract("archive.tar.gz", "./restored")

names = zfs.list_archive("backup.zip")
```

Both create functions accept `filter_fn` for include/exclude logic and `base_dir` to control the top-level directory inside the archive. Both extract functions accept `filter_fn` (operating on member names) and `strip_components` (drop leading path segments).

### 6.10 Directory operations

```python
result = zfs.copy_tree("./src", "./backup",
                       on_conflict="only_if_newer",
                       preserve_metadata=True)
print(f"copied={len(result.copied)} updated={len(result.updated)}")

result = zfs.sync_dirs("./source", "./mirror", delete_extra=True)

with zfs.temp_directory(prefix="work_") as tmp:
    (tmp / "scratch.txt").write_text("...")
# Directory and contents auto-deleted on exit

size  = zfs.tree_size("./build")
count = zfs.tree_file_count("./build")
```

### 6.11 Secure operations

```python
zfs.secure_delete("sensitive.txt", passes=3, random_data=True)

with zfs.private_directory(prefix="secrets_") as private:
    zfs.create_private_file(private / "token", text_content="…")
# Directory cleaned up; file had 0o600
```

Read the limits in §3 before relying on `secure_delete` for adversarial use cases.

### 6.12 Permissions and metadata

```python
meta = zfs.get_metadata("file.txt")
print(meta.size, meta.modified, meta.is_readonly)

zfs.set_readonly("config.json")
zfs.set_executable("script.sh")
zfs.set_permissions("private.key", 0o600)
zfs.copy_permissions("src.txt", "dst.txt")

print(zfs.mode_to_string(0o755))    # "rwxr-xr-x"
print(zfs.string_to_mode("rwxr-xr-x"))  # 493 (= 0o755)
```

### 6.13 Path utilities

```python
zfs.normalize_path("./a/../b/./c")          # Path("b/c")
zfs.to_absolute("file.txt")                 # Path("/cwd/file.txt")
zfs.to_relative("/var/log/app.log", base="/var")  # Path("log/app.log")
zfs.to_posix("C:\\Users\\foo")              # "C:/Users/foo"
zfs.expand_path("~/config/$APP/settings")   # Expands ~ and $APP
zfs.is_subpath("/a/b/c", "/a")              # True
zfs.common_path("/a/b", "/a/c")             # Path("/a")
zfs.validate_path("file.txt", must_exist=True, must_be_file=True)
```

## 7. Troubleshooting

These are the failure modes that the code raises explicitly.

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `TimeoutError: Could not acquire lock within Ns` | Another process holds the same `FileLock`. | Increase the `timeout=` argument or investigate the holder. |
| `FileExistsError: Destination exists: …` (from `move_if_absent`) | Destination collides and `on_conflict="error"` was passed. | Switch to `on_conflict="skip"` or `"rename"`. |
| `RuntimeError: Too many conflicting files` (from `move_if_absent` / `flatten_tree`) | More than 10000 collisions when generating `_1`, `_2`, … suffixes. | Pre-clean the destination or change the naming strategy. |
| `NotImplementedError: set_hidden() is Windows-only` | Calling `set_hidden()` on Unix. | Rename the file with a leading dot. |
| `InvalidPathError: path does not exist / is not a file / is not a directory` | `validate_path` precondition failed. | Pass the right `must_exist`, `must_be_file`, `must_be_dir` combination. |
| `HashMismatchError: Hash mismatch (sha256): expected=…, actual=…` | `verify_file` saw a different hash. | Re-fetch the file or regenerate the manifest. |
| `TransactionError: Commit failed: …` (with `rollback_success=True`) | A `commit()` failed and the transaction restored backups. | Inspect `cause` — usually permissions or disk-full. |
| `TransactionError: Transaction already committed / rolled back` | Reusing a transaction after `commit()`/`rollback()`. | Create a new `FileTransaction`. |
| `ArchiveError: Failed to create/extract … archive: …` | Underlying `tarfile`/`zipfile` raised. | Inspect `cause`; common reasons: permission denied, missing file, corrupted archive. |
| `SecureDeleteError: not a file` / `overwrite failed: …` | Target is a directory or write failed mid-pass. | Use `secure_delete_directory` for directories; check disk space and permissions. |
| `SyncError: Source is not a directory: …` | Passed a file or non-existent path to `copy_tree`/`move_tree`/`sync_dirs`. | Pass an existing directory. |
| `ValueError: Invalid size format: …` (from `Finder.size_*`) | Size string did not match the `<number><unit>` pattern. | Use `1024`, `"1KB"`, `"5MB"`, `"1.5GB"`. |
| `ValueError: Cannot parse datetime: …` (from `Finder.modified_*`) | Date string did not match any supported format. | Use ISO-8601 (`"2024-06-01"` / `"2024-06-01 14:30:00"`) or pass a `datetime` / `timedelta`. |
