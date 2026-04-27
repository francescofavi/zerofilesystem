#!/usr/bin/env python3
"""Example: File locking for concurrent access with zerofilesystem.

This example demonstrates:
- Basic file locking
- Using locks as context managers
- Timeout-based locking
- Concurrent access protection
"""

import tempfile
import threading
import time
from pathlib import Path

import zerofilesystem as zfs


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # Basic File Locking

        print("=== Basic File Locking ===\n")

        lock_file = tmp_path / "my.lock"

        # Using context manager (recommended)
        with zfs.FileLock(lock_file):
            print("Lock acquired!")
            print("Performing protected operation...")
            time.sleep(0.1)
            print("Operation complete!")

        print("Lock released!\n")

        # Manual Acquire/Release

        print("=== Manual Acquire/Release ===\n")

        lock = zfs.FileLock(lock_file)

        lock.acquire()
        print("Lock manually acquired")

        # Do some work...
        time.sleep(0.1)

        lock.release()
        print("Lock manually released\n")

        # Lock with Timeout

        print("=== Lock with Timeout ===\n")

        # Try to acquire with a timeout
        try:
            with zfs.FileLock(lock_file, timeout=1.0):
                print("Acquired lock within timeout!")
        except TimeoutError:
            print("Could not acquire lock within timeout")

        # Protecting Concurrent Access

        print("\n=== Concurrent Access Protection ===\n")

        counter_file = tmp_path / "counter.txt"
        counter_file.write_text("0")
        counter_lock = tmp_path / "counter.lock"

        errors: list[str] = []

        def increment_counter(worker_id: int, iterations: int) -> None:
            """Safely increment counter using file lock."""
            for _ in range(iterations):
                try:
                    with zfs.FileLock(counter_lock, timeout=5.0):
                        # Read current value
                        current = int(counter_file.read_text())
                        # Simulate some processing time
                        time.sleep(0.001)
                        # Write new value
                        counter_file.write_text(str(current + 1))
                except Exception as e:
                    errors.append(f"Worker {worker_id}: {e}")

        # Run multiple threads
        num_workers = 3
        iterations_per_worker = 10

        print(f"Starting {num_workers} workers, each incrementing {iterations_per_worker} times...")

        threads = [
            threading.Thread(target=increment_counter, args=(i, iterations_per_worker))
            for i in range(num_workers)
        ]

        start_time = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.time() - start_time

        final_value = int(counter_file.read_text())
        expected_value = num_workers * iterations_per_worker

        print(f"Completed in {elapsed:.2f}s")
        print(f"Final counter value: {final_value}")
        print(f"Expected value: {expected_value}")

        if errors:
            print(f"Errors: {errors}")
        else:
            print("No errors!")

        if final_value == expected_value:
            print("SUCCESS: Counter value is correct!")
        else:
            print("FAILURE: Counter value mismatch (race condition)")

        # Protecting File Writes

        print("\n=== Protecting File Writes ===\n")

        config_file = tmp_path / "config.json"
        config_lock = tmp_path / "config.lock"

        def safe_update_config(key: str, value: str) -> None:
            """Safely update config file with locking."""
            with zfs.FileLock(config_lock, timeout=5.0):
                # Read current config or create empty
                config = zfs.read_json(config_file) if config_file.exists() else {}

                # Update
                config[key] = value

                # Write back
                zfs.write_json(config_file, config)

        # Multiple updates
        safe_update_config("setting1", "value1")
        safe_update_config("setting2", "value2")
        safe_update_config("setting3", "value3")

        print(f"Final config: {zfs.read_json(config_file)}")

        # Lock File Cleanup

        print("\n=== Lock File Behavior ===\n")

        test_lock = tmp_path / "test.lock"

        print(f"Lock file exists before: {test_lock.exists()}")

        with zfs.FileLock(test_lock):
            print(f"Lock file exists during: {test_lock.exists()}")

        print(f"Lock file exists after: {test_lock.exists()}")
        print("(Lock files persist but lock is released)")

        print("\n=== Done! ===")


if __name__ == "__main__":
    main()
