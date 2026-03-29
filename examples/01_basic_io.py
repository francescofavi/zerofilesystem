#!/usr/bin/env python3
"""Example: Basic file I/O operations with zerofilesystem.

This example demonstrates:
- Reading and writing text files
- Reading and writing binary files
- Atomic writes for data safety
- Automatic parent directory creation
"""

import tempfile
from pathlib import Path

import zerofilesystem as zo


def main() -> None:
    # Create a temporary directory for our examples
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # =========================================================================
        # TEXT FILE OPERATIONS
        # =========================================================================

        print("=== Text File Operations ===\n")

        # Write a simple text file
        text_file = tmp_path / "hello.txt"
        zo.write_text(text_file, "Hello, World!")
        print(f"Created: {text_file}")

        # Read it back
        content = zo.read_text(text_file)
        print(f"Content: {content}")

        # Write with different encoding
        italian_file = tmp_path / "italian.txt"
        zo.write_text(italian_file, "Ciao, come stai? Bene grazie!", encoding="utf-8")
        print(f"\nCreated Italian file: {italian_file}")

        # Write multiline content
        multiline_file = tmp_path / "multiline.txt"
        zo.write_text(
            multiline_file,
            """Line 1: Introduction
Line 2: Main content
Line 3: Conclusion""",
        )
        print(f"Created multiline file: {multiline_file}")

        # =========================================================================
        # AUTOMATIC DIRECTORY CREATION
        # =========================================================================

        print("\n=== Automatic Directory Creation ===\n")

        # Write to a deeply nested path - directories are created automatically
        nested_file = tmp_path / "deep" / "nested" / "path" / "file.txt"
        zo.write_text(nested_file, "This file is deeply nested!")
        print(f"Created nested file: {nested_file}")
        print("Parent directories were created automatically!")

        # =========================================================================
        # BINARY FILE OPERATIONS
        # =========================================================================

        print("\n=== Binary File Operations ===\n")

        # Write binary data
        binary_file = tmp_path / "data.bin"
        binary_data = bytes(range(256))  # All bytes from 0x00 to 0xFF
        zo.write_bytes(binary_file, binary_data)
        print(f"Created binary file: {binary_file}")
        print(f"Size: {len(binary_data)} bytes")

        # Read it back
        read_data = zo.read_bytes(binary_file)
        assert read_data == binary_data
        print("Binary data verified!")

        # Simulate an image header (PNG magic bytes)
        fake_image = tmp_path / "fake.png"
        png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        zo.write_bytes(fake_image, png_header)
        print(f"\nCreated fake PNG: {fake_image}")

        # =========================================================================
        # ATOMIC WRITES
        # =========================================================================

        print("\n=== Atomic Writes (Default) ===\n")

        # Atomic writes ensure that if something goes wrong during write,
        # the original file is not corrupted (write to temp, then rename)

        important_file = tmp_path / "important.txt"

        # First write
        zo.write_text(important_file, "Original important data")
        print(f"Created important file: {important_file}")

        # Update atomically (default behavior)
        zo.write_text(important_file, "Updated important data", atomic=True)
        print("Updated atomically - no risk of data corruption!")

        # Verify
        print(f"Content: {zo.read_text(important_file)}")

        # Non-atomic write (faster but riskier)
        zo.write_text(important_file, "Fast update", atomic=False)
        print("\nNon-atomic update complete")

        # =========================================================================
        # UNICODE SUPPORT
        # =========================================================================

        print("\n=== Unicode Support ===\n")

        unicode_file = tmp_path / "unicode.txt"
        unicode_content = """
Japanese: こんにちは世界
Chinese: 你好世界
Korean: 안녕하세요
Arabic: مرحبا بالعالم
Emoji: 🎉 🚀 ✨ 💯
"""
        zo.write_text(unicode_file, unicode_content)
        print("Created unicode file with content:")
        print(zo.read_text(unicode_file))

        print("\n=== Done! ===")


if __name__ == "__main__":
    main()
