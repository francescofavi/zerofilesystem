"""File system watcher with fluent builder API.

Also provides backward-compatible FileWatcher and WatchEventType aliases
(legacy API from the former file_watcher module).
"""

from __future__ import annotations

import contextlib
import fnmatch
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path

from zerofilesystem._platform import Pathish
from zerofilesystem.classes._internal import is_hidden as _is_hidden
from zerofilesystem.classes._internal import parse_datetime as _parse_datetime
from zerofilesystem.classes._internal import parse_size as _parse_size


class EventType(Enum):
    """Types of file system events."""

    CREATED = auto()
    MODIFIED = auto()
    DELETED = auto()


@dataclass
class WatchEvent:
    """A file system watch event."""

    type: EventType
    path: Path
    is_directory: bool
    timestamp: float

    def __str__(self) -> str:
        return f"WatchEvent({self.type.name}, {self.path})"


class Watcher:
    """
    File system watcher with fluent builder API.

    Example:
        # Simple watch
        (Watcher("./src")
            .patterns("*.py")
            .on_any(lambda e: print(e))
            .start())

        # Complex watch with filters
        (Watcher("./data")
            .patterns("*.csv", "*.json")
            .exclude("*.tmp", "backup_*")
            .recursive()
            .not_hidden()
            .size_min("1KB")
            .modified_after("2024-01-01")
            .poll_interval(0.5)
            .on_created(handle_new_file)
            .on_modified(handle_change)
            .on_deleted(handle_removal)
            .start())

        # As context manager
        with Watcher("./logs").patterns("*.log").on_any(print) as w:
            time.sleep(60)
    """

    def __init__(self, base_dir: Pathish = "."):
        """
        Initialize watcher with base directory.

        Args:
            base_dir: Directory to watch (default: current directory)
        """
        self._base_dir = Path(base_dir)
        self._patterns: list[str] = []
        self._exclude_patterns: list[str] = []
        self._recursive: bool = True
        self._poll_interval_sec: float = 1.0
        self._max_depth: int | None = None

        # Type filters
        self._files_only: bool = False
        self._dirs_only: bool = False

        # Size filters
        self._size_min: int | None = None
        self._size_max: int | None = None

        # Date filters (for filtering which files to watch)
        self._modified_after: datetime | None = None
        self._modified_before: datetime | None = None
        self._created_after: datetime | None = None
        self._created_before: datetime | None = None

        # Attribute filters
        self._include_hidden: bool | None = None
        self._include_empty: bool | None = None
        self._follow_symlinks: bool = True

        # Custom filters
        self._custom_filters: list[Callable[[Path], bool]] = []

        # Callbacks
        self._created_callbacks: list[Callable[[WatchEvent], None]] = []
        self._modified_callbacks: list[Callable[[WatchEvent], None]] = []
        self._deleted_callbacks: list[Callable[[WatchEvent], None]] = []
        self._any_callbacks: list[Callable[[WatchEvent], None]] = []
        self._error_callback: Callable[[Path, Exception], None] | None = None

        # Debounce settings
        self._debounce_sec: float = 0.0
        self._pending_modified: dict[Path, float] = {}  # path -> last_seen_time
        self._debounce_thread: threading.Thread | None = None

        # Runtime state
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._file_states: dict[Path, float] = {}
        self._dir_states: set[Path] = set()

    # =========================================================================
    # PATTERN METHODS
    # =========================================================================

    def patterns(self, *patterns: str) -> Watcher:
        """
        Add glob patterns to watch.

        Args:
            *patterns: Glob patterns (e.g., "*.py", "*.log")

        Returns:
            Self for chaining

        Examples:
            .patterns("*.py")
            .patterns("*.py", "*.pyx", "*.pyi")
        """
        self._patterns.extend(patterns)
        return self

    def pattern(self, pattern: str) -> Watcher:
        """Add single glob pattern. Alias for patterns()."""
        return self.patterns(pattern)

    def exclude(self, *patterns: str) -> Watcher:
        """
        Add patterns to exclude from watching.

        Args:
            *patterns: Patterns to exclude

        Returns:
            Self for chaining

        Examples:
            .exclude("__pycache__", "*.pyc")
            .exclude(".git", ".venv", "node_modules")
        """
        self._exclude_patterns.extend(patterns)
        return self

    # =========================================================================
    # RECURSION AND DEPTH
    # =========================================================================

    def recursive(self, recursive: bool = True) -> Watcher:
        """Enable/disable recursive watching of subdirectories."""
        self._recursive = recursive
        return self

    def non_recursive(self) -> Watcher:
        """Disable recursive watching."""
        return self.recursive(False)

    def max_depth(self, depth: int) -> Watcher:
        """Limit watch depth."""
        self._max_depth = depth
        return self

    # =========================================================================
    # POLL INTERVAL
    # =========================================================================

    def poll_interval(self, seconds: float) -> Watcher:
        """
        Set polling interval.

        Args:
            seconds: Interval between scans (default: 1.0)

        Returns:
            Self for chaining
        """
        self._poll_interval_sec = seconds
        return self

    def poll_fast(self) -> Watcher:
        """Set fast polling (0.1 seconds)."""
        return self.poll_interval(0.1)

    def poll_slow(self) -> Watcher:
        """Set slow polling (5 seconds)."""
        return self.poll_interval(5.0)

    # =========================================================================
    # DEBOUNCE
    # =========================================================================

    def debounce(self, seconds: float) -> Watcher:
        """
        Debounce MODIFIED events.

        Waits for a period of "silence" before emitting MODIFIED events.
        If a file is modified multiple times within the debounce window,
        only one event is emitted after the last modification.

        Args:
            seconds: Debounce delay in seconds

        Returns:
            Self for chaining

        Example:
            # Wait 500ms after last change before emitting
            .debounce(0.5)

        Note:
            Only affects MODIFIED events. CREATED and DELETED events
            are emitted immediately without debouncing.
        """
        self._debounce_sec = seconds
        return self

    def debounce_ms(self, milliseconds: int) -> Watcher:
        """Debounce MODIFIED events (milliseconds)."""
        return self.debounce(milliseconds / 1000.0)

    # =========================================================================
    # SIZE FILTERS
    # =========================================================================

    def size_min(self, size: int | str) -> Watcher:
        """Watch only files >= minimum size."""
        self._size_min = _parse_size(size)
        return self

    def size_max(self, size: int | str) -> Watcher:
        """Watch only files <= maximum size."""
        self._size_max = _parse_size(size)
        return self

    def size_between(self, min_size: int | str, max_size: int | str) -> Watcher:
        """Watch only files within size range."""
        return self.size_min(min_size).size_max(max_size)

    # =========================================================================
    # DATE FILTERS
    # =========================================================================

    def modified_after(self, dt: datetime | str | timedelta) -> Watcher:
        """Watch only files modified after date."""
        self._modified_after = _parse_datetime(dt)
        return self

    def modified_before(self, dt: datetime | str | timedelta) -> Watcher:
        """Watch only files modified before date."""
        self._modified_before = _parse_datetime(dt)
        return self

    def modified_last_days(self, days: int) -> Watcher:
        """Watch only files modified in last N days."""
        return self.modified_after(timedelta(days=days))

    def modified_last_hours(self, hours: int) -> Watcher:
        """Watch only files modified in last N hours."""
        return self.modified_after(timedelta(hours=hours))

    def created_after(self, dt: datetime | str | timedelta) -> Watcher:
        """Watch only files created after date."""
        self._created_after = _parse_datetime(dt)
        return self

    def created_before(self, dt: datetime | str | timedelta) -> Watcher:
        """Watch only files created before date."""
        self._created_before = _parse_datetime(dt)
        return self

    # =========================================================================
    # ATTRIBUTE FILTERS
    # =========================================================================

    def hidden(self) -> Watcher:
        """Watch only hidden files."""
        self._include_hidden = True
        return self

    def not_hidden(self) -> Watcher:
        """Exclude hidden files from watching."""
        self._include_hidden = False
        return self

    def empty(self) -> Watcher:
        """Watch only empty files."""
        self._include_empty = True
        return self

    def not_empty(self) -> Watcher:
        """Exclude empty files from watching."""
        self._include_empty = False
        return self

    def follow_symlinks(self, follow: bool = True) -> Watcher:
        """Enable/disable following symbolic links."""
        self._follow_symlinks = follow
        return self

    def no_symlinks(self) -> Watcher:
        """Don't follow symbolic links."""
        return self.follow_symlinks(False)

    # =========================================================================
    # TYPE FILTERS
    # =========================================================================

    def files_only(self) -> Watcher:
        """Watch only files, not directories."""
        self._files_only = True
        self._dirs_only = False
        return self

    def dirs_only(self) -> Watcher:
        """Watch only directories, not files."""
        self._files_only = False
        self._dirs_only = True
        return self

    def files_and_dirs(self) -> Watcher:
        """Watch both files and directories (default)."""
        self._files_only = False
        self._dirs_only = False
        return self

    # =========================================================================
    # CUSTOM FILTERS
    # =========================================================================

    def filter(self, fn: Callable[[Path], bool]) -> Watcher:
        """
        Add custom filter function.

        Args:
            fn: Function (Path) -> bool, return True to watch

        Returns:
            Self for chaining
        """
        self._custom_filters.append(fn)
        return self

    def where(self, fn: Callable[[Path], bool]) -> Watcher:
        """Alias for filter()."""
        return self.filter(fn)

    # =========================================================================
    # CALLBACKS
    # =========================================================================

    def on_created(self, callback: Callable[[WatchEvent], None]) -> Watcher:
        """
        Register callback for file/directory creation.

        Args:
            callback: Function to call with WatchEvent

        Returns:
            Self for chaining
        """
        self._created_callbacks.append(callback)
        return self

    def on_modified(self, callback: Callable[[WatchEvent], None]) -> Watcher:
        """
        Register callback for file modification.

        Args:
            callback: Function to call with WatchEvent

        Returns:
            Self for chaining
        """
        self._modified_callbacks.append(callback)
        return self

    def on_deleted(self, callback: Callable[[WatchEvent], None]) -> Watcher:
        """
        Register callback for file/directory deletion.

        Args:
            callback: Function to call with WatchEvent

        Returns:
            Self for chaining
        """
        self._deleted_callbacks.append(callback)
        return self

    def on_any(self, callback: Callable[[WatchEvent], None]) -> Watcher:
        """
        Register callback for any event.

        Args:
            callback: Function to call with WatchEvent

        Returns:
            Self for chaining
        """
        self._any_callbacks.append(callback)
        return self

    def on_error(self, callback: Callable[[Path, Exception], None]) -> Watcher:
        """
        Register callback for errors during watching.

        Args:
            callback: Function to call with (path, exception)

        Returns:
            Self for chaining
        """
        self._error_callback = callback
        return self

    # =========================================================================
    # EXECUTION
    # =========================================================================

    def start(self, blocking: bool = False) -> Watcher:
        """
        Start watching.

        Args:
            blocking: If True, block until stop() is called

        Returns:
            Self for chaining
        """
        if self._running:
            return self

        self._running = True
        self._scan_initial_state()

        # Start debounce thread if debouncing is enabled
        if self._debounce_sec > 0:
            self._debounce_thread = threading.Thread(target=self._debounce_loop, daemon=True)
            self._debounce_thread.start()

        if blocking:
            self._watch_loop()
        else:
            self._thread = threading.Thread(target=self._watch_loop, daemon=True)
            self._thread.start()

        return self

    def stop(self) -> Watcher:
        """
        Stop watching.

        Returns:
            Self for chaining
        """
        self._running = False
        if self._thread:
            self._thread.join(timeout=self._poll_interval_sec * 2)
            self._thread = None
        if self._debounce_thread:
            self._debounce_thread.join(timeout=self._debounce_sec * 2)
            self._debounce_thread = None
        return self

    @property
    def is_running(self) -> bool:
        """Check if watcher is running."""
        return self._running

    # =========================================================================
    # INTERNAL METHODS
    # =========================================================================

    def _matches_pattern(self, path: Path) -> bool:
        """Check if path matches any include pattern."""
        if not self._patterns:
            return True

        name = path.name
        return any(fnmatch.fnmatch(name, pattern) for pattern in self._patterns)

    def _is_excluded(self, path: Path) -> bool:
        """Check if path matches any exclude pattern."""
        if not self._exclude_patterns:
            return False

        name = path.name
        rel_path = str(path)

        for pattern in self._exclude_patterns:
            if fnmatch.fnmatch(name, pattern):
                return True
            if fnmatch.fnmatch(rel_path, pattern):
                return True
            # Check parents
            for parent in path.parents:
                if fnmatch.fnmatch(parent.name, pattern):
                    return True
        return False

    def _should_watch(self, path: Path) -> bool:
        """Check if path should be watched based on all filters."""
        try:
            # Pattern matching
            if not self._matches_pattern(path):
                return False

            # Exclusions
            if self._is_excluded(path):
                return False

            # Type filter
            is_file = path.is_file()
            is_dir = path.is_dir()

            if self._files_only and not is_file:
                return False
            if self._dirs_only and not is_dir:
                return False

            # Symlink filter
            if not self._follow_symlinks and path.is_symlink():
                return False

            # Depth filter
            if self._max_depth is not None:
                try:
                    rel = path.relative_to(self._base_dir)
                    if len(rel.parts) > self._max_depth:
                        return False
                except ValueError:
                    return False

            # Hidden filter
            if self._include_hidden is not None:
                is_hidden_file = _is_hidden(path)
                if self._include_hidden and not is_hidden_file:
                    return False
                if not self._include_hidden and is_hidden_file:
                    return False

            # For files, check size and date filters
            if is_file:
                stat = path.stat()
                size = stat.st_size

                # Size filters
                if self._size_min is not None and size < self._size_min:
                    return False
                if self._size_max is not None and size > self._size_max:
                    return False

                # Empty filter
                if self._include_empty is not None:
                    is_empty = size == 0
                    if self._include_empty and not is_empty:
                        return False
                    if not self._include_empty and is_empty:
                        return False

                # Date filters
                mtime = datetime.fromtimestamp(stat.st_mtime)
                ctime = datetime.fromtimestamp(stat.st_ctime)

                if self._modified_after and mtime < self._modified_after:
                    return False
                if self._modified_before and mtime > self._modified_before:
                    return False
                if self._created_after and ctime < self._created_after:
                    return False
                if self._created_before and ctime > self._created_before:
                    return False

            # Custom filters
            return all(filter_fn(path) for filter_fn in self._custom_filters)

        except (OSError, PermissionError):
            return False

    def _scan_initial_state(self) -> None:
        """Scan initial file state."""
        with self._lock:
            self._file_states.clear()
            self._dir_states.clear()

            if not self._base_dir.exists():
                return

            for item in self._enumerate_items():
                self._record_item(item)

    def _enumerate_items(self) -> Iterator[Path]:
        """Enumerate items in watched directory."""
        if not self._base_dir.exists():
            return

        if self._recursive:
            yield from self._base_dir.rglob("*")
        else:
            yield from self._base_dir.iterdir()

    def _record_item(self, path: Path) -> None:
        """Record item in state."""
        if not self._should_watch(path):
            return

        try:
            if path.is_file():
                self._file_states[path] = path.stat().st_mtime
            elif path.is_dir():
                self._dir_states.add(path)
        except OSError:
            pass

    def _watch_loop(self) -> None:
        """Main watch loop."""
        while self._running:
            try:
                self._check_changes()
            except Exception as e:
                if self._error_callback:
                    self._error_callback(self._base_dir, e)

            time.sleep(self._poll_interval_sec)

    def _check_changes(self) -> None:
        """Check for file system changes."""
        current_files: dict[Path, float] = {}
        current_dirs: set[Path] = set()

        if not self._base_dir.exists():
            # Directory deleted - report all as deleted
            with self._lock:
                for path in list(self._file_states.keys()):
                    self._emit_event(EventType.DELETED, path, is_dir=False)
                for path in list(self._dir_states):
                    self._emit_event(EventType.DELETED, path, is_dir=True)
                self._file_states.clear()
                self._dir_states.clear()
            return

        # Scan current state
        for item in self._enumerate_items():
            if not self._should_watch(item):
                continue

            try:
                if item.is_file():
                    current_files[item] = item.stat().st_mtime
                elif item.is_dir():
                    current_dirs.add(item)
            except OSError:
                pass

        with self._lock:
            # Check for created/modified files
            for path, mtime in current_files.items():
                if path not in self._file_states:
                    self._emit_event(EventType.CREATED, path, is_dir=False)
                elif self._file_states[path] != mtime:
                    self._emit_event(EventType.MODIFIED, path, is_dir=False)

            # Check for deleted files
            for path in self._file_states:
                if path not in current_files:
                    self._emit_event(EventType.DELETED, path, is_dir=False)

            # Check for created directories
            for path in current_dirs:
                if path not in self._dir_states:
                    self._emit_event(EventType.CREATED, path, is_dir=True)

            # Check for deleted directories
            for path in self._dir_states:
                if path not in current_dirs:
                    self._emit_event(EventType.DELETED, path, is_dir=True)

            # Update state
            self._file_states = current_files
            self._dir_states = current_dirs

    def _emit_event(
        self,
        event_type: EventType,
        path: Path,
        is_dir: bool,
    ) -> None:
        """Emit an event to callbacks."""
        # Debounce MODIFIED events for files (not directories)
        if event_type == EventType.MODIFIED and not is_dir and self._debounce_sec > 0:
            self._pending_modified[path] = time.time()
            return

        self._emit_event_now(event_type, path, is_dir)

    def _emit_event_now(
        self,
        event_type: EventType,
        path: Path,
        is_dir: bool,
    ) -> None:
        """Emit an event immediately to callbacks."""
        event = WatchEvent(
            type=event_type,
            path=path,
            is_directory=is_dir,
            timestamp=time.time(),
        )

        # Call specific callbacks
        callbacks: list[Callable[[WatchEvent], None]] = []
        if event_type == EventType.CREATED:
            callbacks = self._created_callbacks
        elif event_type == EventType.MODIFIED:
            callbacks = self._modified_callbacks
        elif event_type == EventType.DELETED:
            callbacks = self._deleted_callbacks

        for cb in callbacks:
            try:
                cb(event)
            except Exception as e:
                if self._error_callback:
                    self._error_callback(path, e)

        # Call any callbacks
        for cb in self._any_callbacks:
            try:
                cb(event)
            except Exception as e:
                if self._error_callback:
                    self._error_callback(path, e)

    def _debounce_loop(self) -> None:
        """Background loop to emit debounced MODIFIED events."""
        check_interval = min(self._debounce_sec / 4, 0.1)

        while self._running:
            now = time.time()
            to_emit: list[Path] = []

            with self._lock:
                for path, last_seen in list(self._pending_modified.items()):
                    if now - last_seen >= self._debounce_sec:
                        to_emit.append(path)
                        del self._pending_modified[path]

            # Emit outside the lock
            for path in to_emit:
                self._emit_event_now(EventType.MODIFIED, path, is_dir=False)

            time.sleep(check_interval)

    # =========================================================================
    # CONTEXT MANAGER
    # =========================================================================

    def __enter__(self) -> Watcher:
        self.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.stop()


