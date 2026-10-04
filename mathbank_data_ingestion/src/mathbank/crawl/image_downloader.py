"""
Image downloader for competition math question artifacts.

Two image sources:
  1. AoPS pages — actual diagram/figure images (not LaTeX-rendered PNGs,
     which are already recovered from img[alt] as LaTeX text).
     Target pattern: wiki.artofproblemsolving.com/images/...
  2. PDF papers — already rendered to PNG by pdf_parser.render_pdf_pages;
     this module handles updating the DB with those local paths.

For each question the result is:
  - Local PNG files in  data/crawl/<level>/<question_id>/images/<n>.png
  - questions.image_paths updated to list of local relative paths
  - visual_assets table populated with one row per image
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from mathbank.crawl.downloader import DownloadError, fetch_binary, make_session

# Diagram images are on the AoPS wiki CDN (NOT the latex CDN).
_DIAGRAM_HOSTS = {
    "wiki.artofproblemsolving.com",
    "artofproblemsolving.com",
}
_LATEX_HOST_FRAGMENT = "latex.artofproblemsolving.com"

# Site chrome reused on nearly every wiki page (e.g. wiki/images/d/d1/AMC_Logo.png
# shows up in ~87% of crawled problem pages) — not a per-problem diagram.
_DECORATIVE_FILENAME_RE = re.compile(r"logo|footer|header|banner|wordmark|badge", re.IGNORECASE)

ROOT = Path(__file__).resolve().parents[3]
CRAWL_DIR = ROOT / "data" / "crawl"


def _is_diagram_image(src: str) -> bool:
    """True for actual diagram/figure images; False for LaTeX-rendered math PNGs
    or reused site chrome (logos, footers, banners)."""
    if _LATEX_HOST_FRAGMENT in src:
        return False
    basename = urlparse(src).path.rsplit("/", 1)[-1]
    if _DECORATIVE_FILENAME_RE.search(basename):
        return False
    host = urlparse(src).netloc
    return any(h in host for h in _DIAGRAM_HOSTS) or src.startswith("/")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_diagram_urls(html: str, base_url: str) -> list[str]:
    """Return absolute URLs of non-LaTeX images on an AoPS wiki page."""
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    for img in soup.select("div.mw-parser-output img"):
        src = img.get("src", "") or ""
        if not src or not _is_diagram_image(src):
            continue
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            src = urljoin(base_url, src)
        if src not in urls:
            urls.append(src)
    return urls


def download_images(
    urls: list[str],
    out_dir: Path,
    session=None,
    delay: float = 1.5,
) -> list[str]:
    """Download each URL to out_dir/<sha256[:8]>.png; return list of local paths."""
    if session is None:
        session = make_session()
    out_dir.mkdir(parents=True, exist_ok=True)
    local_paths: list[str] = []
    for url in urls:
        try:
            data = fetch_binary(session, url, delay=delay)
            ext = Path(urlparse(url).path).suffix.lower() or ".png"
            fname = hashlib.sha256(url.encode()).hexdigest()[:12] + ext
            dest = out_dir / fname
            dest.write_bytes(data)
            local_paths.append(str(dest))
        except (DownloadError, Exception):
            pass   # non-fatal — text extraction already succeeded
    return local_paths


def save_aops_images(
    conn: sqlite3.Connection,
    question_id: str,
    exam_level: str,
    html: str,
    base_url: str,
    session=None,
    delay: float = 1.5,
) -> list[str]:
    """
    Extract and download real diagram images from an AoPS HTML page.
    Updates questions.image_paths and inserts visual_assets rows.
    Returns list of local file paths.
    """
    slug = re.sub(r"[^a-z0-9]+", "_", exam_level.lower()).strip("_")
    img_dir = CRAWL_DIR / slug / question_id / "images"

    urls = extract_diagram_urls(html, base_url)
    if not urls:
        return []

    local_paths = download_images(urls, img_dir, session=session, delay=delay)

    # Update questions.image_paths (append to any existing paths from alt-text).
    existing_raw = conn.execute(
        "SELECT image_paths FROM questions WHERE question_id = ?", (question_id,)
    ).fetchone()
    existing: list[str] = json.loads(existing_raw[0]) if existing_raw and existing_raw[0] else []
    merged = existing + [p for p in local_paths if p not in existing]
    conn.execute(
        "UPDATE questions SET image_paths = ? WHERE question_id = ?",
        (json.dumps(merged, ensure_ascii=False), question_id),
    )

    # Upsert visual_assets rows.
    for i, (url, local_path) in enumerate(zip(urls, local_paths)):
        asset_id = f"{question_id}_DIAG_{i+1:02d}"
        conn.execute(
            """INSERT OR REPLACE INTO visual_assets
               (asset_id, question_id, source_side, asset_type,
                local_file_path, drive_asset_url, created_at)
               VALUES (?, ?, 'problem', 'diagram', ?, ?, ?)""",
            (asset_id, question_id, local_path, url, _now()),
        )

    conn.commit()
    return local_paths
