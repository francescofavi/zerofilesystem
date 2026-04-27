"""Archive handling: tar, tar.gz, zip."""

from __future__ import annotations

import os
import shutil
import tarfile
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from zerofilesystem._platform import Pathish
from zerofilesystem.classes.exceptions import ArchiveError


class ArchiveHandler:
    """Archive creation and extraction: tar, tar.gz, tar.bz2, zip."""

    @staticmethod
    def create_tar(
        source: Pathish,
        output: Pathish,
        *,
        compression: Literal["none", "gz", "bz2", "xz"] = "none",
        filter_fn: Callable[[Path], bool] | None = None,
        base_dir: str | None = None,
    ) -> Path:
        """
        Create a tar archive.

        Args:
            source: Source file or directory
            output: Output archive path
            compression: Compression type
            filter_fn: Optional filter function
            base_dir: Base directory name inside archive (default: source name)

        Returns:
            Path to created archive
        """
        src_p = Path(source)
        out_p = Path(output)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        mode_map = {
            "none": "w",
            "gz": "w:gz",
            "bz2": "w:bz2",
            "xz": "w:xz",
        }

        mode = mode_map.get(compression, "w")
        arcname_base = base_dir or src_p.name

        try:
            with tarfile.open(out_p, mode) as tar:  # type: ignore[call-overload]
                if src_p.is_file():
                    if filter_fn is None or filter_fn(src_p):
                        tar.add(src_p, arcname=arcname_base)
                else:
                    for root, _dirs, files in os.walk(src_p):
                        root_path = Path(root)
                        rel_root = root_path.relative_to(src_p)

                        for f in files:
                            file_path = root_path / f
                            if filter_fn and not filter_fn(file_path):
                                continue
                            arcname = str(Path(arcname_base) / rel_root / f)
                            tar.add(file_path, arcname=arcname)

            return out_p

        except Exception as e:  # pragma: no cover -- mid-write filesystem failure
            raise ArchiveError(
                f"Failed to create tar archive: {e}",
                path=output,
                archive_type=f"tar.{compression}" if compression != "none" else "tar",
                cause=e,
            ) from e

    @staticmethod
    def create_zip(
        source: Pathish,
        output: Pathish,
        *,
        compression: Literal["stored", "deflated", "bzip2", "lzma"] = "deflated",
        filter_fn: Callable[[Path], bool] | None = None,
        base_dir: str | None = None,
    ) -> Path:
        """
        Create a zip archive.

        Args:
            source: Source file or directory
            output: Output archive path
            compression: Compression method
            filter_fn: Optional filter function
            base_dir: Base directory name inside archive

        Returns:
            Path to created archive
        """
        src_p = Path(source)
        out_p = Path(output)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        compression_map = {
            "stored": zipfile.ZIP_STORED,
            "deflated": zipfile.ZIP_DEFLATED,
            "bzip2": zipfile.ZIP_BZIP2,
            "lzma": zipfile.ZIP_LZMA,
        }

        comp = compression_map.get(compression, zipfile.ZIP_DEFLATED)
        arcname_base = base_dir or src_p.name

        try:
            with zipfile.ZipFile(out_p, "w", compression=comp) as zf:
                if src_p.is_file():
                    if filter_fn is None or filter_fn(src_p):
                        zf.write(src_p, arcname=arcname_base)
                else:
                    for root, _dirs, files in os.walk(src_p):
                        root_path = Path(root)
                        rel_root = root_path.relative_to(src_p)

                        for f in files:
                            file_path = root_path / f
                            if filter_fn and not filter_fn(file_path):
                                continue
                            arcname = str(Path(arcname_base) / rel_root / f)
                            zf.write(file_path, arcname=arcname)

            return out_p

        except Exception as e:  # pragma: no cover -- mid-write filesystem failure
            raise ArchiveError(
                f"Failed to create zip archive: {e}",
                path=output,
                archive_type="zip",
                cause=e,
            ) from e

    @staticmethod
    def extract_tar(
        archive: Pathish,
        destination: Pathish,
        *,
        filter_fn: Callable[[str], bool] | None = None,
        strip_components: int = 0,
    ) -> Path:
        """
        Extract a tar archive.

        Args:
            archive: Archive path
            destination: Extraction destination
            filter_fn: Optional filter for archive members (by name)
            strip_components: Strip leading path components

        Returns:
            Path to extraction directory
        """
        arc_p = Path(archive)
        dst_p = Path(destination)
        dst_p.mkdir(parents=True, exist_ok=True)

        try:
            with tarfile.open(arc_p, "r:*") as tar:
                members = tar.getmembers()

                for member in members:
                    # Apply filter
                    if filter_fn and not filter_fn(member.name):
                        continue

                    # Strip components
                    if strip_components > 0:
                        parts = Path(member.name).parts[strip_components:]
                        if not parts:
                            continue
                        member.name = str(Path(*parts))

                    # Security check - prevent path traversal
                    member_path = dst_p / member.name
                    try:
                        member_path.resolve().relative_to(dst_p.resolve())
                    except ValueError:
                        continue  # Path traversal attempt

                    tar.extract(member, dst_p, filter="data")

            return dst_p

        except Exception as e:
            raise ArchiveError(
                f"Failed to extract tar archive: {e}",
                path=archive,
                archive_type="tar",
                cause=e,
            ) from e

    @staticmethod
    def extract_zip(
        archive: Pathish,
        destination: Pathish,
        *,
        filter_fn: Callable[[str], bool] | None = None,
        strip_components: int = 0,
    ) -> Path:
        """
        Extract a zip archive.

        Args:
            archive: Archive path
            destination: Extraction destination
            filter_fn: Optional filter for archive members
            strip_components: Strip leading path components

        Returns:
            Path to extraction directory
        """
        arc_p = Path(archive)
        dst_p = Path(destination)
        dst_p.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(arc_p, "r") as zf:
                for info in zf.infolist():
                    # Apply filter
                    if filter_fn and not filter_fn(info.filename):
                        continue

                    # Strip components
                    if strip_components > 0:
                        parts = Path(info.filename).parts[strip_components:]
                        if not parts:
                            continue
                        new_name = str(Path(*parts))
                    else:
                        new_name = info.filename

                    # Security check - prevent path traversal
                    member_path = dst_p / new_name
                    try:
                        member_path.resolve().relative_to(dst_p.resolve())
                    except ValueError:
                        continue  # Path traversal attempt

                    # Extract with new name
                    if info.is_dir():
                        member_path.mkdir(parents=True, exist_ok=True)
                    else:
                        member_path.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(info) as src, open(member_path, "wb") as dst:
                            shutil.copyfileobj(src, dst)

            return dst_p

        except Exception as e:
            raise ArchiveError(
                f"Failed to extract zip archive: {e}",
                path=archive,
                archive_type="zip",
                cause=e,
            ) from e

    @staticmethod
    def list_archive(archive: Pathish) -> list[str]:
        """
        List contents of an archive.

        Args:
            archive: Archive path

        Returns:
            List of file names in archive
        """
        arc_p = Path(archive)

        if arc_p.suffix == ".zip":
            with zipfile.ZipFile(arc_p, "r") as zf:
                return zf.namelist()
        else:
            with tarfile.open(arc_p, "r:*") as tar:
                return tar.getnames()

    @staticmethod
    def detect_archive_type(archive: Pathish) -> str | None:
        """
        Detect archive type from file signature.

        Args:
            archive: Archive path

        Returns:
            Archive type string or None if unknown
        """
        arc_p = Path(archive)

        with open(arc_p, "rb") as f:
            header = f.read(262)

        # Check signatures
        if header[:4] == b"PK\x03\x04":
            return "zip"
        if header[:2] == b"\x1f\x8b":
            return "tar.gz"
        if header[:3] == b"BZh":
            return "tar.bz2"
        if header[:6] == b"\xfd7zXZ\x00":
            return "tar.xz"
        if b"ustar" in header[257:262]:
            return "tar"

        return None

    @staticmethod
    def extract(
        archive: Pathish,
        destination: Pathish,
        **kwargs,
    ) -> Path:
        """
        Auto-detect archive type and extract.

        Args:
            archive: Archive path
            destination: Extraction destination
            **kwargs: Additional arguments for extract functions

        Returns:
            Path to extraction directory
        """
        arc_type = ArchiveHandler.detect_archive_type(archive)

        if arc_type == "zip":
            return ArchiveHandler.extract_zip(archive, destination, **kwargs)
        elif arc_type in ("tar", "tar.gz", "tar.bz2", "tar.xz"):
            return ArchiveHandler.extract_tar(archive, destination, **kwargs)
        else:
            # Try tar first, then zip
            try:
                return ArchiveHandler.extract_tar(archive, destination, **kwargs)
            except Exception:
                return ArchiveHandler.extract_zip(archive, destination, **kwargs)
