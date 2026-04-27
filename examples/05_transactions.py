#!/usr/bin/env python3
"""Example: File transactions with rollback using zerofilesystem.

This example demonstrates:
- Atomic multi-file operations
- Automatic rollback on errors
- Explicit commit and rollback
- Safe file updates
"""

import tempfile
from pathlib import Path

import zerofilesystem as zfs


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # Basic Transaction

        print("=== Basic Transaction ===\n")

        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"

        # Write multiple files atomically
        with zfs.FileTransaction() as tx:
            tx.write_text(file1, "Content for file 1")
            tx.write_text(file2, "Content for file 2")
            # Commit happens automatically on successful exit

        print(f"File 1: {file1.read_text()}")
        print(f"File 2: {file2.read_text()}")

        # Automatic Rollback on Error

        print("\n=== Automatic Rollback on Error ===\n")

        rollback_file1 = tmp_path / "rollback1.txt"
        rollback_file2 = tmp_path / "rollback2.txt"

        # Create original files
        rollback_file1.write_text("Original 1")
        rollback_file2.write_text("Original 2")

        print("Before transaction:")
        print(f"  File 1: {rollback_file1.read_text()}")
        print(f"  File 2: {rollback_file2.read_text()}")

        try:
            with zfs.FileTransaction() as tx:
                tx.write_text(rollback_file1, "Modified 1")
                tx.write_text(rollback_file2, "Modified 2")
                # Simulate an error
                raise ValueError("Something went wrong!")
        except ValueError as e:
            print(f"\nError occurred: {e}")
            print("Transaction automatically rolled back!")

        print("\nAfter failed transaction (files restored):")
        print(f"  File 1: {rollback_file1.read_text()}")
        print(f"  File 2: {rollback_file2.read_text()}")

        # Creating New Files

        print("\n=== Creating New Files in Transaction ===\n")

        new_file = tmp_path / "new_file.txt"

        print(f"File exists before: {new_file.exists()}")

        try:
            with zfs.FileTransaction() as tx:
                tx.write_text(new_file, "New content")
                print(f"File would be created: {new_file}")
                raise ValueError("Abort!")
        except ValueError:
            pass

        print(f"File exists after rollback: {new_file.exists()}")
        print("New file was NOT created because transaction was rolled back!")

        # Explicit commit and rollback
        print("\n=== Explicit Commit ===\n")

        explicit_file = tmp_path / "explicit.txt"

        tx = zfs.FileTransaction()
        tx.write_text(explicit_file, "Explicitly committed content")

        print("Changes are staged but not committed yet...")
        print(f"File exists: {explicit_file.exists()}")

        tx.commit()
        print("Committed!")
        print(f"File exists: {explicit_file.exists()}")
        print(f"Content: {explicit_file.read_text()}")

        print("\n=== Explicit Rollback ===\n")

        explicit_file2 = tmp_path / "explicit2.txt"

        tx2 = zfs.FileTransaction()
        tx2.write_text(explicit_file2, "This will be rolled back")
        tx2.rollback()

        print(f"File exists after rollback: {explicit_file2.exists()}")

        # File Deletion in Transaction

        print("\n=== File Deletion in Transaction ===\n")

        to_delete = tmp_path / "to_delete.txt"
        to_delete.write_text("Important content")

        print(f"File exists before: {to_delete.exists()}")
        print(f"Content: {to_delete.read_text()}")

        try:
            with zfs.FileTransaction() as tx:
                tx.delete_file(to_delete)
                print("File scheduled for deletion...")
                raise ValueError("Oops, changed my mind!")
        except ValueError:
            pass

        print(f"File exists after rollback: {to_delete.exists()}")
        print(f"Content restored: {to_delete.read_text()}")

        # File Copy in Transaction

        print("\n=== File Copy in Transaction ===\n")

        source = tmp_path / "source.txt"
        dest = tmp_path / "destination.txt"
        source.write_text("Source content to copy")

        with zfs.FileTransaction() as tx:
            tx.copy_file(source, dest)

        print(f"Source: {source.read_text()}")
        print(f"Destination: {dest.read_text()}")
        print("Files match:", source.read_text() == dest.read_text())

        # Complex Multi-File Operation

        print("\n=== Complex Multi-File Operation ===\n")

        # Simulate a database migration with multiple files
        config = tmp_path / "config.json"
        data = tmp_path / "data.json"
        schema = tmp_path / "schema.json"

        # Initial state
        zfs.write_json(config, {"version": 1})
        zfs.write_json(data, {"users": []})
        zfs.write_json(schema, {"fields": ["id", "name"]})

        print("Before migration:")
        print(f"  Config: {zfs.read_json(config)}")
        print(f"  Data: {zfs.read_json(data)}")
        print(f"  Schema: {zfs.read_json(schema)}")

        # Migrate atomically
        with zfs.FileTransaction() as tx:
            # Update all files together
            tx.write_text(config, zfs.read_text(config).replace('"version": 1', '"version": 2'))
            new_data = zfs.read_json(data)
            new_data["users"].append({"id": 1, "name": "Alice"})
            zfs.write_json(data, new_data)  # This writes directly, not in transaction!

            # Better approach: use transaction for all files
            tx.write_text(
                schema,
                '{"fields": ["id", "name", "email"]}',
            )

        print("\nAfter migration:")
        print(f"  Config: {zfs.read_json(config)}")
        print(f"  Data: {zfs.read_json(data)}")
        print(f"  Schema: {zfs.read_json(schema)}")

        print("\n=== Done! ===")


if __name__ == "__main__":
    main()
