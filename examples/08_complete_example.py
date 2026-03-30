#!/usr/bin/env python3
"""Example: Complete real-world scenario using zerofilesystem.

This example demonstrates a realistic use case: a configuration
management system that needs to:
- Read/write JSON config files safely
- Backup configs before modification
- Use transactions for atomic updates
- Use file locking for concurrent access
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import zerofilesystem as zfs


class ConfigManager:
    """Configuration manager with safe file operations."""

    def __init__(self, config_dir: Path):
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "config.json"
        self.lock_file = self.config_dir / ".config.lock"
        self.backup_dir = self.config_dir / "backups"

        # Ensure directories exist
        zfs.ensure_dir(self.config_dir)
        zfs.ensure_dir(self.backup_dir)

    def load(self) -> dict:  # type: ignore[type-arg]
        """Load configuration safely with locking."""
        if not self.config_file.exists():
            return self._default_config()

        with zfs.FileLock(self.lock_file, timeout=5.0):
            return self._load_unlocked()

    def _load_unlocked(self) -> dict:  # type: ignore[type-arg]
        """Load configuration (caller must hold lock)."""
        if not self.config_file.exists():
            return self._default_config()
        return zfs.read_json(self.config_file)  # type: ignore[no-any-return]

    def _save_unlocked(self, config: dict) -> None:
        """Save configuration (caller must hold lock)."""
        if self.config_file.exists():
            self._backup_current()
        zfs.write_json(self.config_file, config)

    def save(self, config: dict) -> None:
        """Save configuration safely with backup and locking."""
        with zfs.FileLock(self.lock_file, timeout=5.0):
            self._save_unlocked(config)

    def update(self, updates: dict) -> dict:
        """Update configuration values safely."""
        with zfs.FileLock(self.lock_file, timeout=5.0):
            config = self._load_unlocked()
            config.update(updates)
            self._save_unlocked(config)
            return config

    def _backup_current(self) -> Path:
        """Create a timestamped backup of current config."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"config_{timestamp}.json"

        # Use transaction to ensure backup is atomic
        with zfs.FileTransaction() as tx:
            content = zfs.read_text(self.config_file)
            tx.write_text(backup_file, content)

        return backup_file

    def list_backups(self) -> list[Path]:
        """List all backup files."""
        return sorted(zfs.find_files(self.backup_dir, pattern="*.json"))

    def restore_backup(self, backup_path: Path) -> None:
        """Restore configuration from a backup."""
        with zfs.FileLock(self.lock_file, timeout=5.0):
            # Validate backup is valid JSON
            backup_config = zfs.read_json(backup_path)

            # Save current as backup before restoring
            self._backup_current()

            # Restore
            zfs.write_json(self.config_file, backup_config)

    @staticmethod
    def _default_config() -> dict:
        """Return default configuration."""
        return {
            "app_name": "MyApp",
            "version": "1.0.0",
            "debug": False,
            "database": {
                "host": "localhost",
                "port": 5432,
                "name": "myapp_db",
            },
            "logging": {
                "level": "INFO",
                "file": "/var/log/myapp.log",
            },
            "features": {
                "dark_mode": True,
                "notifications": True,
            },
        }


def main() -> None:
    print("=== Configuration Manager Example ===\n")

    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp) / "config"

        # Initialize manager
        manager = ConfigManager(config_dir)

        # =====================================================================
        # INITIAL CONFIGURATION
        # =====================================================================

        print("--- Initial Configuration ---\n")

        config = manager.load()
        print("Loaded default config:")
        print(json.dumps(config, indent=2))

        # Save initial config
        manager.save(config)
        print(f"\nConfig saved to: {manager.config_file}")

        # =====================================================================
        # UPDATE CONFIGURATION
        # =====================================================================

        print("\n--- Update Configuration ---\n")

        # Update some values
        updated = manager.update(
            {
                "debug": True,
                "features": {
                    "dark_mode": True,
                    "notifications": False,
                    "new_feature": True,
                },
            }
        )

        print("Updated config:")
        print(json.dumps(updated, indent=2))

        # =====================================================================
        # MULTIPLE UPDATES (CREATES BACKUPS)
        # =====================================================================

        print("\n--- Multiple Updates ---\n")

        import time

        for i in range(3):
            manager.update({"version": f"1.0.{i + 1}"})
            print(f"Updated to version 1.0.{i + 1}")
            time.sleep(0.1)  # Small delay for unique timestamps

        # List backups
        backups = manager.list_backups()
        print(f"\nBackups created: {len(backups)}")
        for backup in backups:
            print(f"  - {backup.name}")

        # =====================================================================
        # RESTORE FROM BACKUP
        # =====================================================================

        print("\n--- Restore from Backup ---\n")

        if backups:
            oldest_backup = backups[0]
            print(f"Restoring from: {oldest_backup.name}")

            old_config = zfs.read_json(oldest_backup)
            print(f"Backup version: {old_config.get('version')}")

            current_config = manager.load()
            print(f"Current version: {current_config.get('version')}")

            manager.restore_backup(oldest_backup)

            restored_config = manager.load()
            print(f"After restore: {restored_config.get('version')}")

        # =====================================================================
        # CONCURRENT ACCESS SIMULATION
        # =====================================================================

        print("\n--- Concurrent Access Protection ---\n")

        import threading

        results = []

        def worker(worker_id: int) -> None:
            """Simulate concurrent config access."""
            for _ in range(3):
                config = manager.load()
                config["last_accessed_by"] = f"worker_{worker_id}"
                manager.save(config)
                results.append(worker_id)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        print(f"All workers completed: {len(results)} operations")
        print(f"Final config last accessed by: {manager.load().get('last_accessed_by')}")

        # =====================================================================
        # ARCHIVE BACKUPS
        # =====================================================================

        print("\n--- Archive Backups ---\n")

        if manager.backup_dir.exists():
            archive_path = config_dir / "backups.zip"
            zfs.create_zip(manager.backup_dir, archive_path)
            print(f"Created backup archive: {archive_path}")
            print(f"Archive size: {archive_path.stat().st_size} bytes")

            # List contents
            print("\nArchive contents:")
            for item in zfs.list_archive(archive_path):
                print(f"  - {item}")

        print("\n=== Done! ===")


if __name__ == "__main__":
    main()
