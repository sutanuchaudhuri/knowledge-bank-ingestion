"""
HTTP downloader with retry, rate limiting, and 403-resilience.

AoPS uses Cloudflare-style bot detection — bare bot User-Agents get 403.
Strategy:
  - Full Chrome browser headers to appear legitimate
  - Pre-warm: GET the wiki index to obtain session cookies before crawling
  - Random jitter on every delay so requests don't look metronomic
  - On 403: wait 30s before retry (not exponential — Cloudflare needs a pause)
  - Max 3 retries total; after that raise so caller can mark FAILED
"""
from __future__ import annotations

import random
import time
from pathlib import Path
from urllib.parse import urlparse
import mimetypes

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_fixed,
)


class DownloadError(RuntimeError):
    pass


class BlockedError(DownloadError):
    """HTTP 403/429 — server is actively blocking; caller should back off."""


# Realistic Chrome 124 on macOS headers
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",  # no 'br' — requests can't decompress Brotli
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "max-age=0",
}

_last_request_time: float = 0.0
_AOPS_WARMUP_URL = "https://artofproblemsolving.com/wiki/index.php/AMC_10"


def _throttle(min_gap: float) -> None:
    global _last_request_time
    # Add ±25% jitter so requests don't look metronomic
    jitter = random.uniform(-min_gap * 0.25, min_gap * 0.25)
    gap = max(1.0, min_gap + jitter)
    elapsed = time.monotonic() - _last_request_time
    if elapsed < gap:
        time.sleep(gap - elapsed)
    _last_request_time = time.monotonic()


def make_session(warmup_aops: bool = False) -> requests.Session:
    """Create a browser-mimicking session. warmup_aops=True seeds AoPS cookies."""
    s = requests.Session()
    s.headers.update(_BROWSER_HEADERS)
    if warmup_aops:
        try:
            s.get(_AOPS_WARMUP_URL, timeout=20, allow_redirects=True)
            time.sleep(random.uniform(1.5, 3.0))
        except Exception:
            pass  # warmup failure is non-fatal
    return s


@retry(
    stop=stop_after_attempt(3),
    # Fixed 30s wait — Cloudflare needs a real pause, not exponential
    wait=wait_fixed(30),
    retry=retry_if_exception_type(BlockedError),
    reraise=True,
)
def _fetch_with_block_retry(session: requests.Session, url: str, delay: float) -> requests.Response:
    _throttle(delay)
    # Vary Referer to look like navigation from the wiki
    session.headers["Referer"] = "https://artofproblemsolving.com/wiki/index.php"
    r = session.get(url, timeout=30, allow_redirects=True)
    if r.status_code == 403:
        raise BlockedError(f"HTTP 403 → {url}  (will retry after 30s pause)")
    if r.status_code == 429:
        raise BlockedError(f"HTTP 429 rate-limited → {url}")
    if r.status_code >= 400:
        raise DownloadError(f"HTTP {r.status_code} → {url}")
    return r


def fetch_html(session: requests.Session, url: str, delay: float = 3.0) -> str:
    """Fetch HTML with browser headers, jitter, and 403 retry. Raises DownloadError on failure."""
    r = _fetch_with_block_retry(session, url, delay)
    text = r.text
    # Guard against Brotli or other compressed responses that slipped through.
    if text and not text.lstrip().startswith("<"):
        raise DownloadError(f"Response appears non-HTML (encoding issue?) from {url}")
    return text


def fetch_binary(session: requests.Session, url: str, delay: float = 2.0) -> bytes:
    """Fetch binary content (PDF, image) with jitter."""
    r = _fetch_with_block_retry(session, url, delay)
    return r.content


def save_html(html: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html, encoding="utf-8")


def save_html(html: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html, encoding="utf-8")
