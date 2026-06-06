"""LLM component tests — a fake completer, so no network or API key (design §8)."""

import json

import pytest

from rba_scorer.score import llm


def _completer(payload: dict):
    """A fake completer that records call count and returns ``payload`` as JSON."""
    calls = {"n": 0}

    def complete(_model_id: str, _prompt: str) -> str:
        calls["n"] += 1
        return "here is the result: " + json.dumps(payload)  # prose around the JSON

    return complete, calls


_PAYLOAD = {
    "classifications": [
        {
            "phrase": "upside risks to inflation",
            "dimension": "inflation",
            "polarity": "hawkish",
            "intensity": 0.8,
        },
        {
            "phrase": "growth has been subdued",
            "dimension": "growth",
            "polarity": "dovish",
            "intensity": 0.6,
        },
        {"phrase": "off topic", "dimension": "other", "polarity": "hawkish", "intensity": 1.0},
    ],
    "rationale": "mixed but tilted hawkish on inflation",
}


def test_aggregates_classifications_to_contract(tmp_path) -> None:
    complete, _ = _completer(_PAYLOAD)
    result = llm.score_text("Inflation is high.", completer=complete, cache_dir=tmp_path)

    # net = mean of signed intensities over *valid* rows: (+0.8, -0.6); "other" dropped.
    assert result.net == pytest.approx((0.8 - 0.6) / 2)
    assert result.sub_scores["inflation"] == pytest.approx(0.8)
    assert result.sub_scores["growth"] == pytest.approx(-0.6)
    assert result.sub_scores["employment"] == 0.0
    assert llm.PROMPT_VERSION in result.version and result.version.endswith(llm.AGG_VERSION)
    assert result.extra["rationale"] == "mixed but tilted hawkish on inflation"
    phrases = {e.text for e in result.evidence}
    assert phrases == {"upside risks to inflation", "growth has been subdued"}


def test_long_evidence_phrase_is_capped(tmp_path) -> None:
    long_phrase = " ".join(f"word{i}" for i in range(30))  # 30 words — over the cap
    payload = {
        "classifications": [
            {
                "phrase": long_phrase,
                "dimension": "inflation",
                "polarity": "hawkish",
                "intensity": 0.5,
            }
        ],
        "rationale": "x",
    }
    result = llm.score_text("t", completer=lambda _m, _p: json.dumps(payload), cache_dir=tmp_path)
    (ev,) = result.evidence
    assert len(ev.text.split()) <= llm._MAX_PHRASE_WORDS  # no full-text span persisted (NFR-011)
    assert ev.text.endswith("…")
    assert result.net == pytest.approx(0.5)  # truncating the quote doesn't change the score
    blob = next(tmp_path.glob("*.json")).read_text(encoding="utf-8")
    assert long_phrase not in blob  # the committed cache is sanitized too, not just scores.json


def test_caches_and_does_not_recall(tmp_path) -> None:
    complete, calls = _completer(_PAYLOAD)
    llm.score_text("Inflation is high.", completer=complete, cache_dir=tmp_path)
    llm.score_text("Inflation is high.", completer=complete, cache_dir=tmp_path)
    assert calls["n"] == 1  # second call served from cache

    cached = list(tmp_path.glob("*.json"))
    assert len(cached) == 1
    blob = cached[0].read_text(encoding="utf-8")
    assert "Inflation is high." not in blob  # no full statement text persisted (NFR-011)
    assert "upside risks to inflation" in blob  # only short phrases


def test_uncached_without_key_raises(monkeypatch) -> None:
    import dotenv

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: False)  # don't read any .env
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(llm.LLMUnavailableError):
        llm._resolve_completer(None)  # no completer + no key → loud, not a silent live call


def test_unparseable_response_raises(tmp_path) -> None:
    def complete(_m, _p):
        return "I cannot help with that."

    with pytest.raises(llm.LLMResponseError):
        llm.score_text("text", completer=complete, cache_dir=tmp_path)


def test_is_fatal_api_error_classification() -> None:
    # Systemic precondition failures → batch-fatal.
    assert llm._is_fatal_api_error(401, "invalid x-api-key")
    assert llm._is_fatal_api_error(403, "permission denied")
    assert llm._is_fatal_api_error(404, "model: unknown")
    assert llm._is_fatal_api_error(
        400, "Your credit balance is too low to access the Anthropic API."
    )
    # Transient / per-request → not fatal (skip-and-retry-later, not a wipe).
    assert not llm._is_fatal_api_error(400, "max_tokens is too large for this request")
    assert not llm._is_fatal_api_error(429, "rate limited")
    assert not llm._is_fatal_api_error(529, "overloaded")


def test_empty_classifications_is_neutral(tmp_path) -> None:
    def complete(_m, _p):
        return json.dumps({"classifications": [], "rationale": "no stance"})

    result = llm.score_text("text", completer=complete, cache_dir=tmp_path)
    assert result.net == 0.0
    assert all(v == 0.0 for v in result.sub_scores.values())
