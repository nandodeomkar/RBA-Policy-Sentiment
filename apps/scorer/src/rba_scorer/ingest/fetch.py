"""HTTP fetch with a local on-disk cache of raw pages.

Raw pages are cached under ``.cache/raw/`` (gitignored) so re-runs don't re-hit
rba.gov.au and so parsers can be exercised against saved pages. Full statement
text lives only in this local cache — it is never committed (licensing, NFR-011).
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import httpx

from rba_scorer.paths import RAW_CACHE_DIR

logger = logging.getLogger(__name__)

# rba.gov.au sits behind a WAF that 403s requests lacking a full browser-like
# header set (a bare User-Agent is not enough — it also wants Accept / Sec-Fetch-*).
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}


def _cache_path(url: str, cache_dir: Path) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return cache_dir / f"{digest}.html"


def fetch(
    url: str,
    *,
    cache_dir: Path = RAW_CACHE_DIR,
    force: bool = False,
    client: httpx.Client | None = None,
    timeout: float = 30.0,
) -> str:
    """Return the text of ``url``, caching the raw response under ``cache_dir``.

    A cached copy is returned as-is unless ``force`` is set. Pass a shared
    ``client`` to reuse a connection across many fetches.
    """
    path = _cache_path(url, cache_dir)
    if path.exists() and not force:
        logger.debug("cache hit: %s (%s)", url, path.name)
        return path.read_text(encoding="utf-8")

    logger.info("fetching %s", url)
    owns_client = client is None
    client = client or httpx.Client(headers=DEFAULT_HEADERS, follow_redirects=True, timeout=timeout)
    try:
        response = client.get(url)
        response.raise_for_status()
        text = response.text
    finally:
        if owns_client:
            client.close()

    cache_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text
