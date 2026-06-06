"""Tests for the decision-URL index walker (no network — fetch is injected)."""

from rba_scorer.ingest.index import decision_urls

PAGE_2023 = (
    "<html><body>"
    '<a href="/media-releases/2023/mr-23-01.html">Feb</a>'
    '<a href="/media-releases/2023/mr-23-05.html">Mar</a>'
    '<a href="/media-releases/">All media releases</a>'  # ignored: not a decision
    '<a href="/monetary-policy/int-rate-decisions/2022/">2022</a>'  # ignored
    "</body></html>"
)
PAGE_2024 = '<html><body><a href="/media-releases/2024/mr-24-01.html">Feb</a></body></html>'


def test_decision_urls_collects_release_links_per_year() -> None:
    pages = {
        "https://www.rba.gov.au/monetary-policy/int-rate-decisions/2023/": PAGE_2023,
        "https://www.rba.gov.au/monetary-policy/int-rate-decisions/2024/": PAGE_2024,
    }
    urls = decision_urls(2023, current_year=2024, fetch=lambda url: pages[url])
    assert urls == [
        "https://www.rba.gov.au/media-releases/2023/mr-23-01.html",
        "https://www.rba.gov.au/media-releases/2023/mr-23-05.html",
        "https://www.rba.gov.au/media-releases/2024/mr-24-01.html",
    ]
