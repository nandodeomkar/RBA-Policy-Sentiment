"""Typed records for the ingestion + scoring pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

Action = Literal["hold", "hike", "cut"]


@dataclass(frozen=True)
class Outcome:
    action: Action
    change_bps: int


@dataclass(frozen=True)
class Decision:
    """A single RBA monetary-policy decision. Holds metadata only — never the
    full statement text (licensing, NFR-011)."""

    id: str  # date-slug, e.g. "2024-02-06"
    date: str  # ISO date, YYYY-MM-DD
    title: str
    source_url: str
    outcome: Outcome
    cash_rate_target: float  # resulting target, in per cent

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
