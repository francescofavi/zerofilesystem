<p align="center">
  <img src="https://raw.githubusercontent.com/francescofavi/zerofilesystem/main/logo.png" alt="zerofilesystem" width="200">
</p>

# zerofilesystem

[![CI](https://img.shields.io/github/actions/workflow/status/francescofavi/zerofilesystem/ci.yml?branch=main&label=CI&cacheSeconds=0)](https://github.com/francescofavi/zerofilesystem/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/zerofilesystem.svg?cacheSeconds=0)](https://pypi.org/project/zerofilesystem/)
[![Python versions](https://img.shields.io/pypi/pyversions/zerofilesystem.svg?cacheSeconds=0)](https://pypi.org/project/zerofilesystem/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?cacheSeconds=0)](https://github.com/francescofavi/zerofilesystem/blob/main/LICENSE)
[![Status](https://img.shields.io/pypi/status/zerofilesystem.svg?cacheSeconds=0)](https://pypi.org/project/zerofilesystem/)
[![Typed](https://img.shields.io/badge/typed-PEP%20561-blue.svg?cacheSeconds=0)](https://peps.python.org/pep-0561/)
[![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen.svg?cacheSeconds=0)]()
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg?cacheSeconds=0)](https://docs.astral.sh/ruff/)

**One library for safe filesystem ops on Linux/macOS/Windows: atomic writes, transactions, file locks, finder, watcher, integrity manifests, archives. Pure stdlib, zero runtime dependencies.**

## Why zerofilesystem

Reliable file handling in Python usually means stitching together `os`, `shutil`, `pathlib`, `json`, `gzip`, `tarfile`, `zipfile`, `hashlib`, `fcntl`/`msvcrt`, `tempfile` and `secrets`, then re-deriving the same atomicity, rollback and platform glue in every project. The bugs that result are recognizable: half-written config files when a process dies, multi-file changes left in a half-applied state, and "works on Linux, breaks on Windows" tickets.

`zerofilesystem` collapses those primitives into a single, flat API where the safe behavior is the default — for Python 3.12+ projects that need predictable file I/O across Linux, macOS, and Windows.

## What you get

- **Atomic writes by default** — text, binary, and JSON writes use a temp file plus `os.replace`, so a crash never leaves a half-written file.
- **Fluent file finder** — `Finder` chains patterns, exclusions, size/date/permission filters, and depth limits into a single readable query.
- **Polling file watcher** — `Watcher` raises created/modified/deleted callbacks with debouncing, and shares the same filter vocabulary as `Finder`.
- **Multi-file transactions** — group writes, copies, and deletes under one `FileTransaction`; on error, every step rolls back.
- **One cross-platform lock** — `FileLock` exposes the same interface on Unix/macOS (`fcntl`) and Windows (`msvcrt`), with optional timeout.
- **Integrity, archives, and secure ops** — directory hashing and manifests, tar/zip create/extract with zip-slip protection, `secure_delete`, `private_directory` (0o700), `create_private_file` (0o600).

## How it works

Every public function is built only on the Python standard library and accepts both `str` and `pathlib.Path`. Atomic writes are temp file plus atomic rename. `FileTransaction` records the operations it performs and reverses them on failure. `FileLock` dispatches to `fcntl` or `msvcrt` depending on the platform. The watcher is polling-based — it trades sub-second latency for portability and zero dependencies. The package ships a `py.typed` marker for full PEP 561 typing.

## When to reach for it

- You write configuration, manifests, or deploy artifacts and cannot afford a half-written file after a crash.
- You need to commit several file changes together — and roll them all back if one fails.
- You need cross-process file locking that behaves the same on Linux, macOS, and Windows.
- You want one toolkit for search, polling watch, archives, integrity checks, secure deletion, and permission/metadata handling.
- You need a dependency-free, fully-typed library on Python 3.12+.

## Installation

```bash
pip install zerofilesystem
```

```bash
uv add zerofilesystem
```

Requires Python 3.12+. No runtime dependencies.

## Quick start

```python
import zerofilesystem as zfs

# Atomic JSON write
zfs.write_json("config/app.json", {"version": 2})

# Multi-file transaction with automatic rollback
with zfs.FileTransaction() as tx:
    tx.write_text("config/app.json", '{"version": 3}')
    tx.write_text("config/db.json", '{"host": "localhost"}')
    # Both files committed atomically on exit

# Cross-platform locking
with zfs.FileLock("/tmp/myapp.lock", timeout=5):
    # Critical section — held across processes
    ...

# Fluent file search
from zerofilesystem import Finder
recent_py = (
    Finder("./src")
    .patterns("*.py")
    .modified_last_days(7)
    .not_hidden()
    .exclude("__pycache__")
    .find()
)

# Integrity manifest
manifest = zfs.create_manifest("./src", algorithm="sha256")
zfs.save_manifest(manifest, "src.manifest")
result = zfs.verify_manifest("./src", manifest)
assert result.is_valid
```

More runnable examples in [`examples/`](https://github.com/francescofavi/zerofilesystem/tree/main/examples).

## Comparison with alternatives

The standard library provides every primitive `zerofilesystem` uses; the value is in combining them safely under one API. Third-party libraries cover individual slices.

| Library              | Atomic writes | Transactions | Cross-platform lock | Fluent finder | File watcher | Integrity manifest | Archives | Runtime deps |
|----------------------|:-------------:|:------------:|:-------------------:|:-------------:|:------------:|:------------------:|:--------:|:------------:|
| **zerofilesystem**   |       ✓       |      ✓       |          ✓          |       ✓       |   polling    |          ✓         |  tar+zip |    none      |
| `pathlib` + `shutil` (stdlib) | manual | — | — | basic glob | — | manual | tar+zip | none |
| [`filelock`](https://pypi.org/project/filelock/) | — | — | ✓ | — | — | — | — | none |
| [`portalocker`](https://pypi.org/project/portalocker/) | — | — | ✓ | — | — | — | — | none |
| [`watchdog`](https://pypi.org/project/watchdog/) | — | — | — | — | native FSEvents/inotify | — | — | yes |
| [`send2trash`](https://pypi.org/project/send2trash/) | — | — | — | — | — | — | — | varies |
| [`aiofiles`](https://pypi.org/project/aiofiles/) | — | — | — | — | — | — | — | yes |

`watchdog` is the right choice when you need real-time filesystem events; `zerofilesystem`'s `Watcher` is a polling implementation and trades latency for portability and zero dependencies.

## Known limits and open issues

These are derived from the code and are not blockers for normal use; pick the library only if they fit your scenario.

- *limit:* `Watcher` and `FileWatcher` poll the filesystem (`time.sleep(poll_interval)`) — there is no inotify/FSEvents/ReadDirectoryChangesW backend, so events are bounded by the configured poll interval (default 1.0s).
- *limit:* `secure_delete` is best-effort — modern SSDs with wear leveling, journaling filesystems, and OS-level page cache may retain copies. The docstring says so explicitly. Use full-disk encryption for true confidentiality.
- *limit:* `move_if_absent` is documented as non-atomic — there is a race window between the `exists()` check and `shutil.move()`. Use `FileLock` if you need cross-process exclusivity.
- *limit:* `copy_if_newer` uses a 1-second epsilon on `st_mtime` to tolerate filesystem timestamp granularity, so sub-second updates can be missed.
- *limit:* `FilePermissions.set_hidden()` raises `NotImplementedError` on Unix — hiding a file there requires renaming with a leading dot.
- *limit:* archive extraction silently skips members that would escape the destination (path traversal protection) instead of raising — call `list_archive` first if you need to verify contents.
- *open:* `CHANGELOG.md` currently stops at `0.1.1` while `src/zerofilesystem/__init__.py` declares `__version__ = "0.1.3"` — release-please should reconcile this on the next release.
- *design:* no `async`/`await` variants — every operation is blocking. Wrap in a thread executor if you need to drive I/O from an event loop.

A deeper, per-component breakdown lives outside the public docs.

## Anti-patterns — how NOT to use this project

A short list of misuses that the library does not protect you from.

- Do not use `FileLock` to coordinate threads inside one process — it is a process-level OS lock; use `threading.Lock` for intra-process synchronization.
- Do not call `secure_delete` and assume the data is unrecoverable on SSD or any journaling filesystem — see *Known limits*.
- Do not rely on `move_if_absent(on_conflict="skip")` for atomic "move only if missing" — combine it with `FileLock` if more than one process can race.
- Do not share one `FileTransaction` instance between threads or call `commit()` more than once — a committed/rolled-back transaction refuses further operations.
- Do not start a `Watcher` and forget about it — it spawns a daemon thread; call `.stop()` or use the `with` block.
- Do not use `Finder`/`Watcher` with `poll_fast()` (0.1s) on a tree of tens of thousands of files — every tick re-walks the tree and re-stats every match.
- Do not pass mismatched algorithms to `verify_manifest` — the manifest stores its algorithm; pass the value returned by `load_manifest` instead of hardcoding.
- Do not extract an archive into a directory that contains files you care about — extraction overwrites colliding paths without prompting.

## Running tests

```bash
uv sync
uv run pytest
```

The suite collects over 500 tests across every public module — archives, finder, watcher, file locks, transactions, JSON, path utils, basic I/O, directory ops, integrity, secure ops, permissions — and is pinned at 100% coverage in `pyproject.toml`.

## Running examples

Each script under `examples/` is self-contained and runnable:

```bash
uv run python examples/01_basic_io.py
uv run python examples/09_finder.py
uv run python examples/10_watcher.py
```

See [`examples/`](https://github.com/francescofavi/zerofilesystem/tree/main/examples) for the full list (basic I/O, JSON, discovery, locking, transactions, archives, directory ops, finder, watcher).

## Development

Contributor setup, lint/type/test commands, pre-commit hooks, commit conventions, and the release process are documented in [docs/DEVELOPMENT.md](https://github.com/francescofavi/zerofilesystem/blob/main/docs/DEVELOPMENT.md).

## Documentation map

User documentation:

- [README.md](https://github.com/francescofavi/zerofilesystem/blob/main/README.md) — this file.
- [docs/USER_GUIDE.md](https://github.com/francescofavi/zerofilesystem/blob/main/docs/USER_GUIDE.md) — extended self-sufficient user guide.
- [docs/ANTI_PATTERNS.md](https://github.com/francescofavi/zerofilesystem/blob/main/docs/ANTI_PATTERNS.md) — how NOT to use the library, with the correct alternatives.

Developer documentation:

- [docs/DEVELOPMENT.md](https://github.com/francescofavi/zerofilesystem/blob/main/docs/DEVELOPMENT.md) — contributor setup, tooling, release process.
- [docs/ARCHITECTURE.md](https://github.com/francescofavi/zerofilesystem/blob/main/docs/ARCHITECTURE.md) — modules, dependency graph, design decisions.
- [docs/API_REFERENCE.md](https://github.com/francescofavi/zerofilesystem/blob/main/docs/API_REFERENCE.md) — every public symbol, verbatim signatures.

## Contributing

This repository is maintained as a personal portfolio project. Pull requests are generally not accepted, but exceptional contributions may be considered.

For bug reports and feature requests, please use [GitHub Issues](https://github.com/francescofavi/zerofilesystem/issues).

## License

[MIT License](https://github.com/francescofavi/zerofilesystem/blob/main/LICENSE) — Copyright (c) 2025 Francesco Favi.
