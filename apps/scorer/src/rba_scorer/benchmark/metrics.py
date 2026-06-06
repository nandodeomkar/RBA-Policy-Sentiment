"""Benchmark metrics (design §7): bucket binning, within-one-bucket agreement,
tie-aware Spearman, and a seeded bootstrap stability interval.

Pure functions over plain floats — no I/O, no model deps — so they unit-test on
toy inputs and run in the core env (no ``--extra transformer`` needed).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

# The 5-point net buckets (design §4).
BUCKETS: tuple[float, ...] = (-1.0, -0.5, 0.0, 0.5, 1.0)
_EPS = 1e-9


def bin_to_bucket(net: float) -> float:
    """Snap a continuous net score to the nearest 5-point bucket (clamped to
    [-1, 1]). A value exactly between two buckets resolves toward zero."""
    clamped = max(-1.0, min(1.0, float(net)))
    return min(BUCKETS, key=lambda b: (abs(clamped - b), abs(b)))


def agrees_within_one_bucket(net: float, label: float) -> bool:
    """True if the engine's bucket equals the label's bucket or an adjacent one."""
    return abs(bin_to_bucket(net) - label) <= 0.5 + _EPS


def within_one_bucket_agreement(engine: Sequence[float], label: Sequence[float]) -> float:
    """Fraction of pairs landing in the label's bucket or an adjacent one — the
    primary gate metric. Returns ``nan`` for empty input."""
    if len(engine) != len(label):
        raise ValueError("engine and label sequences must be the same length")
    if not engine:
        return float("nan")
    hits = sum(agrees_within_one_bucket(e, lab) for e, lab in zip(engine, label, strict=True))
    return hits / len(engine)


def align(
    ids: Sequence[str],
    net_by_id: Mapping[str, float],
    label_by_id: Mapping[str, float],
) -> tuple[list[float], list[float], list[str]]:
    """Pair up engine nets and labels for the ids present in both, preserving
    the order of ``ids`` (so callers control determinism)."""
    used = [i for i in ids if i in net_by_id and i in label_by_id]
    return ([net_by_id[i] for i in used], [label_by_id[i] for i in used], used)


def _average_ranks(values: Sequence[float]) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    n = arr.size
    order = np.argsort(arr, kind="mergesort")
    sorted_vals = arr[order]
    ranks = np.empty(n, dtype=float)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and sorted_vals[j + 1] == sorted_vals[i]:
            j += 1
        ranks[order[i : j + 1]] = (i + j) / 2.0 + 1.0  # average of 1-based ranks
        i = j + 1
    return ranks


def spearman(x: Sequence[float], y: Sequence[float]) -> float:
    """Spearman rank correlation with tie-aware average ranks. Returns ``nan``
    for fewer than two points or a constant input."""
    if len(x) != len(y):
        raise ValueError("x and y must be the same length")
    if len(x) < 2:
        return float("nan")
    rx = _average_ranks(x)
    ry = _average_ranks(y)
    rx = rx - rx.mean()
    ry = ry - ry.mean()
    denom = float(np.sqrt((rx**2).sum() * (ry**2).sum()))
    if denom == 0.0:
        return float("nan")
    return float((rx * ry).sum() / denom)


def bootstrap_agreement_ci(
    engine: Sequence[float],
    label: Sequence[float],
    *,
    seed: int,
    resamples: int = 1000,
    lo_pct: float = 2.5,
    hi_pct: float = 97.5,
) -> tuple[float, float]:
    """Seeded bootstrap CI for within-one-bucket agreement — a stability check
    for the small held-out set (design §7). Deterministic given ``seed``."""
    n = len(engine)
    if n == 0:
        return (float("nan"), float("nan"))
    hits = np.array(
        [agrees_within_one_bucket(e, lab) for e, lab in zip(engine, label, strict=True)],
        dtype=float,
    )
    rng = np.random.default_rng(seed)
    means = hits[rng.integers(0, n, size=(resamples, n))].mean(axis=1)
    return (float(np.percentile(means, lo_pct)), float(np.percentile(means, hi_pct)))