# =============================================================================
# LEGACY BACKWARD-COMPATIBLE API (from former file_watcher module)
# =============================================================================

# Alias for legacy code that imported WatchEventType
WatchEventType = EventType


class FileWatcher:
    """Legacy file system watcher using polling.

    Prefer the modern Watcher class with fluent builder API.
    This class is kept for backward compatibility.
    """

    def __init__(
        self,
        path: Pathish,
        *,
        recursive: bool = True,
        poll_interval: float = 1.0,
        filter_fn: Callable[[Path], bool] | None = None,
        ignore_hidden: bool = True,
    ):
        self._path = Path(path)
        self._recursive = recursive
        self._poll_interval = poll_interval
        self._filter_fn = filter_fn
        self._ignore_hidden = ignore_hidden

        self._created_callbacks: list[Callable[[WatchEvent], None]] = []
        self._modified_callbacks: list[Callable[[WatchEvent], None]] = []
        self._deleted_callbacks: list[Callable[[WatchEvent], None]] = []
        self._any_callbacks: list[Callable[[WatchEvent], None]] = []

        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

        self._file_states: dict[Path, float] = {}
        self._dir_states: set[Path] = set()

    def on_created(self, callback: Callable[[WatchEvent], None]) -> FileWatcher:
        self._created_callbacks.append(callback)
        return self

    def on_modified(self, callback: Callable[[WatchEvent], None]) -> FileWatcher:
        self._modified_callbacks.append(callback)
        return self

    def on_deleted(self, callback: Callable[[WatchEvent], None]) -> FileWatcher:
        self._deleted_callbacks.append(callback)
        return self

    def on_any(self, callback: Callable[[WatchEvent], None]) -> FileWatcher:
        self._any_callbacks.append(callback)
        return self

    def start(self, blocking: bool = False) -> None:
        if self._running:
            return

        self._running = True
        self._scan_initial_state()

        if blocking:
            self._watch_loop()
        else:
            self._thread = threading.Thread(target=self._watch_loop, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=self._poll_interval * 2)
            self._thread = None

    def _should_watch(self, path: Path) -> bool:
        if self._ignore_hidden and path.name.startswith("."):
            return False
        return not (self._filter_fn and not self._filter_fn(path))

    def _scan_initial_state(self) -> None:
        with self._lock:
            self._file_states.clear()
            self._dir_states.clear()

            if not self._path.exists():
                return

            if self._recursive:
                for item in self._path.rglob("*"):
                    self._record_item(item)
            else:
                for item in self._path.iterdir():
                    self._record_item(item)

    def _record_item(self, path: Path) -> None:
        if not self._should_watch(path):
            return
        try:
            if path.is_file():
                self._file_states[path] = path.stat().st_mtime
            elif path.is_dir():
                self._dir_states.add(path)
        except OSError:
            pass

    def _watch_loop(self) -> None:
        while self._running:
            with contextlib.suppress(Exception):
                self._check_changes()
            time.sleep(self._poll_interval)

    def _check_changes(self) -> None:
        current_files: dict[Path, float] = {}
        current_dirs: set[Path] = set()

        if not self._path.exists():
            with self._lock:
                for path in list(self._file_states.keys()):
                    self._emit_event(EventType.DELETED, path, is_dir=False)
                for path in list(self._dir_states):
                    self._emit_event(EventType.DELETED, path, is_dir=True)
                self._file_states.clear()
                self._dir_states.clear()
            return

        items = self._path.rglob("*") if self._recursive else self._path.iterdir()

        for item in items:
            if not self._should_watch(item):
                continue
            try:
                if item.is_file():
                    current_files[item] = item.stat().st_mtime
                elif item.is_dir():
                    current_dirs.add(item)
            except OSError:
                pass

        with self._lock:
            for path, mtime in current_files.items():
                if path not in self._file_states:
                    self._emit_event(EventType.CREATED, path, is_dir=False)
                elif self._file_states[path] != mtime:
                    self._emit_event(EventType.MODIFIED, path, is_dir=False)

            for path in self._file_states:
                if path not in current_files:
                    self._emit_event(EventType.DELETED, path, is_dir=False)

            for path in current_dirs:
                if path not in self._dir_states:
                    self._emit_event(EventType.CREATED, path, is_dir=True)

            for path in self._dir_states:
                if path not in current_dirs:
                    self._emit_event(EventType.DELETED, path, is_dir=True)

            self._file_states = current_files
            self._dir_states = current_dirs

    def _emit_event(
        self,
        event_type: EventType,
        path: Path,
        is_dir: bool,
    ) -> None:
        event = WatchEvent(
            type=event_type,
            path=path,
            is_directory=is_dir,
            timestamp=time.time(),
        )

        if event_type == EventType.CREATED:
            for cb in self._created_callbacks:
                with contextlib.suppress(Exception):
                    cb(event)
        elif event_type == EventType.MODIFIED:
            for cb in self._modified_callbacks:
                with contextlib.suppress(Exception):
                    cb(event)
        elif event_type == EventType.DELETED:
            for cb in self._deleted_callbacks:
                with contextlib.suppress(Exception):
                    cb(event)

        for cb in self._any_callbacks:
            with contextlib.suppress(Exception):
                cb(event)

    @property
    def is_running(self) -> bool:
        return self._running

    def __enter__(self) -> FileWatcher:
        self.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.stop()
