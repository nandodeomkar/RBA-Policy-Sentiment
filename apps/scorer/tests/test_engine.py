"""Composite engine-version tests (plan step 18)."""

from rba_scorer.score.engine import compose_engine_version, engine_version_record


def test_record_has_version_and_parts() -> None:
    rec = engine_version_record(
        {
            "lexicon": "lex-v1:abcd",
            "llm": "claude-haiku-4-5:llm-p1",
            "transformer": "fomc-roberta:rev",
        }
    )
    assert rec["engine_version"].startswith("engine-2026.06-")
    assert rec["components"] == {
        "lexicon": "lex-v1:abcd",
        "llm": "claude-haiku-4-5:llm-p1",
        "transformer": "fomc-roberta:rev",
        "reconcile": "reconcile-v1",
    }


def test_subset_versions_differ_from_full() -> None:
    full = engine_version_record({"lexicon": "l", "llm": "m", "transformer": "t"})
    subset = engine_version_record({"lexicon": "l", "llm": "m"})
    assert full["engine_version"] != subset["engine_version"]
    assert set(subset["components"]) == {"lexicon", "llm", "reconcile"}


def test_version_is_stable_and_order_independent() -> None:
    a = compose_engine_version({"lexicon": "x", "llm": "y", "transformer": "z"})
    b = compose_engine_version({"transformer": "z", "lexicon": "x", "llm": "y"})
    assert a == b  # sorted hash → key order does not matter


def test_changing_any_part_changes_the_version() -> None:
    base = compose_engine_version({"lexicon": "x", "llm": "y", "transformer": "z"})
    changed = compose_engine_version({"lexicon": "x", "llm": "y2", "transformer": "z"})
    assert base != changed
