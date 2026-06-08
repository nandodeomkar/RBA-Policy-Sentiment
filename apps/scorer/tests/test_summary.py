"""Tone-summary tests — a fake completer, so no network or API key (FR-012)."""

import json

import pytest

from rba_scorer.score import summary

# A decision + its score record, as persisted in scores.json. `source_url` is
# present on the decision but must NOT feed the summary (no full-text fetch).
_DECISION = {
    "id": "2024-02-06",
    "date": "2024-02-06",
    "outcome": {"action": "hold", "change_bps": 0},
    "cash_rate_target": 4.35,
    "source_url": "https://www.rba.gov.au/media-releases/2024/mr-24-01.html",
}
_SCORE = {
    "net": 0.31,
    "sub_scores": {"inflation": 0.40, "growth": -0.10, "employment": 0.0},
    "confidence": 0.7,
    "evidence_phrases": [
        {"text": "upside risks to inflation", "polarity": "hawkish", "dimension": "inflation"}
    ],
}


def _completer(text: str):
    """A fake completer that records call count and returns ``text`` as JSON."""
    calls = {"n": 0}

    def complete(_model_id: str, _prompt: str) -> str:
        calls["n"] += 1
        return "here you go: " + json.dumps({"summary": text})  # prose around the JSON

    return complete, calls


def test_caches_and_does_not_recall(tmp_path) -> None:
    complete, calls = _completer("The Board held the cash rate, leaning hawkish on inflation.")
    s1 = summary.summary_for(_DECISION, _SCORE, completer=complete, cache_dir=tmp_path)
    s2 = summary.summary_for(_DECISION, _SCORE, completer=complete, cache_dir=tmp_path)
    assert s1 == s2 == "The Board held the cash rate, leaning hawkish on inflation."
    assert calls["n"] == 1  # second served from cache

    cached = list(tmp_path.glob("*.json"))
    assert len(cached) == 1
    blob = cached[0].read_text(encoding="utf-8")
    assert summary.PROMPT_VERSION in blob
    assert _DECISION["source_url"] not in blob  # no statement URL / body persisted (NFR-011)


def test_derives_only_from_persisted_signals() -> None:
    sig = summary._signals(_DECISION, _SCORE)
    # Only score-derived signals — never source_url or anything needing a fetch.
    assert set(sig) == {
        "date",
        "action",
        "change_bps",
        "cash_rate_target",
        "net",
        "sub_scores",
        "confidence",
        "evidence",
    }
    assert "source_url" not in sig
    # The prompt is built purely from those signals (the short evidence phrase rides through).
    assert "upside risks to inflation" in summary.build_prompt(sig)


def test_cache_key_tracks_the_score(tmp_path) -> None:
    complete, calls = _completer("a summary")
    summary.summary_for(_DECISION, _SCORE, completer=complete, cache_dir=tmp_path)
    # A different net is different signals → a different cache key → a fresh call.
    summary.summary_for(_DECISION, dict(_SCORE, net=-0.5), completer=complete, cache_dir=tmp_path)
    assert calls["n"] == 2


def test_uncached_without_key_raises(monkeypatch) -> None:
    import dotenv

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: False)  # don't read any .env
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(summary.SummaryUnavailableError):
        summary._resolve_completer(None)  # no completer + no key → loud, not a silent live call


def test_parse_summary_handles_json_and_prose() -> None:
    assert summary._parse_summary('{"summary": "Hawkish hold."}') == "Hawkish hold."
    assert summary._parse_summary('Sure: {"summary": "Dovish cut."} ') == "Dovish cut."
    assert summary._parse_summary("Just prose, no JSON here.") == "Just prose, no JSON here."
    with pytest.raises(summary.SummaryResponseError):
        summary._parse_summary("   ")


def test_tone_summary_version_format() -> None:
    v = summary.tone_summary_version()
    assert v.startswith(summary.PROMPT_VERSION + ":")
    assert summary.DEFAULT_MODEL in v
