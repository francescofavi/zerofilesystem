"""Tests for the custom exception hierarchy."""

from __future__ import annotations

from pathlib import Path

import pytest

import zerofilesystem as zfs
from zerofilesystem.classes.exceptions import (
    ArchiveError,
    FileLockedError,
    HashMismatchError,
    IntegrityError,
    InvalidPathError,
    PermissionDeniedError,
    SecureDeleteError,
    SyncError,
    TransactionError,
    ZeroFSError,
)

ALL_SUBCLASSES = [
    FileLockedError,
    InvalidPathError,
    HashMismatchError,
    IntegrityError,
    TransactionError,
    ArchiveError,
    PermissionDeniedError,
    SecureDeleteError,
    SyncError,
]


def test_every_subclass_is_re_exported_and_inherits_from_base() -> None:
    """Single check that the public exception family is wired correctly:
    each class is reachable via the top-level package and inherits from
    ZeroFSError."""
    for cls in [ZeroFSError, *ALL_SUBCLASSES]:
        assert getattr(zfs, cls.__name__) is cls, f"{cls.__name__} is not re-exported"
    for cls in ALL_SUBCLASSES:
        assert issubclass(cls, ZeroFSError)


def test_zerofs_error_message_format_includes_context() -> None:
    """ZeroFSError joins the message, path, operation and cause with
    ' | ' separators — this format is what users see in tracebacks and
    log lines."""
    cause = ValueError("inner")
    err = ZeroFSError("boom", path="/x", operation="op", cause=cause)
    msg = str(err)
    assert "boom" in msg
    assert "path=/x" in msg
    assert "operation=op" in msg
    assert "cause=ValueError" in msg
    assert err.path == Path("/x")
    assert err.cause is cause


def test_zerofs_error_minimal_when_no_context() -> None:
    err = ZeroFSError("boom")
    assert str(err) == "boom"
    assert err.path is None
    assert err.operation is None
    assert err.cause is None


def test_file_locked_error_records_timeout() -> None:
    err = FileLockedError("/x", timeout=1.5)
    assert err.timeout == 1.5
    assert "timeout=1.5s" in str(err)


def test_file_locked_error_omits_timeout_when_none() -> None:
    err = FileLockedError("/x")
    assert err.timeout is None
    assert "timeout=" not in str(err)


def test_invalid_path_error_carries_reason() -> None:
    err = InvalidPathError("/x", reason="not a directory")
    assert err.reason == "not a directory"
    assert "not a directory" in str(err)


def test_hash_mismatch_error_truncates_digests_in_message() -> None:
    """Full sha256 hex would make tracebacks unreadable, so the formatted
    message keeps only the first 16 characters."""
    err = HashMismatchError("/x", expected="a" * 64, actual="b" * 64, algorithm="sha256")
    msg = str(err)
    assert "expected=aaaaaaaaaaaaaaaa..." in msg
    assert "actual=bbbbbbbbbbbbbbbb..." in msg
    assert err.expected == "a" * 64  # full digests still available as attributes
    assert err.actual == "b" * 64


def test_integrity_error_records_three_categorised_lists() -> None:
    err = IntegrityError("bad", missing=["a"], extra=["b"], modified=["c"])
    assert err.missing == ["a"]
    assert err.extra == ["b"]
    assert err.modified == ["c"]


def test_integrity_error_default_lists_are_empty() -> None:
    err = IntegrityError("bad")
    assert err.missing == [] and err.extra == [] and err.modified == []


def test_transaction_error_operation_depends_on_rollback_flag() -> None:
    """The operation tag flips between commit and rollback so log filters can
    target one phase without parsing the message."""
    assert TransactionError("x", rollback_success=False).operation == "transaction_commit"
    assert TransactionError("x", rollback_success=True).operation == "transaction_rollback"


def test_archive_error_records_archive_type_in_operation() -> None:
    assert ArchiveError("bad", archive_type="zip").operation == "archive_zip"
    assert ArchiveError("bad").operation == "archive_unknown"


def test_permission_denied_error_includes_operation() -> None:
    msg = str(PermissionDeniedError("/x", operation="read"))
    assert "Permission denied" in msg
    assert "operation=read" in msg


def test_secure_delete_error_default_and_custom_reason() -> None:
    assert "secure delete failed" in str(SecureDeleteError("/x"))
    assert "device error" in str(SecureDeleteError("/x", reason="device error"))


def test_sync_error_records_source_and_destination() -> None:
    err = SyncError("bad", source="/a", destination="/b")
    assert err.source == Path("/a")
    assert err.destination == Path("/b")


def test_subclasses_can_be_caught_via_base_class() -> None:
    """All callers should be able to write `except ZeroFSError` to handle
    every error this package raises."""
    with pytest.raises(ZeroFSError):
        raise FileLockedError("/x", timeout=0.0)


def test_cause_chain_is_preserved_via_raise_from() -> None:
    inner = OSError("device down")
    try:
        try:
            raise inner
        except OSError as e:
            raise ZeroFSError("wrapper", cause=e) from e
    except ZeroFSError as outer:
        assert outer.__cause__ is inner
        assert outer.cause is inner
