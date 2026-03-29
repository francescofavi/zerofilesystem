#!/usr/bin/env python3
"""Example: Fluent file watching with the Watcher class.

This example demonstrates:
- Basic file watching with callbacks
- Pattern filtering
- Exclusion patterns
- Debouncing for MODIFIED events
- Context manager usage
- Error handling
"""

import tempfile
import time
from pathlib import Path

from zerofilesystem import EventType, Watcher, WatchEvent


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        # Resolve to handle macOS /var -> /private/var symlink
        tmp_path = Path(tmp).resolve()

        print(f"Watching directory: {tmp_path}\n")

        # =========================================================================
        # BASIC WATCHING
        # =========================================================================

        print("=== Basic File Watching ===\n")

        events: list[WatchEvent] = []

        def record_event(event: WatchEvent) -> None:
            events.append(event)
            symbol = {
                EventType.CREATED: "+",
                EventType.MODIFIED: "~",
                EventType.DELETED: "-",
            }[event.type]
            print(f"  [{symbol}] {event.type.name}: {event.path.name}")

        watcher = (
            Watcher(tmp_path)
            .poll_interval(0.1)  # Fast polling for demo
            .on_any(record_event)
            .start()
        )

        print("Started watcher. Creating some files...")
        time.sleep(0.15)

        # Create files
        (tmp_path / "file1.txt").write_text("hello")
        time.sleep(0.15)

        (tmp_path / "file2.txt").write_text("world")
        time.sleep(0.15)

        # Modify a file
        (tmp_path / "file1.txt").write_text("hello modified")
        time.sleep(0.15)

        # Delete a file
        (tmp_path / "file2.txt").unlink()
        time.sleep(0.2)

        watcher.stop()
        print(f"\nTotal events captured: {len(events)}")

        # =========================================================================
        # PATTERN FILTERING
        # =========================================================================

        print("\n=== Pattern Filtering ===\n")

        py_events: list[WatchEvent] = []

        watcher = (
            Watcher(tmp_path)
            .patterns("*.py")
            .poll_interval(0.1)
            .on_created(lambda e: py_events.append(e))
        )

        with watcher:  # Using context manager
            print("Watching only *.py files...")
            time.sleep(0.15)

            # Create various files
            (tmp_path / "script.py").write_text("print('hello')")
            (tmp_path / "data.txt").write_text("ignored")
            (tmp_path / "config.json").write_text("{}")
            time.sleep(0.2)

        print(f"Python file events: {len(py_events)}")
        for e in py_events:
            print(f"  - {e.path.name}")

        # =========================================================================
        # EXCLUSION PATTERNS
        # =========================================================================

        print("\n=== Exclusion Patterns ===\n")

        filtered_events: list[WatchEvent] = []

        watcher = (
            Watcher(tmp_path)
            .patterns("*.py")
            .exclude("test_*", "__pycache__")
            .poll_interval(0.1)
            .on_created(lambda e: filtered_events.append(e))
        )

        with watcher:
            print("Watching *.py except test_* files...")
            time.sleep(0.15)

            (tmp_path / "main.py").write_text("# main")
            (tmp_path / "utils.py").write_text("# utils")
            (tmp_path / "test_main.py").write_text("# test (should be ignored)")
            time.sleep(0.2)

        print(f"Non-test Python events: {len(filtered_events)}")
        for e in filtered_events:
            print(f"  - {e.path.name}")

        # =========================================================================
        # DEBOUNCING
        # =========================================================================

        print("\n=== Debouncing MODIFIED Events ===\n")

        debounced_events: list[WatchEvent] = []
        test_file = tmp_path / "debounce_test.txt"
        test_file.write_text("initial")

        watcher = (
            Watcher(tmp_path)
            .patterns("*.txt")
            .debounce(0.3)  # 300ms debounce
            .poll_interval(0.05)
            .on_modified(lambda e: debounced_events.append(e))
        )

        with watcher:
            print("Rapidly modifying a file 5 times...")
            time.sleep(0.1)

            # Rapid modifications
            for i in range(5):
                test_file.write_text(f"content {i}")
                print(f"  Write {i + 1}")
                time.sleep(0.05)

            # Wait for debounce to settle
            print("Waiting for debounce to settle (500ms)...")
            time.sleep(0.5)

        print(f"\nModified events received: {len(debounced_events)}")
        print("(Should be 1 due to debouncing)")

        # =========================================================================
        # WITHOUT DEBOUNCING (COMPARISON)
        # =========================================================================

        print("\n=== Without Debouncing (Comparison) ===\n")

        no_debounce_events: list[WatchEvent] = []
        test_file2 = tmp_path / "no_debounce_test.txt"
        test_file2.write_text("initial")

        watcher = (
            Watcher(tmp_path)
            .patterns("no_debounce_test.txt")
            .poll_interval(0.05)
            .on_modified(lambda e: no_debounce_events.append(e))
        )

        with watcher:
            print("Rapidly modifying a file 5 times (no debounce)...")
            time.sleep(0.1)

            for i in range(5):
                test_file2.write_text(f"content {i}")
                time.sleep(0.08)  # Slightly longer than poll interval

            time.sleep(0.2)

        print(f"\nModified events received: {len(no_debounce_events)}")
        print("(May be multiple events without debouncing)")

        # =========================================================================
        # SIZE AND ATTRIBUTE FILTERS
        # =========================================================================

        print("\n=== Size and Attribute Filters ===\n")

        size_events: list[WatchEvent] = []

        watcher = (
            Watcher(tmp_path)
            .size_min(100)  # Only files >= 100 bytes
            .not_hidden()
            .poll_interval(0.1)
            .on_created(lambda e: size_events.append(e))
        )

        with watcher:
            print("Watching only files >= 100 bytes...")
            time.sleep(0.15)

            (tmp_path / "small.txt").write_text("x")  # < 100 bytes
            (tmp_path / "large.txt").write_text("x" * 200)  # >= 100 bytes
            (tmp_path / ".hidden.txt").write_text("x" * 200)  # hidden
            time.sleep(0.2)

        print(f"Events for large, non-hidden files: {len(size_events)}")
        for e in size_events:
            print(f"  - {e.path.name} ({e.path.stat().st_size} bytes)")

        # =========================================================================
        # ERROR HANDLING
        # =========================================================================

        print("\n=== Error Handling ===\n")

        errors: list[tuple[Path, Exception]] = []
        error_events: list[WatchEvent] = []

        def bad_callback(event: WatchEvent) -> None:
            error_events.append(event)
            raise ValueError("Intentional error in callback")

        watcher = (
            Watcher(tmp_path)
            .patterns("error_test*")
            .poll_interval(0.1)
            .on_created(bad_callback)
            .on_error(lambda p, e: errors.append((p, e)))
        )

        with watcher:
            print("Creating file with callback that raises error...")
            time.sleep(0.15)

            (tmp_path / "error_test.txt").write_text("test")
            time.sleep(0.2)

        print(f"Events processed: {len(error_events)}")
        print(f"Errors caught: {len(errors)}")
        if errors:
            print(f"  Error type: {type(errors[0][1]).__name__}")

        # =========================================================================
        # MULTIPLE CALLBACKS
        # =========================================================================

        print("\n=== Multiple Callbacks ===\n")

        created: list[str] = []
        modified: list[str] = []
        deleted: list[str] = []

        watcher = (
            Watcher(tmp_path)
            .patterns("multi_*")
            .poll_interval(0.1)
            .on_created(lambda e: created.append(e.path.name))
            .on_modified(lambda e: modified.append(e.path.name))
            .on_deleted(lambda e: deleted.append(e.path.name))
        )

        with watcher:
            print("Testing separate callbacks for each event type...")
            time.sleep(0.15)

            multi_file = tmp_path / "multi_test.txt"
            multi_file.write_text("initial")
            time.sleep(0.15)

            multi_file.write_text("modified")
            time.sleep(0.15)

            multi_file.unlink()
            time.sleep(0.2)

        print(f"Created events: {created}")
        print(f"Modified events: {modified}")
        print(f"Deleted events: {deleted}")

        # =========================================================================
        # POLL INTERVAL PRESETS
        # =========================================================================

        print("\n=== Poll Interval Configuration ===\n")

        fast_watcher = Watcher(tmp_path).poll_fast()
        print(f"poll_fast() interval: {fast_watcher._poll_interval_sec}s")

        slow_watcher = Watcher(tmp_path).poll_slow()
        print(f"poll_slow() interval: {slow_watcher._poll_interval_sec}s")

        custom_watcher = Watcher(tmp_path).poll_interval(2.5)
        print(f"poll_interval(2.5) interval: {custom_watcher._poll_interval_sec}s")

        # =========================================================================
        # MANUAL START/STOP
        # =========================================================================

        print("\n=== Manual Start/Stop ===\n")

        watcher = (
            Watcher(tmp_path)
            .patterns("manual_*")
            .poll_interval(0.1)
            .on_any(lambda e: print(f"  Event: {e.type.name} - {e.path.name}"))
        )

        print(f"Before start: is_running = {watcher.is_running}")

        watcher.start()
        print(f"After start: is_running = {watcher.is_running}")

        time.sleep(0.15)
        (tmp_path / "manual_test.txt").write_text("test")
        time.sleep(0.2)

        watcher.stop()
        print(f"After stop: is_running = {watcher.is_running}")

        print("\n=== Done! ===")


if __name__ == "__main__":
    main()
