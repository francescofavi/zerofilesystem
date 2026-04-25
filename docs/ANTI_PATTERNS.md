# Anti-patterns

## Purpose

How NOT to use `zerofilesystem`. Each entry shows a real misuse that the code does not protect you from, explains the consequence, and shows the correct alternative.

## Scope

Anti-patterns derived from explicit warnings in source docstrings, the platform-specific guards in the implementation, and the documented limits of each subsystem. Generic Python advice is intentionally omitted.

---

## 1. Using `FileLock` to coordinate threads in one process

### What it looks like

```python
import threading
from zerofilesystem import FileLock

def worker():
    with FileLock("/tmp/app.lock"):
        update_shared_state()

threading.Thread(target=worker).start()
threading.Thread(target=worker).start()
```

### Why it is wrong

`FileLock` wraps `fcntl.flock` (Unix/macOS) or `msvcrt.locking` (Windows). Both are process-level locks. Two threads inside the same process share the same file descriptor and may both succeed at acquiring the lock, defeating the mutual-exclusion intent. Worse, the underlying behavior is OS-specific and silent — there is no exception telling you the second acquire was a no-op.

### Do instead

```python
import threading
shared_lock = threading.Lock()

def worker():
    with shared_lock:
        update_shared_state()
```

Use `FileLock` only for cross-process coordination. Pair it with `threading.Lock` if you also need intra-process exclusion.

---

## 2. Treating `secure_delete` as cryptographic erasure

### What it looks like

```python
import zerofilesystem as zfs

zfs.secure_delete("private_key.pem", passes=7)
# Now safe to give the SSD to someone else, right?
```

### Why it is wrong

The `secure_delete` docstring is explicit:

> This is a best-effort secure delete. Modern SSDs with wear leveling, journaling filesystems, and OS caching may retain data copies. For true security, use full-disk encryption.

Multi-pass overwrites mean nothing on an SSD whose wear leveling has remapped the blocks behind your back, on a copy-on-write filesystem (Btrfs, APFS, ZFS) that retains old blocks until snapshot expiry, or when the OS still holds a cached copy.

### Do instead

```python
# Encrypt the filesystem (LUKS, FileVault, BitLocker) before storing the secret.
# Then just delete the file:
import os
os.unlink("private_key.pem")
```

If you cannot encrypt the volume, the only reliable erasure is physical destruction of the device.

---

## 3. Relying on `move_if_absent` for cross-process exclusivity

### What it looks like

```python
moved, dest = zfs.move_if_absent("incoming.txt", "./done", on_conflict="skip")
if moved:
    process(dest)
```

### Why it is wrong

The docstring says so explicitly:

> Not atomic! Race condition possible between exists() check and move. Use FileLock if you need atomic "move if not exists" across processes.

Two workers can both observe that `./done/incoming.txt` does not exist and both call `shutil.move`. The second one will overwrite the first.

### Do instead

```python
with zfs.FileLock("./done/.move-lock", timeout=10):
    moved, dest = zfs.move_if_absent("incoming.txt", "./done", on_conflict="skip")
    if moved:
        process(dest)
```

Or pick `on_conflict="rename"` if you want both files preserved with an automatic suffix.

---

## 4. Reusing a `FileTransaction` after commit or rollback

### What it looks like

```python
tx = zfs.FileTransaction()
tx.write_text("a.txt", "first")
tx.commit()

tx.write_text("b.txt", "second")    # Raises TransactionError
```

### Why it is wrong

`FileTransaction` is single-use. After `commit()` or `rollback()`, every subsequent call to `write_text`/`write_bytes`/`copy_file`/`delete_file`/`commit`/`rollback` raises `TransactionError("Transaction already committed")` or `"Transaction already rolled back"`. The internal temp directory has been removed and the pending list is empty.

### Do instead

```python
tx1 = zfs.FileTransaction()
tx1.write_text("a.txt", "first")
tx1.commit()

tx2 = zfs.FileTransaction()
tx2.write_text("b.txt", "second")
tx2.commit()
```

Or use one `with FileTransaction() as tx:` block per atomic group. Do not share a single transaction between threads either — the pending list is not protected by a lock.

---

## 5. Forgetting to stop a `Watcher`

### What it looks like

```python
from zerofilesystem import Watcher

Watcher("./logs").patterns("*.log").on_modified(handle).start()
# ... script keeps running ...
```

### Why it is wrong

`Watcher.start()` (with the default `blocking=False`) spawns a daemon thread that polls every `poll_interval` seconds forever. Without a reference you cannot stop it cleanly, and on long-running services the polling cost adds up. With `debounce(...)` enabled, a second daemon thread is spawned on top.

### Do instead

```python
with Watcher("./logs").patterns("*.log").on_modified(handle):
    run_main_loop()                 # Watcher stops on exit
```

Or keep the reference and call `.stop()` explicitly:

```python
w = Watcher("./logs").patterns("*.log").on_modified(handle).start()
try:
    run_main_loop()
finally:
    w.stop()
```

---

## 6. Using `poll_fast()` on a large directory tree

### What it looks like

```python
Watcher("/data").patterns("*.csv").poll_fast().on_any(handle).start()
# /data has 50000 files
```

### Why it is wrong

`Watcher` re-walks the entire tree every tick (`base_dir.rglob("*")` in `_check_changes`) and re-stats each file that matches the include/exclude rules. `poll_fast()` sets the interval to 0.1 seconds, so you pay that cost ten times per second. CPU and disk I/O climb fast on large trees.

### Do instead

```python
Watcher("/data").patterns("*.csv").poll_interval(2.0).on_any(handle).start()
```

Or scope the watcher to a smaller subdirectory. If you genuinely need real-time event notifications on a large tree, use [`watchdog`](https://pypi.org/project/watchdog/) — it binds to `inotify`/`FSEvents`/`ReadDirectoryChangesW` and pays close to zero per-tick cost.

---

## 7. Hardcoding the algorithm when verifying a manifest

### What it looks like

```python
manifest = zfs.create_manifest("./src", algorithm="sha512")
zfs.save_manifest(manifest, "src.manifest", algorithm="sha512")

# Later, somewhere else:
loaded, _algo = zfs.load_manifest("src.manifest")
result = zfs.verify_manifest("./src", loaded, algorithm="sha256")  # Wrong!
```

### Why it is wrong

`verify_manifest` recomputes hashes with the algorithm you pass it. If the manifest was created with `sha512` and you verify with `sha256`, every entry will look "modified" even on an untouched directory. The algorithm is stored in the manifest precisely so callers do not have to remember it.

### Do instead

```python
loaded, algo = zfs.load_manifest("src.manifest")
result = zfs.verify_manifest("./src", loaded, algorithm=algo)
```

---

## 8. Extracting an archive into a populated directory

### What it looks like

```python
zfs.extract("backup.zip", "./project")    # ./project already contains live files
```

### Why it is wrong

`extract_zip` and `extract_tar` open every member and write it under the destination, overwriting collisions silently. Path-traversal attempts are skipped, but ordinary collisions are not — a `config.json` in the archive will replace your live `config.json`.

### Do instead

```python
with zfs.temp_directory(prefix="extract_") as staging:
    zfs.extract("backup.zip", staging)
    # Inspect or merge staging/ into ./project deliberately
```

Or call `zfs.list_archive("backup.zip")` first and decide whether the contents are safe to land directly.
