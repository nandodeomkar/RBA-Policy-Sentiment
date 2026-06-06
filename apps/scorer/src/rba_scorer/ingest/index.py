"""Enumerate RBA monetary-policy decision release URLs (FR-001).

The decisions index shows only the current year and links to per-year
sub-pages (``/monetary-policy/int-rate-decisions/<year>/``). Each year's page
lists that year's decision releases as ``/media-releases/<year>/mr-NN-NN.html``
links, which is the authoritative set of decisions (not every media release is
a rate decision).
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Callable

import httpx
from bs4 import BeautifulSoup

from rba_scorer.ingest.fetch import fetch as _fetch

BASE = "https://www.rba.gov.au"
_RELEASE_RE = re.compile(r"^/media-releases/\d{4}/mr-\d{2}-\d+\.html$")

Fetcher = Callable[[str], str]


def _year_index_html(year: int, current_year: int, fetch: Fetcher) -> str:
    url = f"{BASE}/monetary-policy/int-rate-decisions/{year}/"
    if year == current_year:
        # The current year may be served at the section root rather than /<year>/.
        try:
            return fetch(url)
        except httpx.HTTPStatusError:
            return fetch(f"{BASE}/monetary-policy/int-rate-decisions/")
    return fetch(url)


def decision_urls(
    since_year: int,
    *,
    current_year: int | None = None,
    fetch: Fetcher = _fetch,
) -> list[str]:
    current_year = current_year or dt.date.today().year
    found: set[str] = set()
    for year in range(since_year, current_year + 1):
        soup = BeautifulSoup(_year_index_html(year, current_year, fetch), "lxml")
        for anchor in soup.find_all("a", href=True):
            if _RELEASE_RE.match(anchor["href"]):
                found.add(BASE + anchor["href"])
    return sorted(found)
