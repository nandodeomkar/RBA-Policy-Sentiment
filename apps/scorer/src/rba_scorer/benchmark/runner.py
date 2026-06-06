"""Run the benchmark end to end: load labels + scores, split, score the metrics,
apply the gate, and write ``benchmark_report.{json,md}`` (design §7).

This is what ``rba-scorer benchmark`` calls. The scoring components (Phase D)
produce ``scores.json``; until then :func:`run_benchmark` raises
:class:`NoScoresError` so the missing prerequisite is explicit, not silent.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rba_scorer.benchmark.labels import load_labels
from rba_scorer.benchmark.report import build_report, write_report
from rba_scorer.benchmark.split import DEFAULT_SEED, DEFAULT_TEST_FRACTION, make_split
from rba_scorer.paths import (
    BENCHMARK_REPORT_JSON_PATH,
    BENCHMARK_REPORT_MD_PATH,
    DECISIONS_PATH,
    ENGINE_VERSION_PATH,
    LABELS_PATH,
    SCORES_PATH,
)
from rba_scorer.storage.json_store import read_json


class NoScoresError(RuntimeError):
    """No scores.json to benchmark against — run ``rba-scorer score`` first."""


def _component_nets(scores: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Pivot scores.json into ``{estimator: {decision_id: net}}`` — the
    reconciled net plus whichever component nets are present."""
    estimators: dict[str, dict[str, float]] = {"reconciled": {}}
    for did, rec in scores.items():
        if rec.get("net") is not None:
            estimators["reconciled"][did] = float(rec["net"])
        for name, crec in (rec.get("components") or {}).items():
            if isinstance(crec, dict) and crec.get("net") is not None:
                estimators.setdefault(name, {})[did] = float(crec["net"])
    return estimators


def _engine_version(scores: dict[str, Any], engine_version_path: Path) -> str | None:
    data = read_json(engine_version_path, default=None)
    if isinstance(data, dict):
        version = data.get("engine_version") or data.get("version")
        if version:
            return str(version)
    for rec in scores.values():
        if rec.get("engine_version"):
            return str(rec["engine_version"])
    return None


def run_benchmark(
    *,
    labels_path: Path = LABELS_PATH,
    scores_path: Path = SCORES_PATH,
    decisions_path: Path = DECISIONS_PATH,
    engine_version_path: Path = ENGINE_VERSION_PATH,
    report_json_path: Path = BENCHMARK_REPORT_JSON_PATH,
    report_md_path: Path = BENCHMARK_REPORT_MD_PATH,
    seed: int = DEFAULT_SEED,
    test_fraction: float = DEFAULT_TEST_FRACTION,
    write: bool = True,
) -> dict[str, Any]:
    """Produce (and optionally persist) the benchmark report. Raises
    :class:`NoScoresError` if there is nothing to evaluate."""
    label_set = load_labels(labels_path)
    scores = read_json(scores_path, default=None)
    if not scores:
        raise NoScoresError(
            f"no scores found at {scores_path} — run `rba-scorer score` first (Phase D)"
        )

    # Pre-register the split over the full decision universe (decisions.json if
    # present, else every row in labels.csv) so the held-out set is fixed
    # regardless of how far labelling has progressed.
    decisions = read_json(decisions_path, default=None)
    universe = [d["id"] for d in decisions] if decisions else list(label_set.ids)
    split = make_split(universe, seed=seed, test_fraction=test_fraction)

    report = build_report(
        split=split,
        labels=label_set.labels,
        estimators=_component_nets(scores),
        engine_version=_engine_version(scores, engine_version_path),
        seed=seed,
        test_fraction=test_fraction,
    )
    if write:
        write_report(report, report_json_path, report_md_path)
    return report
