"""Build and render the benchmark report (design §7).

The report carries the gate verdict, per-split / per-component agreement (so the
iterative build shows what lexicon -> +LLM -> +transformer each contributes),
and per-decision residuals (the largest engine-vs-owner divergences — the tuning
signal). It later seeds the public methodology page (FR-007).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rba_scorer.benchmark.gate import evaluate_gate
from rba_scorer.benchmark.metrics import (
    agrees_within_one_bucket,
    align,
    bin_to_bucket,
    bootstrap_agreement_ci,
    spearman,
    within_one_bucket_agreement,
)
from rba_scorer.benchmark.split import Split
from rba_scorer.storage.json_store import write_json_atomic

# Reported in this order; transformer contributes a net only (no sub-scores).
ESTIMATOR_ORDER: tuple[str, ...] = ("reconciled", "lexicon", "llm", "transformer")


def _metric_block(
    ids: tuple[str, ...], net_by_id: Mapping[str, float], labels: Mapping[str, float]
) -> dict[str, Any]:
    engine, label, used = align(ids, net_by_id, labels)
    return {
        "within_one_bucket": within_one_bucket_agreement(engine, label),
        "spearman": spearman(engine, label),
        "n": len(used),
    }


def build_report(
    *,
    split: Split,
    labels: Mapping[str, float],
    estimators: Mapping[str, Mapping[str, float]],
    engine_version: str | None,
    seed: int,
    test_fraction: float,
) -> dict[str, Any]:
    """Assemble the full report dict from a split, labels, and per-estimator
    net scores (``{estimator: {decision_id: net}}``)."""
    metrics: dict[str, Any] = {}
    for est in ESTIMATOR_ORDER:
        if est in estimators:
            metrics[est] = {
                "dev": _metric_block(split.dev, estimators[est], labels),
                "test": _metric_block(split.test, estimators[est], labels),
            }

    reconciled = estimators.get("reconciled", {})
    t_engine, t_label, t_used = align(split.test, reconciled, labels)
    gate = evaluate_gate(
        within_one_bucket_agreement(t_engine, t_label),
        spearman(t_engine, t_label),
        len(t_used),
    )
    ci = bootstrap_agreement_ci(t_engine, t_label, seed=seed) if t_used else (float("nan"),) * 2

    residuals: list[dict[str, Any]] = []
    for split_name, ids in (("dev", split.dev), ("test", split.test)):
        for did in ids:
            if did in reconciled and did in labels:
                net = reconciled[did]
                lab = labels[did]
                residuals.append(
                    {
                        "decision_id": did,
                        "split": split_name,
                        "label": lab,
                        "engine_net": round(net, 4),
                        "engine_bucket": bin_to_bucket(net),
                        "abs_error": round(abs(net - lab), 4),
                        "within_one_bucket": agrees_within_one_bucket(net, lab),
                    }
                )
    residuals.sort(key=lambda r: r["abs_error"], reverse=True)

    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "engine_version": engine_version,
        "gate": {
            "passed": gate.passed,
            "primary_metric": "within_one_bucket_agreement",
            "within_one_bucket": gate.within_one_bucket,
            "threshold": gate.threshold,
            "spearman": gate.spearman,
            "spearman_target": gate.spearman_target,
            "spearman_meets_target": gate.spearman_meets_target,
            "n_test": gate.n_test,
            "test_stability_ci95": [ci[0], ci[1]],
        },
        "split": {
            "seed": seed,
            "test_fraction": test_fraction,
            "n_dev": len(split.dev),
            "n_test": len(split.test),
            "n_labelled": len(labels),
            "n_scored": len(reconciled),
            "dev_ids": list(split.dev),
            "test_ids": list(split.test),
        },
        "metrics": metrics,
        "residuals": residuals,
    }


def _fmt(value: float) -> str:
    return "n/a" if math.isnan(value) else f"{value:.3f}"


def _pct(value: float) -> str:
    return "n/a" if math.isnan(value) else f"{value * 100:.1f}%"


def render_markdown(report: dict[str, Any]) -> str:
    gate = report["gate"]
    split = report["split"]
    verdict = "✅ PASS" if gate["passed"] else "❌ FAIL"
    ci = gate["test_stability_ci95"]
    lines = [
        "# RBA Policy Sentiment — Benchmark Report",
        "",
        f"_Generated {report['generated_at']} · engine `{report['engine_version'] or 'n/a'}`_",
        "",
        "> **Not the live gate of record unless the corpus is fully labelled and scored.**",
        "",
        "## Gate (NFR-004)",
        "",
        f"**{verdict}** — primary metric: within-one-bucket agreement on the held-out test set.",
        "",
        "| Metric | Value | Target |",
        "| ------ | ----- | ------ |",
        f"| Within-one-bucket (test) | {_pct(gate['within_one_bucket'])} "
        f"| ≥ {_pct(gate['threshold'])} (decides) |",
        f"| Spearman (test) | {_fmt(gate['spearman'])} "
        f"| ≥ {gate['spearman_target']:.2f} (corroborating) |",
        f"| Test set size | {gate['n_test']} | — |",
        f"| Stability (95% bootstrap CI) | {_pct(ci[0])} – {_pct(ci[1])} | — |",
        "",
        "## Coverage",
        "",
        f"- Decisions labelled: **{split['n_labelled']}** · scored: **{split['n_scored']}**",
        f"- Split (seed `{split['seed']}`, test fraction {split['test_fraction']:.3f}): "
        f"**{split['n_dev']}** dev / **{split['n_test']}** test",
        "",
        "## Agreement by component (within-one-bucket / Spearman)",
        "",
        "| Estimator | Dev (n) | Test (n) |",
        "| --------- | ------- | -------- |",
    ]
    for est in ESTIMATOR_ORDER:
        block = report["metrics"].get(est)
        if not block:
            continue
        dev, test = block["dev"], block["test"]
        lines.append(
            f"| {est} | {_pct(dev['within_one_bucket'])} / {_fmt(dev['spearman'])} ({dev['n']}) "
            f"| {_pct(test['within_one_bucket'])} / {_fmt(test['spearman'])} ({test['n']}) |"
        )

    lines += [
        "",
        "## Largest residuals (engine vs. owner)",
        "",
        "| Decision | Split | Label | Engine net | Bucket | |Δ| | Within 1 |",
        "| -------- | ----- | ----- | ---------- | ------ | --- | -------- |",
    ]
    for r in report["residuals"][:15]:
        ok = "yes" if r["within_one_bucket"] else "**NO**"
        lines.append(
            f"| {r['decision_id']} | {r['split']} | {r['label']:+.1f} | {r['engine_net']:+.3f} "
            f"| {r['engine_bucket']:+.1f} | {r['abs_error']:.3f} | {ok} |"
        )
    if not report["residuals"]:
        lines.append("| _(no scored + labelled decisions yet)_ | | | | | | |")
    lines.append("")
    return "\n".join(lines)


def write_report(report: dict[str, Any], json_path: Path, md_path: Path) -> None:
    write_json_atomic(json_path, report)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(report), encoding="utf-8", newline="\n")
