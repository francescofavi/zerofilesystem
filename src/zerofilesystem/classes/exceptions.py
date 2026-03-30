"""Custom exceptions for zerofilesystem package."""

from __future__ import annotations

from pathlib import Path

from zerofilesystem._platform import Pathish


class ZeroFSError(Exception):
    """Base exception for all zerofilesystem errors."""

    def __init__(
        self,
        message: str,
        path: Pathish | None = None,
        operation: str | None = None,
        cause: Exception | None = None,
    ):
        self.path = Path(path) if path else None
        self.operation = operation
        self.cause = cause

        parts = [message]
        if path:
            parts.append(f"path={path}")
        if operation:
            parts.append(f"operation={operation}")
        if cause:
            parts.append(f"cause={type(cause).__name__}: {cause}")

        super().__init__(" | ".join(parts))


class FileLockedError(ZeroFSError):
    """Raised when a file is locked by another process."""

    def __init__(
        self,
        path: Pathish,
        timeout: float | None = None,
        cause: Exception | None = None,
    ):
        self.timeout = timeout
        msg = "File is locked"
        if timeout is not None:
            msg += f" (timeout={timeout}s)"
        super().__init__(msg, path=path, operation="lock", cause=cause)


class InvalidPathError(ZeroFSError):
    """Raised when a path is invalid or doesn't exist when required."""

    def __init__(
        self,
        path: Pathish,
        reason: str = "invalid path",
        operation: str | None = None,
    ):
        self.reason = reason
        super().__init__(reason, path=path, operation=operation)


class HashMismatchError(ZeroFSError):
    """Raised when file hash doesn't match expected value."""

    def __init__(
        self,
        path: Pathish,
        expected: str,
        actual: str,
        algorithm: str = "sha256",
    ):
        self.expected = expected
        self.actual = actual
        self.algorithm = algorithm
        msg = f"Hash mismatch ({algorithm}): expected={expected[:16]}..., actual={actual[:16]}..."
        super().__init__(msg, path=path, operation="verify")


class IntegrityError(ZeroFSError):
    """Raised when integrity verification fails."""

    def __init__(
        self,
        message: str,
        missing: list | None = None,
        extra: list | None = None,
        modified: list | None = None,
    ):
        self.missing = missing or []
        self.extra = extra or []
        self.modified = modified or []
        super().__init__(message, operation="integrity_check")


class TransactionError(ZeroFSError):
    """Raised when a file transaction fails."""

    def __init__(
        self,
        message: str,
        path: Pathish | None = None,
        rollback_success: bool = False,
        cause: Exception | None = None,
    ):
        self.rollback_success = rollback_success
        operation = "transaction_commit" if not rollback_success else "transaction_rollback"
        super().__init__(message, path=path, operation=operation, cause=cause)


class ArchiveError(ZeroFSError):
    """Raised when archive operations fail."""

    def __init__(
        self,
        message: str,
        path: Pathish | None = None,
        archive_type: str | None = None,
        cause: Exception | None = None,
    ):
        self.archive_type = archive_type
        super().__init__(
            message, path=path, operation=f"archive_{archive_type or 'unknown'}", cause=cause
        )


class PermissionDeniedError(ZeroFSError):
    """Raised when permission is denied for an operation."""

    def __init__(
        self,
        path: Pathish,
        operation: str,
        cause: Exception | None = None,
    ):
        super().__init__("Permission denied", path=path, operation=operation, cause=cause)


class SecureDeleteError(ZeroFSError):
    """Raised when secure deletion fails."""

    def __init__(
        self,
        path: Pathish,
        reason: str = "secure delete failed",
        cause: Exception | None = None,
    ):
        super().__init__(reason, path=path, operation="secure_delete", cause=cause)


class SyncError(ZeroFSError):
    """Raised when directory sync/mirror operations fail."""

    def __init__(
        self,
        message: str,
        source: Pathish | None = None,
        destination: Pathish | None = None,
        cause: Exception | None = None,
    ):
        self.source = Path(source) if source else None
        self.destination = Path(destination) if destination else None
        super().__init__(message, path=source, operation="sync", cause=cause)
