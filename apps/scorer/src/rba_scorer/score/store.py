"""Reader/writer for the published scores.json contract (design §4).

scores.json is keyed by ``decision_id``; each record carries the reconciled
net + sub-scores, every component's result, confidence, evidence, and the
engine version (FR-011). Writes are atomic so a crashed run never corrupts a
good dataset (NFR-002).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rba_scorer.paths import SCORES_PATH
from rba_scorer.storage.json_store import read_json, write_json_atomic


def write_scores(scores: dict[str, Any], path: Path = SCORES_PATH) -> None:
    """Persist ``{decision_id: score_record}`` atomically, sorted by id for a
    stable, diffable file."""
    ordered = {decision_id: scores[decision_id] for decision_id in sorted(scores)}
    write_json_atomic(path, ordered)


def read_scores(path: Path = SCORES_PATH) -> dict[str, Any]:
    return read_json(path, default={})
