"""Tests for atomic JSON storage."""

from rba_scorer.storage.json_store import read_json, write_json_atomic


def test_write_atomic_is_idempotent(tmp_path) -> None:
    path = tmp_path / "decisions.json"
    data = [{"id": "2024-02-06", "cash_rate_target": 4.35}]
    write_json_atomic(path, data)
    first = path.read_bytes()
    write_json_atomic(path, data)
    assert path.read_bytes() == first  # same input -> byte-identical file
    assert read_json(path) == data


def test_read_json_missing_returns_default(tmp_path) -> None:
    assert read_json(tmp_path / "nope.json", default=[]) == []
