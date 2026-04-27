"""In-memory file change detector using content hashing.

Copyright (c) 2026 Francesco Favi
License: MIT
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ChangeSummary:
    """Result of a :class:`ChangeDetector` scan."""

    modified: list[Path] = field(default_factory=list)
    new: list[Path] = field(default_factory=list)
    deleted: list[Path] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.modified or self.new or self.deleted)


class ChangeDetector:
    """Detects changes in a directory between successive scans.

    State is kept in-memory: call :meth:`scan` each time you want to check
    for changes since the previous call.  The first scan marks every file as
    *new*.  Use :meth:`reset` to start fresh.

    Example::

        detector = ChangeDetector(extensions={".py"})
        summary = detector.scan(repo_path)   # first call: all files are "new"
        # … files change …
        summary = detector.scan(repo_path)   # subsequent call: shows diffs
    """

    def __init__(self, extensions: set[str] | None = None) -> None:
        self.extensions = extensions or {".py"}
        self._hashes: dict[str, str] = {}

    def scan(self, repo_path: Path) -> ChangeSummary:
        """Compare *repo_path* against the previous snapshot.

        Args:
            repo_path: Root directory to scan.

        Returns:
            :class:`ChangeSummary` with ``new``, ``modified``, and ``deleted`` lists.
        """
        current_files: set[Path] = set()
        for ext in self.extensions:
            current_files.update(repo_path.rglob(f"*{ext}"))

        current_hashes: dict[str, str] = {}
        summary = ChangeSummary()

        for file_path in current_files:
            rel = file_path.relative_to(repo_path).as_posix()
            digest = self._hash_file(file_path)
            current_hashes[rel] = digest
            old_digest = self._hashes.get(rel)
            if old_digest is None:
                summary.new.append(file_path)
            elif old_digest != digest:
                summary.modified.append(file_path)

        current_rels = set(current_hashes.keys())
        old_rels = set(self._hashes.keys())
        for rel in old_rels - current_rels:
            summary.deleted.append(repo_path / rel)

        self._hashes = current_hashes
        return summary

    def reset(self) -> None:
        """Clear the internal hash state so the next :meth:`scan` treats all files as new."""
        self._hashes.clear()

    def _hash_file(self, path: Path) -> str:
        try:
            content = path.read_bytes()
        except OSError:
            return ""
        return hashlib.md5(content, usedforsecurity=False).hexdigest()
