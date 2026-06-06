"""Tests for the lexicon scorer and the component contract."""

import pytest

from rba_scorer.paths import LEXICON_PATH
from rba_scorer.score.base import DIMENSIONS, ComponentResult, EvidencePhrase
from rba_scorer.score.lexicon import Lexicon, LexiconEntry, load_lexicon, score_text
from rba_scorer.score.store import read_scores, write_scores

HAWKISH = "hawkish"
DOVISH = "dovish"


def _lexicon(entries, negators=("not", "no longer")) -> Lexicon:
    return Lexicon(entries=tuple(entries), negators=tuple(negators), version="lex-vtest:0000")


def test_hawkish_terms_drive_net_positive() -> None:
    lex = _lexicon([LexiconEntry("inflation is too high", "inflation", HAWKISH)])
    result = score_text("Inflation is too high and broad-based.", lex)
    assert result.net == 1.0
    assert result.sub_scores["inflation"] == 1.0
    assert result.sub_scores["growth"] == 0.0
    assert result.evidence[0] == EvidencePhrase("inflation is too high", HAWKISH, "inflation")


def test_dovish_terms_drive_net_negative() -> None:
    lex = _lexicon([LexiconEntry("labour market has eased", "employment", DOVISH)])
    result = score_text("The labour market has eased since last meeting.", lex)
    assert result.net == -1.0
    assert result.sub_scores["employment"] == -1.0


def test_negation_flips_polarity() -> None:
    lex = _lexicon([LexiconEntry("elevated", "inflation", HAWKISH)])
    assert score_text("Inflation remains elevated.", lex).net == 1.0
    flipped = score_text("Inflation is no longer elevated.", lex)
    assert flipped.net == -1.0
    assert flipped.evidence[0].polarity == DOVISH


def test_negation_does_not_leak_across_clauses() -> None:
    # The "no longer" negating "elevated" must not reach "wage pressures" in the
    # next clause.
    lex = _lexicon([LexiconEntry("wage pressures", "employment", HAWKISH)])
    result = score_text("Inflation is no longer elevated, though wage pressures persist.", lex)
    assert result.net == 1.0
    assert result.evidence[0].polarity == HAWKISH


def test_balanced_matches_net_zero_but_subscores_split() -> None:
    lex = _lexicon(
        [
            LexiconEntry("upside risks to inflation", "inflation", HAWKISH),
            LexiconEntry("growth has slowed", "growth", DOVISH),
        ]
    )
    result = score_text("There are upside risks to inflation. Meanwhile growth has slowed.", lex)
    assert result.net == 0.0  # one hawkish + one dovish
    assert result.sub_scores["inflation"] == 1.0
    assert result.sub_scores["growth"] == -1.0


def test_no_matches_is_neutral() -> None:
    lex = _lexicon([LexiconEntry("inflation is too high", "inflation", HAWKISH)])
    result = score_text("The Board met today and reviewed conditions.", lex)
    assert result.net == 0.0
    assert all(result.sub_scores[d] == 0.0 for d in DIMENSIONS)
    assert result.evidence == ()


def test_result_serialises_with_version_and_evidence() -> None:
    lex = _lexicon([LexiconEntry("inflation is too high", "inflation", HAWKISH)])
    data = score_text("Inflation is too high.", lex).to_dict()
    assert data["net"] == 1.0
    assert data["version"] == "lex-vtest:0000"
    assert data["sub_scores"]["inflation"] == 1.0
    assert data["evidence"][0]["polarity"] == HAWKISH
    assert data["matched_terms"] == ["inflation is too high"]


def test_component_result_rejects_bad_values() -> None:
    with pytest.raises(ValueError, match="net"):
        ComponentResult(net=2.0, version="x")
    with pytest.raises(ValueError, match="must be in"):
        ComponentResult(net=0.0, version="x", sub_scores={"inflation": 1.5})
    with pytest.raises(ValueError, match="dimension"):
        ComponentResult(net=0.0, version="x", sub_scores={"unknown": 0.5})


def test_shipped_lexicon_loads_and_is_wellformed() -> None:
    lex = load_lexicon(LEXICON_PATH)
    assert lex.entries
    assert lex.version.startswith("lex-v")
    for entry in lex.entries:
        assert entry.dimension in DIMENSIONS
        assert entry.polarity in (HAWKISH, DOVISH)
        assert entry.term == entry.term.lower()
    assert load_lexicon(LEXICON_PATH).version == lex.version  # deterministic


def test_shipped_lexicon_scores_a_realistic_statement() -> None:
    lex = load_lexicon(LEXICON_PATH)
    text = "Inflation remains too high. The labour market is tight. Demand remains strong."
    result = score_text(text, lex)
    assert result.net > 0  # clearly hawkish wording
    assert result.sub_scores["inflation"] == 1.0


def test_score_record_round_trips_through_writer(tmp_path) -> None:
    lex = _lexicon([LexiconEntry("upside risks to inflation", "inflation", HAWKISH)])
    component = score_text("Upside risks to inflation remain.", lex)
    record = {
        "2024-05-07": {
            "net": component.net,
            "sub_scores": component.sub_scores,
            "components": {"lexicon": component.to_dict()},
            "engine_version": "engine-test",
        }
    }
    path = tmp_path / "scores.json"
    write_scores(record, path)
    assert read_scores(path) == record
    assert read_scores(path)["2024-05-07"]["components"]["lexicon"]["net"] == 1.0
