"""FOMC-RoBERTa net-only scorer (design §6, component 3).

A finance-domain transformer (``gtfintechlab/FOMC-RoBERTa``) classifies each
sentence as hawkish / dovish / neutral; we map that to a per-sentence net
(``P(hawkish) − P(dovish)``) and average. It is **net only** — not
dimension-aware — so it contributes no sub-scores (a documented methodology
limitation) and emits no evidence phrases.

The model is Fed-trained; whether it transfers to RBA text is validated on the
dev split during step 16 (design §13). The heavy ``torch``/``transformers``
dependency and the model call sit behind the injectable ``classifier`` seam, so
the default unit suite mocks it and needs neither the ``transformer`` extra nor a
download. Runs in eval mode with a pinned revision → deterministic (NFR-002).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

from rba_scorer.score.base import ComponentResult
from rba_scorer.score.segment import split_sentences

logger = logging.getLogger(__name__)

MODEL_NAME = "gtfintechlab/FOMC-RoBERTa"
# TODO(step 16, human checkpoint): pin to the resolved commit SHA on the first
# live run. "main" is a placeholder; the resolved revision is stamped into the
# component version below so the engine_version tracks it.
DEFAULT_REVISION = "main"

# Raw classifier labels → our polarity vocabulary. Confirm against the model card
# at the step-16 live run (design §13 "FOMC-RoBERTa transfer").
LABEL_MAP: dict[str, str] = {
    "LABEL_0": "dovish",
    "LABEL_1": "hawkish",
    "LABEL_2": "neutral",
    # Some checkpoints expose human-readable labels directly:
    "dovish": "dovish",
    "hawkish": "hawkish",
    "neutral": "neutral",
}

# sentences -> per-sentence {"hawkish": p, "dovish": p, "neutral": p}.
Classifier = Callable[[Sequence[str]], list[dict[str, float]]]


class TransformerUnavailableError(RuntimeError):
    """The transformer was needed but ``torch``/``transformers`` (the ``transformer``
    extra) is not installed and no classifier was injected (design §9)."""


def component_version(revision: str = DEFAULT_REVISION) -> str:
    """The pinned version stamped on this component's output."""
    return f"fomc-roberta:{revision}"


def _sentence_net(probs: dict[str, float]) -> float:
    """Map one sentence's class probabilities to net ∈ [−1, 1]."""
    return float(probs.get("hawkish", 0.0)) - float(probs.get("dovish", 0.0))


def _build_default_classifier(revision: str) -> Classifier:
    """Construct the real FOMC-RoBERTa classifier. Imports ``transformers``/``torch``
    lazily so the core env never needs them."""
    try:
        from transformers import pipeline
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise TransformerUnavailableError(
            "transformer component needs the 'transformer' extra — run "
            "`uv sync --extra transformer` (implementation plan step 16)."
        ) from exc

    pipe = pipeline(
        "text-classification",
        model=MODEL_NAME,
        revision=revision,
        top_k=None,  # return all class scores
    )

    def classify(sentences: Sequence[str]) -> list[dict[str, float]]:
        out: list[dict[str, float]] = []
        for result in pipe(list(sentences)):
            probs = {"hawkish": 0.0, "dovish": 0.0, "neutral": 0.0}
            for entry in result:
                mapped = LABEL_MAP.get(entry["label"], entry["label"])
                if mapped in probs:
                    probs[mapped] = float(entry["score"])
            out.append(probs)
        return out

    return classify


def score_text(
    text: str,
    *,
    classifier: Classifier | None = None,
    revision: str = DEFAULT_REVISION,
) -> ComponentResult:
    """Score ``text`` with the transformer component. Net is the mean per-sentence
    ``P(hawkish) − P(dovish)``; no sub-scores, no evidence."""
    sentences = split_sentences(text)
    classify = classifier or _build_default_classifier(revision)

    nets = [_sentence_net(p) for p in classify(sentences)] if sentences else []
    net = max(-1.0, min(1.0, sum(nets) / len(nets))) if nets else 0.0

    return ComponentResult(
        net=net,
        version=component_version(revision),
        sub_scores={},  # net only — not dimension-aware
        evidence=(),
        extra={"model_revision": revision, "model_name": MODEL_NAME, "n_sentences": len(sentences)},
    )
