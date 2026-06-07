"""The transformer model catalog — one swappable model at a time (design 2026-06-07).

Each model the transformer slot can run is a :class:`TransformerModel`: a frozen
record of everything model-specific (HF repo id, pinned revision, the raw-label
→ polarity map, truncation length). ``ACTIVE_MODEL_NAME`` picks the one the
ensemble runs; the ``RBA_TRANSFORMER_MODEL`` env var can override it for
experiments. The active model's ``version()`` flows into the composite
``engine_version``, so swapping models re-scores honestly and the same config
stays reproducible (NFR-002).

Adding or swapping a model is a one-record change here; ``transformer.py`` stays
model-agnostic.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Our polarity vocabulary. Only hawkish/dovish move the net (P(hawkish) −
# P(dovish)); "neutral" — and any off-topic/"irrelevant" class mapped to it —
# contributes 0.
POLARITIES: tuple[str, ...] = ("hawkish", "dovish", "neutral")

ENV_OVERRIDE = "RBA_TRANSFORMER_MODEL"


@dataclass(frozen=True)
class TransformerModel:
    """One swappable transformer model (design §4).

    ``label_map`` maps the model's *raw* output labels (as in
    ``config.id2label`` — e.g. ``"LABEL_1"``) to our polarity vocabulary.
    ``version()`` is stamped into ``engine_version``, so it must change whenever
    the model or its revision changes.
    """

    name: str
    model_id: str
    revision: str
    label_map: dict[str, str]
    max_tokens: int = 128

    def __post_init__(self) -> None:
        bad = sorted({p for p in self.label_map.values() if p not in POLARITIES})
        if bad:
            raise ValueError(f"{self.name}: label_map polarities {bad} not in {POLARITIES}")

    def version(self) -> str:
        """Component version string folded into the composite ``engine_version``."""
        return f"{self.name}:{self.revision}"


class UnknownTransformerModelError(ValueError):
    """The selected transformer model name is not in the REGISTRY."""


# The catalog. Add a model = add a record; keys are short + stable (they appear
# in the persisted engine_version).
REGISTRY: dict[str, TransformerModel] = {
    # Interim, non-gated: Federal Reserve stance classifier (RoBERTa-base) — the
    # newer generation of the FOMC hawkish/dovish task. Labels verified from the
    # model card: 0 neutral, 1 hawkish, 2 dovish, 3 irrelevant.
    "fed-stance": TransformerModel(
        name="fed-stance",
        model_id="gtfintechlab/model_federal_reserve_system_stance_label",
        revision="7695c0aebcd1a85ee23ff41df6a57b024e20f82b",
        label_map={
            "LABEL_0": "neutral",
            "LABEL_1": "hawkish",
            "LABEL_2": "dovish",
            "LABEL_3": "neutral",  # "irrelevant" — no hawkish/dovish signal
        },
    ),
    # The original M0 design model. GATED on HF — its label order CANNOT be
    # confirmed while gated, so this map is PROVISIONAL: verify against
    # config.id2label on the first authenticated load before making it active.
    # (transformer.py's startup self-check raises if the real labels are not
    # covered.) Revision resolved via model_info on 2026-06-07.
    "fomc-roberta": TransformerModel(
        name="fomc-roberta",
        model_id="gtfintechlab/FOMC-RoBERTa",
        revision="aa3bc4281fb1fe73c8872e09ad5c64b898f90d83",
        label_map={
            "LABEL_0": "dovish",
            "LABEL_1": "hawkish",
            "LABEL_2": "neutral",
        },
    ),
}

# The model the ensemble runs. Swap = change this (or set RBA_TRANSFORMER_MODEL).
ACTIVE_MODEL_NAME = "fed-stance"


def active_model() -> TransformerModel:
    """Resolve the active model: ``RBA_TRANSFORMER_MODEL`` if set, else
    ``ACTIVE_MODEL_NAME``. Raises :class:`UnknownTransformerModelError` if the
    name is not in the registry."""
    override = os.environ.get(ENV_OVERRIDE)
    name = override or ACTIVE_MODEL_NAME
    try:
        return REGISTRY[name]
    except KeyError as exc:
        known = ", ".join(sorted(REGISTRY))
        src = f" (from ${ENV_OVERRIDE})" if override else ""
        raise UnknownTransformerModelError(
            f"unknown transformer model {name!r}{src}; known models: {known}"
        ) from exc
