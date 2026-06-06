"""Seeded, deterministic dev/test split for the benchmark (design §7).

The test set is *pre-registered*: a fixed seed over the full decision universe
locks the held-out set before any tuning, so prompt/lexicon/weight tuning can
read the dev set only. Changing the seed re-draws the locked set, so it is a
module constant — never a CLI flag.
"""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass

# Pre-registered split parameters. Do not change once labelling/tuning begins.
DEFAULT_SEED = 20_260_606
DEFAULT_TEST_FRACTION = 1 / 3


@dataclass(frozen=True)
class Split:
    dev: tuple[str, ...]
    test: tuple[str, ...]


def make_split(
    ids: Iterable[str],
    *,
    seed: int = DEFAULT_SEED,
    test_fraction: float = DEFAULT_TEST_FRACTION,
) -> Split:
    """Partition ``ids`` into disjoint dev/test sets, deterministically.

    The result depends only on the *set* of ids and the seed — input order is
    irrelevant (ids are sorted first) — so re-running yields an identical split.
    """
    unique = sorted(set(ids))
    shuffled = unique[:]
    random.Random(seed).shuffle(shuffled)
    n_test = round(len(unique) * test_fraction)
    test = set(shuffled[:n_test])
    dev = tuple(i for i in unique if i not in test)
    test_sorted = tuple(i for i in unique if i in test)
    return Split(dev=dev, test=test_sorted)
