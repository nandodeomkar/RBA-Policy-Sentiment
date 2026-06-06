"""Deterministic hawkish/dovish lexicon scorer (design §6, component 1).

A transparent, $0 baseline: sentence-split the statement, match a curated,
dimension-tagged term list (with simple negation handling), and reduce to a net
score plus inflation/growth/employment sub-scores. Net is the signed balance of
hawkish vs dovish matches — ``(hawkish - dovish) / (hawkish + dovish)`` — so it
is naturally in [-1, 1]. Pure and pinned (version = a hash of the lexicon
source), so every score is reproducible.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from rba_scorer.score.base import DIMENSIONS, ComponentResult, EvidencePhrase, Polarity
from rba_scorer.score.segment import split_sentences

_DEFAULT_NEGATORS: tuple[str, ...] = ("not", "no longer", "without", "neither", "nor")
_NEG_WINDOW_WORDS = 4  # how many words before a term to scan for a negator
# Clause boundaries: a negator before one of these doesn't reach across it
# (e.g. "no longer elevated, though wage pressures persist" must not negate
# "wage pressures").
_CLAUSE_BREAKS: tuple[str, ...] = (
    ",",
    ";",
    ":",
    " but ",
    " and ",
    " though ",
    " although ",
    " while ",
    " however ",
    " whereas ",
)


@dataclass(frozen=True)
class LexiconEntry:
    term: str  # stored lowercase; matched as a substring within a sentence
    dimension: str
    polarity: Polarity


@dataclass(frozen=True)
class Lexicon:
    entries: tuple[LexiconEntry, ...]
    negators: tuple[str, ...]
    version: str


def load_lexicon(path: Path) -> Lexicon:
    """Load and validate the committed lexicon JSON. Version is a hash of the
    file bytes, so editing the lexicon changes the pinned version."""
    raw = path.read_bytes()
    data = json.loads(raw)
    entries: list[LexiconEntry] = []
    for item in data["terms"]:
        dim, pol = item["dimension"], item["polarity"]
        if dim not in DIMENSIONS:
            raise ValueError(f"lexicon term {item['term']!r} has unknown dimension {dim!r}")
        if pol not in ("hawkish", "dovish"):
            raise ValueError(f"lexicon term {item['term']!r} has unknown polarity {pol!r}")
        entries.append(LexiconEntry(term=item["term"].lower(), dimension=dim, polarity=pol))
    negators = tuple(n.lower() for n in data.get("negators", _DEFAULT_NEGATORS))
    digest = hashlib.sha256(raw).hexdigest()[:8]
    version = f"lex-v{data.get('version', 1)}:{digest}"
    return Lexicon(entries=tuple(entries), negators=negators, version=version)


def _flip(polarity: Polarity) -> Polarity:
    return "dovish" if polarity == "hawkish" else "hawkish"


def _is_negated(sentence_low: str, term: str, negators: tuple[str, ...]) -> bool:
    idx = sentence_low.find(term)
    if idx <= 0:
        return False
    preceding = sentence_low[:idx]
    # Only scan the current clause — cut at the last clause break before the term.
    cut = 0
    for sep in _CLAUSE_BREAKS:
        pos = preceding.rfind(sep)
        if pos != -1:
            cut = max(cut, pos + len(sep))
    clause_words = preceding[cut:].split()[-_NEG_WINDOW_WORDS:]
    chunk = f" {' '.join(clause_words)} "
    return any(f" {neg} " in chunk for neg in negators)


def _ratio(hawkish: int, dovish: int) -> float:
    total = hawkish + dovish
    return 0.0 if total == 0 else (hawkish - dovish) / total


def score_text(text: str, lexicon: Lexicon) -> ComponentResult:
    """Score statement text with the lexicon. Returns a neutral (0.0) result
    when no terms match."""
    counts = {dim: {"hawkish": 0, "dovish": 0} for dim in DIMENSIONS}
    total = {"hawkish": 0, "dovish": 0}
    evidence: list[EvidencePhrase] = []
    seen: set[tuple[str, str, str]] = set()

    for sentence in split_sentences(text):
        low = sentence.lower()
        for entry in lexicon.entries:
            if entry.term not in low:
                continue
            negated = _is_negated(low, entry.term, lexicon.negators)
            polarity: Polarity = _flip(entry.polarity) if negated else entry.polarity
            counts[entry.dimension][polarity] += 1
            total[polarity] += 1
            key = (entry.term, polarity, entry.dimension)
            if key not in seen:
                seen.add(key)
                evidence.append(
                    EvidencePhrase(text=entry.term, polarity=polarity, dimension=entry.dimension)
                )

    sub_scores = {dim: _ratio(counts[dim]["hawkish"], counts[dim]["dovish"]) for dim in DIMENSIONS}
    return ComponentResult(
        net=_ratio(total["hawkish"], total["dovish"]),
        version=lexicon.version,
        sub_scores=sub_scores,
        evidence=tuple(evidence),
        extra={"matched_terms": [e.text for e in evidence]},
    )
