"""Tests for the release-metadata parser, using synthetic (licensing-clean) fixtures."""

import pytest

from rba_scorer.ingest.release import ReleaseParseError, parse_release_meta

_URL = "https://www.rba.gov.au/media-releases/2024/mr-24-01.html"
_TITLE = "Statement by the Reserve Bank Board: Monetary Policy Decision"


def _page(date: str | None, title: str | None) -> str:
    head = ""
    if date:
        head += f'<meta name="dc.date" content="{date}">'
    if title:
        head += f'<meta name="dcterms.title" content="{title}">'
    return f"<html><head>{head}</head><body><h1>Media Release {title or ''}</h1></body></html>"


def test_parse_meta_ok() -> None:
    meta = parse_release_meta(_page("2024-02-06", _TITLE), _URL)
    assert meta is not None
    assert meta.date == "2024-02-06"
    assert meta.title == _TITLE
    assert meta.source_url == _URL


def test_parse_meta_falls_back_to_h1_and_strips_prefix() -> None:
    html = (
        '<html><head><meta name="dc.date" content="2024-02-06"></head><body>'
        f"<h1>Media Release {_TITLE}</h1></body></html>"
    )
    meta = parse_release_meta(html, _URL)
    assert meta is not None and meta.title == _TITLE


def test_parse_meta_strips_date_and_section_suffix() -> None:
    raw = "Statement by the Governor: Monetary Policy Decision - May 2024 | Media Releases"
    meta = parse_release_meta(_page("2024-05-07", raw), _URL)
    assert meta is not None
    assert meta.title == "Statement by the Governor: Monetary Policy Decision"


def test_parse_meta_returns_none_for_non_decision() -> None:
    # A real index can link non-decision media releases (e.g. COVID-era statements).
    meta = parse_release_meta(_page("2024-10-28", "Joint Statement on Project Mandala"), _URL)
    assert meta is None


def test_parse_meta_raises_on_missing_date() -> None:
    with pytest.raises(ReleaseParseError):
        parse_release_meta(_page(None, _TITLE), _URL)
