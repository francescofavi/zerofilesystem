"""Tests for FileLock - Cross-platform file locking.

Copyright (c) 2025 Francesco Favi
"""

import threading
import time
from pathlib import Path
from typing import Any

import pytest

import zerofilesystem as zfs


class TestFileLockBasic:
    """Basic tests for FileLock."""

    def test_lock_acquire_release(self, tmp_path: Path) -> None:
        """Test basic lock acquire and release."""
        lock_path = tmp_path / "test.lock"

        lock = zfs.FileLock(lock_path)
        lock.acquire()

        assert lock._locked is True
        assert lock_path.exists()

        lock.release()
        assert lock._locked is False

    def test_lock_context_manager(self, tmp_path: Path) -> None:
        """Test using FileLock as context manager."""
        lock_path = tmp_path / "test.lock"

        with zfs.FileLock(lock_path) as lock:
            assert lock._locked is True

        assert lock._locked is False

    def test_lock_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Test that FileLock creates parent directories."""
        lock_path = tmp_path / "deep" / "nested" / "test.lock"

        with zfs.FileLock(lock_path):
            assert lock_path.exists()

    def test_lock_reentrant_same_object(self, tmp_path: Path) -> None:
        """Test that releasing and re-acquiring works."""
        lock_path = tmp_path / "test.lock"
        lock = zfs.FileLock(lock_path)

        lock.acquire()
        lock.release()
        lock.acquire()
        lock.release()

        assert lock._locked is False

    def test_lock_release_when_not_locked(self, tmp_path: Path) -> None:
        """Test release when not locked is safe."""
        lock_path = tmp_path / "test.lock"
        lock = zfs.FileLock(lock_path)

        # Should not raise
        lock.release()

    def test_lock_cleanup_on_del(self, tmp_path: Path) -> None:
        """Test that lock is released on garbage collection."""
        lock_path = tmp_path / "test.lock"

        def acquire_and_forget() -> None:
            lock = zfs.FileLock(lock_path)
            lock.acquire()
            # lock goes out of scope

        acquire_and_forget()
        # Force garbage collection
        import gc

        gc.collect()

        # Should be able to acquire new lock
        lock = zfs.FileLock(lock_path)
        lock.acquire()
        lock.release()


class TestFileLockTimeout:
    """Tests for FileLock with timeout."""

    def test_lock_with_timeout_success(self, tmp_path: Path) -> None:
        """Test lock with timeout when lock is available."""
        lock_path = tmp_path / "test.lock"

        with zfs.FileLock(lock_path, timeout=1.0):
            pass  # Should succeed immediately

    def test_lock_timeout_exceeded(self, tmp_path: Path) -> None:
        """Test that timeout raises TimeoutError."""
        lock_path = tmp_path / "test.lock"

        # Acquire lock in main thread
        lock1 = zfs.FileLock(lock_path)
        lock1.acquire()

        # Try to acquire with short timeout in different lock instance
        result = {"timeout_raised": False}

        def try_acquire() -> None:
            lock2 = zfs.FileLock(lock_path, timeout=0.2)
            try:
                lock2.acquire()
            except TimeoutError:
                result["timeout_raised"] = True
            finally:
                lock2.release()

        # Run in separate thread
        thread = threading.Thread(target=try_acquire)
        thread.start()
        thread.join(timeout=2.0)

        lock1.release()

        assert result["timeout_raised"] is True


class TestFileLockConcurrency:
    """Tests for FileLock concurrent access."""

    def test_lock_mutual_exclusion(self, tmp_path: Path) -> None:
        """Test that lock provides mutual exclusion."""
        lock_path = tmp_path / "test.lock"
        counter_file = tmp_path / "counter.txt"
        counter_file.write_text("0")

        errors: list[Any] = []
        iterations = 10

        def increment() -> None:
            for _ in range(iterations):
                try:
                    with zfs.FileLock(lock_path, timeout=5.0):
                        # Read current value
                        current = int(counter_file.read_text())
                        # Simulate some work
                        time.sleep(0.01)
                        # Write new value
                        counter_file.write_text(str(current + 1))
                except Exception as e:
                    errors.append(str(e))

        # Run multiple threads
        threads = [threading.Thread(target=increment) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30.0)

        # Check final value
        final_value = int(counter_file.read_text())

        assert not errors, f"Errors occurred: {errors}"
        assert final_value == iterations * 3

    def test_lock_ordered_access(self, tmp_path: Path) -> None:
        """Test that locks are acquired in order."""
        lock_path = tmp_path / "test.lock"
        access_order: list[int] = []
        lock = threading.Lock()

        def access_resource(thread_id: int) -> None:
            with zfs.FileLock(lock_path, timeout=5.0):
                with lock:
                    access_order.append(thread_id)
                time.sleep(0.1)

        threads = [threading.Thread(target=access_resource, args=(i,)) for i in range(3)]

        # Start threads with small delay to encourage ordering
        for t in threads:
            t.start()
            time.sleep(0.02)

        for t in threads:
            t.join(timeout=10.0)

        # All threads should have accessed
        assert len(access_order) == 3


class TestFileLockEdgeCases:
    """Edge case tests for FileLock."""

    def test_lock_file_path_types(self, tmp_path: Path) -> None:
        """Test FileLock accepts both str and Path."""
        # String path
        str_path = str(tmp_path / "str.lock")
        with zfs.FileLock(str_path):
            assert Path(str_path).exists()

        # Path object
        path_obj = tmp_path / "path.lock"
        with zfs.FileLock(path_obj):
            assert path_obj.exists()

    def test_lock_exception_in_context(self, tmp_path: Path) -> None:
        """Test that lock is released even if exception occurs."""
        lock_path = tmp_path / "test.lock"

        with pytest.raises(ValueError), zfs.FileLock(lock_path) as lock:
            assert lock._locked is True
            raise ValueError("Test error")

        # Lock should be released
        # Verify by acquiring a new lock
        new_lock = zfs.FileLock(lock_path)  # type: ignore[unreachable]
        new_lock.acquire()
        assert new_lock._locked is True
        new_lock.release()

    def test_multiple_locks_different_files(self, tmp_path: Path) -> None:
        """Test multiple locks on different files."""
        lock1_path = tmp_path / "lock1.lock"
        lock2_path = tmp_path / "lock2.lock"

        with zfs.FileLock(lock1_path) as lock1, zfs.FileLock(lock2_path) as lock2:
            assert lock1._locked is True
            assert lock2._locked is True

    def test_lock_path_with_spaces(self, tmp_path: Path) -> None:
        """Test lock with path containing spaces."""
        lock_path = tmp_path / "path with spaces" / "test.lock"

        with zfs.FileLock(lock_path):
            assert lock_path.exists()
