"""Tests for the Watcher class with fluent API."""

import time
from datetime import datetime, timedelta
from pathlib import Path

from zerofilesystem import EventType, Watcher, WatchEvent


class TestWatcherBasic:
    """Test basic watcher functionality."""

    def test_watcher_start_stop(self, tmp_path: Path) -> None:
        watcher = Watcher(tmp_path)

        assert not watcher.is_running

        watcher.start()
        assert watcher.is_running

        watcher.stop()
        assert not watcher.is_running

    def test_watcher_context_manager(self, tmp_path: Path) -> None:
        with Watcher(tmp_path) as w:
            assert w.is_running

        assert not w.is_running

    def test_watcher_detects_created(self, tmp_path: Path) -> None:
        events: list[WatchEvent] = []

        watcher = Watcher(tmp_path).poll_interval(0.1).on_created(lambda e: events.append(e))

        watcher.start()
        time.sleep(0.15)

        (tmp_path / "newfile.txt").write_text("content")
        time.sleep(0.25)

        watcher.stop()

        assert len(events) >= 1
        assert any(e.type == EventType.CREATED for e in events)
        assert any(e.path.name == "newfile.txt" for e in events)

    def test_watcher_detects_modified(self, tmp_path: Path) -> None:
        test_file = tmp_path / "existing.txt"
        test_file.write_text("initial")

        events: list[WatchEvent] = []

        watcher = Watcher(tmp_path).poll_interval(0.1).on_modified(lambda e: events.append(e))

        watcher.start()
        time.sleep(0.15)

        test_file.write_text("modified")
        time.sleep(0.25)

        watcher.stop()

        assert len(events) >= 1
        assert any(e.type == EventType.MODIFIED for e in events)

    def test_watcher_detects_deleted(self, tmp_path: Path) -> None:
        test_file = tmp_path / "todelete.txt"
        test_file.write_text("content")

        events: list[WatchEvent] = []

        watcher = Watcher(tmp_path).poll_interval(0.1).on_deleted(lambda e: events.append(e))

        watcher.start()
        time.sleep(0.15)

        test_file.unlink()
        time.sleep(0.25)

        watcher.stop()

        assert len(events) >= 1
        assert any(e.type == EventType.DELETED for e in events)

    def test_watcher_on_any(self, tmp_path: Path) -> None:
        events: list[WatchEvent] = []

        watcher = Watcher(tmp_path).poll_interval(0.1).on_any(lambda e: events.append(e))

        watcher.start()
        time.sleep(0.15)

        (tmp_path / "file.txt").write_text("content")
        time.sleep(0.25)

        watcher.stop()

        assert len(events) >= 1


class TestWatcherPatterns:
    """Test pattern filtering."""

    def test_watcher_pattern_filter(self, tmp_path: Path) -> None:
        events: list[WatchEvent] = []

        watcher = (
            Watcher(tmp_path)
            .patterns("*.py")
            .poll_interval(0.1)
            .on_created(lambda e: events.append(e))
        )

        watcher.start()
        time.sleep(0.15)

        (tmp_path / "script.py").write_text("python")
        (tmp_path / "data.txt").write_text("text")
        time.sleep(0.25)

        watcher.stop()

        assert len(events) == 1
        assert events[0].path.name == "script.py"

    def test_watcher_exclude_pattern(self, tmp_path: Path) -> None:
        events: list[WatchEvent] = []

        # Use "skip_*" instead of "test_*" to avoid matching pytest's temp dir names
        watcher = (
            Watcher(tmp_path)
            .patterns("*.py")
            .exclude("skip_*")
            .poll_interval(0.1)
            .on_created(lambda e: events.append(e))
        )

        watcher.start()
        time.sleep(0.15)

        (tmp_path / "main.py").write_text("main")
        (tmp_path / "skip_main.py").write_text("skipped")
        time.sleep(0.25)

        watcher.stop()

        assert len(events) == 1
        assert events[0].path.name == "main.py"


class TestWatcherFilters:
    """Test various filters."""

    def test_watcher_not_hidden(self, tmp_path: Path) -> None:
        events: list[WatchEvent] = []

        watcher = (
            Watcher(tmp_path).not_hidden().poll_interval(0.1).on_created(lambda e: events.append(e))
        )

        watcher.start()
        time.sleep(0.15)

        (tmp_path / "visible.txt").write_text("visible")
        (tmp_path / ".hidden.txt").write_text("hidden")
        time.sleep(0.25)

        watcher.stop()

        assert len(events) == 1
        assert events[0].path.name == "visible.txt"

    def test_watcher_size_filter(self, tmp_path: Path) -> None:
        events: list[WatchEvent] = []

        watcher = (
            Watcher(tmp_path)
            .size_min(100)
            .poll_interval(0.1)
            .on_created(lambda e: events.append(e))
        )

        watcher.start()
        time.sleep(0.15)

        (tmp_path / "small.txt").write_text("x")
        (tmp_path / "large.txt").write_text("x" * 200)
        time.sleep(0.25)

        watcher.stop()

        assert len(events) == 1
        assert events[0].path.name == "large.txt"

    def test_watcher_files_only(self, tmp_path: Path) -> None:
        events: list[WatchEvent] = []

        watcher = (
            Watcher(tmp_path).files_only().poll_interval(0.1).on_created(lambda e: events.append(e))
        )

        watcher.start()
        time.sleep(0.15)

        (tmp_path / "file.txt").write_text("content")
        (tmp_path / "subdir").mkdir()
        time.sleep(0.25)

        watcher.stop()

        assert len(events) == 1
        assert events[0].path.name == "file.txt"


