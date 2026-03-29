"""Shared internal utilities for zerofilesystem classes.

Not part of the public API. Used by finder.py, watcher.py, and other modules
to avoid code duplication.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from zerofilesystem._platform import IS_WINDOWS

# =============================================================================
# SHARED CONSTANTS
# =============================================================================

FILE_ATTRIBUTE_HIDDEN: int = 0x2
FILE_ATTRIBUTE_READONLY: int = 0x1

MAX_RENAME_CONFLICTS: int = 10000

HASH_CHUNK_SIZE: int = 1024 * 1024  # 1 MB

# Size unit multipliers (bytes)
SIZE_UNITS: dict[str, int] = {
    "B": 1,
    "KB": 1024,
    "MB": 1024 * 1024,
    "GB": 1024 * 1024 * 1024,
    "TB": 1024 * 1024 * 1024 * 1024,
    "K": 1024,
    "M": 1024 * 1024,
    "G": 1024 * 1024 * 1024,
    "T": 1024 * 1024 * 1024 * 1024,
}


# =============================================================================
# SHARED FUNCTIONS
# =============================================================================


def parse_size(size: int | str) -> int:
    """Parse size string like '1KB', '5MB', '1.5GB' to bytes."""
    if isinstance(size, int):
        return size

    size = size.strip().upper()

    match = re.match(r"^([\d.]+)\s*([A-Z]*B?)$", size)
    if not match:
        raise ValueError(f"Invalid size format: {size}")

    value = float(match.group(1))
    unit = match.group(2) or "B"

    if unit not in SIZE_UNITS:
        raise ValueError(f"Unknown size unit: {unit}")

    return int(value * SIZE_UNITS[unit])


def parse_datetime(dt: datetime | str | timedelta) -> datetime:
    """Parse datetime from various formats."""
    if isinstance(dt, datetime):
        return dt

    if isinstance(dt, timedelta):
        return datetime.now() - dt

    dt_str = dt.strip()

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue

    raise ValueError(f"Cannot parse datetime: {dt}")


def is_hidden(path: Path) -> bool:
    """Check if file is hidden (cross-platform)."""
    if path.name.startswith("."):
        return True

    if IS_WINDOWS:
        try:
            attrs = os.stat(path).st_file_attributes  # type: ignore[attr-defined]
            return bool(attrs & FILE_ATTRIBUTE_HIDDEN)
        except (AttributeError, OSError):
            return False

    return False
