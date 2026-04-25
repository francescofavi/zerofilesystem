"""Platform detection constants and shared types.

zerofilesystem targets POSIX systems only — Linux and macOS. Windows is not
supported: there is no Windows runner in CI and no maintainer setup that can
exercise the os-specific branches that used to live in this package.

Only ``IS_LINUX`` and ``IS_MACOS`` are exposed. The previous ``IS_WINDOWS`` /
``IS_UNIX`` constants were removed in 0.2.0 — see CHANGELOG. If you need to
distinguish at runtime, use ``IS_LINUX`` / ``IS_MACOS`` directly or query
``sys.platform`` yourself.
"""

from __future__ import annotations

import sys
from pathlib import Path

IS_MACOS: bool = sys.platform == "darwin"
IS_LINUX: bool = sys.platform.startswith("linux")

Pathish = str | Path
