"""Transformer component tests — a fake classifier, so no torch / no download."""

import pytest

from rba_scorer.score import transformer


def _classifier(per_sentence):
    """Return a fake classifier yielding the given per-sentence prob dicts in order."""

    def classify(sentences):
        assert len(sentences) == len(per_sentence)
        return list(per_sentence)

    return classify


def test_net_is_mean_hawkish_minus_dovish() -> None:
    probs = [
        {"hawkish": 0.7, "dovish": 0.2, "neutral": 0.1},  # net +0.5
        {"hawkish": 0.1, "dovish": 0.6, "neutral": 0.3},  # net -0.5
    ]
    result = transformer.score_text(
        "Inflation is high. Growth has slowed.", classifier=_classifier(probs)
    )
    assert result.net == pytest.approx(0.0)
    assert result.sub_scores == {}  # net only — not dimension-aware
    assert result.evidence == ()
    assert result.version == "fomc-roberta:main"
    assert result.extra["n_sentences"] == 2


def test_clamps_and_handles_empty_text() -> None:
    result = transformer.score_text("", classifier=_classifier([]))
    assert result.net == 0.0
    assert result.extra["n_sentences"] == 0


def test_revision_flows_into_version() -> None:
    probs = [{"hawkish": 1.0, "dovish": 0.0, "neutral": 0.0}]
    result = transformer.score_text("Hot.", classifier=_classifier(probs), revision="abc123")
    assert result.net == pytest.approx(1.0)
    assert result.version == "fomc-roberta:abc123"


def test_missing_extra_without_classifier_is_unavailable(monkeypatch) -> None:
    # Simulate the 'transformer' extra not being installed.
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "transformers":
            raise ImportError("no transformers")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(transformer.TransformerUnavailableError):
        transformer.score_text("Inflation is high.")
