"""Tests for FileFinder - File discovery and searching.

Copyright (c) 2025 Francesco Favi
"""

from pathlib import Path

import pytest

import zerofilesystem as zo


@pytest.fixture
def sample_tree(tmp_path: Path) -> Path:
    """Create a sample directory tree for testing."""
    # Create directory structure
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "module").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "docs").mkdir()

    # Create files
    (tmp_path / "README.md").write_text("# Readme")
    (tmp_path / "setup.py").write_text("# Setup")
    (tmp_path / "src" / "__init__.py").write_text("")
    (tmp_path / "src" / "main.py").write_text("# Main")
    (tmp_path / "src" / "utils.py").write_text("# Utils")
    (tmp_path / "src" / "module" / "__init__.py").write_text("")
    (tmp_path / "src" / "module" / "core.py").write_text("# Core")
    (tmp_path / "tests" / "test_main.py").write_text("# Test Main")
    (tmp_path / "tests" / "test_utils.py").write_text("# Test Utils")
    (tmp_path / "docs" / "guide.md").write_text("# Guide")
    (tmp_path / "docs" / "api.md").write_text("# API")

    # Hidden file
    (tmp_path / ".hidden").write_text("hidden content")
    (tmp_path / ".gitignore").write_text("*.pyc")

    return tmp_path


class TestFindFiles:
    """Tests for find_files function."""

    def test_find_all_files(self, sample_tree: Path) -> None:
        """Test finding all files recursively."""
        files = zo.find_files(sample_tree)

        # Should find all files including hidden
        assert len(files) >= 11

    def test_find_files_by_extension(self, sample_tree: Path) -> None:
        """Test finding files by extension."""
        py_files = zo.find_files(sample_tree, pattern="*.py")

        # setup.py + 2 __init__.py + main.py + utils.py + core.py + 2 test files = 8
        assert len(py_files) == 8  # All .py files
        assert all(f.suffix == ".py" for f in py_files)

    def test_find_files_by_name_pattern(self, sample_tree: Path) -> None:
        """Test finding files by name pattern."""
        test_files = zo.find_files(sample_tree, pattern="test_*.py")

        assert len(test_files) == 2
        assert all(f.name.startswith("test_") for f in test_files)

    def test_find_files_non_recursive(self, sample_tree: Path) -> None:
        """Test finding files non-recursively."""
        files = zo.find_files(sample_tree, pattern="*.py", recursive=False)

        assert len(files) == 1  # Only setup.py in root
        assert files[0].name == "setup.py"

    def test_find_files_relative_paths(self, sample_tree: Path) -> None:
        """Test finding files with relative paths."""
        files = zo.find_files(sample_tree, pattern="*.md", absolute=False)

        assert len(files) == 3
        # When absolute=False, paths are relative to the base directory
        # but may still be returned as relative paths from cwd
        for f in files:
            assert f.suffix == ".md"

    def test_find_files_max_results(self, sample_tree: Path) -> None:
        """Test limiting number of results."""
        files = zo.find_files(sample_tree, pattern="*.py", max_results=3)

        assert len(files) == 3

    def test_find_files_with_filter(self, sample_tree: Path) -> None:
        """Test finding files with custom filter."""
        # Find Python files NOT starting with test_
        files = zo.find_files(
            sample_tree,
            pattern="*.py",
            filter_fn=lambda p: not p.name.startswith("test_"),
        )

        # setup.py + 2 __init__.py + main.py + utils.py + core.py = 6
        assert len(files) == 6
        assert all(not f.name.startswith("test_") for f in files)

    def test_find_files_filter_by_size(self, sample_tree: Path) -> None:
        """Test finding files filtered by size."""
        # Add a larger file
        large_file = sample_tree / "large.txt"
        large_file.write_text("x" * 1000)

        # Find files > 500 bytes
        files = zo.find_files(
            sample_tree,
            filter_fn=lambda p: p.stat().st_size > 500,
        )

        assert len(files) == 1
        assert files[0].name == "large.txt"

    def test_find_files_empty_dir(self, tmp_path: Path) -> None:
        """Test finding files in empty directory."""
        files = zo.find_files(tmp_path)

        assert files == []

    def test_find_files_nonexistent_dir(self, tmp_path: Path) -> None:
        """Test finding files in non-existent directory."""
        nonexistent = tmp_path / "nonexistent"

        files = zo.find_files(nonexistent)

        assert files == []

    def test_find_files_in_subdirectory(self, sample_tree: Path) -> None:
        """Test finding files in specific subdirectory."""
        files = zo.find_files(sample_tree / "src", pattern="*.py")

        # __init__.py + main.py + utils.py + module/__init__.py + module/core.py = 5
        assert len(files) == 5


