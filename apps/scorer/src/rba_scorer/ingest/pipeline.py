"""Orchestrate ingestion: cash-rate series + decision pages -> decisions.json (FR-001)."""

from __future__ import annotations

import datetime as dt
import logging
from functools import partial

from rba_scorer.ingest.cashrate import (
    CASH_RATE_URL,
    RateChange,
    explicit_change_bps,
    parse_cash_rate_table,
    target_for_decision,
)
from rba_scorer.ingest.fetch import fetch as _fetch
from rba_scorer.ingest.index import Fetcher, decision_urls
from rba_scorer.ingest.release import ReleaseMeta, parse_release_meta
from rba_scorer.models import Action, Decision, Outcome
from rba_scorer.paths import DECISIONS_PATH
from rba_scorer.storage.json_store import write_json_atomic

logger = logging.getLogger(__name__)


def _action_for(change_bps: int) -> Action:
    if change_bps > 0:
        return "hike"
    if change_bps < 0:
        return "cut"
    return "hold"


def build_decisions(metas: list[ReleaseMeta], changes: list[RateChange]) -> list[Decision]:
    """Join decision metadata with the cash-rate series: target from the series,
    outcome from the inter-decision target movement (first from the explicit row)."""
    decisions: list[Decision] = []
    prev_target: float | None = None
    for meta in sorted(metas, key=lambda m: m.date):
        date = dt.date.fromisoformat(meta.date)
        target = target_for_decision(changes, date)
        if prev_target is None:
            change_bps = explicit_change_bps(changes, date) or 0
        else:
            change_bps = round((target - prev_target) * 100)
        decisions.append(
            Decision(
                id=meta.date,
                date=meta.date,
                title=meta.title,
                source_url=meta.source_url,
                outcome=Outcome(_action_for(change_bps), change_bps),
                cash_rate_target=target,
            )
        )
        prev_target = target
    return decisions


def run_ingest(
    since_year: int = 2020,
    *,
    fetch: Fetcher = _fetch,
    force: bool = False,
) -> list[Decision]:
    fetcher: Fetcher = partial(fetch, force=force) if force else fetch

    changes = parse_cash_rate_table(fetcher(CASH_RATE_URL))
    logger.info("parsed %d cash-rate rows", len(changes))

    urls = decision_urls(since_year, fetch=fetcher)
    metas: list[ReleaseMeta] = []
    for url in urls:
        meta = parse_release_meta(fetcher(url), url)
        if meta is None:
            logger.info("skipping non-decision release: %s", url)
            continue
        metas.append(meta)
    logger.info("parsed %d decisions from %d index links", len(metas), len(urls))

    decisions = build_decisions(metas, changes)
    write_json_atomic(DECISIONS_PATH, [d.to_dict() for d in decisions])
    logger.info("wrote %d decisions to %s", len(decisions), DECISIONS_PATH)
    return decisions
