"""Reconcile the component results into one score (design §6, plan step 17).

Blends the independent components into the published reading:

* **Net** — equal-weighted mean of every component's net.
* **Sub-scores** — mean across the *dimension-aware* components only (lexicon +
  LLM); the transformer is net-only and does not contribute here.
* **Confidence** — ``1 − disagreement``, where disagreement is the population
  standard deviation of the component nets. Because nets live in [−1, 1], that
  stdev is itself in [0, 1], so it is already normalised. Agreement → high
  confidence; divergence → low. Needs ≥2 components to be meaningful.
* **Evidence** — every component's phrases, merged and de-duplicated, each tagged
  with which component(s) flagged it.

All of it is reported (FR-011) — nothing about the blend is a black box. Pure
function of the component results → deterministic (NFR-002).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any

from rba_scorer.score.base import DIMENSIONS, ComponentResult

METHOD = "equal_weight_mean"
_NET_DECIMALS = 6


@dataclass(frozen=True)
class Reconciled:
    net: float
    sub_scores: dict[str, float]
    confidence: float | None
    disagreement: float
    weights: dict[str, float]
    evidence_phrases: list[dict[str, Any]]
    method: str = METHOD

    def reconciliation_dict(self) -> dict[str, Any]:
        """The ``reconciliation`` block persisted in the score record (design §4)."""
        return {"method": self.method, "weights": self.weights, "disagreement": self.disagreement}


def _equal_weights(names: list[str]) -> dict[str, float]:
    """Equal weights rounded to 3dp, with the last absorbing the remainder so they
    sum to exactly 1.0 (e.g. three components → 0.333/0.333/0.334)."""
    n = len(names)
    if n == 0:
        return {}
    base = round(1.0 / n, 3)
    weights = {name: base for name in names}
    weights[names[-1]] = round(1.0 - base * (n - 1), 3)
    return weights


def _reconcile_sub_scores(components: dict[str, ComponentResult]) -> dict[str, float]:
    """Mean per dimension over the components that actually produce sub-scores."""
    sub: dict[str, float] = {}
    for dim in DIMENSIONS:
        values = [c.sub_scores[dim] for c in components.values() if dim in c.sub_scores]
        sub[dim] = round(sum(values) / len(values), _NET_DECIMALS) if values else 0.0
    return sub


def _merge_evidence(components: dict[str, ComponentResult]) -> list[dict[str, Any]]:
    """Merge evidence across components, de-duplicating on (text, polarity,
    dimension) and recording which component(s) flagged each phrase."""
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    for name, component in components.items():
        for phrase in component.evidence:
            key = (phrase.text.strip().lower(), phrase.polarity, phrase.dimension)
            entry = merged.get(key)
            if entry is None:
                merged[key] = {
                    "text": phrase.text,
                    "polarity": phrase.polarity,
                    "dimension": phrase.dimension,
                    "source": [name],
                }
            elif name not in entry["source"]:
                entry["source"].append(name)
    return list(merged.values())


def reconcile(components: dict[str, ComponentResult]) -> Reconciled:
    """Blend component results in the order given. Raises ``ValueError`` on empty
    input (there is nothing to reconcile)."""
    if not components:
        raise ValueError("reconcile() requires at least one component result")

    names = list(components)
    nets = [c.net for c in components.values()]
    net = round(sum(nets) / len(nets), _NET_DECIMALS)

    # Population stdev of nets ∈ [0, 1]; confidence only once ≥2 components disagree.
    has_spread = len(nets) >= 2
    raw_disagreement = statistics.pstdev(nets) if has_spread else 0.0
    confidence: float | None = None
    if has_spread:
        confidence = round(max(0.0, min(1.0, 1.0 - raw_disagreement)), _NET_DECIMALS)

    return Reconciled(
        net=net,
        sub_scores=_reconcile_sub_scores(components),
        confidence=confidence,
        disagreement=round(raw_disagreement, _NET_DECIMALS),
        weights=_equal_weights(names),
        evidence_phrases=_merge_evidence(components),
    )
