"""Transformer component tests — a fake classifier, so no torch / no download."""

import pytest

from rba_scorer.score import transformer, transformer_models


def _classifier(per_sentence):
    """Return a fake classifier yielding the given per-sentence polarity prob dicts."""

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
    assert result.version == transformer_models.active_model().version()
    assert result.extra["n_sentences"] == 2
    assert result.extra["model_name"] == transformer_models.active_model().name


def test_clamps_and_handles_empty_text() -> None:
    result = transformer.score_text("", classifier=_classifier([]))
    assert result.net == 0.0
    assert result.extra["n_sentences"] == 0


def test_version_reflects_active_model(monkeypatch) -> None:
    monkeypatch.setenv(transformer_models.ENV_OVERRIDE, "fomc-roberta")
    probs = [{"hawkish": 1.0, "dovish": 0.0, "neutral": 0.0}]
    result = transformer.score_text("Hot.", classifier=_classifier(probs))
    assert result.net == pytest.approx(1.0)
    assert result.version.startswith("fomc-roberta:")
    assert transformer.component_version().startswith("fomc-roberta:")


def test_explicit_model_overrides_active() -> None:
    model = transformer_models.REGISTRY["fomc-roberta"]
    probs = [{"hawkish": 0.0, "dovish": 1.0, "neutral": 0.0}]
    result = transformer.score_text("Cold.", classifier=_classifier(probs), model=model)
    assert result.net == pytest.approx(-1.0)
    assert result.version == model.version()


def test_unknown_model_name_raises(monkeypatch) -> None:
    monkeypatch.setenv(transformer_models.ENV_OVERRIDE, "does-not-exist")
    with pytest.raises(transformer_models.UnknownTransformerModelError):
        transformer_models.active_model()


def test_map_to_polarity_4class_sums_shared_polarity() -> None:
    # fed-stance: LABEL_0 neutral, LABEL_1 hawkish, LABEL_2 dovish, LABEL_3 neutral
    label_map = transformer_models.REGISTRY["fed-stance"].label_map
    raw = [
        [
            {"label": "LABEL_0", "score": 0.1},
            {"label": "LABEL_1", "score": 0.6},
            {"label": "LABEL_2", "score": 0.2},
            {"label": "LABEL_3", "score": 0.1},
        ]
    ]
    [probs] = transformer._map_to_polarity(raw, label_map)
    assert probs["hawkish"] == pytest.approx(0.6)
    assert probs["dovish"] == pytest.approx(0.2)
    assert probs["neutral"] == pytest.approx(0.2)  # LABEL_0 + LABEL_3 summed
    assert transformer._sentence_net(probs) == pytest.approx(0.4)


def test_map_to_polarity_ignores_unmapped_labels() -> None:
    # A label absent from the map contributes nothing (coverage is enforced
    # separately, at classifier-build time).
    raw = [[{"label": "LABEL_0", "score": 0.8}, {"label": "LABEL_9", "score": 0.2}]]
    [probs] = transformer._map_to_polarity(raw, {"LABEL_0": "hawkish"})
    assert probs["hawkish"] == pytest.approx(0.8)
    assert probs["dovish"] == 0.0
    assert probs["neutral"] == 0.0


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


@pytest.mark.integration
def test_real_model_polarity_and_shape() -> None:
    """Load the real active model and score live text (plan step 16).

    Deselected by default (needs the ``transformer`` extra + a model download);
    run with ``uv run pytest -m integration``. Asserts the contract shape/range
    and that clearly hawkish text does not score below clearly dovish text — a
    polarity check that guards against an inverted label_map without coupling to
    exact model values.
    """
    model = transformer_models.active_model()
    classify = transformer._build_default_classifier(model)  # built once, reused
    hawkish = transformer.score_text(
        "The Board raised the cash rate to bring high inflation back to target.",
        classifier=classify,
        model=model,
    )
    dovish = transformer.score_text(
        "The Board cut the cash rate to support employment as growth weakened.",
        classifier=classify,
        model=model,
    )
    for r in (hawkish, dovish):
        assert -1.0 <= r.net <= 1.0
        assert r.sub_scores == {}  # net only
        assert r.evidence == ()
        assert r.version == model.version()
        assert r.extra["n_sentences"] >= 1
    assert hawkish.net >= dovish.net
