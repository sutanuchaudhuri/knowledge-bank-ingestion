"""
PDF-based competition paper parser.

Extraction layer: Docling (preferred) → PyMuPDF fallback.
  - Docling produces layout-aware Markdown with formula detection and figure export.
  - PyMuPDF is used when Docling is unavailable or conversion fails.

Splitting strategy (applied to the extracted Markdown text):
  1. "Problem N" pattern  — most reliable for HMMT/CMM/CHMMC/MPG
  2. "N." strict-line-start with consecutive-sequence validation — for SMT/PUMaC/CHMMC
  3. Whole-paper fallback — returns q_num=0, caller decides how to handle

Per-question artifacts (parsed.json + problem_text.md) are written to
  data/crawl/<competition_slug>/<question_id>/
so that classify_crawled.py finds them using the same path as AoPS questions.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pymupdf as fitz   # kept for render_pdf_pages page renders

from mathbank.crawl.aops_parser import ParsedQuestion
from mathbank.crawl.docling_extractor import extract_pdf, DoclingResult
from mathbank.crawl.pdf_pages import question_page_numbers

# Root resolved relative to this file: mathbank/
_ROOT = Path(__file__).resolve().parents[3]
CRAWL_DIR = _ROOT / "data" / "crawl"


# ── PDF text/figure extraction via Docling (+ PyMuPDF fallback) ──────────────

@dataclass
class PageText:
    """Retained for back-compat; full_text() still works on these."""
    page_no: int
    text: str


def extract_pdf_text(pdf_bytes: bytes) -> list[PageText]:
    """Extract per-page text using PyMuPDF (used for quick local ops)."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages: list[PageText] = []
    for i, page in enumerate(doc, start=1):
        pages.append(PageText(page_no=i, text=page.get_text("text") or ""))
    doc.close()
    return pages


def full_text(pages: list[PageText]) -> str:
    return "\n\n".join(p.text for p in pages)


def extract_markdown(
    pdf_bytes: bytes,
    out_dir: Path | None = None,
    label: str = "doc",
) -> DoclingResult:
    """
    Extract full paper content as Markdown using Docling.
    Figures are saved to ``<out_dir>/figures/`` when out_dir is provided.
    Falls back to PyMuPDF text if Docling is unavailable.
    """
    return extract_pdf(pdf_bytes, out_dir=out_dir, label=label)


# ── Splitting helpers ─────────────────────────────────────────────────────────

def _matches_to_blocks(text: str, matches: list[re.Match]) -> dict[int, str]:
    """Convert an ordered, de-duped list of regex matches to {q_num: text} dict."""
    blocks: dict[int, str] = {}
    for i, m in enumerate(matches):
        q_num = int(m.group(1))
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        blocks[q_num] = text[start:end].strip()
    return blocks


def _keep_consecutive_prefix(matches: list[re.Match]) -> list[re.Match]:
    """
    Keep the first forward sequence 1, 2, 3, ..., k in document order.
    Ignore premature numbers inside a question (e.g. a line starting "15."
    inside question 10), so block boundaries cannot run backwards.
    """
    consecutive: list[re.Match] = []
    for m in matches:
        if int(m.group(1)) == len(consecutive) + 1:
            consecutive.append(m)
    return consecutive


# ── Competition-specific split patterns ───────────────────────────────────────

# Pattern A: "Problem N" at line start  (HMMT, CMM, CHMMC, MPG)
_PROBLEM_N = re.compile(r"(?m)^[ \t]*(?:#{1,6}[ \t]+)?Problem\s+(\d+)\b")

# Pattern B: "N." at strict line start  (SMT, PUMaC, and CHMMC individual fallback)
# Limit to 1-2 digit numbers to avoid matching page numbers like "100."
_NUMBER_DOT = re.compile(r"(?m)^(\d{1,2})\.\s+")

# Pattern C: "(N)" at line start  (some PUMaC rounds)
_PAREN_N = re.compile(r"(?m)^\((\d{1,2})\)\s+")