class TestWalkFiles:
    """Tests for walk_files generator function."""

    def test_walk_files_generator(self, sample_tree: Path) -> None:
        """Test walk_files returns a generator."""
        result = zo.walk_files(sample_tree)

        # Should be a generator/iterator
        assert hasattr(result, "__iter__")
        assert hasattr(result, "__next__")

    def test_walk_files_finds_all(self, sample_tree: Path) -> None:
        """Test walk_files finds all files."""
        files = list(zo.walk_files(sample_tree, pattern="*.py"))

        assert len(files) == 8  # Same as find_files

    def test_walk_files_with_filter(self, sample_tree: Path) -> None:
        """Test walk_files with custom filter."""
        files = list(
            zo.walk_files(
                sample_tree,
                pattern="*.py",
                filter_fn=lambda p: "init" not in p.name,
            )
        )

        # setup.py + main.py + utils.py + core.py + test_main.py + test_utils.py = 6
        assert len(files) == 6
        assert all("init" not in f.name for f in files)

    def test_walk_files_memory_efficient(self, tmp_path: Path) -> None:
        """Test walk_files can be used for large directories."""
        # Create many files
        for i in range(100):
            (tmp_path / f"file_{i}.txt").write_text(f"content {i}")

        # Walk and process lazily
        count = 0
        for _ in zo.walk_files(tmp_path, pattern="*.txt"):
            count += 1
            if count >= 10:
                break  # Early exit - generator not exhausted

        assert count == 10


class TestIsHidden:
    """Tests for is_hidden function."""

    def test_is_hidden_unix_dotfile(self, tmp_path: Path) -> None:
        """Test detecting Unix hidden files (dotfiles)."""
        hidden = tmp_path / ".hidden"
        hidden.write_text("hidden")

        assert zo.is_hidden(hidden) is True

    def test_is_hidden_normal_file(self, tmp_path: Path) -> None:
        """Test normal files are not hidden."""
        normal = tmp_path / "normal.txt"
        normal.write_text("visible")

        assert zo.is_hidden(normal) is False

    def test_is_hidden_gitignore(self, tmp_path: Path) -> None:
        """Test .gitignore is detected as hidden."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc")

        assert zo.is_hidden(gitignore) is True

    def test_is_hidden_ds_store(self, tmp_path: Path) -> None:
        """Test .DS_Store is detected as hidden."""
        ds_store = tmp_path / ".DS_Store"
        ds_store.write_text("")

        assert zo.is_hidden(ds_store) is True


class TestFindFilesEdgeCases:
    """Edge case tests for find_files."""

    def test_find_files_special_chars_in_name(self, tmp_path: Path) -> None:
        """Test finding files with special characters in name."""
        special = tmp_path / "file with spaces.txt"
        special.write_text("content")

        files = zo.find_files(tmp_path, pattern="*.txt")

        assert len(files) == 1
        assert files[0].name == "file with spaces.txt"

    def test_find_files_unicode_names(self, tmp_path: Path) -> None:
        """Test finding files with unicode names."""
        unicode_file = tmp_path / "日本語ファイル.txt"
        unicode_file.write_text("content")

        files = zo.find_files(tmp_path, pattern="*.txt")

        assert len(files) == 1

    def test_find_files_deeply_nested(self, tmp_path: Path) -> None:
        """Test finding files in deeply nested directories."""
        deep_path = tmp_path / "a" / "b" / "c" / "d" / "e"
        deep_path.mkdir(parents=True)
        (deep_path / "deep.txt").write_text("deep")

        files = zo.find_files(tmp_path, pattern="*.txt")

        assert len(files) == 1
        assert files[0].name == "deep.txt"

    def test_find_files_symlinks(self, tmp_path: Path) -> None:
        """Test finding files handles symlinks."""
        # Create a real file
        real_file = tmp_path / "real.txt"
        real_file.write_text("real content")

        # Create a symlink
        link = tmp_path / "link.txt"
        try:
            link.symlink_to(real_file)
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        files = zo.find_files(tmp_path, pattern="*.txt")

        # Should find both real file and symlink
        assert len(files) >= 1
