"""Reconciliation tests (design §6, plan step 17) — pure, synthetic inputs."""

import statistics

import pytest

from rba_scorer.score.base import ComponentResult, EvidencePhrase
from rba_scorer.score.reconcile import reconcile


def _lexicon(net=0.3) -> ComponentResult:
    return ComponentResult(
        net=net,
        version="lex",
        sub_scores={"inflation": 0.5, "growth": -0.2, "employment": 0.1},
        evidence=(EvidencePhrase("upside risks to inflation", "hawkish", "inflation"),),
    )


def _llm(net=0.2) -> ComponentResult:
    return ComponentResult(
        net=net,
        version="llm",
        sub_scores={"inflation": 0.5, "growth": 0.0, "employment": 0.3},
        evidence=(
            EvidencePhrase("upside risks to inflation", "hawkish", "inflation"),
            EvidencePhrase("growth has been subdued", "dovish", "growth"),
        ),
    )


def _transformer(net=0.25) -> ComponentResult:
    return ComponentResult(net=net, version="tf")  # net only


def test_net_is_equal_weighted_mean() -> None:
    r = reconcile({"lexicon": _lexicon(0.3), "llm": _llm(0.2), "transformer": _transformer(0.25)})
    assert r.net == pytest.approx((0.3 + 0.2 + 0.25) / 3)
    assert r.weights == {"lexicon": 0.333, "llm": 0.333, "transformer": 0.334}
    assert r.method == "equal_weight_mean"


def test_sub_scores_use_dimension_aware_components_only() -> None:
    # transformer has no sub-scores → ignored; lexicon + llm averaged per dimension.
    r = reconcile({"lexicon": _lexicon(), "llm": _llm(), "transformer": _transformer()})
    assert r.sub_scores["inflation"] == pytest.approx(0.5)  # (0.5 + 0.5)/2
    assert r.sub_scores["growth"] == pytest.approx(-0.1)  # (-0.2 + 0.0)/2
    assert r.sub_scores["employment"] == pytest.approx(0.2)  # (0.1 + 0.3)/2


def test_confidence_is_one_minus_disagreement() -> None:
    nets = [0.3, 0.2, 0.25]
    r = reconcile({"lexicon": _lexicon(0.3), "llm": _llm(0.2), "transformer": _transformer(0.25)})
    assert r.disagreement == pytest.approx(statistics.pstdev(nets), abs=1e-6)
    assert r.confidence == pytest.approx(1.0 - statistics.pstdev(nets), abs=1e-6)


def test_wide_disagreement_lowers_confidence() -> None:
    agree = reconcile({"a": _transformer(0.30), "b": _transformer(0.32), "c": _transformer(0.31)})
    split = reconcile({"a": _transformer(-1.0), "b": _transformer(1.0), "c": _transformer(0.0)})
    assert agree.confidence > split.confidence


def test_single_component_has_no_confidence() -> None:
    r = reconcile({"lexicon": _lexicon(0.4)})
    assert r.confidence is None
    assert r.weights == {"lexicon": 1.0}
    assert r.net == pytest.approx(0.4)


def test_evidence_merged_with_source_tags() -> None:
    r = reconcile({"lexicon": _lexicon(), "llm": _llm(), "transformer": _transformer()})
    by_text = {e["text"]: e for e in r.evidence_phrases}
    # The shared phrase is flagged by both lexicon and llm.
    assert by_text["upside risks to inflation"]["source"] == ["lexicon", "llm"]
    assert by_text["growth has been subdued"]["source"] == ["llm"]


def test_empty_raises() -> None:
    with pytest.raises(ValueError):
        reconcile({})
