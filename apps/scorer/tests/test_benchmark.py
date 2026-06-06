"""Tests for the benchmark harness: labels, split, metrics, gate, runner."""

import json
import math

import pytest

from rba_scorer.benchmark.gate import evaluate_gate
from rba_scorer.benchmark.labels import LabelError, load_labels
from rba_scorer.benchmark.metrics import (
    bin_to_bucket,
    bootstrap_agreement_ci,
    spearman,
    within_one_bucket_agreement,
)
from rba_scorer.benchmark.runner import NoScoresError, run_benchmark
from rba_scorer.benchmark.split import DEFAULT_SEED, make_split

# --- labels -----------------------------------------------------------------


def _write(path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="")


def test_load_labels_parses_labelled_rows_and_skips_blanks(tmp_path) -> None:
    csv = tmp_path / "labels.csv"
    _write(
        csv,
        "decision_id,date,net_label,note\n"
        "d1,2020-01-01,1,strong\n"
        "d2,2020-02-01,,\n"  # unlabelled -> excluded
        "d3,2020-03-01,-0.5,weak\n"
        "d4,2020-04-01,0,\n",
    )
    ls = load_labels(csv)
    assert ls.ids == ("d1", "d2", "d3", "d4")  # full universe, incl. blank
    assert ls.labels == {"d1": 1.0, "d3": -0.5, "d4": 0.0}
    assert ls.labelled_ids == ("d1", "d3", "d4")


def test_load_labels_rejects_out_of_scale_value(tmp_path) -> None:
    csv = tmp_path / "labels.csv"
    _write(csv, "decision_id,net_label\nd1,0.3\n")  # 0.3 not on the 5-point scale
    with pytest.raises(LabelError):
        load_labels(csv)


def test_load_labels_rejects_non_numeric_value(tmp_path) -> None:
    csv = tmp_path / "labels.csv"
    _write(csv, "decision_id,net_label\nd1,dovish\n")
    with pytest.raises(LabelError):
        load_labels(csv)


def test_load_labels_requires_columns(tmp_path) -> None:
    csv = tmp_path / "labels.csv"
    _write(csv, "decision_id,note\nd1,hello\n")  # no net_label column
    with pytest.raises(ValueError, match="net_label"):
        load_labels(csv)


# --- split ------------------------------------------------------------------


def test_split_is_isolated_complete_and_deterministic() -> None:
    ids = [f"d{i}" for i in range(30)]
    s1 = make_split(ids)
    s2 = make_split(list(reversed(ids)))  # order must not matter
    assert s1 == s2
    assert set(s1.dev).isdisjoint(s1.test)
    assert set(s1.dev) | set(s1.test) == set(ids)
    assert len(s1.test) == round(30 / 3) == 10


def test_split_changes_with_seed() -> None:
    ids = [f"d{i}" for i in range(30)]
    assert set(make_split(ids, seed=1).test) != set(make_split(ids, seed=2).test)


# --- metrics ----------------------------------------------------------------


@pytest.mark.parametrize(
    "net,expected",
    [
        (0.0, 0.0),
        (0.25, 0.0),  # tie -> toward zero
        (0.26, 0.5),
        (0.75, 0.5),  # tie -> toward zero
        (0.76, 1.0),
        (-0.25, 0.0),  # tie -> toward zero
        (-0.26, -0.5),
        (2.0, 1.0),  # clamp
        (-2.0, -1.0),  # clamp
    ],
)
def test_bin_to_bucket(net, expected) -> None:
    assert bin_to_bucket(net) == expected


