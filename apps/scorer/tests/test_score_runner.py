"""Tests for the ensemble scoring runner.

The LLM and transformer components are injected as fakes, so the suite runs with
no network, no API key, and no model download (design §8)."""

import json
import statistics

import pytest

from rba_scorer.score import summary
from rba_scorer.score.base import ComponentResult, EvidencePhrase
from rba_scorer.score.runner import NoDecisionsError, run_score

_FIXED_CLOCK = "2026-01-01T00:00:00Z"
_FAKE_SUMMARY = "Leaned hawkish on inflation while holding the cash rate steady."


def _decision(decision_id: str, url: str) -> dict:
    return {
        "id": decision_id,
        "date": decision_id,
        "title": "x: Monetary Policy Decision",
        "source_url": url,
        "outcome": {"action": "hold", "change_bps": 0},
        "cash_rate_target": 4.35,
    }


def _write_decisions(tmp_path, decisions) -> None:
    (tmp_path / "decisions.json").write_text(json.dumps(decisions), encoding="utf-8")


def _fake_llm(_text: str) -> ComponentResult:
    return ComponentResult(
        net=0.4,
        version="claude-fake:llm-p1",
        sub_scores={"inflation": 0.5, "growth": 0.2, "employment": 0.1},
        evidence=(EvidencePhrase("upside risks to inflation", "hawkish", "inflation"),),
        extra={"model_id": "claude-fake", "rationale": "fake"},
    )


def _fake_transformer(_text: str) -> ComponentResult:
    return ComponentResult(net=0.2, version="fomc-roberta:test", extra={"model_revision": "test"})


def _run(tmp_path, **overrides):
    kwargs = dict(
        decisions_path=tmp_path / "decisions.json",
        scores_path=tmp_path / "scores.json",
        engine_version_path=tmp_path / "engine_version.json",
        llm_scorer=_fake_llm,
        transformer_scorer=_fake_transformer,
        summary_provider=lambda _decision, _score: _FAKE_SUMMARY,
        clock=lambda: _FIXED_CLOCK,
    )
    kwargs.update(overrides)
    return run_score(**kwargs)


def test_run_score_writes_reconciled_records(tmp_path) -> None:
    _write_decisions(
        tmp_path, [_decision("2024-01-01", "u/hawk"), _decision("2024-02-01", "u/dove")]
    )
    texts = {
        "u/hawk": "Inflation remains too high. The labour market is tight.",
        "u/dove": "Inflation has moderated and growth has slowed.",
    }
    scores = _run(tmp_path, text_provider=lambda url: texts[url])

    assert set(scores) == {"2024-01-01", "2024-02-01"}
    rec = scores["2024-01-01"]
    comp = rec["components"]
    assert set(comp) == {"lexicon", "llm", "transformer"}

    # Reconciled net is the equal-weighted mean of the three component nets.
    nets = [comp["lexicon"]["net"], comp["llm"]["net"], comp["transformer"]["net"]]
    assert rec["net"] == round(sum(nets) / 3, 6)
    assert rec["reconciliation"]["method"] == "equal_weight_mean"
    assert rec["reconciliation"]["weights"] == {
        "lexicon": 0.333,
        "llm": 0.333,
        "transformer": 0.334,
    }

    # Confidence = 1 − population stdev of the component nets (design §6).
    assert rec["confidence"] == round(1.0 - statistics.pstdev(nets), 6)
    assert 0.0 <= rec["confidence"] <= 1.0

    assert set(rec["sub_scores"]) == {"inflation", "growth", "employment"}
    assert rec["engine_version"].startswith("engine-2026.06-")
    assert rec["source_url"] == "u/hawk"  # provenance (NFR-006)
    assert rec["scored_at"] == _FIXED_CLOCK
    assert comp["transformer"].get("sub_scores") is None  # net only

    # Tone summary (FR-012) — attached, versioned separately from engine_version.
    assert rec["tone_summary"] == _FAKE_SUMMARY
    assert rec["tone_summary_version"] == summary.tone_summary_version()
    assert "summary" not in rec["engine_version"]  # the summary never moves the score's version

    assert (tmp_path / "scores.json").exists()
    assert (tmp_path / "engine_version.json").exists()


