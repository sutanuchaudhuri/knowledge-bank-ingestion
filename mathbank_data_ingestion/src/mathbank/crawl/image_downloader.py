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
import logging
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from mathbank.crawl.aops_parser import _section_nodes
from mathbank.crawl.downloader import DownloadError, fetch_binary, make_session

log = logging.getLogger(__name__)

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


def extract_diagram_urls(html: str, base_url: str, source_side: str = "problem") -> list[str]:
    """Return diagrams from one explicitly identified problem/solution section."""
    if source_side not in {"problem", "solution"}:
        raise ValueError("source_side must be problem or solution")
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    for img in (img for section in _section_nodes(soup, source_side.title())
                for img in section.find_all("img")):
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
    if not urls:
        return []
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
        except DownloadError as exc:
            log.warning("Diagram download failed for %s: %s", url, exc)
    return local_paths


def save_aops_images(
    conn: sqlite3.Connection,
    question_id: str,
    exam_level: str,
    html: str,
    base_url: str,
    session=None,
    delay: float = 1.5,
    download_missing: bool = True,
) -> list[str]:
    """
    Extract and download real diagram images from an AoPS HTML page.
    Updates questions.image_paths and inserts visual_assets rows.
    Returns list of local file paths.
    """
    slug = re.sub(r"[^a-z0-9]+", "_", exam_level.lower()).strip("_")
    img_dir = CRAWL_DIR / slug / question_id / "images"

    manifest = []
    for side in ("problem", "solution"):
        urls = extract_diagram_urls(html, base_url, side)
        missing = []
        for url in urls:
            ext = Path(urlparse(url).path).suffix.lower() or ".png"
            path = img_dir / (hashlib.sha256(url.encode()).hexdigest()[:12] + ext)
            if not path.is_file():
                missing.append(url)
        if download_missing:
            download_images(missing, img_dir, session=session, delay=delay)
        for url in urls:
            ext = Path(urlparse(url).path).suffix.lower() or ".png"
            path = img_dir / (hashlib.sha256(url.encode()).hexdigest()[:12] + ext)
            if path.is_file():
                manifest.append({"source_side": side, "source_url": url, "local_path": str(path.resolve())})
            else:
                log.warning("%s: %s diagram missing locally: %s", question_id, side, url)
    (img_dir.parent / "image_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    local_paths = list(dict.fromkeys(asset["local_path"] for asset in manifest))
    parsed_path = img_dir.parent / "parsed.json"
    if parsed_path.is_file():
        record = json.loads(parsed_path.read_text())
        record["image_urls"] = local_paths
        for side in ("problem", "solution"):
            record[f"{side}_image_urls"] = [asset["local_path"] for asset in manifest if asset["source_side"] == side]
        parsed_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
    conn.execute(
        "UPDATE questions SET image_paths = ? WHERE question_id = ?",
        (json.dumps(local_paths, ensure_ascii=False), question_id),
    )

    # Upsert visual_assets rows.
    conn.execute("DELETE FROM visual_assets WHERE question_id=? AND asset_type='diagram'", (question_id,))
    for i, asset in enumerate(manifest):
        asset_id = f"{question_id}_DIAG_{i+1:02d}"
        conn.execute(
            """INSERT OR REPLACE INTO visual_assets
               (asset_id, question_id, source_side, asset_type,
                local_file_path, drive_asset_url, created_at)
               VALUES (?, ?, ?, 'diagram', ?, ?, ?)""",
            (asset_id, question_id, asset["source_side"], asset["local_path"], asset["source_url"], _now()),
        )

    conn.commit()
    return local_paths
