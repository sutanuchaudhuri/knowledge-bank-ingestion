"""Repair PDF/AoPS diagrams locally; optional missing-image downloads, never AI."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mathbank.crawl.image_downloader import download_images, extract_diagram_urls  # noqa: E402
from mathbank.crawl.question_figures import extract_question_figures  # noqa: E402
from mathbank.db import DB_PATH  # noqa: E402

log = logging.getLogger(__name__)
IMAGE_BLOCK = re.compile(r"\n+---\n+(?:!\[[^\n]*\n*)+\s*$")


def update_record(
    folder: Path, assets: list[dict], *, apply: bool, status: dict | None = None
) -> None:
    if not apply:
        return
    if folder.is_dir():
        (folder / "image_manifest.json").write_text(json.dumps(assets, indent=2) + "\n")
        if status is not None:
            (folder / "diagram_status.json").write_text(json.dumps(status, indent=2) + "\n")
    parsed = folder / "parsed.json"
    if parsed.is_file():
        record = json.loads(parsed.read_text())
        record["image_urls"] = list(dict.fromkeys(asset["local_path"] for asset in assets))
        if status is not None:
            record["diagram_status"] = status
        for side in ("problem", "solution"):
            record[f"{side}_image_urls"] = [
                asset["local_path"] for asset in assets if asset["source_side"] == side
            ]
        parsed.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")


def update_markdown(path: Path, assets: list[dict], side: str, *, apply: bool) -> None:
    if not apply or not path.is_file():
        return
    original = path.read_text()
    text = IMAGE_BLOCK.sub("", original).rstrip()
    images = [asset for asset in assets if asset["source_side"] == side]
    if images:
        links = []
        for n, asset in enumerate(images, 1):
            relative = Path(asset["local_path"]).relative_to(path.parent.resolve())
            links.append(f"![Source {side} figure {n}]({relative})")
        text += "\n\n---\n\n" + "\n".join(links)
    text += "\n"
    if text != original:
        path.write_text(text)


def sync_staging(conn, code: str, paper: str | None, assets: list[dict], totals: Counter) -> None:
    paths = list(dict.fromkeys(asset["local_path"] for asset in assets))
    cursor = conn.execute(
        "UPDATE questions SET image_paths=? WHERE question_id=?", (json.dumps(paths), code)
    )
    if not cursor.rowcount:
        totals["staging_questions_missing"] += 1
        return
    totals["staging_questions_updated"] += 1
    conn.execute("DELETE FROM visual_assets WHERE question_id=? AND asset_type='diagram'", (code,))
    for number, asset in enumerate(assets, 1):
        receipt = Path(asset["local_path"]).with_suffix(".json")
        evidence = json.loads(receipt.read_text()) if receipt.is_file() else {}
        conn.execute(
            """
            INSERT INTO visual_assets
              (asset_id, question_id, paper_id, source_side, asset_type,
               page_number, local_file_path, bbox_pdf, drive_asset_url)
            VALUES (?, ?, ?, ?, 'diagram', ?, ?, ?, ?)
        """,
            (
                f"{code}_FIGURE_{number:03d}",
                code,
                paper,
                asset["source_side"],
                evidence.get("page"),
                asset["local_path"],
                json.dumps(evidence.get("clip")),
                asset.get("source_url"),
            ),
        )


def repair_pdfs(root: Path, args, conn, totals: Counter) -> None:
    for paper in sorted((root / "data/crawl_pdf").glob("*/PAPER_*")):
        if (
            args.paper
            and paper.name != args.paper
            or args.competition
            and paper.parent.name != args.competition.lower()
        ):
            continue
        questions = sorted((paper / "questions").glob("Q[0-9]*"))
        if not questions:
            continue
        figures = {}
        for side in ("problem", "solution"):
            if not (paper / f"{side}.pdf").is_file():
                continue
            try:
                figures[side] = extract_question_figures(paper, side=side, write=args.apply)
            except ValueError as exc:
                log.warning("%s: %s figure extraction unavailable: %s", paper.name, side, exc)
                totals[f"unverified_{side}_papers"] += 1
        totals["pdf_papers"] += 1
        for folder in questions:
            if not folder.name[1:].isdigit():
                continue
            number = int(folder.name[1:])
            code = f"{paper.name}_Q{number:02d}"
            native = sorted((folder / "images").glob("*_region_*.png"))
            if native:
                assets = [
                    {
                        "source_side": "problem" if p.name.startswith("problem_") else "solution",
                        "local_path": str(p.resolve()),
                    }
                    for p in native
                    if p.name.startswith(("problem_", "solution_"))
                ]
            else:
                assets = [
                    {"source_side": side, "local_path": str(path)}
                    for side in ("problem", "solution")
                    for path in figures.get(side, {}).get(number, [])
                ]
            totals["pdf_questions"] += 1
            totals["pdf_problem_figures"] += sum(a["source_side"] == "problem" for a in assets)
            totals["pdf_solution_figures"] += sum(a["source_side"] == "solution" for a in assets)
            status = {}
            for side in ("problem", "solution"):
                status[side] = (
                    "EXTRACTED"
                    if any(a["source_side"] == side for a in assets)
                    else "VERIFIED_NO_GRAPHICS"
                    if side in figures
                    else "UNVERIFIED"
                    if (paper / f"{side}.pdf").is_file()
                    else "SOURCE_MISSING"
                )
            update_record(folder, assets, apply=args.apply, status=status)
            update_record(
                root / "data/crawl" / paper.parent.name / code,
                assets,
                apply=args.apply,
                status=status,
            )
            update_markdown(folder / "problem.md", assets, "problem", apply=args.apply)
            update_markdown(folder / "solution.md", assets, "solution", apply=args.apply)
            if args.apply:
                sync_staging(conn, code, paper.name, assets, totals)


def repair_aops(root: Path, args, conn, totals: Counter) -> None:
    for html in sorted((root / "data/crawl").glob("*/*/problem.html")):
        folder = html.parent
        if args.paper or args.competition and folder.parent.name != args.competition.lower():
            continue
        parsed = folder / "parsed.json"
        if not parsed.is_file():
            totals["aops_parsed_missing"] += 1
            continue
        record = json.loads(parsed.read_text())
        assets = []
        status = {}
        for side in ("problem", "solution"):
            urls = extract_diagram_urls(html.read_text(), record.get("url", ""), side)
            missing = False
            for url in urls:
                ext = Path(urlparse(url).path).suffix.lower() or ".png"
                path = folder / "images" / (hashlib.sha256(url.encode()).hexdigest()[:12] + ext)
                if not path.is_file():
                    totals["aops_downloads_needed"] += 1
                    if args.apply and getattr(args, "download_missing", False):
                        downloaded = download_images([url], folder / "images")
                        totals["aops_diagrams_downloaded"] += len(downloaded)
                    if not path.is_file():
                        missing = True
                        log.warning("%s: %s diagram missing locally: %s", folder.name, side, url)
                        continue
                assets.append(
                    {"source_side": side, "source_url": url, "local_path": str(path.resolve())}
                )
            status[side] = (
                "DOWNLOAD_MISSING" if missing else "EXTRACTED" if urls else "NO_SECTION_GRAPHICS"
            )
        totals["aops_questions"] += 1
        totals["aops_problem_figures"] += sum(a["source_side"] == "problem" for a in assets)
        totals["aops_solution_figures"] += sum(a["source_side"] == "solution" for a in assets)
        update_record(folder, assets, apply=args.apply, status=status)
        if args.apply:
            sync_staging(conn, folder.name, None, assets, totals)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--paper")
    parser.add_argument("--competition", help="Artifact directory slug, e.g. smt or hmmt_feb")
    parser.add_argument(
        "--download-missing",
        action="store_true",
        help="With --apply, fetch missing AoPS image URLs from cached HTML (no AI)",
    )
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    totals = Counter()
    # Existing staging schema only; this command never creates or migrates a DB.
    conn = (
        sqlite3.connect(f"file:{args.db.resolve()}?mode=rw", uri=True, timeout=60)
        if args.apply
        else None
    )
    try:
        repair_pdfs(ROOT, args, conn, totals)
        repair_aops(ROOT, args, conn, totals)
        if conn:
            conn.commit()
    finally:
        if conn:
            conn.close()
    print(json.dumps({"mode": "applied" if args.apply else "dry-run", **totals}, sort_keys=True))


if __name__ == "__main__":
    main()
