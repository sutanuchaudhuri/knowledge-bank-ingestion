"""Strict, page-anchored ARML book extraction. No network or paid calls."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INGESTION = ROOT / "mathbank_data_ingestion"
VOLUMES = ("2015-2020", "2009-2014", "2004-2008", "1995-2003")
BASE_URL = "https://arml3.com/wp-content/uploads/2026/03/"
ANCHOR = re.compile(r"^(T|I|TB|R[A-Z0-9]*|SR)-([A-Z]|\d+)\.\s*")
NUMBER = re.compile(r"^(\d+)\.$")


def configure_cpu() -> None:
    """Configure before importing Docling/torch/tempfile."""
    paths = {
        "TMPDIR": INGESTION / "logs/arml/tmp",
        "HF_HOME": INGESTION / "data/model_cache/huggingface",
        "TORCH_HOME": INGESTION / "data/model_cache/torch",
        "XDG_CACHE_HOME": INGESTION / "data/model_cache/xdg",
    }
    for key, path in paths.items():
        path.mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(path)
    os.environ["MATHBANK_PDF_DEVICE"] = "cpu"
    os.environ.pop("MATHBANK_PDF_EXTRACTOR", None)
    import tempfile
    tempfile.tempdir = str(paths["TMPDIR"])


def slug(text: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", text.upper()).strip("_")


def plan(doc) -> list[dict]:
    toc = doc.get_toc()
    if not toc:
        raise ValueError("Unsupported ARML layout: embedded TOC missing")
    sections = []
    competition = event = None
    for index, (level, title, page) in enumerate(toc):
        if level == 1:
            competition = ("ARML_LOCAL" if "Local Contests" in title else
                           "ARML_POWER" if "Power Contests" in title else
                           "ARML" if re.search(r"\bARML Contests\b", title) else None)
            event = None
            continue
        elif level == 2 and competition:
            event = title
            if competition != "ARML_POWER":
                continue
        elif level != 3 or not competition or not event:
            continue
        if competition == "ARML_POWER" and level == 3:
            continue
        end = next((entry[2] - 1 for entry in toc[index + 1:]
                    if entry[0] <= level), len(doc))
        year = re.search(r"(?:19|20)\d{2}", event)
        if not year or end < page:
            raise ValueError(f"Unsupported TOC entry: {title}")
        round_name = "POWER_" + slug(event.split(year[0])[0]) if competition == "ARML_POWER" else slug(title.split(" Problem")[0])
        if competition == "ARML_LOCAL":
            round_name = "LOCAL_" + round_name
        sections.append({
            "competition_external_code": competition,
            "paper_external_code": f"PAPER_ARML_{year[0]}_{round_name}",
            "crawl_dir": competition.lower(), "title": title, "event": event,
            "start": page, "end": end,
            "contextual": competition == "ARML_POWER" or "Power Question" in title or "Puzzles" in title,
            "answers_only": title.startswith("Answers"),
        })
    if not sections or len({s["paper_external_code"] for s in sections}) != len(sections):
        raise ValueError("Unsupported ARML TOC: empty/duplicate round inventory")
    return sections


def lines(page) -> list[tuple[str, float]]:
    return [
        ("".join(span["text"] for span in line["spans"]).strip(), line["bbox"][1])
        for block in page.get_text("dict")["blocks"] if block["type"] == 0
        for line in block["lines"]
        if not (NUMBER.match("".join(span["text"] for span in line["spans"]).strip())
                and line["bbox"][0] > 90)
    ]


def mode_for_header(text: str, contextual: bool) -> str:
    if re.search(r"Solutions?|Answers? to .*Puzzles", text, re.I):
        return "solution"
    if re.search(r"Answers?", text, re.I) and not contextual:
        return "answer"
    return "problem"


def segments(doc, section: dict) -> dict[str, dict[str, list]]:
    """Native text locates boundaries only; Docling supplies ingested text/formulas."""
    sides = {"problem": {}, "answer": {}, "solution": {}}
    current = {side: None for side in sides}
    mode = "answer" if section["answers_only"] else "problem"
    for number in range(section["start"], section["end"] + 1):
        page = doc[number - 1]
        entries = lines(page)
        header = next((text for text, _ in entries[:4]
                       if not text.isdigit() and text), "")
        if not header:
            continue
        # Blank endpapers and publisher's back cover aren't contest material.
        if number > section["start"] and not re.search(r"ARML|Power Question|Problems?|Solutions|Answers", header, re.I):
            if section["end"] == len(doc) and number >= len(doc) - 1:
                continue
            raise ValueError(f"Page {number}: unsupported running header {header!r}")
        mode = "answer" if section["answers_only"] else mode_for_header(header, section["contextual"])
        if section["contextual"]:
            sides[mode].setdefault("CONTEXT", []).append([number, 0, page.rect.height])
            continue
        anchors = []
        for text, y in entries:
            match = ANCHOR.match(text)
            if match:
                anchors.append((match[0].strip().rstrip("."), y))
            elif "Super Relay" in section["title"]:
                match = NUMBER.match(text)
                if match:
                    anchors.append((f"SR-{match[1]}", y))
        if not anchors and current[mode] is None:
            raise ValueError(f"Page {number}: no {mode} question anchor")
        if anchors and current[mode] is not None and anchors[0][1] > 85:
            sides[mode][current[mode]].append([number, 55, anchors[0][1]])
        for i, (key, y) in enumerate(anchors):
            if mode != "solution" and key in sides[mode] and key != current[mode]:
                raise ValueError(f"Page {number}: duplicate {mode} anchor {key}")
            sides[mode].setdefault(key, []).append(
                [number, max(0, y - 1), anchors[i + 1][1] if i + 1 < len(anchors) else page.rect.height - 25])
            current[mode] = key
        if not anchors:
            sides[mode][current[mode]].append([number, 55, page.rect.height - 25])
    if not section["answers_only"]:
        if not sides["problem"] or set(sides["problem"]) != set(sides["solution"]):
            raise ValueError(f"{section['paper_external_code']}: missing/mismatched problems and worked solutions")
        if sides["answer"] and set(sides["answer"]) != set(sides["problem"]):
            raise ValueError(f"{section['paper_external_code']}: incomplete answer key")
    return sides


def extract_span(doc, spans, folder: Path, side: str, book_hash: str | None = None) -> str:
    import pymupdf as fitz
    sys.path.insert(0, str(INGESTION / "src"))
    from mathbank.crawl.docling_extractor import extract_pdf
    target = folder / f"{side}.md"
    book_hash = book_hash or hashlib.sha256(doc.tobytes()).hexdigest()
    fingerprint = hashlib.sha256(("arml-redacted-v4:" + json.dumps(spans) + book_hash).encode()).hexdigest()
    receipt = folder / f"{side}.docling.json"
    if target.is_file() and receipt.is_file():
        cached = json.loads(receipt.read_text())
        if (cached.get("input_hash") == fingerprint and cached.get("used_fallback") is False
                and (folder / f"{side}.native.txt").is_file()
                and all((folder / name).is_file() for name in cached.get("images", []))):
            return target.read_text()
    images = folder / "images"
    images.mkdir(parents=True, exist_ok=True)
    chunks = []
    # At most one page per conversion; no 504-page model invocation.
    for ordinal, (number, top, bottom) in enumerate(spans, 1):
        page = doc[number - 1]
        clip = fitz.Rect(0, top, page.rect.width, bottom)
        with fitz.open() as bounded:
            bounded.insert_pdf(doc, from_page=number - 1, to_page=number - 1)
            output = bounded[0]
            # show_pdf_page(clip=...) leaves invisible off-clip text accessible
            # to PDF backends. Redact it from the bounded input instead.
            if top > 0:
                output.add_redact_annot(fitz.Rect(0, 0, page.rect.width, top))
            if bottom < page.rect.height:
                output.add_redact_annot(fitz.Rect(0, bottom, page.rect.width, page.rect.height))
            output.apply_redactions(images=2, graphics=1, text=0)
            result = extract_pdf(bounded.tobytes(), out_dir=images, label=f"{side}_{ordinal:03d}")
        if result.used_fallback or result.warnings or not result.markdown.strip():
            raise RuntimeError(f"ARML requires successful CPU Docling extraction: page {number}, {result.warnings}")
        chunks.append(result.markdown)
        for figure in result.figure_paths:
            figure = Path(figure)
            figure.replace(images / figure.name)
        page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).save(str(images / f"{side}_page_{number:03d}.png"))
        page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip).save(
            str(images / f"{side}_region_{ordinal:03d}_page_{number:03d}.png"))
        # Preserve all original raster assets, including assets Docling didn't detect.
        for i, image in enumerate(page.get_images(full=True), 1):
            data = doc.extract_image(image[0])
            (images / f"{side}_page_{number:03d}_raster_{i:03d}.{data['ext']}").write_bytes(data["image"])
            pixmap = fitz.Pixmap(doc, image[0])
            if pixmap.n - pixmap.alpha > 3:
                pixmap = fitz.Pixmap(fitz.csRGB, pixmap)
            pixmap.save(str(images / f"{side}_page_{number:03d}_raster_{i:03d}.png"))
    text = "\n\n".join(chunks)
    if side != "answer" and len(re.sub(r"<!--.*?-->|[^A-Za-z]", "", text)) < 8:
        raise RuntimeError(f"Docling produced no meaningful {side} text; image-only extraction is incomplete")
    target.write_text(text)
    (folder / f"{side}.native.txt").write_text("\n\n".join(
        doc[number - 1].get_text("text", clip=fitz.Rect(
            0, top, doc[number - 1].rect.width, bottom))
        for number, top, bottom in spans))
    receipt.write_text(json.dumps({"input_hash": fingerprint, "used_fallback": False,
                                   "device": "cpu", "formula_enrichment": True, "spans": spans,
                                   "images": [str(p.relative_to(folder)) for p in sorted(images.glob("*")) if p.is_file()]}, indent=2))
    return text


def extract_book(path: Path, only_paper: str | None = None, plan_only: bool = False) -> list[dict]:
    configure_cpu()
    import pymupdf as fitz
    with fitz.open(path) as doc:
        inventory = plan(doc)
        planned = [(section, segments(doc, section)) for section in inventory]
        book_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        sources = []
        for section, sides in planned:
            if section["answers_only"] or (only_paper and section["paper_external_code"] != only_paper):
                continue
            source = {**section, "volume": path.name, "book_sha256": book_hash,
                      "problem_url": BASE_URL + path.name, "expected_count": len(sides["problem"])}
            if plan_only:
                sources.append(source)
                continue
            folder = INGESTION / "data/crawl_pdf" / section["crawl_dir"] / section["paper_external_code"]
            folder.mkdir(parents=True, exist_ok=True)
            codes, answers, provenance = [], {}, {}
            for ordinal, key in enumerate(sides["problem"], 1):
                question = folder / "questions" / f"Q{ordinal:02d}"
                question.mkdir(parents=True, exist_ok=True)
                codes.append(f"{section['paper_external_code']}_Q{ordinal:02d}")
                provenance[str(ordinal)] = {"source_id": key, "book": path.name, "book_sha256": book_hash}
                for side in ("problem", "solution", "answer"):
                    spans = sides[side].get(key)
                    # Local keys are printed together at the end of each contest.
                    if side == "answer" and not spans:
                        candidates = [s["answer"].get(key) for entry, s in planned
                                      if entry["answers_only"] and entry["event"] == section["event"]
                                      and entry["competition_external_code"] == section["competition_external_code"]]
                        spans = next((candidate for candidate in candidates if candidate), None)
                    if spans:
                        text = extract_span(doc, spans, question, side, book_hash)
                        provenance[str(ordinal)][side] = spans
                        if side == "answer":
                            answers[str(ordinal)] = re.sub(
                                r"^\s*[-*#\s]*" + re.escape(key) + r"\.?\s*", "", text).strip()
                if section["competition_external_code"] == "ARML_LOCAL" and str(ordinal) not in answers:
                    raise ValueError(f"{codes[-1]}: official local answer missing")
                provenance[str(ordinal)]["answer_availability"] = (
                    "OFFICIAL_KEY_AVAILABLE" if str(ordinal) in answers else
                    "NOT_APPLICABLE_CONTEXTUAL_PROOF" if section["contextual"] and "Puzzles" not in section["title"] else
                    "NO_SEPARATE_PUZZLE_KEY_WORKED_ANSWERS_RETAINED" if "Puzzles" in section["title"] else
                    "NO_SEPARATE_OFFICIAL_KEY")
                provenance[str(ordinal)]["shared_parent_context"] = bool(section["contextual"])
            (folder / "answers.json").write_text(json.dumps(answers, indent=2))
            (folder / "provenance.json").write_text(json.dumps(provenance, indent=2))
            (folder / "index.json").write_text(json.dumps({"questions": codes, "source": source}, indent=2))
            sources.append(source)
        if only_paper and not sources:
            raise ValueError(f"Unknown round: {only_paper}")
        return sources


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--paper")
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(extract_book(args.pdf, args.paper, args.plan_only), indent=2))


if __name__ == "__main__":
    main()