class TestWatcherDebounce:
    """Test debounce functionality."""

    def test_debounce_modified(self, tmp_path: Path) -> None:
        test_file = tmp_path / "file.txt"
        test_file.write_text("initial")

        events: list[WatchEvent] = []

        watcher = (
            Watcher(tmp_path)
            .debounce(0.5)
            .poll_interval(0.05)
            .on_modified(lambda e: events.append(e))
        )

        watcher.start()
        time.sleep(0.2)

        # Multiple rapid modifications
        for i in range(5):
            test_file.write_text(f"content {i}")
            time.sleep(0.05)

        # Wait for debounce to settle
        time.sleep(1.0)

        watcher.stop()

        # Should only get 1 event due to debouncing
        assert len(events) == 1

    def test_debounce_does_not_affect_created(self, tmp_path: Path) -> None:
        events: list[WatchEvent] = []

        watcher = (
            Watcher(tmp_path)
            .debounce(0.5)
            .poll_interval(0.05)
            .on_created(lambda e: events.append(e))
        )

        watcher.start()
        time.sleep(0.1)

        (tmp_path / "file1.txt").write_text("1")
        (tmp_path / "file2.txt").write_text("2")
        time.sleep(0.2)

        watcher.stop()

        # CREATED events are not debounced
        assert len(events) == 2

    def test_debounce_ms(self, tmp_path: Path) -> None:
        test_file = tmp_path / "file.txt"
        test_file.write_text("initial")

        events: list[WatchEvent] = []

        watcher = (
            Watcher(tmp_path)
            .debounce_ms(300)
            .poll_interval(0.05)
            .on_modified(lambda e: events.append(e))
        )

        watcher.start()
        time.sleep(0.2)

        test_file.write_text("modified 1")
        time.sleep(0.05)
        test_file.write_text("modified 2")
        time.sleep(0.8)

        watcher.stop()

        assert len(events) == 1


class TestWatcherPollInterval:
    """Test poll interval settings."""

    def test_poll_fast(self, tmp_path: Path) -> None:
        watcher = Watcher(tmp_path).poll_fast()
        assert watcher._poll_interval_sec == 0.1

    def test_poll_slow(self, tmp_path: Path) -> None:
        watcher = Watcher(tmp_path).poll_slow()
        assert watcher._poll_interval_sec == 5.0

    def test_custom_poll_interval(self, tmp_path: Path) -> None:
        watcher = Watcher(tmp_path).poll_interval(2.5)
        assert watcher._poll_interval_sec == 2.5


class TestWatcherErrorHandling:
    """Test error callback."""

    def test_error_callback(self, tmp_path: Path) -> None:
        errors: list[tuple[Path, Exception]] = []

        def bad_callback(event: WatchEvent) -> None:
            raise ValueError("Intentional error")

        watcher = (
            Watcher(tmp_path)
            .poll_interval(0.1)
            .on_created(bad_callback)
            .on_error(lambda p, e: errors.append((p, e)))
        )

        watcher.start()
        time.sleep(0.15)

        (tmp_path / "file.txt").write_text("content")
        time.sleep(0.25)

        watcher.stop()

        assert len(errors) >= 1
        assert isinstance(errors[0][1], ValueError)


class TestWatcherChaining:
    """Test method chaining."""

    def test_full_chain(self, tmp_path: Path) -> None:
        events: list[WatchEvent] = []

        watcher = (
            Watcher(tmp_path)
            .patterns("*.py", "*.txt")
            .exclude("*.pyc", "__pycache__")
            .recursive()
            .not_hidden()
            .not_empty()
            .size_min(1)
            .poll_interval(0.1)
            .debounce(0.2)
            .on_created(lambda e: events.append(e))
            .on_modified(lambda e: events.append(e))
            .on_deleted(lambda e: events.append(e))
            .start()
        )

        assert watcher.is_running

        time.sleep(0.15)
        (tmp_path / "test.py").write_text("content")
        time.sleep(0.3)

        watcher.stop()

        assert len(events) >= 1


class TestWatcherBuilderSetters:
    """Verify every fluent setter on Watcher returns self and runs cleanly.

    The dedicated tests above exercise the runtime semantics; this parametric
    test is the regression guard for the fluent API contract itself.
    """

    def test_setters_with_argument_return_self(self, tmp_path: Path) -> None:
        w = Watcher(tmp_path)
        chain = (
            w.pattern("*.py")
            .patterns("*.txt", "*.md")
            .exclude("__pycache__")
            .recursive(True)
            .non_recursive()
            .max_depth(3)
            .poll_interval(0.5)
            .debounce(1.0)
            .debounce_ms(500)
            .size_min("1KB")
            .size_max("10MB")
            .size_between("1B", "1GB")
            .modified_after(datetime(2020, 1, 1))
            .modified_before(datetime(2030, 1, 1))
            .modified_last_days(30)
            .modified_last_hours(24)
            .created_after(timedelta(days=365))
            .created_before(datetime(2030, 1, 1))
        )
        assert chain is w

    def test_zero_arg_setters_return_self(self, tmp_path: Path) -> None:
        w = Watcher(tmp_path)
        chain = (
            w.hidden()
            .not_hidden()
            .empty()
            .not_empty()
            .follow_symlinks(True)
            .no_symlinks()
            .files_only()
            .dirs_only()
            .files_and_dirs()
        )
        assert chain is w