def test_within_one_bucket_agreement_counts_adjacent_as_hit() -> None:
    assert within_one_bucket_agreement([0.0, 0.5, 1.0], [0.0, 0.5, 1.0]) == 1.0
    assert within_one_bucket_agreement([0.24], [0.5]) == 1.0  # adjacent bucket
    assert within_one_bucket_agreement([0.24], [1.0]) == 0.0  # two buckets away
    assert within_one_bucket_agreement([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert math.isnan(within_one_bucket_agreement([], []))


def test_spearman_known_values() -> None:
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert spearman([1, 2, 3, 4], [40, 30, 20, 10]) == pytest.approx(-1.0)
    assert spearman([1, 1, 2], [1, 2, 3]) == pytest.approx(0.8660, abs=1e-3)  # tie-aware
    assert math.isnan(spearman([1, 1, 1], [1, 2, 3]))  # constant -> nan
    assert math.isnan(spearman([1.0], [2.0]))  # too few points


def test_bootstrap_ci_is_seeded_and_bounded() -> None:
    engine = [0.0, 0.5, 1.0, -0.5, -1.0]
    label = [0.0, 0.5, 1.0, -0.5, -1.0]  # all exact hits
    ci_a = bootstrap_agreement_ci(engine, label, seed=7)
    ci_b = bootstrap_agreement_ci(engine, label, seed=7)
    assert ci_a == ci_b  # deterministic given the seed
    assert ci_a == (1.0, 1.0)  # every resample is all-hits


# --- gate -------------------------------------------------------------------


def test_gate_uses_within_one_bucket_as_the_switch() -> None:
    assert evaluate_gate(0.85, 0.9, 20).passed is True  # exactly at threshold
    assert evaluate_gate(0.84, 0.99, 20).passed is False
    # low Spearman never flips a passing within-one-bucket result
    passing = evaluate_gate(0.90, 0.10, 20)
    assert passing.passed is True
    assert passing.spearman_meets_target is False
    assert evaluate_gate(float("nan"), float("nan"), 0).passed is False


# --- runner (end to end on toy data) ----------------------------------------


def _toy_corpus(tmp_path, *, engine_sign: int):
    """Write toy decisions/labels/scores. engine_sign=+1 -> perfect agreement."""
    ids = [f"2020-{m:02d}-01" for m in range(1, 10)]  # 9 decisions
    scale = [-1.0, -0.5, 0.0, 0.5, 1.0]
    labels = {d: scale[i % len(scale)] for i, d in enumerate(ids)}

    (tmp_path / "decisions.json").write_text(json.dumps([{"id": d} for d in ids]), encoding="utf-8")
    rows = ["decision_id,net_label"] + [f"{d},{labels[d]}" for d in ids]
    _write(tmp_path / "labels.csv", "\n".join(rows) + "\n")

    scores = {}
    for d in ids:
        net = engine_sign * labels[d]
        scores[d] = {
            "net": net,
            "components": {
                "lexicon": {"net": net},
                "llm": {"net": net},
                "transformer": {"net": net},
            },
            "engine_version": "engine-test-1",
        }
    (tmp_path / "scores.json").write_text(json.dumps(scores), encoding="utf-8")
    return ids


def _run(tmp_path):
    return run_benchmark(
        labels_path=tmp_path / "labels.csv",
        scores_path=tmp_path / "scores.json",
        decisions_path=tmp_path / "decisions.json",
        engine_version_path=tmp_path / "engine_version.json",
        report_json_path=tmp_path / "benchmark_report.json",
        report_md_path=tmp_path / "benchmark_report.md",
    )


def test_run_benchmark_perfect_scores_pass_and_write_report(tmp_path) -> None:
    _toy_corpus(tmp_path, engine_sign=+1)
    report = _run(tmp_path)

    gate = report["gate"]
    assert gate["passed"] is True
    assert gate["within_one_bucket"] == 1.0
    assert gate["n_test"] == round(9 / 3) == 3
    assert report["engine_version"] == "engine-test-1"

    split = report["split"]
    assert set(split["dev_ids"]).isdisjoint(split["test_ids"])  # isolation
    assert len(split["dev_ids"]) + len(split["test_ids"]) == 9
    assert split["seed"] == DEFAULT_SEED

    # per-component metrics present for the iterative-build story
    assert set(report["metrics"]) == {"reconciled", "lexicon", "llm", "transformer"}

    assert (tmp_path / "benchmark_report.json").exists()
    assert (tmp_path / "benchmark_report.md").exists()
    assert "PASS" in (tmp_path / "benchmark_report.md").read_text(encoding="utf-8")


def test_run_benchmark_bad_scores_fail_the_gate(tmp_path) -> None:
    _toy_corpus(tmp_path, engine_sign=-1)  # engine net = -label
    gate = _run(tmp_path)["gate"]
    assert gate["passed"] is False
    assert gate["within_one_bucket"] < 0.85


def test_run_benchmark_without_scores_raises(tmp_path) -> None:
    _write(tmp_path / "labels.csv", "decision_id,net_label\nd1,1\n")
    with pytest.raises(NoScoresError):
        run_benchmark(
            labels_path=tmp_path / "labels.csv",
            scores_path=tmp_path / "missing.json",
            decisions_path=tmp_path / "missing_decisions.json",
        )
