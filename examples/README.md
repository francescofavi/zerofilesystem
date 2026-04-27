# zerofilesystem examples

Each script is self-contained and runnable from the project root:

```bash
uv run python examples/01_basic_io.py
```

A smoke test (`tests/test_examples.py`) executes every script as a subprocess and
asserts a clean exit (`0`).

| # | Script | What it shows |
|---|--------|---------------|
| 01 | `01_basic_io.py` | Read/write text and bytes; encoding and atomic writes |
| 02 | `02_json_operations.py` | JSON read/write, nested data, unicode, indentation |
| 03 | `03_file_discovery.py` | `find_files`, `walk_files`, hidden detection |
| 04 | `04_file_locking.py` | Cross-platform `FileLock` with timeout |
| 05 | `05_transactions.py` | `FileTransaction` with auto-rollback and explicit commit |
| 06 | `06_archives.py` | tar/zip create and extract |
| 07 | `07_directory_ops.py` | `copy_tree`, `move_tree`, `sync_dirs`, tree size/count |
| 08 | `08_complete_example.py` | End-to-end pipeline combining several features |
| 09 | `09_finder.py` | Fluent `Finder` builder API |
| 10 | `10_watcher.py` | Fluent `Watcher` builder API for change events |

Examples write only to `tempfile.TemporaryDirectory` paths — no project files
are touched and no environment variables are read.
