"""Offline contract tests for etl/embed_textbook_steps.py (no database, no model calls)."""

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("embed_textbook_steps", ROOT / "mathbank-db/etl/embed_textbook_steps.py")
ets = importlib.util.module_from_spec(spec)
sys.modules["embed_textbook_steps"] = ets
spec.loader.exec_module(ets)


def step(**overrides):
    row = {
        "solution_step_id": "STEP-1", "solution_part_id": "PART-1", "solution_id": "sol-uuid",
        "problem_id": "prob-uuid", "global_step_index": 1, "step_index_in_part": 1,
        "step_text": "Triangles ABC and ADE are similar.", "step_type": "SIMILARITY_RELATION",
        "tutor_role": "KEY_STEP", "concept_node_id": "CONCEPT.1", "subconcept_node_id": "SUB.1",
        "skill_node_id": "SKILL.1", "skill_name": "Recognise similar triangles", "hint_level": 2,
        "is_checkpoint": True, "publication_status": "PUBLISHED", "book_code": "PRASOLOV",
        "chapter_number": 1, "section_number": "1.1", "section_title": "Similar triangles",
        "subconcept_name": "Similarity", "technique_slugs": ["angle-chasing"],
    }
    row.update(overrides)
    return row


def item(**overrides):
    row = {
        "learning_item_id": "LI-1", "source_problem_id": "prob-uuid", "transformed_form": "MCQ",
        "transformation_type": "MCQ_FIRST_MOVE", "target_concept_node_id": "CONCEPT.1",
        "target_subconcept_node_id": "SUB.1", "target_skill_node_id": "SKILL.1",
        "difficulty_direction": "LOWER", "question_text": "Which pair of triangles is similar?",
        "no_proof": True, "review_status": "APPROVED", "student_visible": True,
        "diagram_strategy": "REUSE_SOURCE", "book_code": "PRASOLOV", "skill_name": "Recognise similar triangles",
        "subconcept_name": "Similarity", "anchor_step_id": "STEP-1", "chapter_number": 1, "section_number": "1.1",
    }
    row.update(overrides)
    return row


class SurrogateIdTests(unittest.TestCase):
    def test_surrogate_is_deterministic_and_type_scoped(self):
        self.assertEqual(ets.surrogate_id("SOLUTION_STEP", "X"), ets.surrogate_id("SOLUTION_STEP", "X"))
        self.assertNotEqual(ets.surrogate_id("SOLUTION_STEP", "X"), ets.surrogate_id("LEARNING_ITEM", "X"))


class StepRowTests(unittest.TestCase):
    def test_step_row_carries_canonical_filter_metadata(self):
        (row,) = ets.step_rows([step()])
        self.assertEqual(row.kind, "SOLUTION_STEP")
        self.assertEqual((row.skill_node_id, row.subconcept_node_id, row.concept_node_id),
                         ("SKILL.1", "SUB.1", "CONCEPT.1"))
        for key in ("problem_id", "solution_id", "solution_part_id", "solution_step_id", "concept_id",
                    "subconcept_id", "skill_id", "technique_ids", "step_type", "tutor_role", "hint_level",
                    "is_checkpoint", "source_book", "chapter", "section", "publication_status"):
            self.assertIn(key, row.metadata)
        self.assertEqual(row.metadata["technique_ids"], ["angle-chasing"])
        self.assertTrue(row.rendered_text.startswith("[Solution step] Recognise similar triangles"))

    def test_metadata_change_keeps_content_hash(self):
        (a,) = ets.step_rows([step()])
        (b,) = ets.step_rows([step(hint_level=3)])
        self.assertEqual(a.content_hash, b.content_hash)
        self.assertNotEqual(a.metadata, b.metadata)


class LearningItemRowTests(unittest.TestCase):
    def test_published_item_yields_question_and_signature(self):
        rows = ets.item_rows([item()])
        self.assertEqual({r.kind for r in rows}, {"LEARNING_ITEM_QUESTION", "LEARNING_ITEM_SKILL_SIGNATURE"})
        for r in rows:
            self.assertEqual(r.learning_item_id, "LI-1")
            self.assertTrue(r.metadata["no_proof"])
            self.assertEqual(r.metadata["publication_status"], "PUBLISHED")
            self.assertEqual(r.metadata["solution_step_anchor_id"], "STEP-1")

    def test_unpublished_items_are_never_staged(self):
        for override in ({"review_status": "PENDING_REVIEW", "student_visible": False},
                         {"student_visible": False}, {"no_proof": False}):
            self.assertEqual(ets.item_rows([item(**override)]), [], override)


def node(node_id, node_type, name, parent=None, chapter=None, section=None, description=""):
    return {"taxonomy_node_id": node_id, "node_type": node_type, "name": name, "parent_node_id": parent,
            "chapter_number": chapter, "section_number": section, "description": description,
            "concept_id": None, "skill_id": None, "technique_id": None, "book_code": "PRASOLOV_PGV1"}


