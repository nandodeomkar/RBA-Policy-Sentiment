"""Claude sentence-level hawkish/dovish scorer (design §6, component 2).

The model reads a statement and returns, as structured JSON, a list of
policy-relevant **short verbatim phrases** (≤ ~15 words) each tagged with a
dimension (inflation/growth/employment), a polarity (hawkish/dovish), and an
intensity in [0, 1], plus a one-line rationale. We aggregate those into the
shared ``net + sub_scores`` contract.

Two properties make this licensing-clean and reproducible:

* **No full text is ever persisted.** Only the short phrases + rationale are
  cached — the statement body is sent to the API transiently and discarded.
* **Cache-first & deterministic.** Every response is cached on disk keyed by
  ``hash(model_id + prompt_version + text)`` and the call uses ``temperature=0``,
  so re-runs and the test suite never re-hit the API (NFR-002, design §10).

The Anthropic call sits behind the injectable ``completer`` seam; unit tests
pass a fake and need neither network nor an API key.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from collections.abc import Callable
from pathlib import Path

from rba_scorer.paths import LLM_CACHE_DIR
from rba_scorer.score.base import DIMENSIONS, ComponentResult, EvidencePhrase, Polarity

logger = logging.getLogger(__name__)

# Default model + prompt version. Bumping either changes the cache key *and* the
# component version (so the composite engine_version moves too) — design §6/§10.
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
PROMPT_VERSION = "llm-p1"
_MAX_TOKENS = 1536

# Aggregation-logic version. Part of the component version (so changing how we
# reduce the payload re-scores), but deliberately NOT part of the cache key — a
# re-aggregation reuses the cached model responses rather than re-calling the API.
AGG_VERSION = "agg-v1"

# Hard cap on a persisted evidence phrase, enforced regardless of what the model
# returns: we store only short verbatim quotes, never long spans (licensing, NFR-011).
_MAX_PHRASE_WORDS = 15

# (model_id, prompt) -> raw model text (expected to contain the JSON payload).
Completer = Callable[[str, str], str]

_POLARITIES: tuple[str, ...] = ("hawkish", "dovish")


class LLMUnavailableError(RuntimeError):
    """A score was needed but the response was uncached and no API key / completer
    is available — surfaced loudly so the determinism contract is never silently
    violated (design §9)."""


class LLMResponseError(ValueError):
    """The model returned something we could not parse into the expected schema."""


def component_version(model_id: str = DEFAULT_MODEL) -> str:
    """The pinned version stamped on this component's output (model + prompt + agg)."""
    return f"{model_id}:{PROMPT_VERSION}:{AGG_VERSION}"


def build_prompt(text: str) -> str:
    """The sentence-classification prompt. Kept in code (versioned by
    :data:`PROMPT_VERSION`) so the cache key tracks any wording change."""
    dims = ", ".join(DIMENSIONS)
    return (
        "You are a monetary-policy analyst classifying the tone of a Reserve Bank "
        "of Australia interest-rate decision statement.\n\n"
        "Read the statement below. Identify every sentence that signals policy "
        "stance and, for each, extract ONE short verbatim phrase (at most 15 words, "
        "copied exactly from the text) with:\n"
        f"  - dimension: one of [{dims}] (the economic theme it speaks to)\n"
        '  - polarity: "hawkish" (favours tighter policy / higher rates) or '
        '"dovish" (favours easier policy / lower rates)\n'
        "  - intensity: a number from 0 to 1 for how strong the signal is\n\n"
        "Ignore sentences with no clear stance. Do not invent phrases; copy them "
        "verbatim. Reply with ONLY a JSON object, no prose, of the form:\n"
        '{"classifications": [{"phrase": "...", "dimension": "inflation", '
        '"polarity": "hawkish", "intensity": 0.8}], "rationale": "one sentence"}\n\n'
        "STATEMENT:\n"
        f"{text}\n"
    )


def _cache_key(text: str, model_id: str) -> str:
    raw = f"{model_id}\0{PROMPT_VERSION}\0{text}".encode()
    return hashlib.sha256(raw).hexdigest()[:32]


def _cache_path(text: str, model_id: str, cache_dir: Path) -> Path:
    return cache_dir / f"{_cache_key(text, model_id)}.json"


