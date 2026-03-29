#!/usr/bin/env python3
"""Example: Archive operations (ZIP and TAR) with zerofilesystem.

This example demonstrates:
- Creating ZIP archives
- Creating TAR archives with various compressions
- Extracting archives
- Listing archive contents
- Filtering files during archiving
"""

import tempfile
from pathlib import Path

import zerofilesystem as zo


def create_sample_project(base: Path) -> None:
    """Create sample files for archiving."""
    (base / "src").mkdir()
    (base / "docs").mkdir()
    (base / "tests").mkdir()

    (base / "README.md").write_text("# Sample Project\n\nA demo project.")
    (base / "src" / "main.py").write_text("print('Hello World')")
    (base / "src" / "utils.py").write_text("def helper(): pass")
    (base / "docs" / "guide.md").write_text("# User Guide")
    (base / "tests" / "test_main.py").write_text("def test_hello(): pass")

    # Create a binary file
    (base / "data.bin").write_bytes(bytes(range(256)))


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        source_dir = tmp_path / "project"
        source_dir.mkdir()
        create_sample_project(source_dir)

        print(f"Sample project created at: {source_dir}\n")

        # =========================================================================
        # CREATE ZIP ARCHIVE
        # =========================================================================

        print("=== Create ZIP Archive ===\n")

        zip_file = tmp_path / "project.zip"
        zo.create_zip(source_dir, zip_file)

        print(f"Created: {zip_file}")
        print(f"Size: {zip_file.stat().st_size} bytes")

        # List contents
        print("\nContents:")
        for item in zo.list_archive(zip_file):
            print(f"  - {item}")

        # =========================================================================
        # CREATE TAR ARCHIVE (NO COMPRESSION)
        # =========================================================================

        print("\n=== Create TAR Archive ===\n")

        tar_file = tmp_path / "project.tar"
        zo.create_tar(source_dir, tar_file)

        print(f"Created: {tar_file}")
        print(f"Size: {tar_file.stat().st_size} bytes")

        # =========================================================================
        # CREATE COMPRESSED TAR ARCHIVES
        # =========================================================================

        print("\n=== Create Compressed TAR Archives ===\n")

        # GZIP compression
        tar_gz = tmp_path / "project.tar.gz"
        zo.create_tar(source_dir, tar_gz, compression="gz")
        print(f"tar.gz: {tar_gz.stat().st_size} bytes")

        # BZIP2 compression
        tar_bz2 = tmp_path / "project.tar.bz2"
        zo.create_tar(source_dir, tar_bz2, compression="bz2")
        print(f"tar.bz2: {tar_bz2.stat().st_size} bytes")

        # XZ compression (best ratio)
        tar_xz = tmp_path / "project.tar.xz"
        zo.create_tar(source_dir, tar_xz, compression="xz")
        print(f"tar.xz: {tar_xz.stat().st_size} bytes")

        # Compare sizes
        print("\nCompression comparison:")
        print(f"  Uncompressed TAR: {tar_file.stat().st_size} bytes")
        print(f"  GZIP:             {tar_gz.stat().st_size} bytes")
        print(f"  BZIP2:            {tar_bz2.stat().st_size} bytes")
        print(f"  XZ:               {tar_xz.stat().st_size} bytes")

        # =========================================================================
        # EXTRACT ZIP ARCHIVE
        # =========================================================================

        print("\n=== Extract ZIP Archive ===\n")

        extract_zip_dir = tmp_path / "extracted_zip"
        zo.extract_zip(zip_file, extract_zip_dir)

        print(f"Extracted to: {extract_zip_dir}")
        print("\nExtracted files:")
        for f in extract_zip_dir.rglob("*"):
            if f.is_file():
                print(f"  - {f.relative_to(extract_zip_dir)}")

        # =========================================================================
        # EXTRACT TAR ARCHIVE
        # =========================================================================

        print("\n=== Extract TAR.GZ Archive ===\n")

        extract_tar_dir = tmp_path / "extracted_tar"
        zo.extract_tar(tar_gz, extract_tar_dir)

        print(f"Extracted to: {extract_tar_dir}")
        print("\nExtracted files:")
        for f in extract_tar_dir.rglob("*"):
            if f.is_file():
                print(f"  - {f.relative_to(extract_tar_dir)}")

        # =========================================================================
        # AUTO-DETECT ARCHIVE FORMAT
        # =========================================================================

        print("\n=== Auto-Detect Archive Format ===\n")

        extract_auto_dir = tmp_path / "extracted_auto"

        # extract() auto-detects the format
        zo.extract(zip_file, extract_auto_dir / "from_zip")
        zo.extract(tar_gz, extract_auto_dir / "from_tar_gz")
        zo.extract(tar_xz, extract_auto_dir / "from_tar_xz")

        print("Auto-extracted archives:")
        print(f"  ZIP extracted: {(extract_auto_dir / 'from_zip').exists()}")
        print(f"  TAR.GZ extracted: {(extract_auto_dir / 'from_tar_gz').exists()}")
        print(f"  TAR.XZ extracted: {(extract_auto_dir / 'from_tar_xz').exists()}")

        # =========================================================================
        # FILTERED ARCHIVING
        # =========================================================================

        print("\n=== Filtered Archiving ===\n")

        # Only archive Python files
        py_only_zip = tmp_path / "python_only.zip"
        zo.create_zip(
            source_dir,
            py_only_zip,
            filter_fn=lambda p: p.suffix == ".py",
        )

        print("Python-only archive contents:")
        for item in zo.list_archive(py_only_zip):
            print(f"  - {item}")

        # Exclude test files
        no_tests_zip = tmp_path / "no_tests.zip"
        zo.create_zip(
            source_dir,
            no_tests_zip,
            filter_fn=lambda p: "test" not in p.name.lower(),
        )

        print("\nArchive without tests:")
        for item in zo.list_archive(no_tests_zip):
            print(f"  - {item}")

        # =========================================================================
        # FILTERED EXTRACTION
        # =========================================================================

        print("\n=== Filtered Extraction ===\n")

        filtered_extract = tmp_path / "filtered_extract"

        # Only extract markdown files
        zo.extract_zip(
            zip_file,
            filtered_extract,
            filter_fn=lambda name: name.endswith(".md"),
        )

        print("Extracted only .md files:")
        for f in filtered_extract.rglob("*"):
            if f.is_file():
                print(f"  - {f.relative_to(filtered_extract)}")

        # =========================================================================
        # VERIFY ARCHIVE INTEGRITY
        # =========================================================================

        print("\n=== Verify Archive Roundtrip ===\n")

        # Check that extracted content matches original
        # Note: archive preserves the source directory name as top-level folder
        original_main = (source_dir / "src" / "main.py").read_text()
        extracted_main = (extract_zip_dir / "project" / "src" / "main.py").read_text()

        print(f"Original main.py:  {repr(original_main)}")
        print(f"Extracted main.py: {repr(extracted_main)}")
        print(f"Content matches: {original_main == extracted_main}")

        print("\n=== Done! ===")


if __name__ == "__main__":
    main()