def test_subset_run_skips_transformer(tmp_path) -> None:
    _write_decisions(tmp_path, [_decision("d", "u")])
    scores = _run(
        tmp_path, text_provider=lambda _u: "Inflation remains high.", use_transformer=False
    )
    comp = scores["d"]["components"]
    assert set(comp) == {"lexicon", "llm"}  # transformer skipped — no torch needed
    assert scores["d"]["confidence"] is not None  # two components → confidence defined
    ev = json.loads((tmp_path / "engine_version.json").read_text(encoding="utf-8"))
    assert set(ev["components"]) == {"lexicon", "llm", "reconcile"}


def test_engine_version_file_records_parts(tmp_path) -> None:
    _write_decisions(tmp_path, [_decision("d", "u")])
    _run(tmp_path, text_provider=lambda _u: "Inflation remains high.")
    ev = json.loads((tmp_path / "engine_version.json").read_text(encoding="utf-8"))
    assert ev["engine_version"].startswith("engine-2026.06-")
    assert set(ev["components"]) == {"lexicon", "llm", "transformer", "reconcile"}


def test_run_score_is_byte_identical_on_rerun(tmp_path) -> None:
    _write_decisions(tmp_path, [_decision("d", "u")])

    def provider(_url: str) -> str:
        return "Inflation remains too high and broad-based."

    _run(tmp_path, text_provider=provider)
    first = (tmp_path / "scores.json").read_bytes()
    _run(tmp_path, text_provider=provider)
    assert (tmp_path / "scores.json").read_bytes() == first  # deterministic (NFR-002)


def test_compute_once_reuses_unless_forced(tmp_path) -> None:
    _write_decisions(tmp_path, [_decision("d", "u")])
    provider = lambda _u: "Inflation remains high."  # noqa: E731

    _run(tmp_path, text_provider=provider, clock=lambda: "2026-01-01T00:00:00Z")
    # A second run at a *different* wall-clock must reuse the stored record (same
    # engine_version) — scored_at stays put.
    scores = _run(tmp_path, text_provider=provider, clock=lambda: "2099-12-31T23:59:59Z")
    assert scores["d"]["scored_at"] == "2026-01-01T00:00:00Z"

    # --force re-scores, stamping the new clock.
    forced = _run(
        tmp_path, text_provider=provider, clock=lambda: "2099-12-31T23:59:59Z", force=True
    )
    assert forced["d"]["scored_at"] == "2099-12-31T23:59:59Z"


def test_bumping_a_component_version_triggers_rescore(tmp_path) -> None:
    _write_decisions(tmp_path, [_decision("d", "u")])
    provider = lambda _u: "Inflation remains high."  # noqa: E731

    _run(tmp_path, text_provider=provider, clock=lambda: "2026-01-01T00:00:00Z")
    # Changing the LLM version moves the composite engine_version → not reused.
    rescored = _run(
        tmp_path,
        text_provider=provider,
        clock=lambda: "2026-02-02T00:00:00Z",
        llm_version="claude-fake:llm-p2",
    )
    assert rescored["d"]["scored_at"] == "2026-02-02T00:00:00Z"


def test_unavailable_component_aborts_without_wiping_scores(tmp_path) -> None:
    from rba_scorer.score.llm import LLMUnavailableError

    _write_decisions(tmp_path, [_decision("d", "u")])
    scores_path = tmp_path / "scores.json"
    scores_path.write_text('{"sentinel": 1}', encoding="utf-8")  # pre-existing good data

    def boom(_text: str) -> ComponentResult:
        raise LLMUnavailableError("no key")

    # A missing key is batch-fatal: it propagates rather than skipping every page,
    # and the prior scores.json is left untouched (not overwritten with {}).
    with pytest.raises(LLMUnavailableError):
        _run(tmp_path, text_provider=lambda _u: "text", llm_scorer=boom)
    assert scores_path.read_text(encoding="utf-8") == '{"sentinel": 1}'


