"""
Docling-based PDF extractor for competition math papers.

Replaces the raw PyMuPDF text dump with Docling's layout-aware extraction:
  - Proper reading order (handles multi-column layouts)
  - Mathematical formula detection  →  output as $...$ / $$...$$
  - Figure/image extraction with bounding-box metadata
  - Native Markdown export (headings, tables, math blocks)

Falls back to PyMuPDF if Docling is not installed or conversion fails,
so the pipeline continues working in constrained environments.

Usage:
    from mathbank.crawl.docling_extractor import extract_pdf, DoclingResult

    result = extract_pdf(pdf_bytes, out_dir=Path("visuals"), label="problem")
    # result.markdown  — full paper as Markdown
    # result.figure_paths  — list of extracted figure image paths
    # result.page_count  — number of pages
"""
from __future__ import annotations

import hashlib
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

_DOCLING_AVAILABLE: bool | None = None   # cached after first import attempt


def _check_docling() -> bool:
    global _DOCLING_AVAILABLE
    if _DOCLING_AVAILABLE is None:
        try:
            import docling  # noqa: F401
            _DOCLING_AVAILABLE = True
        except ImportError:
            _DOCLING_AVAILABLE = False
    return _DOCLING_AVAILABLE


@dataclass
class DoclingResult:
    markdown: str
    figure_paths: list[str] = field(default_factory=list)
    page_count: int = 0
    used_fallback: bool = False
    warnings: list[str] = field(default_factory=list)


def _extract_with_docling(pdf_bytes: bytes, out_dir: Path | None, label: str) -> DoclingResult:
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions

    # Build pipeline options — enable image and figure extraction.
    opts = PdfPipelineOptions()
    opts.generate_picture_images = True
    opts.generate_page_images = False  # skip full page renders; we keep PyMuPDF for those
    opts.images_scale = 2.0

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=opts)
        }
    )

    # Docling requires a file path, not bytes; write to a temp file.
    warnings: list[str] = []
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        tf.write(pdf_bytes)
        tmp_path = Path(tf.name)

    try:
        result = converter.convert(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    doc = result.document
    page_count = len(doc.pages) if hasattr(doc, "pages") else 0

    # Export to Markdown.
    markdown = doc.export_to_markdown()

    # Extract figure images if an output directory was provided.
    figure_paths: list[str] = []
    if out_dir is not None:
        (out_dir / "figures").mkdir(parents=True, exist_ok=True)
        try:
            # Docling 2.x: iterate doc.pictures
            pictures = list(doc.pictures) if hasattr(doc, "pictures") else []
            for i, pic in enumerate(pictures, start=1):
                img = getattr(pic, "image", None)
                pil_img = getattr(img, "pil_image", None) if img else None
                if pil_img is None:
                    continue
                fname = f"{label}_figure_{i:03d}.png"
                fpath = out_dir / "figures" / fname
                pil_img.save(str(fpath))
                figure_paths.append(str(fpath))
        except Exception as exc:
            warnings.append(f"Figure extraction warning: {exc}")

    return DoclingResult(
        markdown=markdown,
        figure_paths=figure_paths,
        page_count=page_count,
        used_fallback=False,
        warnings=warnings,
    )


def _extract_with_pymupdf(pdf_bytes: bytes, out_dir: Path | None, label: str) -> DoclingResult:
    """Fallback: PyMuPDF raw text extraction."""
    import pymupdf as fitz

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages: list[str] = []
    figure_paths: list[str] = []

    if out_dir is not None:
        (out_dir / "figures").mkdir(parents=True, exist_ok=True)

    for i, page in enumerate(doc, start=1):
        pages.append(page.get_text("text") or "")
        if out_dir is not None:
            for j, img_info in enumerate(page.get_images(full=True), start=1):
                xref = int(img_info[0])
                try:
                    pix = fitz.Pixmap(doc, xref)
                    if pix.n - pix.alpha > 3:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    fname = f"{label}_p{i:03d}_fig_{j:02d}.png"
                    fpath = out_dir / "figures" / fname
                    pix.save(str(fpath))
                    figure_paths.append(str(fpath))
                except Exception:
                    pass

    doc.close()
    markdown = "\n\n".join(pages)
    return DoclingResult(
        markdown=markdown,
        figure_paths=figure_paths,
        page_count=len(pages),
        used_fallback=True,
    )


def extract_pdf(
    pdf_bytes: bytes,
    out_dir: Path | None = None,
    label: str = "doc",
    force_fallback: bool = False,
) -> DoclingResult:
    """
    Extract PDF content using Docling (preferred) or PyMuPDF (fallback).

    Parameters
    ----------
    pdf_bytes:
        Raw PDF bytes.
    out_dir:
        Directory in which to save extracted figure images.
        Figures are placed in ``<out_dir>/figures/``.
    label:
        Prefix for figure file names (e.g. "problem", "solution").
    force_fallback:
        Skip Docling and go straight to PyMuPDF (useful for testing or
        when Docling's heavyweight models are unavailable).
    """
    if not force_fallback and _check_docling():
        try:
            return _extract_with_docling(pdf_bytes, out_dir, label)
        except Exception as exc:
            result = _extract_with_pymupdf(pdf_bytes, out_dir, label)
            result.warnings.insert(0, f"Docling failed ({exc}); used PyMuPDF fallback")
            return result

    return _extract_with_pymupdf(pdf_bytes, out_dir, label)
