"""Tests for the statement-text extractor (synthetic, licensing-clean HTML)."""

import pytest

from rba_scorer.score.extract import StatementTextError, extract_statement_text

PAGE = """
<html><head><title>x</title></head><body>
<nav><p>Skip to main content navigation</p></nav>
<header><p>RBA site header boilerplate text here</p></header>
<div id="content">
  <h1>Statement by the Board</h1>
  <p>Inflation remains too high and broad-based across the economy.</p>
  <p>The Board decided to hold the cash rate target at its current level.</p>
  <p>The labour market is tight and conditions remain resilient.</p>
</div>
<footer><p>Enquiries: phone 02 1234 5678, media office.</p></footer>
<script>var tracking = 1;</script>
</body></html>
"""


def test_extracts_body_paragraphs_only() -> None:
    text = extract_statement_text(PAGE)
    assert "Inflation remains too high" in text
    assert "hold the cash rate target" in text
    assert "labour market is tight" in text
    # noise outside #content is stripped
    assert "header boilerplate" not in text
    assert "Skip to main content" not in text
    assert "Enquiries" not in text
    assert "tracking" not in text


def test_raises_on_empty_body() -> None:
    with pytest.raises(StatementTextError):
        extract_statement_text("<html><body><div id='content'></div></body></html>")
