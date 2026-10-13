"""Offline contract tests for etl/import_textbook_package.py (no database)."""

import csv
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("textbook_import", ROOT / "mathbank-db/etl/import_textbook_package.py")
tb = importlib.util.module_from_spec(spec)
sys.modules["textbook_import"] = tb
spec.loader.exec_module(tb)

HEADERS = {
    "csv/source_manifest.csv": ["book_id", "title", "author", "translator_editor", "source_file"],
    "csv/chapters_sections.csv": ["chapter_number", "chapter_title", "section_number", "section_title"],
    "csv/problems.csv": ["problem_id", "chapter_number", "section_number", "section_title", "problem_text",
                         "source_page_start", "difficulty_band_source_order"],
    "csv/solutions.csv": ["solution_id", "problem_id", "solution_text", "source_page"],
    "csv/diagram_manifest.csv": ["diagram_id", "problem_id", "usage", "asset_path"],
    "pedagogy_v3/csv/taxonomy_nodes.csv": ["taxonomy_node_id", "node_type", "name", "parent_node_id",
                                           "chapter_number", "section_number", "description"],
    "pedagogy_v3/csv/taxonomy_edges.csv": ["from_node_id", "to_node_id", "relationship_type", "confidence"],
    "pedagogy_v3/csv/problem_taxonomy_enriched.csv": ["problem_id", "concept_id", "subconcept_id",
                                                      "primary_skill_id", "solution_step_skill_ids", "technique_ids",
                                                      "taxonomy_confidence"],
    "pedagogy_v3/csv/solution_parts.csv": ["solution_part_id", "solution_id", "problem_id", "part_label",
                                           "step_count"],
    "pedagogy_v3/csv/solution_steps.csv": ["solution_step_id", "solution_part_id", "solution_id", "problem_id",
                                           "global_step_index", "step_index_in_part", "step_text", "step_type",
                                           "skill_id", "hint_level", "is_checkpoint"],
    "pedagogy_v3/csv/solution_step_dependencies.csv": ["from_step_id", "to_step_id", "relationship_type",
                                                       "confidence"],
    "pedagogy_v3/csv/transformations_v3_no_proof.csv": ["transformation_id", "source_problem_id",
                                                        "transformation_type", "transformed_question",
                                                        "choices_json", "review_status", "no_proof",
                                                        "solution_step_anchor_id"],
}


def test_import_flags_unsupported_power_candidate_without_retagging_staged_input():
    conflicts = []
    proposal = {"technique_ids": [tb.POWER]}
    plan = SimpleNamespace(
        enrichment={"6.76": proposal},
        problems={"6.76": {"statement_text": "If n is not a power of a prime, construct an equiangular n-gon."}},
        steps={"step": {"problem": "6.76", "step_text": "Use vector projections."}},
        conflict=lambda *args, **kwargs: conflicts.append((args, kwargs)),
    )
    tb.flag_power_candidates(plan)
    assert proposal["technique_ids"] == [tb.POWER]
    assert proposal["blocked_technique_ids"] == [tb.POWER]
    assert conflicts[0][0][2] == "TECHNIQUE_EVIDENCE_MISSING"
    good = {"technique_ids": [tb.POWER]}
    plan.enrichment = {"1.1": good}
    plan.problems = {"1.1": {"statement_text": "Two chords of a circle intersect at P."}}
    plan.steps = {"step": {"problem": "1.1", "step_text": "PA*PB=PC*PD"}}
    tb.flag_power_candidates(plan)
    assert "blocked_technique_ids" not in good


def step(sid, part, pid, gi, ii):
    return [sid, part, f"SOL-{pid}", pid, gi, ii, f"text {sid} {gi}", "INFERENCE", "SKILL.X", "2", "FALSE"]


