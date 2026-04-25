"""Integrity verification with manifest and directory hashing."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from zerofilesystem._platform import Pathish
from zerofilesystem.classes.exceptions import HashMismatchError
from zerofilesystem.classes.files import FileHasher


@dataclass
class ManifestEntry:
    """Entry in a manifest file."""

    path: str
    hash: str
    size: int
    modified: float

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "hash": self.hash,
            "size": self.size,
            "modified": self.modified,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ManifestEntry:
        return cls(
            path=d["path"],
            hash=d["hash"],
            size=d["size"],
            modified=d["modified"],
        )


@dataclass
class VerificationResult:
    """Result of integrity verification."""

    valid: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not (self.missing or self.extra or self.modified or self.errors)

    def __str__(self) -> str:
        return (
            f"VerificationResult(valid={len(self.valid)}, "
            f"missing={len(self.missing)}, extra={len(self.extra)}, "
            f"modified={len(self.modified)}, errors={len(self.errors)})"
        )


class IntegrityChecker:
    """Integrity verification with manifest and directory hashing."""

    @staticmethod
    def directory_hash(
        path: Pathish,
        algorithm: Literal["md5", "sha1", "sha256", "sha512"] = "sha256",
        filter_fn: Callable[[Path], bool] | None = None,
    ) -> str:
        """
        Calculate a hash for an entire directory tree.

        Args:
            path: Directory path
            algorithm: Hash algorithm
            filter_fn: Optional filter for files to include

        Returns:
            Hexadecimal hash representing the directory state

        Note:
            Hash includes file paths, sizes, and content hashes.
            Changes to any file will change the directory hash.
        """
        p = Path(path)
        h = hashlib.new(algorithm)

        # Collect all files and sort for deterministic order
        files = []
        for root, dirs, filenames in os.walk(p):
            dirs.sort()  # Sort for deterministic traversal
            for f in sorted(filenames):
                file_path = Path(root) / f
                if filter_fn and not filter_fn(file_path):
                    continue
                rel_path = file_path.relative_to(p)
                files.append((str(rel_path), file_path))

        # Hash each file's path, size, and content hash
        for rel_path_str, file_path in files:
            try:
                file_stat = file_path.stat()
                file_hash = FileHasher.file_hash(file_path, algo=algorithm)

                # Include path, size, and hash in directory hash
                h.update(rel_path_str.encode())
                h.update(str(file_stat.st_size).encode())
                h.update(file_hash.encode())
            except (
                OSError
            ):  # pragma: no cover -- best-effort: skip files we can't stat during a walk
                pass

        return h.hexdigest()

    @staticmethod
    def create_manifest(
        path: Pathish,
        algorithm: Literal["md5", "sha1", "sha256", "sha512"] = "sha256",
        filter_fn: Callable[[Path], bool] | None = None,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> dict[str, ManifestEntry]:
        """
        Create a manifest of all files in a directory.

        Args:
            path: Directory path
            algorithm: Hash algorithm
            filter_fn: Optional filter for files
            progress_callback: Optional callback(file_path, current, total)

        Returns:
            Dictionary mapping relative paths to ManifestEntry objects
        """
        p = Path(path)
        manifest: dict[str, ManifestEntry] = {}

        # Count files for progress
        files_list = []
        for root, _dirs, files in os.walk(p):
            for f in files:
                file_path = Path(root) / f
                if filter_fn and not filter_fn(file_path):
                    continue
                files_list.append(file_path)

        total = len(files_list)

        for i, file_path in enumerate(files_list):
            try:
                rel_path = str(file_path.relative_to(p))
                stat = file_path.stat()
                file_hash = FileHasher.file_hash(file_path, algo=algorithm)

                manifest[rel_path] = ManifestEntry(
                    path=rel_path,
                    hash=file_hash,
                    size=stat.st_size,
                    modified=stat.st_mtime,
                )

                if progress_callback:
                    progress_callback(rel_path, i + 1, total)

            except OSError:  # pragma: no cover -- skip files we can't stat during walk
                pass

        return manifest

    @staticmethod
    def save_manifest(
        manifest: dict[str, ManifestEntry],
        output_path: Pathish,
        algorithm: str = "sha256",
    ) -> Path:
        """
        Save manifest to JSON file.

        Args:
            manifest: Manifest dictionary
            output_path: Output file path
            algorithm: Hash algorithm used (stored in manifest)

        Returns:
            Path to saved manifest file
        """
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "algorithm": algorithm,
            "created": datetime.now().isoformat(),
            "files": {k: v.to_dict() for k, v in manifest.items()},
        }

        out.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        return out

    @staticmethod
    def load_manifest(manifest_path: Pathish) -> tuple[dict[str, ManifestEntry], str]:
        """
        Load manifest from JSON file.

        Args:
            manifest_path: Path to manifest file

        Returns:
            Tuple of (manifest dict, algorithm used)
        """
        data = json.loads(Path(manifest_path).read_text())

        algorithm = data.get("algorithm", "sha256")
        manifest = {k: ManifestEntry.from_dict(v) for k, v in data["files"].items()}

        return manifest, algorithm

    @staticmethod
    def verify_manifest(
        directory: Pathish,
        manifest: dict[str, ManifestEntry],
        algorithm: Literal["md5", "sha1", "sha256", "sha512"] = "sha256",
        check_extra: bool = True,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> VerificationResult:
        """
        Verify directory against manifest.

        Args:
            directory: Directory to verify
            manifest: Manifest to verify against
            algorithm: Hash algorithm
            check_extra: Also report files not in manifest
            progress_callback: Optional callback(file_path, current, total)

        Returns:
            VerificationResult with details
        """
        p = Path(directory)
        result = VerificationResult()

        # Collect actual files
        actual_files: set[str] = set()
        for root, _dirs, files in os.walk(p):
            for f in files:
                file_path = Path(root) / f
                rel_path = str(file_path.relative_to(p))
                actual_files.add(rel_path)

        manifest_files = set(manifest.keys())
        total = len(manifest_files)

        # Check manifest entries
        for i, (rel_path, entry) in enumerate(manifest.items()):
            file_path = p / rel_path

            if progress_callback:
                progress_callback(rel_path, i + 1, total)

            if rel_path not in actual_files:
                result.missing.append(rel_path)
                continue

            try:
                actual_hash = FileHasher.file_hash(file_path, algo=algorithm)
                if actual_hash != entry.hash:
                    result.modified.append(rel_path)
                else:
                    result.valid.append(rel_path)
            except Exception as e:
                result.errors.append((rel_path, str(e)))

        # Check for extra files
        if check_extra:
            extra = actual_files - manifest_files
            result.extra.extend(sorted(extra))

        return result

    @staticmethod
    def verify_file(
        path: Pathish,
        expected_hash: str,
        algorithm: Literal["md5", "sha1", "sha256", "sha512"] = "sha256",
    ) -> bool:
        """
        Verify a single file against expected hash.

        Args:
            path: File path
            expected_hash: Expected hash value
            algorithm: Hash algorithm

        Returns:
            True if hash matches

        Raises:
            HashMismatchError: If hash doesn't match
        """
        actual = FileHasher.file_hash(path, algo=algorithm)
        if actual != expected_hash:
            raise HashMismatchError(path, expected_hash, actual, algorithm)
        return True

    @staticmethod
    def compare_directories(
        dir1: Pathish,
        dir2: Pathish,
        algorithm: Literal["md5", "sha1", "sha256", "sha512"] = "sha256",
    ) -> VerificationResult:
        """
        Compare two directories for differences.

        Args:
            dir1: First directory
            dir2: Second directory
            algorithm: Hash algorithm

        Returns:
            VerificationResult where:
            - missing: files in dir1 but not in dir2
            - extra: files in dir2 but not in dir1
            - modified: files with different content
            - valid: files with same content
        """
        manifest1 = IntegrityChecker.create_manifest(dir1, algorithm=algorithm)
        manifest2 = IntegrityChecker.create_manifest(dir2, algorithm=algorithm)

        result = VerificationResult()

        files1 = set(manifest1.keys())
        files2 = set(manifest2.keys())

        # Missing in dir2
        result.missing = sorted(files1 - files2)

        # Extra in dir2
        result.extra = sorted(files2 - files1)

        # Compare common files
        common = files1 & files2
        for rel_path in sorted(common):
            if manifest1[rel_path].hash == manifest2[rel_path].hash:
                result.valid.append(rel_path)
            else:
                result.modified.append(rel_path)

        return result

    @staticmethod
    def snapshot_hash(
        path: Pathish,
        algorithm: Literal["md5", "sha1", "sha256", "sha512"] = "sha256",
    ) -> str:
        """
        Create a quick snapshot hash for change detection.

        This is faster than full directory_hash as it only uses
        file paths, sizes, and modification times (not content).

        Args:
            path: Directory path
            algorithm: Hash algorithm

        Returns:
            Hash representing directory state
        """
        p = Path(path)
        h = hashlib.new(algorithm)

        for root, dirs, files in os.walk(p):
            dirs.sort()
            for f in sorted(files):
                file_path = Path(root) / f
                try:
                    stat = file_path.stat()
                    rel_path = str(file_path.relative_to(p))

                    # Only use path, size, and mtime (no content)
                    h.update(rel_path.encode())
                    h.update(str(stat.st_size).encode())
                    h.update(str(int(stat.st_mtime)).encode())
                except OSError:
                    pass

        return h.hexdigest()
