"""Net-only transformer stance scorer (design §6 component 3; pluggable per 2026-06-07).

A finance-domain text-classification model labels each sentence hawkish / dovish
/ neutral (some models add an "irrelevant" class); we map that to a per-sentence
net (``P(hawkish) − P(dovish)``) and average. It is **net only** — not
dimension-aware — so it contributes no sub-scores and emits no evidence phrases.

*Which* model runs is decided by :mod:`rba_scorer.score.transformer_models` (one
active adapter at a time); this module is model-agnostic. The heavy
``torch``/``transformers`` dependency and the model call sit behind the
injectable ``classifier`` seam, so the default unit suite mocks it and needs
neither the ``transformer`` extra nor a download. The real classifier runs in
eval mode at a pinned revision → deterministic (NFR-002).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

from rba_scorer.score.base import ComponentResult
from rba_scorer.score.segment import split_sentences
from rba_scorer.score.transformer_models import TransformerModel, active_model

logger = logging.getLogger(__name__)

# sentences -> per-sentence {"hawkish": p, "dovish": p, "neutral": p}.
Classifier = Callable[[Sequence[str]], list[dict[str, float]]]


class TransformerUnavailableError(RuntimeError):
    """The transformer was needed but ``torch``/``transformers`` (the ``transformer``
    extra) is not installed and no classifier was injected (design §9)."""


class TransformerLabelMapError(RuntimeError):
    """The active model emits labels the adapter's ``label_map`` does not cover —
    scoring it would silently drop signal, so fail loud (design §6 self-check)."""


# Built classifiers are cached per model version so a batch run loads each model
# once, not once per decision.
_CLASSIFIER_CACHE: dict[str, Classifier] = {}


def component_version() -> str:
    """The version stamped on this component's output — the active model's."""
    return active_model().version()


def _sentence_net(probs: dict[str, float]) -> float:
    """Map one sentence's polarity probabilities to net ∈ [−1, 1]."""
    return float(probs.get("hawkish", 0.0)) - float(probs.get("dovish", 0.0))


def _map_to_polarity(
    raw: list[list[dict[str, object]]], label_map: dict[str, str]
) -> list[dict[str, float]]:
    """Fold raw classifier output (per sentence: a list of ``{label, score}``)
    into per-sentence polarity probabilities, **summing** labels that share a
    polarity (e.g. neutral + irrelevant). Pure → unit-testable without a model."""
    out: list[dict[str, float]] = []
    for result in raw:
        probs = {"hawkish": 0.0, "dovish": 0.0, "neutral": 0.0}
        for entry in result:
            polarity = label_map.get(str(entry["label"]))
            if polarity in probs:
                probs[polarity] += float(entry["score"])
        out.append(probs)
    return out


def _build_default_classifier(model: TransformerModel) -> Classifier:
    """Construct (and cache) the real Hugging Face classifier for ``model``.

    Imports ``transformers``/``torch`` lazily so the core env never needs them.
    Self-checks that the model's label set is covered by the adapter's
    ``label_map`` — an uncovered label would silently drop signal."""
    cached = _CLASSIFIER_CACHE.get(model.version())
    if cached is not None:
        return cached

    try:
        from transformers import pipeline
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise TransformerUnavailableError(
            "transformer component needs the 'transformer' extra — run "
            "`uv sync --extra transformer` (implementation plan step 16)."
        ) from exc

    pipe = pipeline(
        "text-classification",
        model=model.model_id,
        revision=model.revision,
        top_k=None,  # return all class scores
    )

    # Fail loud if the model can emit a label the adapter doesn't map (guards the
    # inverted-/stale-map risk on any future model swap).
    unmapped = sorted(set(pipe.model.config.id2label.values()) - set(model.label_map))
    if unmapped:
        raise TransformerLabelMapError(
            f"{model.name} ({model.model_id}@{model.revision[:8]}): model labels "
            f"{unmapped} are not in label_map {sorted(model.label_map)} — verify the "
            "mapping against the model card before scoring."
        )

    def classify(sentences: Sequence[str]) -> list[dict[str, float]]:
        raw = pipe(list(sentences), truncation=True, max_length=model.max_tokens)
        return _map_to_polarity(raw, model.label_map)

    _CLASSIFIER_CACHE[model.version()] = classify
    return classify


def score_text(
    text: str,
    *,
    classifier: Classifier | None = None,
    model: TransformerModel | None = None,
) -> ComponentResult:
    """Score ``text`` with the active transformer model. Net is the mean
    per-sentence ``P(hawkish) − P(dovish)``; no sub-scores, no evidence.

    ``model`` defaults to the active adapter; ``classifier`` is the injectable
    seam the unit suite uses to avoid any model download."""
    model = model or active_model()
    sentences = split_sentences(text)
    classify = classifier or _build_default_classifier(model)

    nets = [_sentence_net(p) for p in classify(sentences)] if sentences else []
    net = max(-1.0, min(1.0, sum(nets) / len(nets))) if nets else 0.0

    return ComponentResult(
        net=net,
        version=model.version(),
        sub_scores={},  # net only — not dimension-aware
        evidence=(),
        extra={
            "model_name": model.name,
            "model_id": model.model_id,
            "model_revision": model.revision,
            "n_sentences": len(sentences),
        },
    )
