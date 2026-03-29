"""Powerful file finder with fluent builder API."""

from __future__ import annotations

import fnmatch
import os
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta
from pathlib import Path

from zerofilesystem._platform import Pathish
from zerofilesystem.classes._internal import is_hidden as _is_hidden
from zerofilesystem.classes._internal import parse_datetime as _parse_datetime
from zerofilesystem.classes._internal import parse_size as _parse_size


class Finder:
    """
    Powerful file finder with fluent builder API.

    Example:
        # Find Python files modified in last 7 days
        files = (Finder("./src")
            .patterns("*.py")
            .modified_after(timedelta(days=7))
            .not_hidden()
            .find())

        # Find large log files
        files = (Finder("./logs")
            .patterns("*.log", "*.txt")
            .size_min("10MB")
            .size_max("1GB")
            .find())

        # Complex search
        files = (Finder("/data")
            .patterns("*.csv", "*.json")
            .exclude("*.tmp", "backup_*")
            .recursive()
            .modified_after("2024-01-01")
            .size_min("1KB")
            .not_empty()
            .max_depth(3)
            .find())
    """

    def __init__(self, base_dir: Pathish = "."):
        """
        Initialize finder with base directory.

        Args:
            base_dir: Directory to search in (default: current directory)
        """
        self._base_dir = Path(base_dir)
        self._patterns: list[str] = []
        self._exclude_patterns: list[str] = []
        self._recursive: bool = True
        self._absolute: bool = True
        self._max_results: int | None = None
        self._max_depth: int | None = None

        # Type filters
        self._files_only: bool = True
        self._dirs_only: bool = False

        # Size filters
        self._size_min: int | None = None
        self._size_max: int | None = None

        # Date filters
        self._modified_after: datetime | None = None
        self._modified_before: datetime | None = None
        self._created_after: datetime | None = None
        self._created_before: datetime | None = None
        self._accessed_after: datetime | None = None
        self._accessed_before: datetime | None = None

        # Attribute filters
        self._include_hidden: bool | None = None  # None = don't filter
        self._include_empty: bool | None = None
        self._follow_symlinks: bool = True
        self._must_be_readable: bool = False
        self._must_be_writable: bool = False
        self._must_be_executable: bool = False

        # Custom filters
        self._custom_filters: list[Callable[[Path], bool]] = []

    # =========================================================================
    # PATTERN METHODS
    # =========================================================================

    def patterns(self, *patterns: str) -> Finder:
        """
        Add glob patterns to match.

        Args:
            *patterns: Glob patterns (e.g., "*.py", "test_*.txt", "**/*.json")

        Returns:
            Self for chaining

        Examples:
            .patterns("*.py")
            .patterns("*.py", "*.pyx", "*.pyi")
            .patterns("src/**/*.py", "tests/**/*.py")
        """
        self._patterns.extend(patterns)
        return self

    def pattern(self, pattern: str) -> Finder:
        """Add single glob pattern. Alias for patterns()."""
        return self.patterns(pattern)

    def exclude(self, *patterns: str) -> Finder:
        """
        Add patterns to exclude from results.

        Args:
            *patterns: Patterns to exclude (matched against filename or path)

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

    def recursive(self, recursive: bool = True) -> Finder:
        """
        Enable/disable recursive search into subdirectories.

        Args:
            recursive: True to search subdirectories (default)

        Returns:
            Self for chaining
        """
        self._recursive = recursive
        return self

    def non_recursive(self) -> Finder:
        """Disable recursive search. Alias for recursive(False)."""
        return self.recursive(False)

    def max_depth(self, depth: int) -> Finder:
        """
        Limit search depth.

        Args:
            depth: Maximum directory depth (1 = immediate children only)

        Returns:
            Self for chaining
        """
        self._max_depth = depth
        return self

    # =========================================================================
    # SIZE FILTERS
    # =========================================================================

    def size_min(self, size: int | str) -> Finder:
        """
        Filter files >= minimum size.

        Args:
            size: Minimum size as int (bytes) or string ("1KB", "5MB", "1.5GB")

        Returns:
            Self for chaining

        Examples:
            .size_min(1024)        # 1024 bytes
            .size_min("1KB")       # 1 kilobyte
            .size_min("10MB")      # 10 megabytes
            .size_min("1.5GB")     # 1.5 gigabytes
        """
        self._size_min = _parse_size(size)
        return self

    def size_max(self, size: int | str) -> Finder:
        """
        Filter files <= maximum size.

        Args:
            size: Maximum size as int (bytes) or string

        Returns:
            Self for chaining
        """
        self._size_max = _parse_size(size)
        return self

    def size_between(self, min_size: int | str, max_size: int | str) -> Finder:
        """
        Filter files within size range.

        Args:
            min_size: Minimum size
            max_size: Maximum size

        Returns:
            Self for chaining
        """
        return self.size_min(min_size).size_max(max_size)

    # =========================================================================
    # DATE FILTERS
    # =========================================================================

    def modified_after(self, dt: datetime | str | timedelta) -> Finder:
        """
        Filter files modified after date.

        Args:
            dt: Datetime, ISO string ("2024-01-01"), or timedelta (from now)

        Returns:
            Self for chaining

        Examples:
            .modified_after("2024-01-01")
            .modified_after(datetime(2024, 6, 1))
            .modified_after(timedelta(days=7))  # Last 7 days
        """
        self._modified_after = _parse_datetime(dt)
        return self

    def modified_before(self, dt: datetime | str | timedelta) -> Finder:
        """Filter files modified before date."""
        self._modified_before = _parse_datetime(dt)
        return self

    def modified_between(
        self, after: datetime | str | timedelta, before: datetime | str | timedelta
    ) -> Finder:
        """Filter files modified within date range."""
        return self.modified_after(after).modified_before(before)

    def modified_today(self) -> Finder:
        """Filter files modified today."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.modified_after(today)

    def modified_last_days(self, days: int) -> Finder:
        """Filter files modified in last N days."""
        return self.modified_after(timedelta(days=days))

    def modified_last_hours(self, hours: int) -> Finder:
        """Filter files modified in last N hours."""
        return self.modified_after(timedelta(hours=hours))

    def created_after(self, dt: datetime | str | timedelta) -> Finder:
        """Filter files created after date."""
        self._created_after = _parse_datetime(dt)
        return self

    def created_before(self, dt: datetime | str | timedelta) -> Finder:
        """Filter files created before date."""
        self._created_before = _parse_datetime(dt)
        return self

    def accessed_after(self, dt: datetime | str | timedelta) -> Finder:
        """Filter files accessed after date."""
        self._accessed_after = _parse_datetime(dt)
        return self

    def accessed_before(self, dt: datetime | str | timedelta) -> Finder:
        """Filter files accessed before date."""
        self._accessed_before = _parse_datetime(dt)
        return self

    # =========================================================================
    # ATTRIBUTE FILTERS
    # =========================================================================

    def hidden(self) -> Finder:
        """Include only hidden files."""
        self._include_hidden = True
        return self

    def not_hidden(self) -> Finder:
        """Exclude hidden files."""
        self._include_hidden = False
        return self

    def empty(self) -> Finder:
        """Include only empty files (size = 0)."""
        self._include_empty = True
        return self

    def not_empty(self) -> Finder:
        """Exclude empty files."""
        self._include_empty = False
        return self

    def follow_symlinks(self, follow: bool = True) -> Finder:
        """Enable/disable following symbolic links."""
        self._follow_symlinks = follow
        return self

    def no_symlinks(self) -> Finder:
        """Don't follow symbolic links."""
        return self.follow_symlinks(False)

    def readable(self) -> Finder:
        """Include only readable files."""
        self._must_be_readable = True
        return self

    def writable(self) -> Finder:
        """Include only writable files."""
        self._must_be_writable = True
        return self

    def executable(self) -> Finder:
        """Include only executable files."""
        self._must_be_executable = True
        return self

    # =========================================================================
    # TYPE FILTERS
    # =========================================================================

    def files_only(self) -> Finder:
        """Include only files (default)."""
        self._files_only = True
        self._dirs_only = False
        return self

    def dirs_only(self) -> Finder:
        """Include only directories."""
        self._files_only = False
        self._dirs_only = True
        return self

    def files_and_dirs(self) -> Finder:
        """Include both files and directories."""
        self._files_only = False
        self._dirs_only = False
        return self

    # =========================================================================
    # OUTPUT OPTIONS
    # =========================================================================

    def absolute(self, absolute: bool = True) -> Finder:
        """Return absolute paths (default)."""
        self._absolute = absolute
        return self

    def relative(self) -> Finder:
        """Return relative paths."""
        return self.absolute(False)

    def limit(self, max_results: int) -> Finder:
        """
        Limit number of results.

        Args:
            max_results: Maximum number of files to return

        Returns:
            Self for chaining
        """
        self._max_results = max_results
        return self

    def first(self, n: int = 1) -> Finder:
        """Return first N results. Alias for limit()."""
        return self.limit(n)

    # =========================================================================
    # CUSTOM FILTERS
    # =========================================================================

    def filter(self, fn: Callable[[Path], bool]) -> Finder:
        """
        Add custom filter function.

        Args:
            fn: Function (Path) -> bool, return True to include

        Returns:
            Self for chaining

        Example:
            .filter(lambda p: "test" not in p.name)
            .filter(lambda p: p.stat().st_nlink == 1)  # No hardlinks
        """
        self._custom_filters.append(fn)
        return self

    def where(self, fn: Callable[[Path], bool]) -> Finder:
        """Alias for filter()."""
        return self.filter(fn)

    # =========================================================================
    # EXECUTION
    # =========================================================================

    def find(self) -> list[Path]:
        """
        Execute search and return list of matching paths.

        Returns:
            List of Path objects matching all criteria
        """
        return list(self.walk())

    def walk(self) -> Iterator[Path]:
        """
        Execute search and yield matching paths one at a time.

        Memory efficient for large result sets.

        Yields:
            Path objects matching all criteria
        """
        if not self._base_dir.is_dir():
            return

        # Default pattern if none specified
        patterns = self._patterns if self._patterns else ["*"]

        count = 0

        for path in self._enumerate_paths(patterns):
            if self._matches(path):
                yield path.resolve() if self._absolute else path

                count += 1
                if self._max_results and count >= self._max_results:
                    return

    def _enumerate_paths(self, patterns: list[str]) -> Iterator[Path]:
        """Enumerate paths matching patterns."""
        seen: set[Path] = set()

        for pattern in patterns:
            # Determine if pattern implies recursion
            use_recursive = self._recursive

            # Clean pattern for glob
            if pattern.startswith("**/"):
                clean_pattern = pattern[3:]
                use_recursive = True
            elif "**" in pattern:
                clean_pattern = pattern
                use_recursive = True
            else:
                clean_pattern = pattern

            # Use glob or rglob
            if use_recursive:
                iterator = self._base_dir.rglob(clean_pattern)
            else:
                iterator = self._base_dir.glob(clean_pattern)

            for path in iterator:
                # Deduplicate across patterns
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)

                # Check depth limit
                if self._max_depth is not None:
                    try:
                        rel = path.relative_to(self._base_dir)
                        if len(rel.parts) > self._max_depth:
                            continue
                    except ValueError:
                        continue

                yield path

    def _matches(self, path: Path) -> bool:
        """Check if path matches all filters."""
        try:
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

            # Exclude patterns
            if self._exclude_patterns:
                name = path.name
                rel_path = str(path)
                for exc_pattern in self._exclude_patterns:
                    if fnmatch.fnmatch(name, exc_pattern):
                        return False
                    if fnmatch.fnmatch(rel_path, exc_pattern):
                        return False
                    # Check if any parent matches
                    for parent in path.parents:
                        if fnmatch.fnmatch(parent.name, exc_pattern):
                            return False

            # Hidden filter
            if self._include_hidden is not None:
                is_hidden = _is_hidden(path)
                if self._include_hidden and not is_hidden:
                    return False
                if not self._include_hidden and is_hidden:
                    return False

            # Get stat once for efficiency
            stat = path.stat()

            # Size filters (only for files)
            if is_file:
                size = stat.st_size

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
            atime = datetime.fromtimestamp(stat.st_atime)

            if self._modified_after and mtime < self._modified_after:
                return False
            if self._modified_before and mtime > self._modified_before:
                return False
            if self._created_after and ctime < self._created_after:
                return False
            if self._created_before and ctime > self._created_before:
                return False
            if self._accessed_after and atime < self._accessed_after:
                return False
            if self._accessed_before and atime > self._accessed_before:
                return False

            # Permission filters
            if self._must_be_readable and not os.access(path, os.R_OK):
                return False
            if self._must_be_writable and not os.access(path, os.W_OK):
                return False
            if self._must_be_executable and not os.access(path, os.X_OK):
                return False

            # Custom filters
            return all(filter_fn(path) for filter_fn in self._custom_filters)

        except (OSError, PermissionError):
            return False

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def count(self) -> int:
        """Count matching files without building full list."""
        return sum(1 for _ in self.walk())

    def exists(self) -> bool:
        """Check if any file matches."""
        for _ in self.walk():
            return True
        return False

    def first_match(self) -> Path | None:
        """Return first matching file or None."""
        for path in self.walk():
            return path
        return None

    def __iter__(self) -> Iterator[Path]:
        """Allow direct iteration: for f in Finder(...)."""
        return self.walk()

    def __len__(self) -> int:
        """Allow len(Finder(...))."""
        return self.count()