# Competitions that prefer "Problem N" over number-dot
_PROBLEM_N_FIRST = {"HMMT_FEB", "HMMT_NOV", "HMMT_INV", "HMMT", "CMM", "CHMMC",
                    "MPG_MAIN", "MPG_OLY", "MPG", "PURPLE_MS", "PURPLE_HS"}


def split_questions(
    text: str,
    competition_id: str,
    expected_count: int | None = None,
) -> dict[int, str]:
    """
    Split full PDF text into {question_number: text_block}.
    Returns {0: full_text} if no reliable split is found.
    """
    def _good_enough(blocks: dict[int, str], expected: int | None) -> bool:
        """Accept split if it yields a plausible question count."""
        n = len(blocks)
        if n < 2:
            return False
        if expected and n < max(2, expected * 0.6):
            return False
        if expected and n > expected * 1.5:
            return False
        return True

    # ── Try Problem N first for competitions that use it ─────────────────────
    if competition_id in _PROBLEM_N_FIRST or not competition_id:
        m_list = _keep_consecutive_prefix(list(_PROBLEM_N.finditer(text)))
        if m_list:
            blocks = _matches_to_blocks(text, m_list)
            if _good_enough(blocks, expected_count):
                return blocks

    # ── Try number-dot with consecutive-sequence validation ───────────────────
    m_list = _keep_consecutive_prefix(list(_NUMBER_DOT.finditer(text)))
    if m_list:
        blocks = _matches_to_blocks(text, m_list)
        if _good_enough(blocks, expected_count):
            return blocks

    # ── Try (N) parenthesis style ─────────────────────────────────────────────
    m_list = _keep_consecutive_prefix(list(_PAREN_N.finditer(text)))
    if m_list:
        blocks = _matches_to_blocks(text, m_list)
        if _good_enough(blocks, expected_count):
            return blocks

    # ── Final fallback: Problem N for non-primary competitions ────────────────
    if competition_id not in _PROBLEM_N_FIRST:
        m_list = _keep_consecutive_prefix(list(_PROBLEM_N.finditer(text)))
        if m_list:
            blocks = _matches_to_blocks(text, m_list)
            if _good_enough(blocks, expected_count):
                return blocks

    return {0: text.strip()}   # unsplit


# ── Answer extraction ─────────────────────────────────────────────────────────

def _extract_boxed_answer(text: str) -> str:
    m = re.search(r"\\boxed\{([^}]+)\}", text)
    if m:
        return m.group(1).strip()
    # Competition answers often appear as "Answer: N" or "The answer is N"
    m = re.search(r"(?i)(?:answer|ans)[:\s]+([^\n]{1,30})", text)
    return m.group(1).strip() if m else ""


# ── Per-question artifact saving ──────────────────────────────────────────────

