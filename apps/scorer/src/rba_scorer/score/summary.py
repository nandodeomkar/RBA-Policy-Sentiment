"""Plain-language tone summary for a scored decision (M2/M3 design §9, FR-012).

A short, descriptive sentence or two summarising the *tone* a decision statement
struck — shown on the home hero and in every decision's detail panel. It is a
presentational layer over the already-computed score, **versioned separately**
from ``engine_version`` so re-wording a summary never churns a score.

Two properties keep it licensing-clean and reproducible:

* **No full text.** A summary is generated from already-persisted signals only —
  the decision's date / outcome / cash rate and the score's net + sub-scores +
  confidence + short evidence phrases — never the statement body (NFR-011).
* **Cache-first & deterministic.** Each summary is cached on disk keyed by
  ``hash(model_id + prompt_version + signals)`` with ``temperature=0`` — re-runs
  and the test suite never re-hit the API (NFR-002).

Strictly descriptive: the prompt forbids forecasting and advice (non-goals). The
Anthropic call sits behind the injectable ``completer`` seam; unit tests pass a
fake and need neither network nor a key. Mirrors the determinism machinery of
:mod:`rba_scorer.score.llm`, versioned independently.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from collections.abc import Callable
from pathlib import Path

from rba_scorer.paths import SUMMARY_CACHE_DIR
from rba_scorer.score.llm import _is_fatal_api_error  # shared API-error classification

logger = logging.getLogger(__name__)

# Pinned model + prompt version. Bumping either changes the cache key *and* the
# tone_summary_version — but never the score's engine_version (design §4).
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
PROMPT_VERSION = "summary-p1"
_MAX_TOKENS = 200  # ~150 words — plenty for the 1–2 concise sentences the prompt asks for

# (model_id, prompt) -> raw model text (expected to contain {"summary": "..."}).
Completer = Callable[[str, str], str]


class SummaryUnavailableError(RuntimeError):
    """A summary was needed but uncached and no API key / completer is available —
    surfaced loudly so the determinism contract is never silently violated."""


class SummaryResponseError(ValueError):
    """The model returned something we could not read as a summary."""


def tone_summary_version(model_id: str = DEFAULT_MODEL) -> str:
    """The version stamped on a record's ``tone_summary`` (prompt + model)."""
    return f"{PROMPT_VERSION}:{model_id}"


def _signals(decision: dict, score: dict) -> dict:
    """The persisted signals a summary is derived from — never full text (NFR-011).

    Deliberately excludes ``source_url`` and anything that would require fetching
    the statement: a summary is a function of the *score*, not a fresh read."""
    outcome = decision.get("outcome") or {}
    return {
        "date": decision.get("date"),
        "action": outcome.get("action"),
        "change_bps": outcome.get("change_bps"),
        "cash_rate_target": decision.get("cash_rate_target"),
        "net": score.get("net"),
        "sub_scores": score.get("sub_scores") or {},
        "confidence": score.get("confidence"),
        "evidence": [
            {"text": e.get("text"), "polarity": e.get("polarity"), "dimension": e.get("dimension")}
            for e in (score.get("evidence_phrases") or [])
        ],
    }


