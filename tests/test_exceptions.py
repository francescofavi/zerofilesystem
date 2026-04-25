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

ALL_SUBCLASSES: list[type[ZeroFSError]] = [
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


@pytest.mark.parametrize("cls", [ZeroFSError, *ALL_SUBCLASSES])
def test_every_exception_is_re_exported_at_top_level(cls: type[Exception]) -> None:
    assert getattr(zfs, cls.__name__) is cls


@pytest.mark.parametrize("cls", ALL_SUBCLASSES)
def test_every_subclass_inherits_from_zerofs_error(cls: type[Exception]) -> None:
    assert issubclass(cls, ZeroFSError)
    assert issubclass(cls, Exception)


def test_zerofs_error_message_is_minimal_when_no_context() -> None:
    err = ZeroFSError("boom")
    assert str(err) == "boom"
    assert err.path is None
    assert err.operation is None
    assert err.cause is None


def test_zerofs_error_includes_path_and_operation_in_message() -> None:
    cause = ValueError("inner")
    err = ZeroFSError("boom", path="/x", operation="op", cause=cause)
    msg = str(err)
    assert "boom" in msg
    assert "path=/x" in msg
    assert "operation=op" in msg
    assert "cause=ValueError" in msg
    assert err.path == Path("/x")
    assert err.cause is cause


def test_file_locked_error_records_timeout() -> None:
    err = FileLockedError("/x", timeout=1.5)
    assert err.timeout == 1.5
    assert "timeout=1.5s" in str(err)
    assert err.path == Path("/x")


def test_file_locked_error_without_timeout() -> None:
    err = FileLockedError("/x")
    assert err.timeout is None
    assert "timeout=" not in str(err)


def test_invalid_path_error_carries_reason() -> None:
    err = InvalidPathError("/x", reason="not a directory")
    assert err.reason == "not a directory"
    assert "not a directory" in str(err)


def test_hash_mismatch_error_truncates_digests_in_message() -> None:
    expected = "a" * 64
    actual = "b" * 64
    err = HashMismatchError("/x", expected=expected, actual=actual, algorithm="sha256")
    assert err.expected == expected
    assert err.actual == actual
    assert err.algorithm == "sha256"
    msg = str(err)
    assert "expected=aaaaaaaaaaaaaaaa..." in msg
    assert "actual=bbbbbbbbbbbbbbbb..." in msg


def test_integrity_error_default_lists_are_empty() -> None:
    err = IntegrityError("bad")
    assert err.missing == []
    assert err.extra == []
    assert err.modified == []


def test_integrity_error_records_three_lists() -> None:
    err = IntegrityError("bad", missing=["a"], extra=["b"], modified=["c"])
    assert err.missing == ["a"]
    assert err.extra == ["b"]
    assert err.modified == ["c"]


def test_transaction_error_operation_depends_on_rollback_flag() -> None:
    commit_err = TransactionError("commit failed", rollback_success=False)
    rollback_err = TransactionError("rollback failed", rollback_success=True)
    assert commit_err.operation == "transaction_commit"
    assert rollback_err.operation == "transaction_rollback"


def test_archive_error_records_archive_type() -> None:
    err = ArchiveError("bad", archive_type="zip")
    assert err.archive_type == "zip"
    assert "archive_zip" in str(err)


def test_archive_error_unknown_type_falls_back_to_unknown() -> None:
    err = ArchiveError("bad")
    assert err.archive_type is None
    assert "archive_unknown" in str(err)


def test_permission_denied_error_includes_operation() -> None:
    err = PermissionDeniedError("/x", operation="read")
    msg = str(err)
    assert "Permission denied" in msg
    assert "operation=read" in msg
    assert "path=/x" in msg


def test_secure_delete_error_default_reason() -> None:
    err = SecureDeleteError("/x")
    assert "secure delete failed" in str(err)


def test_secure_delete_error_custom_reason() -> None:
    err = SecureDeleteError("/x", reason="device error")
    assert "device error" in str(err)


def test_sync_error_records_source_and_destination() -> None:
    err = SyncError("bad", source="/a", destination="/b")
    assert err.source == Path("/a")
    assert err.destination == Path("/b")


def test_exception_can_be_raised_and_caught_by_base() -> None:
    with pytest.raises(ZeroFSError):
        raise FileLockedError("/x", timeout=0.0)


def test_cause_chain_is_preserved_via_from() -> None:
    inner = OSError("device down")
    try:
        try:
            raise inner
        except OSError as e:
            raise ZeroFSError("wrapper", cause=e) from e
    except ZeroFSError as outer:
        assert outer.__cause__ is inner
        assert outer.cause is inner
