"""Original problem documents, separate from student-safe diagram crops."""

import hashlib
import json
import logging
import re
from pathlib import Path
from urllib.parse import quote, urlsplit

from sqlalchemy import text

log = logging.getLogger(__name__)
PDF_ROOT = Path(__file__).resolve().parents[4] / "mathbank_data_ingestion/data/crawl_pdf"


def source_record(conn, code: str) -> dict | None:
    row = (
        conn.execute(
            text("""
        SELECT p.source_url, p.statement_text, p.problem_number,
               s.problem_url, s.crawl_dir, s.paper_external_code, s.link_scope,
               b.title AS book_title,b.author AS book_author,
               r.chapter_number,r.source_printed_problem_id,r.source_problem_id
        FROM core.problem p
        LEFT JOIN pedagogy.problem_source_ref r ON r.problem_id=p.problem_id
        LEFT JOIN pedagogy.source_book b USING(book_code)
        LEFT JOIN pipeline.pdf_source s
          ON s.paper_external_code = regexp_replace(p.canonical_code, '_Q[0-9]+$', '')
        WHERE p.canonical_code = :code
    """),
            {"code": code},
        )
        .mappings()
        .first()
    )
    return dict(row) if row is not None else None


def source_pdf(record: dict) -> Path | None:
    directory, paper = record.get("crawl_dir"), record.get("paper_external_code")
    if not directory or not paper:
        return None
    path = (PDF_ROOT / directory / paper / "problem.pdf").resolve()
    if PDF_ROOT.resolve() not in path.parents:
        raise ValueError("Source PDF path is outside the corpus")
    return path if path.is_file() else None


def source_metadata(record: dict, code: str) -> dict | None:
    local = source_pdf(record)
    url = record.get("problem_url") or record.get("source_url")
    if url:
        try:
            parsed = urlsplit(url)
            valid = (
                parsed.scheme in {"http", "https"}
                and bool(parsed.hostname)
                and not (parsed.username or parsed.password)
            )
        except ValueError:
            valid = False
        if not valid:
            log.warning("%s: invalid original source URL", code)
            url = None
    book = record.get("book_title")
    if not url and local is None:
        if not book:
            return None
        return {"kind": "identified", "url": None, "embed_url": None,
                "label": book, "book_title": book, "author": record.get("book_author"),
                "chapter": record.get("chapter_number"),
                "source_problem_id": record.get("source_printed_problem_id") or record.get("source_problem_id"),
                "provenance_status": "LOCATION_INCOMPLETE", "location": None}
    registered_pdf = bool(record.get("problem_url")) and record.get("link_scope") in {
        "DIRECT_PROBLEM_AND_SOLUTION",
        "DIRECT_PROBLEM_ONLY",
        "DIRECT_PROBLEM_PDF",
        "AGGREGATE_MULTI_EXAM_PDF",
    }
    is_pdf = (
        local is not None
        or registered_pdf
        or bool(url and urlsplit(url).path.lower().endswith(".pdf"))
    )
    location = problem_location(local, record, code) if local else None
    return {
        "url": url,
        "kind": "pdf" if is_pdf else "web",
        "embed_url": f"/api/rest/solve/source-pdf/{quote(code, safe='')}"
        if local
        else url
        if is_pdf
        else None,
        "label": "Original full document" if is_pdf else "Original source page",
        "book_title": book,
        "chapter": record.get("chapter_number"),
        "source_problem_id": record.get("source_printed_problem_id") or record.get("source_problem_id"),
        "provenance_status": "DOCUMENT_AVAILABLE",
        "problem_number": record.get("problem_number"),
        "location": location,
        "highlight_url": f"/api/rest/solve/source-highlight/{quote(code, safe='')}"
        if location
        else None,
        "highlight_pdf_url": f"/api/rest/solve/source-marked-pdf/{quote(code, safe='')}"
        if location
        else None,
    }


