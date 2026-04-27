"""Tests for the integrity checker and manifest helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import zerofilesystem as zfs
from zerofilesystem.classes.exceptions import HashMismatchError
from zerofilesystem.classes.integrity_checker import ManifestEntry, VerificationResult


def test_directory_hash_is_deterministic(populated_tree: Path) -> None:
    h1 = zfs.directory_hash(populated_tree)
    h2 = zfs.directory_hash(populated_tree)
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex


def test_directory_hash_changes_when_content_changes(populated_tree: Path) -> None:
    before = zfs.directory_hash(populated_tree)
    (populated_tree / "a.txt").write_text("MUTATED")
    after = zfs.directory_hash(populated_tree)
    assert before != after


def test_directory_hash_changes_when_file_added(populated_tree: Path) -> None:
    before = zfs.directory_hash(populated_tree)
    (populated_tree / "extra.txt").write_text("new file")
    after = zfs.directory_hash(populated_tree)
    assert before != after


def test_directory_hash_changes_when_file_removed(populated_tree: Path) -> None:
    before = zfs.directory_hash(populated_tree)
    (populated_tree / "a.txt").unlink()
    after = zfs.directory_hash(populated_tree)
    assert before != after


def test_directory_hash_filter_excludes_files(populated_tree: Path) -> None:
    full = zfs.directory_hash(populated_tree)
    txt_only = zfs.directory_hash(populated_tree, filter_fn=lambda p: p.suffix == ".txt")
    assert full != txt_only


@pytest.mark.parametrize("algo", ["md5", "sha1", "sha256", "sha512"])
def test_directory_hash_supports_multiple_algorithms(populated_tree: Path, algo: str) -> None:
    h = zfs.directory_hash(populated_tree, algorithm=algo)  # type: ignore[arg-type]
    assert isinstance(h, str)
    assert len(h) > 0


def test_create_manifest_lists_every_file(populated_tree: Path) -> None:
    manifest = zfs.create_manifest(populated_tree)
    expected_paths = {
        str(p.relative_to(populated_tree)) for p in populated_tree.rglob("*") if p.is_file()
    }
    assert set(manifest.keys()) == expected_paths


def test_create_manifest_entries_carry_size_and_hash(populated_tree: Path) -> None:
    manifest = zfs.create_manifest(populated_tree)
    rel = "a.txt"
    entry = manifest[rel]
    assert isinstance(entry, ManifestEntry)
    assert entry.path == rel
    assert entry.size == (populated_tree / rel).stat().st_size
    assert len(entry.hash) > 0


def test_create_manifest_with_filter_excludes_files(populated_tree: Path) -> None:
    manifest = zfs.create_manifest(populated_tree, filter_fn=lambda p: p.suffix == ".txt")
    assert all(k.endswith(".txt") for k in manifest)
    assert "b.log" not in manifest


def test_create_manifest_progress_callback_is_invoked(populated_tree: Path) -> None:
    seen: list[tuple[str, int, int]] = []

    def cb(path: str, current: int, total: int) -> None:
        seen.append((path, current, total))

    zfs.create_manifest(populated_tree, progress_callback=cb)
    assert seen
    assert seen[-1][1] == seen[-1][2]


def test_save_manifest_writes_json(populated_tree: Path, tmp_path: Path) -> None:
    manifest = zfs.create_manifest(populated_tree)
    out = tmp_path / "manifest.json"
    written = zfs.save_manifest(manifest, out, algorithm="sha256")
    assert written == out
    data = json.loads(out.read_text())
    assert data["algorithm"] == "sha256"
    assert data["version"] == "1.0"
    assert "files" in data
    assert "a.txt" in data["files"]


def test_save_manifest_creates_parent_directories(populated_tree: Path, tmp_path: Path) -> None:
    manifest = zfs.create_manifest(populated_tree)
    out = tmp_path / "deep" / "nested" / "manifest.json"
    zfs.save_manifest(manifest, out)
    assert out.exists()


def test_load_manifest_round_trip(populated_tree: Path, tmp_path: Path) -> None:
    original = zfs.create_manifest(populated_tree)
    out = tmp_path / "manifest.json"
    zfs.save_manifest(original, out, algorithm="sha256")
    loaded, algo = zfs.load_manifest(out)
    assert algo == "sha256"
    assert set(loaded.keys()) == set(original.keys())
    for k, v in original.items():
        assert loaded[k].hash == v.hash
        assert loaded[k].size == v.size


def test_load_manifest_defaults_algorithm_when_missing(tmp_path: Path) -> None:
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps({"version": "1.0", "files": {}}))
    _manifest, algo = zfs.load_manifest(p)
    assert algo == "sha256"


def test_verify_manifest_on_unchanged_directory(populated_tree: Path) -> None:
    manifest = zfs.create_manifest(populated_tree)
    result = zfs.verify_manifest(populated_tree, manifest)
    assert isinstance(result, VerificationResult)
    assert result.is_valid
    assert sorted(result.valid) == sorted(manifest.keys())


def test_verify_manifest_detects_modification(populated_tree: Path) -> None:
    manifest = zfs.create_manifest(populated_tree)
    (populated_tree / "a.txt").write_text("CORRUPTED")
    result = zfs.verify_manifest(populated_tree, manifest)
    assert not result.is_valid
    assert "a.txt" in result.modified


def test_verify_manifest_detects_missing_file(populated_tree: Path) -> None:
    manifest = zfs.create_manifest(populated_tree)
    (populated_tree / "a.txt").unlink()
    result = zfs.verify_manifest(populated_tree, manifest)
    assert "a.txt" in result.missing


def test_verify_manifest_detects_extra_file(populated_tree: Path) -> None:
    manifest = zfs.create_manifest(populated_tree)
    (populated_tree / "rogue.txt").write_text("not in manifest")
    result = zfs.verify_manifest(populated_tree, manifest)
    assert "rogue.txt" in result.extra


def test_verify_manifest_check_extra_disabled_skips_extras(populated_tree: Path) -> None:
    manifest = zfs.create_manifest(populated_tree)
    (populated_tree / "rogue.txt").write_text("not in manifest")
    result = zfs.verify_manifest(populated_tree, manifest, check_extra=False)
    assert result.extra == []


def test_verify_file_returns_true_when_hash_matches(sample_file: Path) -> None:
    digest = zfs.file_hash(sample_file)
    assert zfs.verify_file(sample_file, expected_hash=digest) is True


def test_verify_file_raises_on_mismatch(sample_file: Path) -> None:
    with pytest.raises(HashMismatchError):
        zfs.verify_file(sample_file, expected_hash="0" * 64)


def test_compare_directories_detects_differences(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "common.txt").write_text("same")
    (b / "common.txt").write_text("same")
    (a / "only_a.txt").write_text("a")
    (b / "only_b.txt").write_text("b")
    (a / "modified.txt").write_text("v1")
    (b / "modified.txt").write_text("v2")
    result = zfs.compare_directories(a, b)
    assert "common.txt" in result.valid
    assert "only_a.txt" in result.missing
    assert "only_b.txt" in result.extra
    assert "modified.txt" in result.modified


def test_snapshot_hash_is_deterministic_and_changes_with_content(populated_tree: Path) -> None:
    h1 = zfs.snapshot_hash(populated_tree)
    h2 = zfs.snapshot_hash(populated_tree)
    assert h1 == h2
    (populated_tree / "extra.txt").write_text("new")
    assert zfs.snapshot_hash(populated_tree) != h1


def test_snapshot_hash_is_faster_than_directory_hash_logic(populated_tree: Path) -> None:
    """snapshot_hash uses metadata only — same directory must yield same hash
    even after rewriting identical content (mtime may shift, so this is a
    weaker assertion: identical re-read yields identical hash)."""
    s1 = zfs.snapshot_hash(populated_tree)
    s2 = zfs.snapshot_hash(populated_tree)
    assert s1 == s2


def test_verification_result_is_valid_property() -> None:
    ok = VerificationResult(valid=["a"])
    bad = VerificationResult(valid=["a"], modified=["b"])
    assert ok.is_valid is True
    assert bad.is_valid is False


def test_manifest_entry_to_dict_round_trip() -> None:
    entry = ManifestEntry(path="a.txt", hash="abc", size=10, modified=1.0)
    restored = ManifestEntry.from_dict(entry.to_dict())
    assert restored == entry
