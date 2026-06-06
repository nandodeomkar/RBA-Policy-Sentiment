"""The pre-registered M0 accuracy gate (NFR-004).

Primary, deciding metric: within-one-bucket agreement on the held-out TEST set
>= 0.85. Spearman is reported alongside as corroboration but never flips the
result. Fixing the deciding metric in advance prevents post-hoc metric-shopping
(design §7).
"""

from __future__ import annotations

from dataclasses import dataclass

WITHIN_ONE_BUCKET_THRESHOLD = 0.85  # primary gate — the switch
SPEARMAN_TARGET = 0.80  # corroborating — reported, not the switch


@dataclass(frozen=True)
class GateResult:
    passed: bool
    within_one_bucket: float
    spearman: float
    n_test: int
    threshold: float = WITHIN_ONE_BUCKET_THRESHOLD
    spearman_target: float = SPEARMAN_TARGET

    @property
    def spearman_meets_target(self) -> bool:
        return self.spearman >= self.spearman_target


def evaluate_gate(within_one_bucket: float, spearman_value: float, n_test: int) -> GateResult:
    """Apply the pre-registered gate to held-out test metrics. A ``nan``
    agreement (no test data) does not pass."""
    passed = within_one_bucket >= WITHIN_ONE_BUCKET_THRESHOLD
    return GateResult(
        passed=passed,
        within_one_bucket=within_one_bucket,
        spearman=spearman_value,
        n_test=n_test,
    )
