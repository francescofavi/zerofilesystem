#!/usr/bin/env python3
"""
Code Quality Checks Menu.

Interactive menu for running various code quality tools:
- Ruff (linting and formatting)
- MyPy (type checking)
- Bandit (security scanning)
- Vulture (dead code detection)
- Pytest (testing)
"""

import os
import subprocess  # nosec B404
import sys
from collections.abc import Callable
from pathlib import Path

# GENERAL UTILITIES


def _clear_screen() -> None:
    """Clear the terminal screen."""
    os.system("cls" if sys.platform == "win32" else "clear")  # nosec B605


def _get_check_dirs() -> list[str]:
    """Determine which directories to check."""
    dirs = []
    if Path("src").is_dir():
        dirs.append("src/")
    if Path("tests").is_dir():
        dirs.append("tests/")

    if not dirs:
        print("Error: No source directories found (src/ or tests/)")
        sys.exit(1)

    return dirs


def _run_command(name: str, cmd: list[str]) -> bool:
    """Run a command and return success status."""
    print(f"\nRunning {name}...\n")

    try:
        result = subprocess.run(cmd, check=False)  # nosec B603
        success = result.returncode == 0

        print()
        if success:
            print(f"[OK] {name} passed")
        else:
            print(f"[FAIL] {name} found errors")

        return success
    except FileNotFoundError:
        print(f"[ERROR] Command not found: {cmd[0]}")
        return False


# QUALITY CHECK FUNCTIONS


def run_ruff_check(check_dirs: list[str]) -> bool:
    """Run ruff linting check."""
    return _run_command(name="Ruff check", cmd=["uv", "run", "ruff", "check"] + check_dirs)


def run_ruff_format(check_dirs: list[str]) -> bool:
    """Run ruff format check."""
    return _run_command(
        name="Ruff format check", cmd=["uv", "run", "ruff", "format", "--check"] + check_dirs
    )


def run_mypy() -> bool:
    """Run mypy type checking."""
    return _run_command(name="MyPy", cmd=["uv", "run", "mypy", "src/"])


def run_bandit(check_dirs: list[str]) -> bool:
    """Run bandit security scan."""
    return _run_command(
        name="Bandit security scan",
        cmd=["uv", "run", "bandit", "-c", "pyproject.toml", "-r"] + check_dirs,
    )


def run_vulture(check_dirs: list[str]) -> bool:
    """Run vulture dead code detection."""
    return _run_command(name="Vulture", cmd=["uv", "run", "vulture"] + check_dirs)


def run_pytest() -> bool:
    """Run pytest tests."""
    return _run_command(name="Pytest", cmd=["uv", "run", "pytest"])


def run_all_checks(check_dirs: list[str]) -> bool:
    """Run all quality checks."""
    _clear_screen()
    print("\nRunning all checks...\n")

    checks: list[tuple[str, Callable[..., bool], list[str] | None]] = [
        ("Ruff check", run_ruff_check, check_dirs),
        ("Ruff format", run_ruff_format, check_dirs),
        ("MyPy", run_mypy, None),
        ("Bandit", run_bandit, check_dirs),
        ("Vulture", run_vulture, check_dirs),
        ("Pytest", run_pytest, None),
    ]

    all_passed = True
    for _name, check_fn, dirs in checks:
        result = check_fn(check_dirs=dirs) if dirs is not None else check_fn()
        if not result:
            all_passed = False

    print()
    print("=" * 40)
    if all_passed:
        print("[OK] All checks passed")
    else:
        print("[FAIL] Some checks failed")
    print("=" * 40)

    return all_passed


def show_menu() -> None:
    """Display the interactive menu."""
    _clear_screen()
    print()
    print("=" * 40)
    print("    CODE QUALITY CHECKS MENU")
    print("=" * 40)
    print()
    print("  1. Run all checks")
    print("  2. Ruff check (linting)")
    print("  3. Ruff format check")
    print("  4. MyPy (type checking)")
    print("  5. Bandit (security scan)")
    print("  6. Vulture (dead code detection)")
    print("  7. Pytest (tests)")
    print("  0. Exit")
    print()
    print("=" * 40)


def main() -> None:
    """Main entry point."""
    check_dirs = _get_check_dirs()

    while True:
        show_menu()
        print()

        try:
            choice = input("Choose an option [0-7]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nExiting. Goodbye!\n")
            sys.exit(0)

        if choice == "1":
            run_all_checks(check_dirs=check_dirs)
        elif choice == "2":
            run_ruff_check(check_dirs=check_dirs)
        elif choice == "3":
            run_ruff_format(check_dirs=check_dirs)
        elif choice == "4":
            run_mypy()
        elif choice == "5":
            run_bandit(check_dirs=check_dirs)
        elif choice == "6":
            run_vulture(check_dirs=check_dirs)
        elif choice == "7":
            run_pytest()
        elif choice == "0":
            _clear_screen()
            print("\nExiting. Goodbye!\n")
            sys.exit(0)
        else:
            print("\nInvalid option. Please try again.")

        print()
        input("Press ENTER to continue...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting. Goodbye!\n")
        sys.exit(0)
