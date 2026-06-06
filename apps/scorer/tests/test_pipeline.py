"""Tests for the decision build/join step."""

from rba_scorer.ingest.cashrate import parse_cash_rate_table
from rba_scorer.ingest.pipeline import build_decisions
from rba_scorer.ingest.release import ReleaseMeta

TABLE = (
    "<html><body><table>"
    "<tr><th>Effective Date</th><th>Change</th><th>Target</th></tr>"
    "<tr><th>5 May 2022</th><td>+0.25</td><td>0.35</td></tr>"
    "<tr><th>8 Jun 2022</th><td>+0.50</td><td>0.85</td></tr>"
    "<tr><th>6 Jul 2022</th><td>+0.50</td><td>1.35</td></tr>"
    "</table></body></html>"
)


def _meta(date: str) -> ReleaseMeta:
    return ReleaseMeta(date=date, title="x: Monetary Policy Decision", source_url=f"u/{date}")


def test_build_decisions_sets_target_and_outcome() -> None:
    changes = parse_cash_rate_table(TABLE)
    metas = [_meta("2022-07-05"), _meta("2022-05-03"), _meta("2022-06-07")]  # unsorted

    out = build_decisions(metas, changes)

    assert [d.date for d in out] == ["2022-05-03", "2022-06-07", "2022-07-05"]
    # First decision: change from the explicit row effective the next day.
    assert out[0].cash_rate_target == 0.35
    assert out[0].outcome.action == "hike"
    assert out[0].outcome.change_bps == 25
    # Subsequent: change derived from the inter-decision target delta.
    assert out[1].cash_rate_target == 0.85
    assert out[1].outcome.change_bps == 50
    assert out[2].cash_rate_target == 1.35
    assert out[2].outcome.change_bps == 50