def _parse_payload(raw: str) -> dict:
    """Extract the JSON object from the model's reply. Tolerant of leading/trailing
    prose by slicing to the outermost braces."""
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end <= start:
        raise LLMResponseError("no JSON object found in model response")
    try:
        payload = json.loads(raw[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMResponseError(f"invalid JSON in model response: {exc}") from exc
    if not isinstance(payload, dict) or "classifications" not in payload:
        raise LLMResponseError("response JSON missing 'classifications'")
    return payload


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _clamp_unit(value: float) -> float:
    return max(-1.0, min(1.0, value))


def _shorten(phrase: str) -> str:
    """Bound a persisted evidence quote to the licensing cap; over-long phrases are
    truncated to the first ``_MAX_PHRASE_WORDS`` words with an ellipsis."""
    words = phrase.split()
    if len(words) <= _MAX_PHRASE_WORDS:
        return phrase
    return " ".join(words[:_MAX_PHRASE_WORDS]) + "…"


def _sanitize_payload(payload: dict) -> dict:
    """Cap every classification phrase *before* caching, so the committed cache
    (design §10) never holds a long verbatim span either — not just scores.json
    (licensing, NFR-011). Mutates and returns the payload."""
    for item in payload.get("classifications") or []:
        if isinstance(item, dict) and "phrase" in item:
            item["phrase"] = _shorten(str(item["phrase"]).strip())
    return payload


def _aggregate(payload: dict, model_id: str) -> ComponentResult:
    """Reduce the model's per-phrase classifications to the shared contract.

    A phrase contributes a signed value = ``±intensity`` (hawkish +, dovish −).
    Net is the mean over all valid phrases; each sub-score is the mean over the
    phrases tagged to that dimension (0.0 if none)."""
    by_dim: dict[str, list[float]] = {dim: [] for dim in DIMENSIONS}
    signed_all: list[float] = []
    evidence: list[EvidencePhrase] = []
    seen: set[tuple[str, str, str]] = set()

    for item in payload.get("classifications") or []:
        if not isinstance(item, dict):
            continue
        dim = str(item.get("dimension", "")).lower()
        pol = str(item.get("polarity", "")).lower()
        phrase = str(item.get("phrase", "")).strip()
        if dim not in DIMENSIONS or pol not in _POLARITIES or not phrase:
            continue  # skip off-schema rows (e.g. dimension "other") rather than fail
        try:
            intensity = max(0.0, min(1.0, float(item.get("intensity", 0.0))))
        except (TypeError, ValueError):
            continue
        polarity: Polarity = pol  # type: ignore[assignment]
        signed = intensity if polarity == "hawkish" else -intensity
        by_dim[dim].append(signed)
        signed_all.append(signed)
        phrase = _shorten(phrase)  # enforce the licensing cap before persisting (NFR-011)
        key = (phrase.lower(), polarity, dim)
        if key not in seen:
            seen.add(key)
            evidence.append(EvidencePhrase(text=phrase, polarity=polarity, dimension=dim))

    sub_scores = {dim: _clamp_unit(_mean(by_dim[dim])) for dim in DIMENSIONS}
    rationale = str(payload.get("rationale", "")).strip()
    return ComponentResult(
        net=_clamp_unit(_mean(signed_all)),
        version=component_version(model_id),
        sub_scores=sub_scores,
        evidence=tuple(evidence),
        extra={"model_id": model_id, "rationale": rationale},
    )


# 4xx statuses that mean the account/config can't serve *any* request (auth,
# permission, missing model) — systemic, never a per-page issue.
_FATAL_API_STATUSES: frozenset[int] = frozenset({401, 403, 404})


def _is_fatal_api_error(status_code: int | None, message: str) -> bool:
    """True if an Anthropic API error is a systemic precondition failure (auth,
    permission, missing model, or exhausted credit) rather than a transient or
    per-request one (e.g. an overloaded 5xx, or one over-long input)."""
    if status_code in _FATAL_API_STATUSES:
        return True
    low = message.lower()
    return status_code == 400 and ("credit" in low or "billing" in low)


def _anthropic_completer(model_id: str, prompt: str) -> str:
    """Default completer: one ``temperature=0`` Claude call. Imported lazily so
    the SDK/key are only needed for an actual cache-miss live run.

    Systemic API errors (auth, billing, missing model) are re-raised as
    :class:`LLMUnavailableError` so the batch aborts loudly instead of skipping
    every decision and writing an empty result (design §9)."""
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
            raise LLMUnavailableError(
                f"Anthropic API cannot serve requests (HTTP {exc.status_code}): {detail}"
            ) from exc
        raise
    return "".join(block.text for block in message.content if block.type == "text")


def _resolve_completer(provided: Completer | None) -> Completer:
    if provided is not None:
        return provided
    # Live path: require a key up front so a cache miss fails loudly, not mid-batch.
    from dotenv import load_dotenv

    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise LLMUnavailableError(
            "LLM response uncached and ANTHROPIC_API_KEY is not set — add it to "
            "apps/scorer/.env to run the LLM component live (implementation plan step 15)."
        )
    return _anthropic_completer


def score_text(
    text: str,
    *,
    completer: Completer | None = None,
    model_id: str = DEFAULT_MODEL,
    cache_dir: Path = LLM_CACHE_DIR,
) -> ComponentResult:
    """Score ``text`` with the LLM component, reading/writing the on-disk cache.

    On a cache hit no model call is made. On a miss, ``completer`` (or the default
    Anthropic client) is called once, the parsed payload is cached, and the result
    is aggregated. Raises :class:`LLMUnavailableError` if a live call is needed
    but unavailable."""
    path = _cache_path(text, model_id, cache_dir)
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))["payload"]
        return _aggregate(payload, model_id)

    raw = _resolve_completer(completer)(model_id, build_prompt(text))
    payload = _sanitize_payload(_parse_payload(raw))

    cache_dir.mkdir(parents=True, exist_ok=True)
    # Persist only the structured payload (short phrases + rationale) — never the
    # statement body (licensing, NFR-011).
    path.write_text(
        json.dumps(
            {"model_id": model_id, "prompt_version": PROMPT_VERSION, "payload": payload},
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    logger.debug("llm cache write: %s", path.name)
    return _aggregate(payload, model_id)
