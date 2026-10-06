"""Compatibility exports; PDF figure extraction belongs to ingestion."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mathbank_data_ingestion/src"))
from mathbank.crawl.question_figures import (  # noqa: F401
    extract_pdf_figures,
    extract_question_figures,
    figure_regions,
    question_boundaries,
)
