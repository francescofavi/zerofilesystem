"""POSIX file permissions and extended metadata."""

from __future__ import annotations

import grp
import os
import pwd
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from zerofilesystem._platform import Pathish


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
    """POSIX file permissions and extended metadata."""

    @staticmethod
    def get_metadata(path: Pathish) -> FileMetadata:
        """Get extended metadata for a file or directory.

        Example:
            meta = FilePermissions.get_metadata("file.txt")
            print(f"Size: {meta.size}, Owner: {meta.owner}")
        """
        p = Path(path)
        st = p.stat()

        # uid/gid is always present on POSIX. The lookup may still fail if the
        # uid/gid is not in the local passwd db (containers / NIS down) — in
        # that case we surface the numeric id so callers always get a value.
        try:
            owner: str | None = pwd.getpwuid(st.st_uid).pw_name
            group: str | None = grp.getgrgid(st.st_gid).gr_name
        except KeyError:
            owner = str(st.st_uid)
            group = str(st.st_gid)

        return FileMetadata(
            path=p,
            size=st.st_size,
            created=datetime.fromtimestamp(st.st_ctime),
            modified=datetime.fromtimestamp(st.st_mtime),
            accessed=datetime.fromtimestamp(st.st_atime),
            is_file=p.is_file(),
            is_dir=p.is_dir(),
            is_symlink=p.is_symlink(),
            is_hidden=p.name.startswith("."),
            is_readonly=not os.access(p, os.W_OK),
            is_executable=os.access(p, os.X_OK),
            owner=owner,
            group=group,
            mode=st.st_mode,
        )

    @staticmethod
    def set_readonly(path: Pathish, readonly: bool = True) -> None:
        """Set or unset read-only by toggling write bits in the file mode."""
        p = Path(path)
        current = p.stat().st_mode
        if readonly:
            new_mode = current & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
        else:
            new_mode = current | stat.S_IWUSR
        p.chmod(new_mode)

    @staticmethod
    def set_executable(path: Pathish, executable: bool = True) -> None:
        """Set or unset the executable bit.

        When enabling, the user x-bit is always added; group and other x-bits
        are added only if their respective r-bits are already set, mirroring
        the convention used by ``chmod +x``.
        """
        p = Path(path)
        current = p.stat().st_mode

        if executable:
            new_mode = current | stat.S_IXUSR
            if current & stat.S_IRGRP:
                new_mode |= stat.S_IXGRP
            if current & stat.S_IROTH:
                new_mode |= stat.S_IXOTH
        else:
            new_mode = current & ~(stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        p.chmod(new_mode)

    @staticmethod
    def set_permissions(path: Pathish, mode: int) -> None:
        """Set file permissions using numeric mode (``0o755``, ``0o644``, ...)."""
        Path(path).chmod(mode)

    @staticmethod
    def copy_permissions(src: Pathish, dst: Pathish) -> None:
        """Copy mode bits from src to dst."""
        Path(dst).chmod(Path(src).stat().st_mode)

    @staticmethod
    def set_timestamps(
        path: Pathish,
        modified: datetime | None = None,
        accessed: datetime | None = None,
    ) -> None:
        """Set file timestamps. ``None`` keeps the current value."""
        p = Path(path)
        st = p.stat()

        atime = accessed.timestamp() if accessed else st.st_atime
        mtime = modified.timestamp() if modified else st.st_mtime

        os.utime(p, (atime, mtime))

    @staticmethod
    def mode_to_string(mode: int) -> str:
        """Convert numeric mode (``0o755``) to a string (``"rwxr-xr-x"``)."""
        # stat.filemode returns e.g. "-rwxr-xr-x"; drop the leading type char.
        return stat.filemode(mode)[1:]

    @staticmethod
    def string_to_mode(s: str) -> int:
        """Convert a mode string (``"rwxr-xr-x"`` or ``"755"``) to a numeric mode."""
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
