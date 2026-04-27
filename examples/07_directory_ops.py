#!/usr/bin/env python3
"""Example: Directory operations with zerofilesystem.

This example demonstrates:
- Copying directory trees
- Moving directories
- Syncing directories
- Temporary directories
- Directory size and file count
"""

import tempfile
from pathlib import Path

import zerofilesystem as zfs


def create_sample_tree(base: Path) -> None:
    """Create a sample directory tree."""
    (base / "src").mkdir()
    (base / "src" / "components").mkdir()
    (base / "config").mkdir()

    (base / "README.md").write_text("# Project")
    (base / "src" / "main.py").write_text("# Main")
    (base / "src" / "utils.py").write_text("# Utils")
    (base / "src" / "components" / "widget.py").write_text("# Widget")
    (base / "config" / "settings.json").write_text('{"debug": true}')


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        source = tmp_path / "source"
        source.mkdir()
        create_sample_tree(source)

        print(f"Source directory created at: {source}\n")

        # Copy Directory Tree

        print("=== Copy Directory Tree ===\n")

        dest_copy = tmp_path / "copy"
        zfs.copy_tree(source, dest_copy)

        print(f"Copied to: {dest_copy}")
        print("\nCopied files:")
        for f in dest_copy.rglob("*"):
            if f.is_file():
                print(f"  - {f.relative_to(dest_copy)}")

        # Copy with Filter

        print("\n=== Copy with Filter (Python files only) ===\n")

        dest_filtered = tmp_path / "py_only"
        zfs.copy_tree(
            source,
            dest_filtered,
            filter_fn=lambda p: p.suffix == ".py",
        )

        print("Filtered copy (only .py files):")
        for f in dest_filtered.rglob("*"):
            if f.is_file():
                print(f"  - {f.relative_to(dest_filtered)}")

        # Sync Directories

        print("\n=== Sync Directories ===\n")

        sync_source = tmp_path / "sync_source"
        sync_dest = tmp_path / "sync_dest"
        sync_source.mkdir()
        sync_dest.mkdir()

        # Create source files
        (sync_source / "file1.txt").write_text("Source 1")
        (sync_source / "file2.txt").write_text("Source 2")
        (sync_source / "file3.txt").write_text("Source 3")

        # Create dest with some existing files
        (sync_dest / "file1.txt").write_text("Old content")
        (sync_dest / "extra.txt").write_text("Extra file")

        print("Before sync:")
        print(f"  Source: {[f.name for f in sync_source.iterdir()]}")
        print(f"  Dest: {[f.name for f in sync_dest.iterdir()]}")

        # Sync (without deleting extra files)
        zfs.sync_dirs(sync_source, sync_dest)

        print("\nAfter sync (without delete_extra):")
        print(f"  Dest: {[f.name for f in sync_dest.iterdir()]}")

        # Reset dest
        for f in sync_dest.iterdir():
            f.unlink()
        (sync_dest / "file1.txt").write_text("Old content")
        (sync_dest / "extra.txt").write_text("Extra file")

        # Sync with delete_extra
        zfs.sync_dirs(sync_source, sync_dest, delete_extra=True)

        print("\nAfter sync (with delete_extra):")
        print(f"  Dest: {[f.name for f in sync_dest.iterdir()]}")

        # Temporary Directory

        print("\n=== Temporary Directory ===\n")

        with zfs.temp_directory(prefix="myapp_") as temp_dir:
            print(f"Temp dir created: {temp_dir}")
            print(f"Exists: {temp_dir.exists()}")

            # Create some files
            (temp_dir / "temp_file.txt").write_text("Temporary content")
            print(f"Files in temp: {list(temp_dir.iterdir())}")

        print(f"Temp dir exists after context: {temp_dir.exists()}")
        print("(Automatically cleaned up!)")

        # Keep temp directory
        print("\n--- Keeping temp directory ---")
        with zfs.temp_directory(prefix="keep_", cleanup=False) as keep_dir:
            (keep_dir / "data.txt").write_text("Keep me")
            print(f"Created: {keep_dir}")

        print(f"Still exists: {keep_dir.exists()}")
        # Clean up manually
        import shutil

        shutil.rmtree(keep_dir)

        # Directory size and file count
        print("\n=== Directory Size and File Count ===\n")

        size = zfs.tree_size(source)
        count = zfs.tree_file_count(source)

        print("Source directory:")
        print(f"  Total size: {size} bytes")
        print(f"  File count: {count} files")

        # Move Directory Tree

        print("\n=== Move Directory Tree ===\n")

        move_source = tmp_path / "move_source"
        move_source.mkdir()
        (move_source / "data.txt").write_text("Data to move")
        (move_source / "subdir").mkdir()
        (move_source / "subdir" / "nested.txt").write_text("Nested")

        move_dest = tmp_path / "move_dest"

        print("Before move:")
        print(f"  Source exists: {move_source.exists()}")
        print(f"  Dest exists: {move_dest.exists()}")

        zfs.move_tree(move_source, move_dest)

        print("\nAfter move:")
        print(f"  Source exists: {move_source.exists()}")
        print(f"  Dest exists: {move_dest.exists()}")

        print("\nMoved files:")
        for f in move_dest.rglob("*"):
            if f.is_file():
                print(f"  - {f.relative_to(move_dest)}")

        # Flatten Directory Tree

        print("\n=== Flatten Directory Tree ===\n")

        flat_source = tmp_path / "flat_source"
        flat_source.mkdir()
        (flat_source / "a").mkdir()
        (flat_source / "a" / "b").mkdir()
        (flat_source / "file1.txt").write_text("Root file")
        (flat_source / "a" / "file2.txt").write_text("Level 1")
        (flat_source / "a" / "b" / "file3.txt").write_text("Level 2")

        flat_dest = tmp_path / "flat_dest"

        zfs.flatten_tree(flat_source, flat_dest)

        print("Flattened structure:")
        for f in sorted(flat_dest.iterdir()):
            if f.is_file():
                print(f"  - {f.name}")

        print("\n=== Done! ===")


if __name__ == "__main__":
    main()
