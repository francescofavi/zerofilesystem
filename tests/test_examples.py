"""Smoke test: every script under examples/ must exit 0 within a timeout.

Each example is launched as a fresh `python <example>` subprocess so import-time
side effects, top-level code paths and output handling are all exercised end to
end. The example contract is that it writes only to its own tempfile-backed
working area, so this test does not need to clean anything up.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"

EXAMPLE_TIMEOUT_SECS = 60


def _example_scripts() -> list[Path]:
    return sorted(p for p in EXAMPLES_DIR.glob("*.py") if not p.name.startswith("_"))


EXAMPLE_IDS = [p.name for p in _example_scripts()]


@pytest.mark.parametrize("script", _example_scripts(), ids=EXAMPLE_IDS)
def test_example_runs_cleanly(script: Path) -> None:
    """The example exits 0 within the timeout.

    stdout and stderr are captured and only surfaced when the assertion fails,
    so passing runs stay quiet and failing runs are debuggable.
    """
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        timeout=EXAMPLE_TIMEOUT_SECS,
        cwd=REPO_ROOT,
        env=env,
        check=False,
    )
    assert result.returncode == 0, (
        f"{script.name} exited with {result.returncode}\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )


def test_examples_directory_is_documented() -> None:
    """examples/README.md must list every script file by name."""
    readme = (EXAMPLES_DIR / "README.md").read_text(encoding="utf-8")
    for script in _example_scripts():
        assert script.name in readme, f"examples/README.md does not mention {script.name}"


def test_example_inventory_is_not_empty() -> None:
    assert _example_scripts(), "no example scripts were discovered"
