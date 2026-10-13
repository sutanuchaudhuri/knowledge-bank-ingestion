"""Crop PDF figures inside verified question boundaries, never entire pages."""

from __future__ import annotations

import hashlib
import json
import re
from itertools import pairwise
from pathlib import Path

import pymupdf as fitz

PATTERNS = (
    re.compile(r"^\s*Problem\s+(\d+)\b"),
    re.compile(r"^\s*(\d{1,2})\.\s+"),
    re.compile(r"^\s*\((\d{1,2})\)\s+"),
)


def question_boundaries(doc, expected_count: int) -> list[tuple[int, fitz.Rect]]:
    lines = []
    for page_number, page in enumerate(doc):
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                content = "".join(span["text"] for span in line["spans"])
                lines.append((page_number, fitz.Rect(line["bbox"]), content))
    for pattern in PATTERNS:
        headings = []
        numbers = []
        for page_number, rect, content in lines:
            match = pattern.match(content)
            if match:
                numbers.append(int(match.group(1)))
                headings.append((page_number, rect))
        if numbers != list(range(1, expected_count + 1)):
            continue
        if any((p, r.y0) >= (p2, r2.y0) for (p, r), (p2, r2) in pairwise(headings)):
            continue
        if max(r.x0 for _, r in headings) - min(r.x0 for _, r in headings) > 40:
            continue
        return headings
    raise ValueError(f"Cannot verify spatial boundaries for all {expected_count} questions")


def figure_regions(doc, expected_count: int) -> dict[int, list[tuple[int, fitz.Rect]]]:
    headings = question_boundaries(doc, expected_count)
    result = {n: [] for n in range(1, expected_count + 1)}
    for index, (first_page, start) in enumerate(headings):
        next_page, end = (
            headings[index + 1] if index + 1 < len(headings) else (len(doc) - 1, doc[-1].rect)
        )
        for page_number in range(first_page, next_page + 1):
            page = doc[page_number]
            # Repeated headers/footers are outside the printable question area.
            top = start.y0 if page_number == first_page else 55
            bottom = (
                end.y0 - 2
                if index + 1 < len(headings) and page_number == next_page
                else page.rect.height - 35
            )
            if bottom <= top:
                continue
            band = fitz.Rect(0, top, page.rect.width, bottom)
            graphics = []
            for drawing in page.get_drawings():
                rect = drawing["rect"]
                if rect.width > 8 and rect.height > 8 and band.contains(rect):
                    graphics.append(rect)
            for image in page.get_image_info():
                rect = fitz.Rect(image["bbox"])
                if rect.width > 8 and rect.height > 8 and band.contains(rect):
                    graphics.append(rect)
            if not graphics:
                continue
            bounds = fitz.Rect(graphics[0])
            for rect in graphics[1:]:
                bounds |= rect
            # Labels can sit just outside the vector paths; retain nearby short text.
            neighbourhood = fitz.Rect(
                bounds.x0 - 18, bounds.y0 - 18, bounds.x1 + 18, bounds.y1 + 18
            )
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    content = "".join(span["text"] for span in line["spans"]).strip()
                    rect = fitz.Rect(line["bbox"])
                    if (
                        len(content) <= 40
                        and band.contains(rect)
                        and neighbourhood.intersects(rect)
                    ):
                        bounds |= rect
            clip = fitz.Rect(bounds.x0 - 8, bounds.y0 - 8, bounds.x1 + 8, bounds.y1 + 8) & band
            if clip.width >= page.rect.width * 0.9 and clip.height >= page.rect.height * 0.8:
                raise ValueError(f"Question {index + 1}: figure bounds cover almost an entire page")
            result[index + 1].append((page_number, clip))
    return result


def extract_pdf_figures(
    pdf_bytes: bytes,
    expected_count: int,
    output_root: Path,
    *,
    side: str = "problem",
    write: bool = False,
) -> dict[int, list[Path]]:
    if side not in {"problem", "solution"}:
        raise ValueError("Figure source side must be problem or solution")
    fingerprint = hashlib.sha256(pdf_bytes).hexdigest()[:16]
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        regions = figure_regions(doc, expected_count)
        result = {}
        for number, clips in regions.items():
            folder = output_root / "questions" / f"Q{number:02d}" / "images"
            result[number] = []
            for ordinal, (page_number, clip) in enumerate(clips, 1):
                crop_key = hashlib.sha256(
                    json.dumps(
                        {"algorithm": 2, "page": page_number, "clip": list(clip), "scale": 2},
                        sort_keys=True,
                    ).encode()
                ).hexdigest()[:10]
                path = folder / f"{side}_figure_{fingerprint}_{crop_key}_{ordinal:03d}.png"
                if write:
                    folder.mkdir(parents=True, exist_ok=True)
                    if not path.is_file():
                        doc[page_number].get_pixmap(
                            matrix=fitz.Matrix(2, 2), clip=clip, alpha=False
                        ).save(path)
                    receipt = path.with_suffix(".json")
                    receipt.write_text(
                        json.dumps(
                            {
                                "method": "question_bounded_pdf_figure",
                                "algorithm_version": 2,
                                "source_side": side,
                                "pdf_sha256_prefix": fingerprint,
                                "question": number,
                                "page": page_number + 1,
                                "clip": list(clip),
                            },
                            indent=2,
                        )
                        + "\n"
                    )
                result[number].append(path.resolve())
        return result


def extract_question_figures(
    paper_dir: Path,
    *,
    write: bool = False,
    side: str = "problem",
    expected_count: int | None = None,
) -> dict[int, list[Path]]:
    if expected_count is None:
        numbers = sorted(
            int(q.name[1:])
            for q in (paper_dir / "questions").glob("Q[0-9]*")
            if q.name[1:].isdigit() and (q / "problem.md").is_file()
        )
        if not numbers or numbers != list(range(1, max(numbers) + 1)):
            raise ValueError("Question inventory is not a complete consecutive sequence")
        expected_count = len(numbers)
    return extract_pdf_figures(
        (paper_dir / f"{side}.pdf").read_bytes(), expected_count, paper_dir, side=side, write=write
    )
