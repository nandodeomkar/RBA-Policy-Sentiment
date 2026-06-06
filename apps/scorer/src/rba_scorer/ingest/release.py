"""Parse decision metadata (date, title) from an RBA release page (FR-001).

Rate and outcome come from the official cash-rate series (see ``cashrate.py``),
not the statement prose — RBA decision wording varies too much across years
(2020-21 COVID phrasing especially). The release page supplies only the
canonical announcement date, the title, and the source link.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup


class ReleaseParseError(ValueError):
    """A release page is missing an expected metadata field (R-003)."""


@dataclass(frozen=True)
class ReleaseMeta:
    date: str  # ISO YYYY-MM-DD (announcement date)
    title: str
    source_url: str


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _meta(soup: BeautifulSoup, name: str) -> str | None:
    tag = soup.find("meta", attrs={"name": name})
    content = tag.get("content") if tag else None
    return content.strip() if content else None


def parse_release_meta(html: str, source_url: str) -> ReleaseMeta | None:
    """Return the decision's metadata, or ``None`` if the page is not a monetary
    policy decision (a normal skip). Raise ``ReleaseParseError`` only when a page
    that should be a decision is missing its date or title."""
    soup = BeautifulSoup(html, "lxml")

    date = _meta(soup, "dc.date")
    if not date or not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        raise ReleaseParseError(f"missing/invalid dc.date meta: {source_url}")

    title = _meta(soup, "dcterms.title")
    if not title:
        h1 = soup.find("h1")
        title = _clean(h1.get_text(" ", strip=True)) if h1 else None
    if not title:
        raise ReleaseParseError(f"missing title: {source_url}")
    title = re.sub(r"^(Joint )?Media Release\s*", "", title).strip()
    title = title.split("|", 1)[0].strip()  # drop the "| Media Releases" section suffix
    title = re.sub(r"\s*[-–]\s*[A-Z][a-z]+\s+\d{4}\s*$", "", title).strip()  # drop "- May 2024"

    if "Monetary Policy Decision" not in title:
        return None  # e.g. a COVID-era market-operations statement; not a decision
    return ReleaseMeta(date=date, title=title, source_url=source_url)
