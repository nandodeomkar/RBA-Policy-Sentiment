"""Tests for the cash-rate series parser and decision join."""

import datetime as dt

from rba_scorer.ingest.cashrate import (
    explicit_change_bps,
    parse_cash_rate_table,
    target_for_decision,
)

# Rows out of order and with a legend row, mirroring the real page.
TABLE = (
    "<html><body><table>"
    "<tr><th>Effective Date</th><th>Change</th><th>Target</th><th>Docs</th></tr>"
    "<tr><th>7 Feb 2024</th><td>0.00</td><td>4.35</td><td>Statement</td></tr>"
    "<tr><th>8 Nov 2023</th><td>+0.25</td><td>4.35</td><td>Statement</td></tr>"
    "<tr><th>19 Feb 2025</th><td>-0.25</td><td>4.10</td><td>Statement</td></tr>"
    "<tr><td>Cash rate unchanged</td></tr>"
    "</table></body></html>"
)


def test_parse_table_filters_and_sorts() -> None:
    changes = parse_cash_rate_table(TABLE)
    assert [c.effective_date for c in changes] == [
        dt.date(2023, 11, 8),
        dt.date(2024, 2, 7),
        dt.date(2025, 2, 19),
    ]
    assert changes[0].change_pct == 0.25
    assert changes[0].target == 4.35


def test_target_for_decision_uses_next_business_day_change() -> None:
    changes = parse_cash_rate_table(TABLE)
    # Decision announced the day before the effective date.
    assert target_for_decision(changes, dt.date(2024, 2, 6)) == 4.35  # hold
    assert target_for_decision(changes, dt.date(2025, 2, 18)) == 4.10  # cut


def test_explicit_change_bps() -> None:
    changes = parse_cash_rate_table(TABLE)
    assert explicit_change_bps(changes, dt.date(2025, 2, 18)) == -25
    assert explicit_change_bps(changes, dt.date(2024, 2, 6)) == 0
    assert explicit_change_bps(changes, dt.date(2024, 6, 1)) is None
