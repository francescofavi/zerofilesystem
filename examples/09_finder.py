#!/usr/bin/env python3
"""Example: Fluent file discovery with the Finder class.

This example demonstrates:
- Pattern matching with multiple patterns
- Exclusion patterns
- Size filtering with human-readable units
- Date filtering
- Attribute filtering (hidden, empty)
- Custom filter functions
- Various execution methods (find, walk, count, exists)
"""

import tempfile
import time
from datetime import timedelta
from pathlib import Path

from zerofilesystem import Finder


def create_sample_project(base: Path) -> None:
    """Create a sample project structure for demonstration."""
    # Create directories
    (base / "src").mkdir()
    (base / "src" / "utils").mkdir()
    (base / "tests").mkdir()
    (base / "docs").mkdir()
    (base / "__pycache__").mkdir()
    (base / ".git").mkdir()

    # Create Python files with varying sizes
    (base / "main.py").write_text("# Main entry point\n" * 50)  # ~1KB
    (base / "src" / "__init__.py").write_text("")  # Empty
    (base / "src" / "app.py").write_text("# App logic\n" * 200)  # ~2KB
    (base / "src" / "models.py").write_text("# Data models\n" * 100)  # ~1.4KB
    (base / "src" / "utils" / "__init__.py").write_text("")  # Empty
    (base / "src" / "utils" / "helpers.py").write_text("# Helper functions\n" * 30)

    # Create test files
    (base / "tests" / "test_app.py").write_text("# App tests\n" * 100)
    (base / "tests" / "test_models.py").write_text("# Model tests\n" * 100)

    # Create documentation
    (base / "docs" / "guide.md").write_text("# User Guide\n" * 50)
    (base / "docs" / "api.md").write_text("# API Reference\n" * 100)

    # Create config files
    (base / "pyproject.toml").write_text("[project]\nname = 'demo'\n")
    (base / "config.json").write_text('{"debug": true}')
    (base / ".gitignore").write_text("__pycache__/\n*.pyc\n")
    (base / ".env").write_text("SECRET=xxx")

    # Create cache file (old timestamp)
    cache_file = base / "__pycache__" / "main.cpython-312.pyc"
    cache_file.write_bytes(b"\x00" * 100)
    old_time = time.time() - 86400 * 30  # 30 days ago
    import os

    os.utime(cache_file, (old_time, old_time))

    # Create a large file
    (base / "large_data.txt").write_text("x" * 50000)  # 50KB


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        # Resolve to handle macOS /var -> /private/var symlink
        tmp_path = Path(tmp).resolve()
        create_sample_project(tmp_path)

        print(f"Sample project created at: {tmp_path}\n")

        # Basic Pattern Matching

        print("=== Basic Pattern Matching ===\n")

        # Single pattern
        py_files = Finder(tmp_path).patterns("*.py").find()
        print(f"Python files: {len(py_files)}")

        # Multiple patterns
        code_files = Finder(tmp_path).patterns("*.py", "*.json", "*.toml").find()
        print(f"Code + config files: {len(code_files)}")

        # Exclusion Patterns

        print("\n=== Exclusion Patterns ===\n")

        # Exclude test files
        non_test = Finder(tmp_path).patterns("*.py").exclude("test_*", "__pycache__").find()
        print(f"Non-test Python files: {len(non_test)}")
        for f in non_test:
            print(f"  - {f.relative_to(tmp_path)}")

        # Exclude multiple directories
        clean_files = (
            Finder(tmp_path)
            .patterns("*")
            .exclude("__pycache__", ".git", "*.pyc")
            .not_hidden()
            .find()
        )
        print(f"\nClean files (no cache/git/hidden): {len(clean_files)}")

        # Size Filtering

        print("\n=== Size Filtering ===\n")

        # Files larger than 1KB
        large_files = Finder(tmp_path).size_min("1KB").find()
        print(f"Files >= 1KB: {len(large_files)}")
        for f in large_files:
            size = f.stat().st_size
            print(f"  - {f.name}: {size} bytes")

        # Files between 500B and 2KB
        medium_files = Finder(tmp_path).size_between(500, "2KB").find()
        print(f"\nFiles 500B-2KB: {len(medium_files)}")

        # Empty files
        empty_files = Finder(tmp_path).empty().find()
        print(f"\nEmpty files: {len(empty_files)}")
        for f in empty_files:
            print(f"  - {f.relative_to(tmp_path)}")

        # Date Filtering

        print("\n=== Date Filtering ===\n")

        # Files modified in last 7 days
        recent = Finder(tmp_path).modified_last_days(7).find()
        print(f"Modified in last 7 days: {len(recent)}")

        # Files modified in last hour
        very_recent = Finder(tmp_path).modified_last_hours(1).find()
        print(f"Modified in last hour: {len(very_recent)}")

        # Using timedelta
        files_24h = Finder(tmp_path).modified_after(timedelta(hours=24)).find()
        print(f"Modified in last 24 hours: {len(files_24h)}")

        # Attribute Filtering

        print("\n=== Attribute Filtering ===\n")

        # Hidden files only
        hidden_files = Finder(tmp_path).hidden().find()
        print(f"Hidden files: {len(hidden_files)}")
        for f in hidden_files:
            print(f"  - {f.name}")

        # Non-hidden, non-empty files
        visible_nonempty = Finder(tmp_path).not_hidden().not_empty().find()
        print(f"\nVisible, non-empty files: {len(visible_nonempty)}")

        # Type Filtering

        print("\n=== Type Filtering ===\n")

        # Directories only
        dirs = Finder(tmp_path).dirs_only().find()
        print(f"Directories: {len(dirs)}")
        for d in dirs:
            print(f"  - {d.relative_to(tmp_path)}")

        # Recursion and depth
        print("\n=== Recursion and Depth ===\n")

        # Non-recursive (top level only)
        top_level = Finder(tmp_path).patterns("*.py").non_recursive().find()
        print(f"Python files at top level: {len(top_level)}")
        for f in top_level:
            print(f"  - {f.name}")

        # Limited depth
        shallow = Finder(tmp_path).patterns("*.py").max_depth(2).find()
        print(f"\nPython files (max depth 2): {len(shallow)}")

        # Custom Filters

        print("\n=== Custom Filters ===\n")

        # Files with "app" in name
        app_files = Finder(tmp_path).filter(lambda p: "app" in p.name.lower()).find()
        print(f"Files with 'app' in name: {len(app_files)}")
        for f in app_files:
            print(f"  - {f.relative_to(tmp_path)}")

        # Multiple custom filters
        special = (
            Finder(tmp_path)
            .patterns("*.py")
            .filter(lambda p: len(p.stem) > 3)  # Name longer than 3 chars
            .filter(lambda p: p.stat().st_size > 500)  # Size > 500 bytes
            .find()
        )
        print(f"\nPython files with long names and >500B: {len(special)}")

        # Execution Methods

        print("\n=== Execution Methods ===\n")

        finder = Finder(tmp_path).patterns("*.py")

        # Count without loading
        count = finder.count()
        print(f"Python file count: {count}")

        # Check existence
        has_py = Finder(tmp_path).patterns("*.py").exists()
        has_rs = Finder(tmp_path).patterns("*.rs").exists()
        print(f"Has Python files: {has_py}")
        print(f"Has Rust files: {has_rs}")

        # First match
        first = Finder(tmp_path).patterns("*.md").first_match()
        print(f"First markdown file: {first.name if first else 'None'}")

        # Limit results
        first_3 = Finder(tmp_path).patterns("*.py").limit(3).find()
        print(f"\nFirst 3 Python files: {[f.name for f in first_3]}")

        # Memory-Efficient Iteration

        print("\n=== Memory-Efficient Iteration ===\n")

        print("Walking files one at a time:")
        for count, path in enumerate(Finder(tmp_path).patterns("*.py").walk(), 1):
            print(f"  {count}. {path.name}")
            if count >= 3:
                print("  ... (stopping early for demo)")
                break

        # Chained Builder Example

        print("\n=== Complex Chained Query ===\n")

        results = (
            Finder(tmp_path)
            .patterns("*.py", "*.md")
            .exclude("__pycache__", "test_*")
            .not_hidden()
            .not_empty()
            .size_min(100)
            .modified_last_days(7)
            .recursive()
            .limit(10)
            .find()
        )

        print(f"Complex query results ({len(results)} files):")
        for f in results:
            size = f.stat().st_size
            print(f"  - {f.relative_to(tmp_path)} ({size} bytes)")

        print("\n=== Done! ===")


if __name__ == "__main__":
    main()
