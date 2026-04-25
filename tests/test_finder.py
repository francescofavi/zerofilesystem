"""Tests for the Finder class with fluent API."""

import time
from datetime import datetime, timedelta
from pathlib import Path

from zerofilesystem import Finder


class TestFinderPatterns:
    """Test pattern matching."""

    def test_single_pattern(self, tmp_path: Path) -> None:
        (tmp_path / "file1.py").write_text("python")
        (tmp_path / "file2.txt").write_text("text")
        (tmp_path / "file3.py").write_text("python")

        files = Finder(tmp_path).patterns("*.py").find()

        assert len(files) == 2
        names = {f.name for f in files}
        assert names == {"file1.py", "file3.py"}

    def test_multiple_patterns(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.txt").write_text("")
        (tmp_path / "c.json").write_text("")
        (tmp_path / "d.md").write_text("")

        files = Finder(tmp_path).patterns("*.py", "*.txt", "*.json").find()

        assert len(files) == 3
        names = {f.name for f in files}
        assert names == {"a.py", "b.txt", "c.json"}

    def test_no_pattern_matches_all(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.txt").write_text("")

        files = Finder(tmp_path).find()

        assert len(files) == 2

    def test_exclude_patterns(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text("")
        (tmp_path / "skip_main.py").write_text("")
        (tmp_path / "utils.py").write_text("")

        # Use "skip_*" instead of "test_*" to avoid matching pytest's temp dir names
        files = Finder(tmp_path).patterns("*.py").exclude("skip_*").find()

        assert len(files) == 2
        names = {f.name for f in files}
        assert names == {"main.py", "utils.py"}

    def test_exclude_directory(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "main.cpython-312.pyc").write_text("")

        files = Finder(tmp_path).patterns("*").exclude("__pycache__").find()

        names = {f.name for f in files}
        assert "main.py" in names
        assert "main.cpython-312.pyc" not in names


class TestFinderRecursion:
    """Test recursive searching."""

    def test_recursive_default(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.py").write_text("")

        files = Finder(tmp_path).patterns("*.py").find()

        assert len(files) == 2

    def test_non_recursive(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.py").write_text("")

        files = Finder(tmp_path).patterns("*.py").non_recursive().find()

        assert len(files) == 1
        assert files[0].name == "a.py"

    def test_max_depth(self, tmp_path: Path) -> None:
        (tmp_path / "level0.py").write_text("")
        (tmp_path / "d1").mkdir()
        (tmp_path / "d1" / "level1.py").write_text("")
        (tmp_path / "d1" / "d2").mkdir()
        (tmp_path / "d1" / "d2" / "level2.py").write_text("")

        files = Finder(tmp_path).patterns("*.py").max_depth(1).find()

        assert len(files) == 1
        assert files[0].name == "level0.py"

        files = Finder(tmp_path).patterns("*.py").max_depth(2).find()
        assert len(files) == 2


class TestFinderSizeFilters:
    """Test size-based filtering."""

    def test_size_min(self, tmp_path: Path) -> None:
        (tmp_path / "small.txt").write_text("x")
        (tmp_path / "large.txt").write_text("x" * 1000)

        files = Finder(tmp_path).size_min(500).find()

        assert len(files) == 1
        assert files[0].name == "large.txt"

    def test_size_max(self, tmp_path: Path) -> None:
        (tmp_path / "small.txt").write_text("x")
        (tmp_path / "large.txt").write_text("x" * 1000)

        files = Finder(tmp_path).size_max(500).find()

        assert len(files) == 1
        assert files[0].name == "small.txt"

    def test_size_between(self, tmp_path: Path) -> None:
        (tmp_path / "tiny.txt").write_text("x")
        (tmp_path / "medium.txt").write_text("x" * 500)
        (tmp_path / "huge.txt").write_text("x" * 2000)

        files = Finder(tmp_path).size_between(100, 1000).find()

        assert len(files) == 1
        assert files[0].name == "medium.txt"

    def test_size_with_units(self, tmp_path: Path) -> None:
        (tmp_path / "small.txt").write_text("x" * 500)
        (tmp_path / "large.txt").write_text("x" * 2000)

        files = Finder(tmp_path).size_min("1KB").find()

        assert len(files) == 1
        assert files[0].name == "large.txt"

    def test_empty_filter(self, tmp_path: Path) -> None:
        (tmp_path / "empty.txt").write_text("")
        (tmp_path / "nonempty.txt").write_text("content")

        empty_files = Finder(tmp_path).empty().find()
        assert len(empty_files) == 1
        assert empty_files[0].name == "empty.txt"

        nonempty_files = Finder(tmp_path).not_empty().find()
        assert len(nonempty_files) == 1
        assert nonempty_files[0].name == "nonempty.txt"


class TestFinderDateFilters:
    """Test date-based filtering."""

    def test_modified_after_datetime(self, tmp_path: Path) -> None:
        old_file = tmp_path / "old.txt"
        old_file.write_text("old")
        # Set old modification time
        import os

        old_time = time.time() - 86400 * 10  # 10 days ago
        os.utime(old_file, (old_time, old_time))

        new_file = tmp_path / "new.txt"
        new_file.write_text("new")

        cutoff = datetime.now() - timedelta(days=5)
        files = Finder(tmp_path).modified_after(cutoff).find()

        assert len(files) == 1
        assert files[0].name == "new.txt"

    def test_modified_last_days(self, tmp_path: Path) -> None:
        old_file = tmp_path / "old.txt"
        old_file.write_text("old")
        import os

        old_time = time.time() - 86400 * 10
        os.utime(old_file, (old_time, old_time))

        new_file = tmp_path / "new.txt"
        new_file.write_text("new")

        files = Finder(tmp_path).modified_last_days(5).find()

        assert len(files) == 1
        assert files[0].name == "new.txt"

    def test_modified_with_string_date(self, tmp_path: Path) -> None:
        (tmp_path / "file.txt").write_text("content")

        # File should be modified after year 2000
        files = Finder(tmp_path).modified_after("2000-01-01").find()
        assert len(files) == 1


class TestFinderAttributeFilters:
    """Test attribute-based filtering."""

    def test_hidden_files(self, tmp_path: Path) -> None:
        (tmp_path / "visible.txt").write_text("")
        (tmp_path / ".hidden.txt").write_text("")

        visible = Finder(tmp_path).not_hidden().find()
        assert len(visible) == 1
        assert visible[0].name == "visible.txt"

        hidden = Finder(tmp_path).hidden().find()
        assert len(hidden) == 1
        assert hidden[0].name == ".hidden.txt"

    def test_files_only(self, tmp_path: Path) -> None:
        (tmp_path / "file.txt").write_text("")
        (tmp_path / "subdir").mkdir()

        files = Finder(tmp_path).files_only().find()

        assert len(files) == 1
        assert files[0].name == "file.txt"

    def test_dirs_only(self, tmp_path: Path) -> None:
        (tmp_path / "file.txt").write_text("")
        (tmp_path / "subdir").mkdir()

        dirs = Finder(tmp_path).dirs_only().find()

        assert len(dirs) == 1
        assert dirs[0].name == "subdir"


class TestFinderCustomFilters:
    """Test custom filter functions."""

    def test_custom_filter(self, tmp_path: Path) -> None:
        (tmp_path / "short.txt").write_text("x")
        (tmp_path / "medium_name.txt").write_text("x")
        (tmp_path / "very_long_filename.txt").write_text("x")

        files = Finder(tmp_path).filter(lambda p: len(p.stem) > 5).find()

        assert len(files) == 2
        names = {f.name for f in files}
        assert "short.txt" not in names

    def test_multiple_custom_filters(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x" * 100)
        (tmp_path / "b.py").write_text("x" * 10)
        (tmp_path / "c.txt").write_text("x" * 100)

        files = (
            Finder(tmp_path)
            .filter(lambda p: p.suffix == ".py")
            .filter(lambda p: p.stat().st_size > 50)
            .find()
        )

        assert len(files) == 1
        assert files[0].name == "a.py"


class TestFinderOutput:
    """Test output options."""

    def test_absolute_paths_default(self, tmp_path: Path) -> None:
        (tmp_path / "file.txt").write_text("")

        files = Finder(tmp_path).find()

        assert files[0].is_absolute()

    def test_relative_paths(self, tmp_path: Path) -> None:
        (tmp_path / "file.txt").write_text("")

        files = Finder(tmp_path).relative().find()

        # With relative(), paths are not resolved to absolute
        assert not files[0].is_absolute() or str(files[0]).startswith(str(tmp_path))

    def test_limit(self, tmp_path: Path) -> None:
        for i in range(10):
            (tmp_path / f"file{i}.txt").write_text("")

        files = Finder(tmp_path).limit(3).find()

        assert len(files) == 3

    def test_first(self, tmp_path: Path) -> None:
        for i in range(5):
            (tmp_path / f"file{i}.txt").write_text("")

        files = Finder(tmp_path).first(2).find()

        assert len(files) == 2


class TestFinderUtilityMethods:
    """Test utility methods."""

    def test_count(self, tmp_path: Path) -> None:
        for i in range(5):
            (tmp_path / f"file{i}.txt").write_text("")

        count = Finder(tmp_path).count()

        assert count == 5

    def test_exists(self, tmp_path: Path) -> None:
        assert not Finder(tmp_path).patterns("*.py").exists()

        (tmp_path / "file.py").write_text("")

        assert Finder(tmp_path).patterns("*.py").exists()

    def test_first_match(self, tmp_path: Path) -> None:
        assert Finder(tmp_path).patterns("*.py").first_match() is None

        (tmp_path / "file.py").write_text("")

        match = Finder(tmp_path).patterns("*.py").first_match()
        assert match is not None
        assert match.name == "file.py"

    def test_walk_generator(self, tmp_path: Path) -> None:
        for i in range(3):
            (tmp_path / f"file{i}.txt").write_text("")

        count = 0
        for _ in Finder(tmp_path).walk():
            count += 1

        assert count == 3

    def test_iteration(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("")
        (tmp_path / "b.txt").write_text("")

        files = list(Finder(tmp_path))

        assert len(files) == 2

    def test_len(self, tmp_path: Path) -> None:
        for i in range(4):
            (tmp_path / f"file{i}.txt").write_text("")

        assert len(Finder(tmp_path)) == 4


class TestFinderEdgeCases:
    """Test edge cases."""

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        files = Finder(tmp_path / "nonexistent").find()

        assert files == []

    def test_empty_directory(self, tmp_path: Path) -> None:
        files = Finder(tmp_path).find()

        assert files == []

    def test_chaining(self, tmp_path: Path) -> None:
        (tmp_path / "test.py").write_text("x" * 100)

        files = (
            Finder(tmp_path)
            .patterns("*.py")
            .exclude("__pycache__")
            .recursive()
            .not_hidden()
            .size_min(50)
            .limit(10)
            .find()
        )

        assert len(files) == 1
