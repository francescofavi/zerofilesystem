"""Manifest-backed persistent JSON cache keyed by source directory.

Copyright (c) 2026 Francesco Favi
License: MIT
"""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, cast

from zerofilesystem.classes.integrity_checker import IntegrityChecker
from zerofilesystem.classes.io import JsonHandler


class ManifestCache:
    """Manifest-backed persistent cache for arbitrary JSON-serializable data.

    Each source directory gets an isolated cache slot identified by a SHA-256
    hash of its resolved path. A call to :meth:`save` snapshots the directory
    via an integrity manifest and writes an arbitrary JSON blob. :meth:`load`
    returns the blob only if the directory is byte-for-byte identical to the
    snapshot; any addition, modification, or deletion causes a cache miss.

    Example::

        cache = ManifestCache(Path.home() / ".cache" / "myapp")
        cache.save(repo, data, filter_fn=lambda p: p.suffix == ".py")
        data = cache.load(repo, filter_fn=lambda p: p.suffix == ".py")
    """

    def __init__(self, cache_root: Path | str) -> None:
        self._root = Path(cache_root)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(
        self,
        source_dir: Path | str,
        *,
        blob_name: str = "data.json",
        filter_fn: Callable[[Path], bool] | None = None,
    ) -> Any | None:
        """Return the cached JSON blob if *source_dir* is unchanged, else ``None``.

        Args:
            source_dir: Directory whose state was snapshotted at :meth:`save` time.
            blob_name: Filename of the stored blob inside the cache slot.
            filter_fn: Same predicate used when :meth:`save` was called.  Only
                extra files that pass this predicate are treated as invalidating
                changes; untracked build artefacts are therefore ignored.

        Returns:
            Deserialized JSON object, or ``None`` on cache miss.
        """
        slot = self._slot(Path(source_dir))
        manifest_path = slot / "manifest.json"
        blob_path = slot / blob_name

        if not manifest_path.exists() or not blob_path.exists():
            return None

        try:
            manifest, algorithm = IntegrityChecker.load_manifest(manifest_path)
        except Exception:
            return None

        algo: Literal["md5", "sha1", "sha256", "sha512"] = cast(
            Literal["md5", "sha1", "sha256", "sha512"], algorithm
        )
        result = IntegrityChecker.verify_manifest(
            source_dir, manifest, algorithm=algo, check_extra=True
        )

        if result.missing or result.modified or result.errors:
            return None

        if result.extra:
            src = Path(source_dir)
            relevant = (
                [p for p in result.extra if filter_fn(src / p)]
                if filter_fn is not None
                else result.extra
            )
            if relevant:
                return None

        try:
            return JsonHandler.read_json(blob_path)
        except Exception:
            return None

    def save(
        self,
        source_dir: Path | str,
        data: Any,
        *,
        blob_name: str = "data.json",
        filter_fn: Callable[[Path], bool] | None = None,
    ) -> None:
        """Snapshot *source_dir* into a manifest and write *data* as a JSON blob.

        Args:
            source_dir: Directory to snapshot.
            data: Any JSON-serializable value.
            blob_name: Filename for the stored blob inside the cache slot.
            filter_fn: Optional predicate — only matching files enter the manifest.
        """
        src = Path(source_dir)
        slot = self._slot(src)

        manifest = IntegrityChecker.create_manifest(src, filter_fn=filter_fn)
        IntegrityChecker.save_manifest(manifest, slot / "manifest.json")
        JsonHandler.write_json(slot / blob_name, data)

    def changed_files(
        self,
        source_dir: Path | str,
        *,
        filter_fn: Callable[[Path], bool] | None = None,
    ) -> list[Path]:
        """Return files changed since the last :meth:`save`, or ``[]`` if no snapshot.

        Includes modified, missing, and new files that pass *filter_fn*.

        Args:
            source_dir: Directory to compare against the stored snapshot.
            filter_fn: Same predicate used at :meth:`save` time.

        Returns:
            List of absolute :class:`~pathlib.Path` objects.
        """
        src = Path(source_dir)
        slot = self._slot(src)
        manifest_path = slot / "manifest.json"

        if not manifest_path.exists():
            return []

        try:
            manifest, algorithm = IntegrityChecker.load_manifest(manifest_path)
        except Exception:
            return []

        algo: Literal["md5", "sha1", "sha256", "sha512"] = cast(
            Literal["md5", "sha1", "sha256", "sha512"], algorithm
        )
        result = IntegrityChecker.verify_manifest(src, manifest, algorithm=algo, check_extra=True)

        changed: list[Path] = [src / rel for rel in result.modified + result.missing]
        for rel in result.extra:
            p = src / rel
            if filter_fn is None or filter_fn(p):
                changed.append(p)

        return changed

    def clear(self, source_dir: Path | str) -> bool:
        """Delete the cache slot for *source_dir*.

        Args:
            source_dir: The directory whose cache slot should be removed.

        Returns:
            ``True`` if a slot existed and was deleted, ``False`` otherwise.
        """
        slot = self._slot(Path(source_dir))
        if not slot.exists():
            return False
        shutil.rmtree(slot)
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _slot(self, source_dir: Path) -> Path:
        key = hashlib.sha256(str(source_dir.resolve()).encode()).hexdigest()[:16]
        return self._root / key
