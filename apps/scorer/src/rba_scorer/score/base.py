"""Shared contract for scoring components (design §6).

Every component — lexicon, LLM, transformer — emits the same shape: a net score
plus inflation/growth/employment sub-scores on [-1, +1] (hawkish positive,
dovish negative), the evidence phrases behind it, and a pinned version. Uniform
output is what makes the components directly comparable and reconcilable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

DIMENSIONS: tuple[str, ...] = ("inflation", "growth", "employment")
Polarity = Literal["hawkish", "dovish"]


def _check_range(name: str, value: float) -> None:
    if not -1.0 <= value <= 1.0:
        raise ValueError(f"{name} must be in [-1, 1], got {value}")


@dataclass(frozen=True)
class EvidencePhrase:
    """A short verbatim phrase that drove the score (licensing: never full text)."""

    text: str
    polarity: Polarity
    dimension: str

    def to_dict(self) -> dict[str, str]:
        return {"text": self.text, "polarity": self.polarity, "dimension": self.dimension}


@dataclass(frozen=True)
class ComponentResult:
    """One component's reading of a statement.

    ``sub_scores`` may be empty for a net-only component (e.g. the transformer is
    not dimension-aware). ``extra`` carries component-specific fields (matched
    terms, model id, rationale) for the published breakdown (FR-011).
    """

    net: float
    version: str
    sub_scores: dict[str, float] = field(default_factory=dict)
    evidence: tuple[EvidencePhrase, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _check_range("net", self.net)
        for dim, value in self.sub_scores.items():
            if dim not in DIMENSIONS:
                raise ValueError(f"unknown sub-score dimension {dim!r}")
            _check_range(dim, value)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"net": self.net, "version": self.version}
        if self.sub_scores:
            out["sub_scores"] = dict(self.sub_scores)
        if self.evidence:
            out["evidence"] = [e.to_dict() for e in self.evidence]
        out.update(self.extra)
        return out
