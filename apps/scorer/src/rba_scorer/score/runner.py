"""Score ingested decisions into data/scores.json (design §4, §6).

Drives the reconciled hybrid ensemble: the lexicon, LLM, and transformer
components each score a decision's statement independently, then
:mod:`rba_scorer.score.reconcile` blends them into the net + sub-scores +
confidence + merged evidence published per decision (FR-002, FR-011).

Statement text is fetched (cache-first) and scored in memory; only short
evidence phrases are persisted (NFR-011). Each score is stamped with the
composite ``engine_version``; **compute-once** means a decision already scored at
the current version is reused untouched unless ``force`` is set — so a re-run
with no version change is a no-op and byte-identical (NFR-002).

The text provider and the LLM/transformer scorers are injectable, so the test
suite runs with no network, no API key, and no model download.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rba_scorer.ingest.fetch import fetch as _fetch
from rba_scorer.paths import DECISIONS_PATH, ENGINE_VERSION_PATH, LEXICON_PATH, SCORES_PATH
from rba_scorer.score import llm as llm_component
from rba_scorer.score import summary as summary_component
from rba_scorer.score import transformer as transformer_component
from rba_scorer.score.base import ComponentResult
from rba_scorer.score.engine import engine_version_record, write_engine_version
from rba_scorer.score.extract import extract_statement_text
from rba_scorer.score.lexicon import Lexicon, load_lexicon
from rba_scorer.score.lexicon import score_text as score_lexicon
from rba_scorer.score.reconcile import reconcile
from rba_scorer.score.store import read_scores, write_scores
from rba_scorer.storage.json_store import read_json

logger = logging.getLogger(__name__)

# source_url -> statement text; str -> one component's reading. Injectable so the
# suite needs no network / API key / model weights.
TextProvider = Callable[[str], str]
ComponentScorer = Callable[[str], ComponentResult]


class NoDecisionsError(RuntimeError):
    """No decisions.json to score — run ``rba-scorer ingest`` first."""


class ScoringError(RuntimeError):
    """Every decision failed to score — aborted before write so an empty result
    never overwrites existing good scores (design §9)."""


def _default_text_provider(source_url: str) -> str:
    return extract_statement_text(_fetch(source_url))


def _utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def score_decision(
    decision: dict[str, Any],
    text: str,
    *,
    lexicon: Lexicon,
    llm_scorer: ComponentScorer,
    transformer_scorer: ComponentScorer | None,
    engine_version: str,
    scored_at: str,
) -> dict[str, Any]:
    """Build one decision's full score record (design §4) from its statement text.

    ``transformer_scorer`` may be ``None`` to score the lexicon+LLM subset (the
    plan's step-15 checkpoint, before the heavy transformer is wired)."""
    components = {
        "lexicon": score_lexicon(text, lexicon),
        "llm": llm_scorer(text),
    }
    if transformer_scorer is not None:
        components["transformer"] = transformer_scorer(text)
    recon = reconcile(components)
    return {
        "decision_id": decision["id"],
        "net": recon.net,
        "sub_scores": recon.sub_scores,
        "confidence": recon.confidence,
        "components": {name: result.to_dict() for name, result in components.items()},
        "reconciliation": recon.reconciliation_dict(),
        "evidence_phrases": recon.evidence_phrases,
        "engine_version": engine_version,
        "source_url": decision["source_url"],  # provenance, NFR-006
        "scored_at": scored_at,
    }


def run_score(
    *,
    decisions_path: Path = DECISIONS_PATH,
    lexicon_path: Path = LEXICON_PATH,
    scores_path: Path = SCORES_PATH,
    engine_version_path: Path = ENGINE_VERSION_PATH,
    text_provider: TextProvider = _default_text_provider,
    llm_scorer: ComponentScorer | None = None,
    transformer_scorer: ComponentScorer | None = None,
    llm_version: str | None = None,
    transformer_version: str | None = None,
    use_transformer: bool = True,
    summary_provider: Callable[[dict, dict], str] | None = None,
    use_summaries: bool = True,
    force: bool = False,
    clock: Callable[[], str] = _utc_now_iso,
    write: bool = True,
) -> dict[str, Any]:
    """Score every ingested decision with the reconciled ensemble.

    Compute-once: a decision whose stored score already carries the current
    ``engine_version`` is reused (unless ``force``). A single failing page is
    skipped-and-logged, not fatal to the batch (design §9)."""
    decisions = read_json(decisions_path, default=None)
    if not decisions:
        raise NoDecisionsError(f"no decisions at {decisions_path} — run `rba-scorer ingest` first")

    lexicon = load_lexicon(lexicon_path)
    llm_scorer = llm_scorer or llm_component.score_text
    llm_version = llm_version or llm_component.component_version()

    component_versions = {"lexicon": lexicon.version, "llm": llm_version}
    if use_transformer:
        transformer_scorer = transformer_scorer or transformer_component.score_text
        component_versions["transformer"] = (
            transformer_version or transformer_component.component_version()
        )
    else:
        transformer_scorer = None  # lexicon+LLM subset (plan step 15)

    ev_record = engine_version_record(component_versions)
    engine_version = ev_record["engine_version"]

    existing = read_scores(scores_path)
    scores: dict[str, Any] = {}
    failures = reused = 0
    for decision in decisions:
        decision_id = decision["id"]
        prior = existing.get(decision_id)
        if not force and prior and prior.get("engine_version") == engine_version:
            scores[decision_id] = prior  # compute-once: unchanged version, reuse as-is
            reused += 1
            continue
        try:
            text = text_provider(decision["source_url"])
            scores[decision_id] = score_decision(
                decision,
                text,
                lexicon=lexicon,
                llm_scorer=llm_scorer,
                transformer_scorer=transformer_scorer,
                engine_version=engine_version,
                scored_at=clock(),
            )
        except (
            llm_component.LLMUnavailableError,
            transformer_component.TransformerUnavailableError,
        ):
            # A missing key / model is a batch precondition, not a bad page — abort
            # loudly before write so existing scores are never wiped (design §9).
            raise
        except Exception as exc:  # noqa: BLE001 — resilience: skip one bad page, keep the batch
            failures += 1
            logger.warning("scoring failed for %s: %s", decision_id, exc)

    if not scores:
        # Every decision failed — a systemic problem, not bad pages. Fail loud and
        # leave any existing scores.json untouched rather than wiping it.
        raise ScoringError(
            f"scored 0 of {len(decisions)} decisions ({failures} failed) — not writing; "
            "existing scores preserved. Check the logged failures."
        )

    # Plain-language tone summary (FR-012) — presentational, versioned separately
    # from engine_version. Compute-once on its own axis: reuse a record's summary
    # while its tone_summary_version is current; (re)generate otherwise. Runs before
    # write, so a missing key aborts loudly without clobbering existing scores.
    if use_summaries:
        summarize = summary_provider or summary_component.summary_for
        summary_version = summary_component.tone_summary_version()
        decisions_by_id = {d["id"]: d for d in decisions}
        for record in scores.values():
            if (
                not force
                and record.get("tone_summary")
                and record.get("tone_summary_version") == summary_version
            ):
                continue
            record["tone_summary"] = summarize(decisions_by_id[record["decision_id"]], record)
            record["tone_summary_version"] = summary_version

    if write:
        write_scores(scores, scores_path)
        write_engine_version(ev_record, engine_version_path)
    logger.info(
        "scored %d/%d decisions (%d reused, %d skipped) — engine %s",
        len(scores),
        len(decisions),
        reused,
        failures,
        engine_version,
    )
    return scores