def _q_slug(exam_level: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", exam_level.lower()).strip("_")


def save_question_artifacts(
    question_id: str,
    exam_level: str,
    problem_text: str,
    solution_texts: list[str],
    answer_value: str,
    image_paths: list[str],
    parse_warnings: list[str],
    source_url: str = "",
) -> Path:
    """
    Write parsed.json and problem_text.md for one question into
    data/crawl/<exam_level_slug>/<question_id>/
    Returns the question directory path.
    """
    qdir = CRAWL_DIR / _q_slug(exam_level) / question_id
    qdir.mkdir(parents=True, exist_ok=True)

    record = {
        "question_id": question_id,
        "url": source_url,
        "problem_text": problem_text,
        "solution_texts": solution_texts,
        "answer_choices": [],
        "answer_value": answer_value,
        "image_urls": image_paths,
        "parse_warnings": parse_warnings,
        "crawled_at": datetime.now(timezone.utc).isoformat(),
    }
    (qdir / "parsed.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Markdown artifact — same format as aops_parser.ParsedQuestion.to_md()
    lines = [f"# {question_id}", "", "## Problem", "", problem_text.strip()]
    for i, sol in enumerate(solution_texts, 1):
        label = "Solution" if len(solution_texts) == 1 else f"Solution {i}"
        lines += ["", f"## {label}", "", sol.strip()]
    if answer_value:
        lines += ["", f"**Answer:** {answer_value}"]
    (qdir / "problem_text.md").write_text("\n".join(lines), encoding="utf-8")

    return qdir


# ── Main public function ──────────────────────────────────────────────────────

def parse_pdf_paper(
    paper_id: str,
    competition_id: str,
    problem_bytes: bytes,
    solution_bytes: bytes | None,
    expected_count: int | None = None,
    save_artifacts: bool = True,
    exam_level: str = "",
    paper_url: str = "",
    visuals_dir: Path | None = None,
) -> list[ParsedQuestion]:
    """
    Parse a PDF paper into a list of ParsedQuestion objects, one per question.

    Uses Docling for layout-aware Markdown extraction with figure export,
    falling back to PyMuPDF when Docling is unavailable.

    When save_artifacts=True, writes parsed.json and problem_text.md
    to data/crawl/<exam_level_slug>/<question_id>/ for each question.
    Extracted figures are saved to visuals_dir/figures/ when provided.
    """
    level = exam_level or competition_id

    # ── Extract problem PDF ───────────────────────────────────────────────────
    prob_result = extract_markdown(problem_bytes, out_dir=visuals_dir, label="problem")
    prob_blocks = split_questions(prob_result.markdown, competition_id, expected_count)
    prob_figures = prob_result.figure_paths

    # ── Extract solution PDF ──────────────────────────────────────────────────
    sol_blocks: dict[int, str] = {}
    sol_figures: list[str] = []
    if solution_bytes:
        sol_result = extract_markdown(solution_bytes, out_dir=visuals_dir, label="solution")
        sol_blocks = split_questions(sol_result.markdown, competition_id, expected_count)
        sol_figures = sol_result.figure_paths

    all_q_nums = sorted(set(prob_blocks) | set(sol_blocks))
    results: list[ParsedQuestion] = []

    for q_num in all_q_nums:
        problem_text = prob_blocks.get(q_num, "")
        solution_text = sol_blocks.get(q_num, "")

        warnings: list[str] = []
        if not problem_text:
            warnings.append(f"No problem text found for Q{q_num}")
        if not solution_text:
            warnings.append(f"No solution text found for Q{q_num}")
        if prob_result.used_fallback:
            warnings.append("Extracted with PyMuPDF native text (Docling unavailable or explicitly bypassed)")
        warnings.extend(prob_result.warnings)

        q_id = f"{paper_id}_Q{q_num:02d}" if q_num > 0 else paper_id
        answer = _extract_boxed_answer(solution_text)
        solution_list = [solution_text] if solution_text else []

        # Heuristic: assign problem figures to questions proportionally.
        n_q = max(len(all_q_nums), 1)
        if len(prob_figures) > 0 and q_num > 0:
            figs_per_q = max(1, len(prob_figures) // n_q)
            start = (q_num - 1) * figs_per_q
            q_figs = prob_figures[start:start + figs_per_q]
        else:
            q_figs = prob_figures  # unsplit fallback: all figures to the single block

        all_images = q_figs + ([sol_figures[q_num - 1]] if q_num > 0 and q_num <= len(sol_figures) else [])

        if save_artifacts:
            save_question_artifacts(
                question_id=q_id,
                exam_level=level,
                problem_text=problem_text,
                solution_texts=solution_list,
                answer_value=answer,
                image_paths=all_images,
                parse_warnings=warnings,
                source_url=paper_url,
            )

        results.append(ParsedQuestion(
            question_id=q_id,
            url=paper_url,
            problem_text=problem_text,
            solution_texts=solution_list,
            answer_choices=[],
            answer_value=answer,
            image_urls=all_images,
            parse_warnings=warnings,
        ))

    return results


# ── Visual page renders ───────────────────────────────────────────────────────

def render_pdf_pages(pdf_bytes: bytes, out_dir: Path, label: str, dpi: int = 144) -> list[str]:
    """Render each PDF page to PNG; return list of absolute file paths."""
    (out_dir / "pages").mkdir(parents=True, exist_ok=True)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    paths: list[str] = []
    zoom = max(dpi, 72) / 72.0
    for i, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        fname = f"{label}_page_{i:03d}.png"
        fpath = out_dir / "pages" / fname
        pix.save(str(fpath))
        paths.append(str(fpath))
    doc.close()
    return paths