TAXONOMY = [
    node("GEO", "DOMAIN", "Geometry", description="Plane geometry domain."),
    node("GEO.C03", "CONCEPT", "Circles", parent="GEO", chapter=3),
    node("GEO.C03.S04", "SUBCONCEPT", "Power of a point", parent="GEO.C03", chapter=3, section="4",
         description="Method/subtopic from Chapter 3."),
    node("SKILL.POWER", "SKILL", "Apply power of a point", description="Skill from existing enrichment."),
    node("TECH.SIM", "TECHNIQUE", "Similar triangles", description="Technique from existing enrichment."),
]
EDGES = [
    {"from_node_id": "GEO.C03", "to_node_id": "GEO", "relationship_type": "PART_OF"},
    {"from_node_id": "GEO.C03.S04", "to_node_id": "GEO.C03", "relationship_type": "PART_OF"},
    {"from_node_id": "SKILL.POWER", "to_node_id": "GEO.C03.S04", "relationship_type": "PART_OF"},
    {"from_node_id": "TECH.SIM", "to_node_id": "GEO.C03.S04", "relationship_type": "SUPPORTS"},
]


class TaxonomyRowTests(unittest.TestCase):
    def rows(self):
        return {r.entity_id: r for r in ets.taxonomy_rows(TAXONOMY, EDGES)}

    def test_every_node_is_staged_once_with_taxonomy_identity(self):
        rows = self.rows()
        self.assertEqual(set(rows), {n["taxonomy_node_id"] for n in TAXONOMY})
        for node_id, r in rows.items():
            self.assertEqual((r.kind, r.entity_type), ("TAXONOMY_NODE", "TAXONOMY_NODE"))
            self.assertIsNone(r.problem_id)
            self.assertEqual(r.metadata["taxonomy_node_id"], node_id)
            self.assertEqual(r.source_entity_id, ets.surrogate_id("TAXONOMY_NODE", node_id))

    def test_subconcept_text_has_path_neighbours_and_no_boilerplate(self):
        text = self.rows()["GEO.C03.S04"].rendered_text
        self.assertTrue(text.startswith("[Taxonomy subconcept] Power of a point"))
        self.assertIn("Within: Geometry > Circles", text)
        self.assertIn("Chapter 3, section 4", text)
        self.assertIn("Skills: Apply power of a point", text)
        self.assertIn("Techniques: Similar triangles", text)
        self.assertNotIn("Method/subtopic", text)
        self.assertIn("Plane geometry domain.", self.rows()["GEO"].rendered_text)

    def test_all_imported_provenance_descriptions_are_dropped(self):
        for text in ("Skill from existing enrichment.", "Technique from existing enrichment.",
                     "Method/subtopic from Chapter 12.", "Canonical concept for Prasolov Chapter 3.",
                     "Canonical geometry domain.", "Skill inferred from ordered solution steps."):
            self.assertRegex(text, ets.BOILERPLATE_DESCRIPTION)
        self.assertNotRegex("Plane geometry domain.", ets.BOILERPLATE_DESCRIPTION)

    def test_skill_and_technique_list_where_they_are_used(self):
        rows = self.rows()
        self.assertIn("Used in: Power of a point", rows["SKILL.POWER"].rendered_text)
        self.assertIn("Supports: Power of a point", rows["TECH.SIM"].rendered_text)
        self.assertEqual(rows["GEO.C03"].rendered_text.count("Power of a point"), 1)

    def test_hard_filter_columns_follow_node_type(self):
        rows = self.rows()
        self.assertEqual((rows["GEO.C03"].concept_node_id, rows["GEO.C03"].subconcept_node_id), ("GEO.C03", None))
        sub = rows["GEO.C03.S04"]
        self.assertEqual((sub.concept_node_id, sub.subconcept_node_id, sub.skill_node_id),
                         ("GEO.C03", "GEO.C03.S04", None))
        self.assertEqual(rows["SKILL.POWER"].skill_node_id, "SKILL.POWER")
        tech = rows["TECH.SIM"]
        self.assertEqual((tech.concept_node_id, tech.subconcept_node_id, tech.skill_node_id), (None, None, None))
        self.assertEqual(tech.metadata["related_node_ids"], ["GEO.C03.S04"])

    def test_rendering_is_deterministic_and_neighbours_are_capped(self):
        many = TAXONOMY + [node(f"SKILL.{i:02d}", "SKILL", f"Skill {i:02d}") for i in range(20)]
        edges = EDGES + [{"from_node_id": f"SKILL.{i:02d}", "to_node_id": "GEO.C03.S04",
                          "relationship_type": "PART_OF"} for i in range(20)]
        first = {r.entity_id: r.content_hash for r in ets.taxonomy_rows(many, edges)}
        second = {r.entity_id: r.content_hash for r in ets.taxonomy_rows(list(reversed(many)), list(reversed(edges)))}
        self.assertEqual(first, second)
        text = {r.entity_id: r for r in ets.taxonomy_rows(many, edges)}["GEO.C03.S04"].rendered_text
        self.assertIn("and 6 more", text)

    def test_parent_cycles_do_not_loop(self):
        cyc = [node("A", "CONCEPT", "A", parent="B"), node("B", "CONCEPT", "B", parent="A")]
        self.assertEqual(len(ets.taxonomy_rows(cyc, [])), 2)


if __name__ == "__main__":
    unittest.main()
