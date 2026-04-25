"""Path normalization and management utilities."""

from __future__ import annotations

import os
from pathlib import Path

from zerofilesystem._platform import Pathish
from zerofilesystem.classes.exceptions import InvalidPathError


class PathUtils:
    """Path normalization and cross-platform path utilities."""

    @staticmethod
    def normalize(path: Pathish) -> Path:
        """
        Normalize a path by resolving . and .. components.

        Args:
            path: Path to normalize

        Returns:
            Normalized Path object

        Example:
            normalize("./foo/../bar/./baz")  # -> Path("bar/baz")
        """
        p = Path(path)
        # Use os.path.normpath to handle . and .. without resolving symlinks
        return Path(os.path.normpath(str(p)))

    @staticmethod
    def to_absolute(path: Pathish, base: Pathish | None = None) -> Path:
        """
        Convert path to absolute path.

        Args:
            path: Path to convert
            base: Base directory for relative paths (default: cwd)

        Returns:
            Absolute Path object
        """
        p = Path(path)
        if p.is_absolute():
            return p

        if base:
            return Path(base).resolve() / p
        return p.resolve()

    @staticmethod
    def to_relative(path: Pathish, base: Pathish | None = None) -> Path:
        """
        Convert path to relative path.

        Args:
            path: Path to convert
            base: Base directory (default: cwd)

        Returns:
            Relative Path object

        Raises:
            ValueError: If path cannot be made relative to base
        """
        p = Path(path).resolve()
        base_p = Path(base).resolve() if base else Path.cwd()

        try:
            return p.relative_to(base_p)
        except ValueError:
            # Path is not under base, try to compute relative path with ..
            # Find common ancestor
            try:
                # Use os.path.relpath for cross-drive handling on Windows
                rel = os.path.relpath(str(p), str(base_p))
                return Path(rel)
            except ValueError as e:
                raise ValueError(f"Cannot make {path} relative to {base}: {e}") from e

    @staticmethod
    def to_posix(path: Pathish) -> str:
        """
        Convert path to POSIX format (forward slashes).

        Args:
            path: Path to convert

        Returns:
            POSIX-style path string

        Example:
            to_posix("C:\\Users\\foo\\bar")  # -> "C:/Users/foo/bar"
        """
        return Path(path).as_posix()

    @staticmethod
    def to_native(path: Pathish) -> str:
        """
        Convert path to native OS format.

        Args:
            path: Path to convert

        Returns:
            Native path string
        """
        return str(Path(path))

    @staticmethod
    def normalize_separators(path: Pathish) -> str:
        """Normalize path separators to POSIX (replace ``\\`` with ``/``)."""
        return str(path).replace("\\", "/")

    @staticmethod
    def is_subpath(path: Pathish, parent: Pathish) -> bool:
        """
        Check if path is a subpath of parent.

        Args:
            path: Path to check
            parent: Potential parent path

        Returns:
            True if path is under parent

        Example:
            is_subpath("/foo/bar/baz", "/foo/bar")  # -> True
            is_subpath("/foo/bar", "/foo/bar/baz")  # -> False
        """
        try:
            Path(path).resolve().relative_to(Path(parent).resolve())
            return True
        except ValueError:
            return False

    @staticmethod
    def common_path(*paths: Pathish) -> Path | None:
        """
        Find the common ancestor path of multiple paths.

        Args:
            *paths: Paths to find common ancestor for

        Returns:
            Common ancestor Path, or None if no common path exists
        """
        if not paths:
            return None

        try:
            resolved = [str(Path(p).resolve()) for p in paths]
            common = os.path.commonpath(resolved)
            return Path(common)
        except ValueError:
            # No common path (e.g., different drives on Windows)
            return None

    @staticmethod
    def split_path(path: Pathish) -> list[str]:
        """
        Split path into its components.

        Args:
            path: Path to split

        Returns:
            List of path components

        Example:
            split_path("/foo/bar/baz.txt")  # -> ["/", "foo", "bar", "baz.txt"]
        """
        p = Path(path)
        parts = list(p.parts)
        return parts

    @staticmethod
    def join_path(*parts: str) -> Path:
        """
        Join path components.

        Args:
            *parts: Path components to join

        Returns:
            Joined Path
        """
        if not parts:
            return Path(".")
        return Path(*parts)

    @staticmethod
    def portable_path(path: Pathish) -> str:
        """
        Create a portable path string that works across OSes.

        Uses forward slashes and handles Windows drive letters.

        Args:
            path: Path to convert

        Returns:
            Portable path string
        """
        p = Path(path)
        posix = p.as_posix()

        # Handle Windows UNC paths
        if posix.startswith("//"):
            return posix

        return posix

    @staticmethod
    def validate_path(
        path: Pathish,
        must_exist: bool = False,
        must_be_file: bool = False,
        must_be_dir: bool = False,
    ) -> Path:
        """
        Validate a path and return it as a Path object.

        Args:
            path: Path to validate
            must_exist: Raise if path doesn't exist
            must_be_file: Raise if path is not a file
            must_be_dir: Raise if path is not a directory

        Returns:
            Validated Path object

        Raises:
            InvalidPathError: If validation fails
        """
        p = Path(path)

        if must_exist and not p.exists():
            raise InvalidPathError(path, "path does not exist", operation="validate")

        if must_be_file and p.exists() and not p.is_file():
            raise InvalidPathError(path, "path is not a file", operation="validate")

        if must_be_dir and p.exists() and not p.is_dir():
            raise InvalidPathError(path, "path is not a directory", operation="validate")

        return p

    @staticmethod
    def expand_user(path: Pathish) -> Path:
        """
        Expand ~ to user home directory.

        Args:
            path: Path potentially containing ~

        Returns:
            Expanded Path
        """
        return Path(path).expanduser()

    @staticmethod
    def expand_vars(path: Pathish) -> Path:
        """
        Expand environment variables in path.

        Args:
            path: Path with potential env vars ($VAR or %VAR%)

        Returns:
            Expanded Path
        """
        return Path(os.path.expandvars(str(path)))

    @staticmethod
    def expand(path: Pathish) -> Path:
        """
        Expand both ~ and environment variables.

        Args:
            path: Path to expand

        Returns:
            Fully expanded Path
        """
        return PathUtils.expand_user(PathUtils.expand_vars(path))
