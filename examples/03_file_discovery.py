#!/usr/bin/env python3
"""Example: File discovery and searching with zerofilesystem.

This example demonstrates:
- Finding files by pattern (glob)
- Using custom filters
- Generator-based file walking
- Detecting hidden files
"""

import tempfile
from pathlib import Path

import zerofilesystem as zfs


def create_sample_project(base: Path) -> None:
    """Create a sample project structure for demonstration."""
    # Create directories
    (base / "src").mkdir()
    (base / "src" / "utils").mkdir()
    (base / "tests").mkdir()
    (base / "docs").mkdir()
    (base / ".git").mkdir()

    # Create Python files
    (base / "main.py").write_text("# Main entry point")
    (base / "src" / "__init__.py").write_text("")
    (base / "src" / "app.py").write_text("# App logic")
    (base / "src" / "models.py").write_text("# Data models")
    (base / "src" / "utils" / "__init__.py").write_text("")
    (base / "src" / "utils" / "helpers.py").write_text("# Helper functions")

    # Create test files
    (base / "tests" / "test_app.py").write_text("# App tests")
    (base / "tests" / "test_models.py").write_text("# Model tests")

    # Create documentation
    (base / "docs" / "guide.md").write_text("# User Guide")
    (base / "docs" / "api.md").write_text("# API Reference")

    # Create config files
    (base / "pyproject.toml").write_text("[project]")
    (base / ".gitignore").write_text("__pycache__/")
    (base / ".env").write_text("SECRET=xxx")

    # Create a large file for size filtering demo
    (base / "large_file.txt").write_text("x" * 10000)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        create_sample_project(tmp_path)

        print(f"Sample project created at: {tmp_path}\n")

        # Find All Files

        print("=== Find All Files (Recursive) ===\n")

        all_files = zfs.find_files(tmp_path)
        print(f"Total files found: {len(all_files)}")
        for f in all_files[:5]:
            print(f"  - {f.relative_to(tmp_path)}")
        if len(all_files) > 5:
            print(f"  ... and {len(all_files) - 5} more")

        # Find By Extension

        print("\n=== Find Python Files ===\n")

        py_files = zfs.find_files(tmp_path, pattern="*.py")
        print(f"Python files: {len(py_files)}")
        for f in py_files:
            print(f"  - {f.relative_to(tmp_path)}")

        # Find By Name Pattern

        print("\n=== Find Test Files ===\n")

        test_files = zfs.find_files(tmp_path, pattern="test_*.py")
        print(f"Test files: {len(test_files)}")
        for f in test_files:
            print(f"  - {f.relative_to(tmp_path)}")

        # Non-Recursive Search

        print("\n=== Find Files in Root Only (Non-Recursive) ===\n")

        root_files = zfs.find_files(tmp_path, pattern="*", recursive=False)
        print(f"Files in root directory: {len(root_files)}")
        for f in root_files:
            print(f"  - {f.name}")

        # Custom Filters

        print("\n=== Custom Filter: Files Larger Than 1KB ===\n")

        large_files = zfs.find_files(
            tmp_path,
            filter_fn=lambda p: p.stat().st_size > 1000,
        )
        print(f"Large files (>1KB): {len(large_files)}")
        for f in large_files:
            size = f.stat().st_size
            print(f"  - {f.name} ({size} bytes)")

        print("\n=== Custom Filter: Non-Test Python Files ===\n")

        non_test_py = zfs.find_files(
            tmp_path,
            pattern="*.py",
            filter_fn=lambda p: not p.name.startswith("test_"),
        )
        print(f"Non-test Python files: {len(non_test_py)}")
        for f in non_test_py:
            print(f"  - {f.relative_to(tmp_path)}")

        # Limiting Results

        print("\n=== Limited Results ===\n")

        first_three = zfs.find_files(tmp_path, pattern="*.py", max_results=3)
        print("First 3 Python files:")
        for f in first_three:
            print(f"  - {f.relative_to(tmp_path)}")

        # Relative Paths

        print("\n=== Relative Paths ===\n")

        relative_files = zfs.find_files(tmp_path, pattern="*.md", absolute=False)
        print("Markdown files (relative paths):")
        for f in relative_files:
            print(f"  - {f}")

        # Generator-Based Walking

        print("\n=== Generator-Based Walking (Memory Efficient) ===\n")

        print("Processing files one at a time:")
        for count, filepath in enumerate(zfs.walk_files(tmp_path, pattern="*.py"), 1):
            print(f"  Processing: {filepath.name}")
            if count >= 3:
                print("  (stopping early for demo)")
                break

        # Hidden Files

        print("\n=== Hidden File Detection ===\n")

        all_items = zfs.find_files(tmp_path)
        for f in all_items:
            if zfs.is_hidden(f):
                print(f"  [HIDDEN] {f.relative_to(tmp_path)}")

        # Check specific files
        print(f"\n.gitignore is hidden: {zfs.is_hidden(tmp_path / '.gitignore')}")
        print(f"main.py is hidden: {zfs.is_hidden(tmp_path / 'main.py')}")

        # Searching in Subdirectory

        print("\n=== Search in Specific Subdirectory ===\n")

        src_files = zfs.find_files(tmp_path / "src", pattern="*.py")
        print("Python files in src/:")
        for f in src_files:
            print(f"  - {f.relative_to(tmp_path)}")

        print("\n=== Done! ===")


if __name__ == "__main__":
    main()
