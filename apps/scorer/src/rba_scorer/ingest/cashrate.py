"""Parse the RBA cash-rate target history (the authoritative rate series).

The ``/statistics/cash-rate/`` page renders one HTML table of every cash rate
decision since 1990: effective date, change in percentage points, and the new
target. RBA changes take effect the business day *after* the meeting, so a
decision announced on date ``D`` maps to the row effective on the next business
day. We therefore read the prevailing target as the step-function value a week
after ``D`` (robust to long weekends) and read an explicit change from the row
in ``[D, D + lookahead]``. Outcome (hold/hike/cut) is derived from target
movement, never from the statement prose — which varies too much across years.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

CASH_RATE_URL = "https://www.rba.gov.au/statistics/cash-rate/"

# A decision's change takes effect ~1 business day later; read the settled target
# a week on (safe against holidays; decisions are ~6 weeks apart so it never bleeds
# into the next one).
_ASOF_OFFSET = dt.timedelta(days=7)
_JOIN_LOOKAHEAD = dt.timedelta(days=8)


@dataclass(frozen=True)
class RateChange:
    effective_date: dt.date
    change_pct: float | None  # signed percentage points; None if unparseable
    target: float | None  # new cash rate target, per cent


def _parse_date(text: str) -> dt.date | None:
    text = text.strip().replace("\xa0", " ")
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_float(text: str) -> float | None:
    try:
        return float(text.strip().replace("\xa0", " ").lstrip("+"))
    except (ValueError, AttributeError):
        return None


def parse_cash_rate_table(html: str) -> list[RateChange]:
    table = BeautifulSoup(html, "lxml").find("table")
    if table is None:
        raise ValueError("no cash-rate table found on the page")
    changes: list[RateChange] = []
    for row in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["th", "td"])]
        if len(cells) < 3:
            continue
        effective = _parse_date(cells[0])
        if effective is None:
            continue
        changes.append(RateChange(effective, _parse_float(cells[1]), _parse_float(cells[2])))
    if not changes:
        raise ValueError("cash-rate table parsed to zero rows")
    changes.sort(key=lambda c: c.effective_date)
    return changes


def target_asof(changes: list[RateChange], on_date: dt.date) -> float | None:
    """The cash rate target in effect on ``on_date`` (step function)."""
    current: float | None = None
    for change in changes:
        if change.effective_date > on_date:
            break
        if change.target is not None:
            current = change.target
    return current


def explicit_change_bps(changes: list[RateChange], decision_date: dt.date) -> int | None:
    """Basis-point change from the row effective just after ``decision_date``."""
    for change in changes:
        if decision_date <= change.effective_date <= decision_date + _JOIN_LOOKAHEAD:
            if change.change_pct is not None:
                return round(change.change_pct * 100)
    return None


def target_for_decision(changes: list[RateChange], decision_date: dt.date) -> float:
    target = target_asof(changes, decision_date + _ASOF_OFFSET)
    if target is None:
        raise ValueError(f"no cash rate target known as of {decision_date}")
    return target
