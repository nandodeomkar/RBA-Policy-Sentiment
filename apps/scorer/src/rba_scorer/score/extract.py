"""Extract the statement body text from an RBA release page.

The full text is read **transiently** to score it and is never persisted — only
short evidence phrases are stored downstream (licensing, NFR-011). Body lives in
the page's ``#content`` region; nav/header/footer/script noise is stripped.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

_NOISE_TAGS = ("script", "style", "nav", "header", "footer", "aside", "form")
_MIN_BODY_CHARS = 100  # a real decision statement is ~thousands of chars


class StatementTextError(ValueError):
    """A release page yielded no usable body text (R-003)."""


def extract_statement_text(html: str) -> str:
    """Return the statement's paragraph text. Raises :class:`StatementTextError`
    if the page has no usable body (fail loud, per R-003)."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(list(_NOISE_TAGS)):
        tag.decompose()

    container = (
        soup.find(id="content") or soup.find("main") or soup.find("article") or soup.body or soup
    )
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    text = "\n".join(p for p in paragraphs if p)

    if len(text.strip()) < _MIN_BODY_CHARS:
        raise StatementTextError("no usable statement body text extracted")
    return text