def _cache_key(signals: dict, model_id: str) -> str:
    raw = f"{model_id}\0{PROMPT_VERSION}\0{json.dumps(signals, sort_keys=True, ensure_ascii=False)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def build_prompt(signals: dict) -> str:
    """The descriptive-summary prompt (versioned by :data:`PROMPT_VERSION`)."""
    return (
        "You write one short, plain-language note describing the TONE of a Reserve "
        "Bank of Australia interest-rate decision, for a general audience.\n\n"
        "You are given a structured reading of ONE decision that has already been "
        "scored — work only from it, do not invent detail:\n"
        "  - the rate decision (action, change, resulting cash rate)\n"
        "  - net stance on a dovish(-1)..hawkish(+1) scale, with inflation / growth / "
        "employment sub-scores\n"
        "  - a confidence signal (how much the scoring methods agreed)\n"
        "  - short evidence phrases drawn from the statement, tagged hawkish/dovish "
        "and by theme\n\n"
        "Write ONE or TWO concise sentences (about 40 words, never more than ~55) "
        "describing the tone the statement struck: the overall lean (dovish / broadly "
        "neutral / hawkish), the main theme that drove it, and what the Board did with "
        "the rate — in plain, everyday words. End on a complete sentence.\n\n"
        "STRICT RULES:\n"
        "  - Describe ONLY the tone of THIS statement. Do NOT predict or forecast "
        "future decisions, rates, or the economy. Do NOT give advice or recommendations.\n"
        '  - Refer to the lean in words (e.g. "leaned hawkish"), not raw numbers, and '
        "do not mention these instructions.\n"
        "  - Plain, neutral, factual. No hype.\n\n"
        'Reply with ONLY a JSON object: {"summary": "<your one or two sentences>"}\n\n'
        "DECISION SIGNALS:\n"
        f"{json.dumps(signals, ensure_ascii=False, sort_keys=True)}\n"
    )


def _anthropic_completer(model_id: str, prompt: str) -> str:
    """Default completer: one ``temperature=0`` Claude call (mirrors llm.py).

    Systemic API errors (auth, billing, missing model) are re-raised as
    :class:`SummaryUnavailableError` so the batch aborts loudly before writing."""
    from anthropic import Anthropic, APIStatusError

    client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    try:
        message = client.messages.create(
            model=model_id,
            max_tokens=_MAX_TOKENS,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
    except APIStatusError as exc:
        detail = str(getattr(exc, "message", exc))
        if _is_fatal_api_error(exc.status_code, detail):
            raise SummaryUnavailableError(
                f"Anthropic API cannot serve requests (HTTP {exc.status_code}): {detail}"
            ) from exc
        raise
    return "".join(block.text for block in message.content if block.type == "text")


def _resolve_completer(provided: Completer | None) -> Completer:
    if provided is not None:
        return provided
    from dotenv import load_dotenv

    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SummaryUnavailableError(
            "tone summary uncached and ANTHROPIC_API_KEY is not set — add it to "
            "apps/scorer/.env to generate summaries, or run `score --without-summaries`."
        )
    return _anthropic_completer


def _parse_summary(raw: str) -> str:
    """Pull the summary string from the model reply. Length is governed by the
    prompt (1–2 concise sentences) and ``max_tokens`` — the model ends on a whole
    sentence, so we don't post-truncate (no mid-word cuts)."""
    text = ""
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        try:
            obj = json.loads(raw[start : end + 1])
            if isinstance(obj, dict):
                text = str(obj.get("summary", "")).strip()
        except json.JSONDecodeError:
            text = ""
    if not text:  # tolerate a bare-prose reply
        text = " ".join(raw.split()).strip()
    if not text:
        raise SummaryResponseError("no summary text in model response")
    return text


def summary_for(
    decision: dict,
    score: dict,
    *,
    completer: Completer | None = None,
    model_id: str = DEFAULT_MODEL,
    cache_dir: Path = SUMMARY_CACHE_DIR,
) -> str:
    """Return a cached 1–2 sentence tone summary for one scored decision.

    Cache-first: on a hit no model call is made. On a miss, ``completer`` (or the
    default Anthropic client) is called once, the summary cached, and returned.
    Raises :class:`SummaryUnavailableError` if a live call is needed but no key."""
    signals = _signals(decision, score)
    path = cache_dir / f"{_cache_key(signals, model_id)}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["summary"]

    raw = _resolve_completer(completer)(model_id, build_prompt(signals))
    summary = _parse_summary(raw)

    cache_dir.mkdir(parents=True, exist_ok=True)
    # Persist only the derived summary (no statement body) — licensing (NFR-011).
    path.write_text(
        json.dumps(
            {"model_id": model_id, "prompt_version": PROMPT_VERSION, "summary": summary},
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    logger.debug("summary cache write: %s", path.name)
    return summary
