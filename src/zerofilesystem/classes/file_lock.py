"""Cross-platform file locking."""

from __future__ import annotations

import contextlib
import os
import time
from pathlib import Path
from typing import Self

from zerofilesystem._platform import IS_WINDOWS, Pathish

LOCK_POLL_INTERVAL: float = 0.05


class FileLock:
    """
    Cross-platform file lock using fcntl (Unix/macOS) or msvcrt (Windows).

    Features:
    - Auto-cleanup on process crash (lock is released)
    - Optional timeout
    - Blocking or non-blocking acquisition
    - Works across processes (not just threads)

    Platform-specific:
        - Unix/macOS: Uses fcntl.flock()
        - Windows: Uses msvcrt.locking()

    Usage:
        with FileLock("/tmp/my.lock", timeout=10):
            # Critical section
            pass

    Example:
        # Blocking lock (wait forever)
        with FileLock("/tmp/my.lock"):
            do_work()

        # Non-blocking with timeout
        try:
            with FileLock("/tmp/my.lock", timeout=5):
                do_work()
        except TimeoutError:
            print("Could not acquire lock")
    """

    def __init__(self, lock_path: Pathish, timeout: float | None = None):
        """
        Initialize file lock.

        Args:
            lock_path: Path to lock file (will be created)
            timeout: Max seconds to wait for lock (None = wait forever)
        """
        self.lock_path = Path(lock_path)
        self.timeout = timeout
        self.fd: int | None = None
        self._locked = False

    def __enter__(self) -> Self:
        self.acquire()
        return self

    def __exit__(self, *_args: object) -> None:
        self.release()

    def acquire(self) -> None:
        """
        Acquire lock.

        Raises:
            TimeoutError: If timeout expires before acquiring lock
            OSError: On system errors
        """
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)

        # Open/create lock file
        self.fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o644)

        try:
            if IS_WINDOWS:  # pragma: no cover -- Windows-only, exercised by Windows CI runner
                self._acquire_windows()
            else:
                self._acquire_unix()

            self._locked = True

        except Exception:
            # Cleanup on failure
            if self.fd is not None:
                with contextlib.suppress(Exception):
                    os.close(self.fd)
                self.fd = None
            raise

    def _acquire_unix(self) -> None:
        """Acquire lock on Unix/macOS using fcntl."""
        import fcntl

        assert self.fd is not None  # Set in acquire() before calling this

        if self.timeout is None:
            # Blocking lock (wait forever)
            fcntl.flock(self.fd, fcntl.LOCK_EX)
        else:
            # Non-blocking with timeout
            start = time.time()
            while True:
                try:
                    fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError as e:
                    if time.time() - start > self.timeout:
                        raise TimeoutError(
                            f"Could not acquire lock within {self.timeout}s: {self.lock_path}"
                        ) from e
                    time.sleep(LOCK_POLL_INTERVAL)

    def _acquire_windows(
        self,
    ) -> None:  # pragma: no cover -- Windows-only, exercised by Windows CI runner
        """Acquire lock on Windows using msvcrt."""
        import msvcrt

        assert self.fd is not None  # Set in acquire() before calling this

        if self.timeout is None:
            # Blocking lock
            while True:
                try:
                    msvcrt.locking(self.fd, msvcrt.LK_NBLCK, 1)  # type: ignore[attr-defined]
                    break
                except OSError:
                    time.sleep(LOCK_POLL_INTERVAL)
        else:
            # Non-blocking with timeout
            start = time.time()
            while True:
                try:
                    msvcrt.locking(self.fd, msvcrt.LK_NBLCK, 1)  # type: ignore[attr-defined]
                    break
                except OSError as e:
                    if time.time() - start > self.timeout:
                        raise TimeoutError(
                            f"Could not acquire lock within {self.timeout}s: {self.lock_path}"
                        ) from e
                    time.sleep(LOCK_POLL_INTERVAL)

    def release(self) -> None:
        """Release lock."""
        if not self._locked or self.fd is None:
            return

        try:
            if IS_WINDOWS:  # pragma: no cover -- Windows-only, exercised by Windows CI runner
                import msvcrt

                msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined]
            else:
                import fcntl

                fcntl.flock(self.fd, fcntl.LOCK_UN)
        finally:
            with contextlib.suppress(Exception):
                os.close(self.fd)
            self.fd = None
            self._locked = False

    def __del__(self) -> None:
        """Cleanup on garbage collection."""
        if self._locked:
            with contextlib.suppress(Exception):
                self.release()
