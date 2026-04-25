"""Platform detection constants and shared types."""

from __future__ import annotations

import sys
from pathlib import Path

IS_WINDOWS: bool = sys.platform == "win32"
IS_MACOS: bool = sys.platform == "darwin"
IS_LINUX: bool = sys.platform.startswith("linux")
IS_UNIX: bool = IS_MACOS or IS_LINUX

Pathish = str | Path