def problem_location(pdf: Path, record: dict, code: str) -> dict | None:
    """Use verified extraction coordinates, otherwise an unambiguous text match."""
    import pymupdf

    with pymupdf.open(pdf) as document:
        directory = (pdf.parent / "questions" / code.rsplit("_", 1)[-1] / "images").resolve()
        clips = []
        if pdf.parent.resolve() in directory.parents and directory.is_dir():
            digest = hashlib.sha256(pdf.read_bytes()).hexdigest()[:16]
            for file in sorted(directory.glob("problem_figure_*.json")):
                metadata = json.loads(file.read_text())
                page = metadata.get("page")
                clip = metadata.get("clip")
                if (
                    metadata.get("source_side") == "problem"
                    and metadata.get("question") == record.get("problem_number")
                    and metadata.get("pdf_sha256_prefix") == digest
                    and isinstance(page, int)
                    and 1 <= page <= len(document)
                    and isinstance(clip, list)
                    and len(clip) == 4
                ):
                    clips.append((page, clip))
        # Prefer exact prose location; math delimiters are excluded from the match.
        statement = re.sub(r"^\s*\d+[.)]\s*", "", record.get("statement_text") or "")
        statement = re.split(r"\\\(|\$|\[asy\]", statement, maxsplit=1)[0].strip()
        words = statement.split()
        phrase = " ".join(words[:12]).rstrip(".,:;") if len(words) >= 4 else ""
        matches = []
        occurrences = 0
        if phrase:
            for index in range(min(len(document), 100)):
                page_text = " ".join(document[index].get_text().split())
                found = page_text.casefold().count(phrase.casefold())
                occurrences += found
                rects = document[index].search_for(phrase) if found == 1 else []
                if found == 1 and rects:
                    matches.append((index + 1, rects))
        if len(matches) == 1 and occurrences == 1:
            page, rects = matches[0]
            rectangles = [list(rect) for rect in rects]
            for block in document[page - 1].get_text("blocks"):
                if (
                    re.match(rf"^\s*{record.get('problem_number')}[.)]\s", block[4])
                    and any(pymupdf.Rect(block[:4]).intersects(rect) for rect in rects)
                    and len(re.findall(r"(?m)^\s*\d+[.)]\s", block[4])) == 1
                ):
                    rectangles = [list(block[:4])]
                    break
            rectangles += [clip for number, clip in clips if number == page]
        elif clips and len({number for number, _ in clips}) == 1:
            page = clips[0][0]
            rectangles = [clip for _, clip in clips]
        else:
            return None
        regions = {page: rectangles}
        for number, clip in clips:
            if number != page:
                regions.setdefault(number, []).append(clip)
        pages = []
        for number, rectangles in sorted(regions.items()):
            bounds = document[number - 1].rect
            valid = [
                list(pymupdf.Rect(rect) & bounds)
                for rect in dict.fromkeys(tuple(rect) for rect in rectangles)
                if not (pymupdf.Rect(rect) & bounds).is_empty
            ]
            if valid:
                pages.append({"page": number, "rectangles": valid})
        primary = next((entry for entry in pages if entry["page"] == page), None)
        return {**primary, "pages": pages} if primary else None


def _mark_page(document, location: dict):
    import pymupdf

    page = document[location["page"] - 1]
    for rectangle in location["rectangles"]:
        annotation = page.add_rect_annot(pymupdf.Rect(rectangle))
        annotation.set_colors(stroke=(0.8, 0.5, 0), fill=(1, 0.9, 0.2))
        annotation.set_opacity(0.25)
        annotation.update()
    return page


def highlighted_page(pdf: Path, location: dict) -> bytes:
    import pymupdf

    with pymupdf.open(pdf) as document:
        page = _mark_page(document, location)
        # Bounded full-page preview, never stored or reused as a problem diagram.
        scale = min(1.5, 1600 / max(page.rect.width, page.rect.height))
        return page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes("png")


def highlighted_pdf(pdf: Path, location: dict) -> bytes:
    """Return an annotated full-document copy; never change the original file."""
    import pymupdf

    with pymupdf.open(pdf) as document:
        for region in location.get("pages", [location]):
            _mark_page(document, region)
        return document.tobytes(deflate=True)
