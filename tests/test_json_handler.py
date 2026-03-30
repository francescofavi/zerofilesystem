"""Tests for JsonHandler - JSON file operations.

Copyright (c) 2025 Francesco Favi
"""

import json
from pathlib import Path
from typing import Any

import pytest

import zerofilesystem as zfs


class TestReadJson:
    """Tests for read_json function."""

    def test_read_json_dict(self, tmp_path: Path) -> None:
        """Test reading JSON dict."""
        file_path = tmp_path / "data.json"
        data: dict[str, Any] = {"name": "John", "age": 30}
        file_path.write_text(json.dumps(data))

        result = zfs.read_json(file_path)
        assert result == data

    def test_read_json_list(self, tmp_path: Path) -> None:
        """Test reading JSON list."""
        file_path = tmp_path / "list.json"
        data: list[Any] = [1, 2, 3, "four", {"five": 5}]
        file_path.write_text(json.dumps(data))

        result = zfs.read_json(file_path)
        assert result == data

    def test_read_json_nested(self, tmp_path: Path) -> None:
        """Test reading nested JSON structure."""
        file_path = tmp_path / "nested.json"
        data: dict[str, Any] = {
            "users": [
                {"name": "Alice", "roles": ["admin", "user"]},
                {"name": "Bob", "roles": ["user"]},
            ],
            "config": {"debug": True, "version": "1.0"},
        }
        file_path.write_text(json.dumps(data))

        result = zfs.read_json(file_path)
        assert result == data

    def test_read_json_unicode(self, tmp_path: Path) -> None:
        """Test reading JSON with unicode characters."""
        file_path = tmp_path / "unicode.json"
        data = {"greeting": "こんにちは", "emoji": "🎉"}
        file_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        result = zfs.read_json(file_path)
        assert result == data

    def test_read_json_invalid_raises(self, tmp_path: Path) -> None:
        """Test reading invalid JSON raises JSONDecodeError."""
        file_path = tmp_path / "invalid.json"
        file_path.write_text("not valid json {")

        with pytest.raises(json.JSONDecodeError):
            zfs.read_json(file_path)

    def test_read_json_nonexistent_raises(self, tmp_path: Path) -> None:
        """Test reading non-existent file raises FileNotFoundError."""
        file_path = tmp_path / "nonexistent.json"

        with pytest.raises(FileNotFoundError):
            zfs.read_json(file_path)


class TestWriteJson:
    """Tests for write_json function."""

    def test_write_json_dict(self, tmp_path: Path) -> None:
        """Test writing JSON dict."""
        file_path = tmp_path / "output.json"
        data = {"key": "value", "number": 42}

        result = zfs.write_json(file_path, data)

        assert result == file_path
        assert json.loads(file_path.read_text()) == data

    def test_write_json_list(self, tmp_path: Path) -> None:
        """Test writing JSON list."""
        file_path = tmp_path / "list.json"
        data: list[Any] = [1, 2, 3, {"nested": True}]

        zfs.write_json(file_path, data)

        assert json.loads(file_path.read_text()) == data

    def test_write_json_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Test write_json creates parent directories."""
        file_path = tmp_path / "deep" / "nested" / "data.json"
        data = {"created": True}

        zfs.write_json(file_path, data)

        assert file_path.exists()
        assert json.loads(file_path.read_text()) == data

    def test_write_json_custom_indent(self, tmp_path: Path) -> None:
        """Test write_json with custom indentation."""
        file_path = tmp_path / "indented.json"
        data = {"key": "value"}

        zfs.write_json(file_path, data, indent=4)

        content = file_path.read_text()
        # Should have 4-space indentation
        assert '    "key"' in content

    def test_write_json_unicode_preserved(self, tmp_path: Path) -> None:
        """Test write_json preserves unicode characters."""
        file_path = tmp_path / "unicode.json"
        data = {"message": "Привет мир", "symbol": "€"}

        zfs.write_json(file_path, data)

        content = file_path.read_text(encoding="utf-8")
        # Unicode should NOT be escaped
        assert "Привет мир" in content
        assert "€" in content

    def test_write_json_atomic(self, tmp_path: Path) -> None:
        """Test atomic JSON write."""
        file_path = tmp_path / "atomic.json"
        zfs.write_json(file_path, {"original": True})

        zfs.write_json(file_path, {"updated": True}, atomic=True)

        assert zfs.read_json(file_path) == {"updated": True}
        # No temp files should remain
        temp_files = list(tmp_path.glob(".*tmp"))
        assert len(temp_files) == 0

    def test_write_json_overwrites_existing(self, tmp_path: Path) -> None:
        """Test write_json overwrites existing file."""
        file_path = tmp_path / "existing.json"
        zfs.write_json(file_path, {"old": "data"})

        zfs.write_json(file_path, {"new": "data"})

        assert zfs.read_json(file_path) == {"new": "data"}


class TestJsonRoundTrip:
    """Tests for JSON read/write roundtrip."""

    def test_roundtrip_complex_data(self, tmp_path: Path) -> None:
        """Test complex data survives JSON roundtrip."""
        file_path = tmp_path / "complex.json"
        data: dict[str, Any] = {
            "string": "hello",
            "number": 123,
            "float": 3.14,
            "bool_true": True,
            "bool_false": False,
            "null": None,
            "list": [1, 2, 3],
            "nested": {"a": {"b": {"c": "deep"}}},
        }

        zfs.write_json(file_path, data)
        result = zfs.read_json(file_path)

        assert result == data

    def test_roundtrip_empty_structures(self, tmp_path: Path) -> None:
        """Test empty structures survive roundtrip."""
        file_path = tmp_path / "empty.json"

        # Empty dict
        zfs.write_json(file_path, {})
        assert zfs.read_json(file_path) == {}

        # Empty list
        zfs.write_json(file_path, [])
        assert zfs.read_json(file_path) == []

    def test_roundtrip_special_values(self, tmp_path: Path) -> None:
        """Test special float values."""
        file_path = tmp_path / "special.json"
        data = {"large": 1e100, "small": 1e-100, "negative": -99999}

        zfs.write_json(file_path, data)
        result = zfs.read_json(file_path)

        assert result == data
