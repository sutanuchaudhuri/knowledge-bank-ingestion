"""Newest-volume native evidence, run using the ingestion project's interpreter."""
import json
import os
import shutil
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "mathbank-db/etl"))
sys.path.insert(0, str(ROOT / "mathbank_data_ingestion/src"))
import arml_archive as archive


class ActualBookTests(unittest.TestCase):
    def setUp(self):
        archive.configure_cpu()
        self.doc = pymupdf.open(ROOT / "mathbank_data_ingestion/data/archive_books/arml/ARML-2015-2020.pdf")
        self.output = ROOT / "mathbank_data_ingestion/logs/arml/test_native_contract"
        self.section = next(s for s in archive.plan(self.doc) if s["paper_external_code"] == "PAPER_ARML_2015_TEAM")

    def tearDown(self):
        self.doc.close()
        shutil.rmtree(self.output, ignore_errors=True)

    def test_complete_native_inventory_includes_every_family(self):
        planned = [s for s in archive.plan(self.doc) if not s["answers_only"]]
        counts = {family: sum(len(archive.segments(self.doc, s)["problem"]) for s in planned
                              if s["competition_external_code"] == family)
                  for family in ("ARML", "ARML_LOCAL", "ARML_POWER")}
        self.assertEqual(len(planned), 66)
        self.assertEqual(counts, {"ARML": 226, "ARML_LOCAL": 229, "ARML_POWER": 11})

    def test_question_clip_physically_removes_other_questions(self):
        seen = []

        def fake_docling(data, out_dir, label):
            with pymupdf.open(stream=data, filetype="pdf") as bounded:
                text = bounded[0].get_text()
            seen.append(text)
            return SimpleNamespace(markdown=text, used_fallback=False, warnings=[], figure_paths=[])

        spans = archive.segments(self.doc, self.section)["problem"]["T-1"]
        with patch("mathbank.crawl.docling_extractor.extract_pdf", side_effect=fake_docling):
            archive.extract_span(self.doc, spans, self.output, "problem")
        self.assertIn("T-1.", seen[0])
        self.assertNotIn("T-2.", seen[0])
        self.assertNotIn("Kelly Property", seen[0])
        receipt = json.loads((self.output / "problem.docling.json").read_text())
        self.assertFalse(receipt["used_fallback"])
        self.assertTrue(any("region_" in p for p in receipt["images"]))
        self.assertTrue((self.output / "problem.native.txt").is_file())

    def test_fallback_never_completes(self):
        spans = archive.segments(self.doc, self.section)["problem"]["T-1"]
        with patch("mathbank.crawl.docling_extractor.extract_pdf", return_value=SimpleNamespace(
            markdown="Native fallback must not be accepted", used_fallback=True, warnings=[], figure_paths=[])):
            with self.assertRaises(RuntimeError):
                archive.extract_span(self.doc, spans, self.output, "problem")
        self.assertFalse((self.output / "problem.docling.json").is_file())

    def test_cpu_and_all_model_temporary_paths_on_external_project(self):
        self.assertEqual(os.environ["MATHBANK_PDF_DEVICE"], "cpu")
        for key in ("TMPDIR", "HF_HOME", "TORCH_HOME", "XDG_CACHE_HOME"):
            self.assertTrue(Path(os.environ[key]).is_relative_to(ROOT))


if __name__ == "__main__":
    unittest.main()