def test_all_failures_abort_without_writing(tmp_path) -> None:
    from rba_scorer.score.runner import ScoringError

    _write_decisions(tmp_path, [_decision("a", "u/a"), _decision("b", "u/b")])
    scores_path = tmp_path / "scores.json"
    scores_path.write_text('{"sentinel": 1}', encoding="utf-8")

    def boom_llm(_text: str) -> ComponentResult:
        raise ValueError("transient per-page failure")  # not batch-fatal → skipped

    # With *every* page failing, the run aborts before write — no empty {} clobber.
    with pytest.raises(ScoringError):
        _run(tmp_path, text_provider=lambda _u: "Inflation high.", llm_scorer=boom_llm)
    assert scores_path.read_text(encoding="utf-8") == '{"sentinel": 1}'


def test_run_score_skips_failing_pages(tmp_path) -> None:
    _write_decisions(tmp_path, [_decision("good", "u/good"), _decision("bad", "u/bad")])

    def provider(url: str) -> str:
        if url == "u/bad":
            raise RuntimeError("fetch boom")
        return "Inflation remains too high."

    scores = _run(tmp_path, text_provider=provider)
    assert "good" in scores
    assert "bad" not in scores  # one bad page is skipped, not fatal


def test_without_summaries_omits_the_field(tmp_path) -> None:
    _write_decisions(tmp_path, [_decision("d", "u")])
    scores = _run(tmp_path, text_provider=lambda _u: "Inflation high.", use_summaries=False)
    assert "tone_summary" not in scores["d"]  # no key needed, fields simply absent
    assert "tone_summary_version" not in scores["d"]


def test_summary_reused_unless_version_or_force(tmp_path) -> None:
    _write_decisions(tmp_path, [_decision("d", "u")])
    calls = {"n": 0}

    def provider(_decision, _score):
        calls["n"] += 1
        return "a summary"

    _run(tmp_path, text_provider=lambda _u: "Inflation high.", summary_provider=provider)
    assert calls["n"] == 1
    # Re-run: score reused (same engine_version) AND summary current → no new call.
    _run(tmp_path, text_provider=lambda _u: "Inflation high.", summary_provider=provider)
    assert calls["n"] == 1
    # --force re-scores → fresh records → the summary is regenerated.
    _run(
        tmp_path,
        text_provider=lambda _u: "Inflation high.",
        summary_provider=provider,
        force=True,
    )
    assert calls["n"] == 2


def test_summary_failure_aborts_without_wiping_scores(tmp_path) -> None:
    from rba_scorer.score.summary import SummaryUnavailableError

    _write_decisions(tmp_path, [_decision("d", "u")])
    scores_path = tmp_path / "scores.json"
    scores_path.write_text('{"sentinel": 1}', encoding="utf-8")  # pre-existing good data

    def boom(_decision, _score):
        raise SummaryUnavailableError("no key")

    # A missing key for summaries is batch-fatal — it aborts before write, leaving
    # the prior scores.json untouched (not overwritten with an unsummarised set).
    with pytest.raises(SummaryUnavailableError):
        _run(tmp_path, text_provider=lambda _u: "Inflation high.", summary_provider=boom)
    assert scores_path.read_text(encoding="utf-8") == '{"sentinel": 1}'


def test_run_score_without_decisions_raises(tmp_path) -> None:
    with pytest.raises(NoDecisionsError):
        _run(tmp_path, decisions_path=tmp_path / "missing.json", text_provider=lambda _u: "")
