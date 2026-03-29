#!/usr/bin/env python3
"""Example: JSON file operations with zerofilesystem.

This example demonstrates:
- Reading and writing JSON files
- Working with complex nested data structures
- Unicode in JSON
- Atomic JSON writes
"""

import tempfile
from pathlib import Path

import zerofilesystem as zo


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # =========================================================================
        # BASIC JSON OPERATIONS
        # =========================================================================

        print("=== Basic JSON Operations ===\n")

        # Write a simple JSON object
        config_file = tmp_path / "config.json"
        config = {
            "app_name": "MyApp",
            "version": "1.0.0",
            "debug": True,
            "max_connections": 100,
        }
        zo.write_json(config_file, config)
        print(f"Created config file: {config_file}")

        # Read it back
        loaded_config = zo.read_json(config_file)
        print(f"Loaded config: {loaded_config}")

        # =========================================================================
        # COMPLEX NESTED STRUCTURES
        # =========================================================================

        print("\n=== Complex Nested Structures ===\n")

        # Write complex nested data
        data_file = tmp_path / "users.json"
        users_data = {
            "metadata": {"created_at": "2025-01-01", "version": 2},
            "users": [
                {
                    "id": 1,
                    "name": "Alice",
                    "email": "alice@example.com",
                    "roles": ["admin", "user"],
                    "settings": {"theme": "dark", "notifications": True},
                },
                {
                    "id": 2,
                    "name": "Bob",
                    "email": "bob@example.com",
                    "roles": ["user"],
                    "settings": {"theme": "light", "notifications": False},
                },
            ],
        }
        zo.write_json(data_file, users_data)
        print(f"Created users file: {data_file}")

        # Read and access nested data
        loaded = zo.read_json(data_file)
        print(f"\nFirst user: {loaded['users'][0]['name']}")
        print(f"Admin roles: {loaded['users'][0]['roles']}")

        # =========================================================================
        # JSON WITH UNICODE
        # =========================================================================

        print("\n=== JSON with Unicode ===\n")

        i18n_file = tmp_path / "translations.json"
        translations = {
            "en": {"greeting": "Hello", "farewell": "Goodbye"},
            "ja": {"greeting": "こんにちは", "farewell": "さようなら"},
            "zh": {"greeting": "你好", "farewell": "再见"},
            "ar": {"greeting": "مرحبا", "farewell": "مع السلامة"},
        }
        zo.write_json(i18n_file, translations)
        print("Created translations file with unicode support")

        # Read and display
        loaded_translations = zo.read_json(i18n_file)
        for lang, strings in loaded_translations.items():
            print(f"  {lang}: {strings['greeting']}")

        # =========================================================================
        # JSON ARRAYS
        # =========================================================================

        print("\n=== JSON Arrays ===\n")

        # JSON files can also be arrays at the root
        tasks_file = tmp_path / "tasks.json"
        tasks = [
            {"id": 1, "title": "Write code", "done": True},
            {"id": 2, "title": "Write tests", "done": True},
            {"id": 3, "title": "Write docs", "done": False},
        ]
        zo.write_json(tasks_file, tasks)
        print("Created tasks file (root is array)")

        loaded_tasks = zo.read_json(tasks_file)
        for task in loaded_tasks:
            status = "done" if task["done"] else "pending"
            print(f"  [{status}] {task['title']}")

        # =========================================================================
        # CUSTOM INDENTATION
        # =========================================================================

        print("\n=== Custom Indentation ===\n")

        # Default is 2 spaces
        default_file = tmp_path / "default_indent.json"
        zo.write_json(default_file, {"key": "value"})

        # Use 4 spaces
        four_space_file = tmp_path / "four_space.json"
        zo.write_json(four_space_file, {"key": "value"}, indent=4)

        print("Default (2 spaces):")
        print(zo.read_text(default_file))

        print("\n4-space indent:")
        print(zo.read_text(four_space_file))

        # =========================================================================
        # UPDATING JSON FILES
        # =========================================================================

        print("\n=== Updating JSON Files ===\n")

        settings_file = tmp_path / "settings.json"

        # Create initial settings
        zo.write_json(settings_file, {"volume": 50, "brightness": 80})
        print(f"Initial: {zo.read_json(settings_file)}")

        # Read, modify, write back
        settings = zo.read_json(settings_file)
        settings["volume"] = 75
        settings["new_setting"] = "added"
        zo.write_json(settings_file, settings)
        print(f"Updated: {zo.read_json(settings_file)}")

        print("\n=== Done! ===")


if __name__ == "__main__":
    main()