ROWS = {
    "csv/source_manifest.csv": [["PRASOLOV_PLANE_GEOMETRY_V1", "Book", "Author", "Translator", "book.pdf"]],
    "csv/chapters_sections.csv": [["1", "Ch1", "1", "S1"], ["2", "Ch2", "1", "S1"]],
    "csv/problems.csv": [
        ["1.1", "1", "1", "S1", "Prove A.", "10", "1"],
        ["1.2", "1", "INTRO", "", "Chapter intro prose", "", ""],
        ["1.2", "1", "1", "S1", "Prove B.", "11", "2"],
        ["2.1", "2", "1", "S1", "Prove C.", "20", "1"],
    ],
    "csv/solutions.csv": [["SOL-1.1", "1.1", "Sol A", "30"], ["SOL-1.2", "1.2", "Sol B", "31"],
                          ["SOL-9.9", "9.9", "Orphan", "32"], ["SOL-2.1", "2.1", "Sol C", "33"]],
    "csv/diagram_manifest.csv": [["D1", "1.1", "PROBLEM", "diagrams/problems/d1.png"],
                                 ["D2", "1.1", "SOLUTION", "diagrams/solutions/d2.png"],
                                 ["D3", "1.1", "PROBLEM", "diagrams/problems/missing.png"]],
    "pedagogy_v3/csv/taxonomy_nodes.csv": [["GEO", "DOMAIN", "Geometry", "", "", "", ""],
                                           ["GEO.C01", "CONCEPT", "Similarity", "GEO", "1", "", ""],
                                           ["GEO.C01.S01", "SUBCONCEPT", "Sub", "GEO.C01", "1", "1", ""],
                                           ["SKILL.X", "SKILL", "Skill X", "GEO.C01.S01", "", "", ""],
                                           ["TECH.Y", "TECHNIQUE", "Tech Y", "", "", "", ""]],
    "pedagogy_v3/csv/taxonomy_edges.csv": [["SKILL.X", "GEO.C01.S01", "PART_OF", "0.9"],
                                           ["GEO.C01.S01", "GEO.C01", "PART_OF", "1"],
                                           ["TECH.Y", "GEO.C01.S01", "SUPPORTS", "0.8"]],
    "pedagogy_v3/csv/problem_taxonomy_enriched.csv": [
        ["1.1", "GEO.C01", "GEO.C01.S01", "SKILL.X", "SKILL.X", "TECH.Y", "0.9"],
        ["1.2", "GEO.C01", "GEO.C01.S01", "SKILL.X", "", "TECH.Y", "0.9"],
        ["2.1", "GEO.C01", "GEO.C01.S01", "SKILL.X", "", "", "0.9"],
    ],
    "pedagogy_v3/csv/solution_parts.csv": [["PART-1.1-A", "SOL-1.1", "1.1", "A", "2"],
                                           ["PART-1.1-A", "SOL-1.1", "1.1", "A", "1"],
                                           ["PART-1.2-MAIN", "SOL-1.2", "1.2", "MAIN", "3"],
                                           ["PART-2.1-MAIN", "SOL-2.1", "2.1", "MAIN", "1"]],
    "pedagogy_v3/csv/solution_steps.csv": [
        step("STEP-1.1-A-01", "PART-1.1-A", "1.1", "1", "1"),
        step("STEP-1.1-A-02", "PART-1.1-A", "1.1", "2", "2"),
        step("STEP-1.1-A-01", "PART-1.1-A", "1.1", "3", "1"),
        step("STEP-1.2-MAIN-01", "PART-1.2-MAIN", "1.2", "1", "1"),
        step("STEP-1.2-MAIN-02", "PART-1.2-MAIN", "1.2", "2", "2"),
        step("STEP-1.2-MAIN-03", "PART-1.2-MAIN", "1.2", "3", "3"),
        step("STEP-2.1-MAIN-01", "PART-2.1-MAIN", "2.1", "1", "1"),
    ],
    "pedagogy_v3/csv/solution_step_dependencies.csv": [
        ["STEP-1.1-A-01", "STEP-1.1-A-02", "NEXT", "1"],
        ["STEP-1.2-MAIN-01", "STEP-1.2-MAIN-02", "NEXT", "1"],
        ["STEP-1.2-MAIN-02", "STEP-1.2-MAIN-03", "NEXT", "1"],
        ["STEP-1.2-MAIN-03", "STEP-1.2-MAIN-01", "DEPENDS_ON", "0.5"],
        ["STEP-1.2-MAIN-01", "STEP-1.2-MAIN-01", "DEPENDS_ON", "0.5"],
        ["STEP-1.1-A-01", "STEP-9.9-A-01", "NEXT", "1"],
    ],
    "pedagogy_v3/csv/transformations_v3_no_proof.csv": [
        ["1.1-T1", "1.1", "MCQ", "Q1", '["a","b"]', "PENDING_REVIEW", "TRUE", "STEP-1.1-A-01|STEP-1.1-A-02"],
        ["1.1-T1", "1.1", "MCQ", "Q1 again", "not json", "PENDING_REVIEW", "TRUE", ""],
        ["1.1-T2", "1.1", "PROOF", "Prove", "", "PENDING_REVIEW", "FALSE", ""],
        ["1.2-T1", "1.2", "MCQ", "Q", "", "WEIRD", "TRUE", "STEP-1.2-MAIN-09"],
    ],
}


class TextbookPackageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name) / "Fixture_Corpus"
        for rel, header in HEADERS.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle)
                writer.writerow(header)
                writer.writerows(ROWS[rel])
        for asset in ("diagrams/problems/d1.png", "diagrams/solutions/d2.png"):
            (root / asset).parent.mkdir(parents=True, exist_ok=True)
            (root / asset).write_bytes(b"png")
        cls.package = tb.load_package(root)
        cls.plan = tb.build_plan(cls.package)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_manifest_hash_is_stable_and_covers_assets(self):
        again = tb.load_package(self.package.root)
        self.assertEqual(self.package.manifest_hash, again.manifest_hash)
        self.assertIn("diagrams/problems/d1.png", self.package.files)

    def test_duplicate_problem_keeps_numbered_section_row(self):
        self.assertEqual(self.plan.problems["1.2"]["statement_text"], "Prove B.")
        self.assertEqual(self.plan.problems["1.2"]["canonical_code"], "PRASOLOV_PGV1_CH01_P002")
        self.assertIn(("problem", "1.2", "DUPLICATE_PROBLEM_ID"), self.plan.conflicts)

    def test_orphan_solution_rejected_not_fatal(self):
        self.assertNotIn("9.9", self.plan.solutions)
        self.assertIn(("solution", "SOL-9.9", "ORPHAN_SOLUTION"), self.plan.conflicts)

    def test_repeated_part_and_step_ids_get_occurrences(self):
        self.assertIn("PRASOLOV_PGV1/PART-1.1-A#2", self.plan.parts)
        second = self.plan.steps["PRASOLOV_PGV1/STEP-1.1-A-01#2"]
        self.assertEqual(second["part"], "PRASOLOV_PGV1/PART-1.1-A#2")
        self.assertEqual(self.plan.parts["PRASOLOV_PGV1/PART-1.1-A"]["step_count"], 2)
        self.assertEqual(self.plan.parts["PRASOLOV_PGV1/PART-1.1-A#2"]["step_count"], 1)

    def test_dependency_dag_rejects_self_loops_cycles_and_missing_endpoints(self):
        keys = set(self.plan.dependencies)
        main = "PRASOLOV_PGV1/STEP-1.2-MAIN-0"
        self.assertIn((main + "1", main + "2", "NEXT"), keys)
        self.assertNotIn((main + "3", main + "1", "DEPENDS_ON"), keys)
        self.assertFalse(any(a == b for a, b, _ in keys))
        self.assertTrue(any(c[2] == "CYCLE_EDGE_REJECTED" for c in self.plan.conflicts))
        self.assertFalse(tb._has_cycle(list(keys)))

    def test_learning_items_are_review_gated_and_anchor_split(self):
        items = self.plan.learning_items
        self.assertIn("PRASOLOV_PGV1/1.1-T1#2", items)
        self.assertNotIn("PRASOLOV_PGV1/1.1-T2", items)  # no_proof=FALSE rejected
        self.assertEqual(items["PRASOLOV_PGV1/1.2-T1"]["review_status"], "PENDING_REVIEW")
        self.assertIsNone(items["PRASOLOV_PGV1/1.1-T1#2"]["choices"])
        anchors = {k for k in self.plan.anchors if k[0] == "PRASOLOV_PGV1/1.1-T1"}
        self.assertEqual(len(anchors), 2)
        self.assertIn(("learning_item", "PRASOLOV_PGV1/1.2-T1", "MISSING_STEP_ANCHOR"), self.plan.conflicts)

    def test_solution_diagrams_hidden_and_missing_assets_rejected(self):
        diagrams = self.plan.diagrams
        self.assertEqual(diagrams["PRASOLOV_PGV1/D1"]["visibility"], "STUDENT_PROBLEM")
        self.assertEqual(diagrams["PRASOLOV_PGV1/D2"]["visibility"], "SOLUTION_HIDDEN")
        self.assertNotIn("PRASOLOV_PGV1/D3", diagrams)

    def test_chapter_pilot_scope(self):
        pilot = tb.build_plan(self.package, [2])
        self.assertEqual(set(pilot.problems), {"2.1"})
        self.assertEqual(len(pilot.nodes), 5)  # shared taxonomy always imported
        self.assertTrue(all(s["problem"] == "2.1" for s in pilot.steps.values()))
        self.assertEqual(pilot.scope, "chapters:2")


if __name__ == "__main__":
    unittest.main()
