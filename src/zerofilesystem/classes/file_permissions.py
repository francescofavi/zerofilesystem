"""File permissions and extended metadata operations."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from zerofilesystem._platform import IS_UNIX, IS_WINDOWS, Pathish
from zerofilesystem.classes._internal import FILE_ATTRIBUTE_HIDDEN, FILE_ATTRIBUTE_READONLY
from zerofilesystem.classes.exceptions import PermissionDeniedError


@dataclass
class FileMetadata:
    """Extended file metadata."""

    path: Path
    size: int
    created: datetime
    modified: datetime
    accessed: datetime
    is_file: bool
    is_dir: bool
    is_symlink: bool
    is_hidden: bool
    is_readonly: bool
    is_executable: bool
    owner: str | None = None
    group: str | None = None
    mode: int | None = None

    def __str__(self) -> str:
        return (
            f"FileMetadata({self.path.name}, "
            f"size={self.size}, "
            f"modified={self.modified.isoformat()})"
        )


class FilePermissions:
    """File permissions and extended metadata operations."""

    @staticmethod
    def get_metadata(path: Pathish) -> FileMetadata:
        """
        Get extended metadata for a file or directory.

        Args:
            path: Path to file or directory

        Returns:
            FileMetadata object with all available information

        Example:
            meta = FilePermissions.get_metadata("file.txt")
            print(f"Size: {meta.size}, Owner: {meta.owner}")
        """
        p = Path(path)
        st = p.stat()

        # Get owner/group on Unix
        owner = None
        group = None
        if IS_UNIX:
            try:
                import grp
                import pwd

                owner = pwd.getpwuid(st.st_uid).pw_name
                group = grp.getgrgid(st.st_gid).gr_name
            except (KeyError, ImportError):
                owner = str(st.st_uid)
                group = str(st.st_gid)

        # Check if hidden
        is_hidden = p.name.startswith(".")
        if IS_WINDOWS:
            try:
                attrs = st.st_file_attributes  # type: ignore[attr-defined]
                is_hidden = bool(attrs & stat.FILE_ATTRIBUTE_HIDDEN)  # type: ignore[attr-defined]
            except AttributeError:
                pass

        # Check if readonly
        is_readonly = not os.access(p, os.W_OK)

        # Check if executable
        is_executable = os.access(p, os.X_OK)

        return FileMetadata(
            path=p,
            size=st.st_size,
            created=datetime.fromtimestamp(st.st_ctime),
            modified=datetime.fromtimestamp(st.st_mtime),
            accessed=datetime.fromtimestamp(st.st_atime),
            is_file=p.is_file(),
            is_dir=p.is_dir(),
            is_symlink=p.is_symlink(),
            is_hidden=is_hidden,
            is_readonly=is_readonly,
            is_executable=is_executable,
            owner=owner,
            group=group,
            mode=st.st_mode,
        )

    @staticmethod
    def set_readonly(path: Pathish, readonly: bool = True) -> None:
        """
        Set or unset read-only attribute.

        Args:
            path: Path to file or directory
            readonly: True to make read-only, False to make writable

        Cross-platform:
            - Unix: Removes/adds write permission
            - Windows: Sets/clears FILE_ATTRIBUTE_READONLY
        """
        p = Path(path)

        if IS_WINDOWS:
            import ctypes

            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(p))  # type: ignore[attr-defined]
            if attrs == -1:
                raise PermissionDeniedError(p, "get_attributes")

            new_attrs = (
                attrs | FILE_ATTRIBUTE_READONLY if readonly else attrs & ~FILE_ATTRIBUTE_READONLY
            )

            if not ctypes.windll.kernel32.SetFileAttributesW(str(p), new_attrs):  # type: ignore[attr-defined]
                raise PermissionDeniedError(p, "set_readonly")
        else:
            current = p.stat().st_mode
            if readonly:
                # Remove write permissions
                new_mode = current & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
            else:
                # Add user write permission
                new_mode = current | stat.S_IWUSR
            p.chmod(new_mode)

    @staticmethod
    def set_hidden(path: Pathish, hidden: bool = True) -> None:
        """
        Set or unset hidden attribute (Windows-specific, Unix uses dot prefix).

        Args:
            path: Path to file or directory
            hidden: True to hide, False to unhide

        Note:
            On Unix, hiding is done by renaming with/without dot prefix.
            This method only works on Windows for the hidden attribute.
        """
        p = Path(path)

        if IS_WINDOWS:
            import ctypes

            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(p))  # type: ignore[attr-defined]
            if attrs == -1:
                raise PermissionDeniedError(p, "get_attributes")

            new_attrs = attrs | FILE_ATTRIBUTE_HIDDEN if hidden else attrs & ~FILE_ATTRIBUTE_HIDDEN

            if not ctypes.windll.kernel32.SetFileAttributesW(str(p), new_attrs):  # type: ignore[attr-defined]
                raise PermissionDeniedError(p, "set_hidden")
        else:
            # On Unix, hiding requires renaming with '.' prefix which is destructive
            raise NotImplementedError(
                "set_hidden() is Windows-only. On Unix, rename the file with '.' prefix."
            )

    @staticmethod
    def set_executable(path: Pathish, executable: bool = True) -> None:
        """
        Set or unset executable permission (Unix-specific).

        Args:
            path: Path to file
            executable: True to make executable, False to remove

        Note:
            On Windows, executability is determined by file extension.
        """
        if IS_WINDOWS:
            return  # No-op on Windows

        p = Path(path)
        current = p.stat().st_mode

        if executable:
            # Add execute permission for owner (and group/others if readable)
            new_mode = current | stat.S_IXUSR
            if current & stat.S_IRGRP:
                new_mode |= stat.S_IXGRP
            if current & stat.S_IROTH:
                new_mode |= stat.S_IXOTH
        else:
            # Remove all execute permissions
            new_mode = current & ~(stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        p.chmod(new_mode)

    @staticmethod
    def set_permissions(path: Pathish, mode: int) -> None:
        """
        Set file permissions using numeric mode.

        Args:
            path: Path to file or directory
            mode: Numeric mode (e.g., 0o755, 0o644)

        Example:
            set_permissions("script.sh", 0o755)  # rwxr-xr-x
            set_permissions("config.txt", 0o600)  # rw-------
        """
        Path(path).chmod(mode)

    @staticmethod
    def copy_permissions(src: Pathish, dst: Pathish) -> None:
        """
        Copy permissions from source to destination.

        Args:
            src: Source file/directory
            dst: Destination file/directory
        """
        src_stat = Path(src).stat()
        Path(dst).chmod(src_stat.st_mode)

    @staticmethod
    def set_timestamps(
        path: Pathish,
        modified: datetime | None = None,
        accessed: datetime | None = None,
    ) -> None:
        """
        Set file timestamps.

        Args:
            path: Path to file
            modified: New modification time (None = keep current)
            accessed: New access time (None = keep current)
        """
        p = Path(path)
        st = p.stat()

        atime = accessed.timestamp() if accessed else st.st_atime
        mtime = modified.timestamp() if modified else st.st_mtime

        os.utime(p, (atime, mtime))

    @staticmethod
    def mode_to_string(mode: int) -> str:
        """Convert numeric mode to string representation.

        Args:
            mode: Numeric file mode

        Returns:
            String like "rwxr-xr-x"

        Example:
            mode_to_string(0o755)  # -> "rwxr-xr-x"
        """
        # Use stdlib stat.filemode() which returns e.g. "-rwxr-xr-x"
        # Strip the leading type character (-, d, l, etc.) to get just permissions
        return stat.filemode(mode)[1:]

    @staticmethod
    def string_to_mode(s: str) -> int:
        """
        Convert string representation to numeric mode.

        Args:
            s: String like "rwxr-xr-x" or "755"

        Returns:
            Numeric mode

        Example:
            string_to_mode("rwxr-xr-x")  # -> 0o755
            string_to_mode("755")  # -> 0o755
        """
        # Handle numeric string
        if s.isdigit():
            return int(s, 8)

        if len(s) != 9:
            raise ValueError(f"Invalid mode string: {s}")

        # Valid characters at each position: r at 0,3,6; w at 1,4,7; x at 2,5,8
        valid_at_position = [
            {"r", "-"},
            {"w", "-"},
            {"x", "-"},
            {"r", "-"},
            {"w", "-"},
            {"x", "-"},
            {"r", "-"},
            {"w", "-"},
            {"x", "-"},
        ]

        mode = 0
        for i, c in enumerate(s):
            if c not in valid_at_position[i]:
                raise ValueError(f"Invalid character '{c}' at position {i}")
            if c != "-":
                bit_pos = 8 - i
                mode |= 1 << bit_pos

        return mode
