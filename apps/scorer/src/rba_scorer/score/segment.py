"""Sentence segmentation shared by the scoring components.

Deliberately simple and dependency-free: RBA statements are clean prose, so a
punctuation split is enough and keeps every component reading the *same*
sentences (the lexicon, the LLM aggregation, and the transformer all agree on
what "a sentence" is). Pure function — no I/O, no model deps.
"""

from __future__ import annotations

import re

_SENTENCE_RE = re.compile(r"[^.!?]+[.!?]?")


def split_sentences(text: str) -> list[str]:
    """Split ``text`` into trimmed, non-empty sentences."""
    return [s.strip() for s in _SENTENCE_RE.findall(text) if s.strip()]
