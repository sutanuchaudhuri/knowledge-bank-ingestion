"""Synthetic contract fixtures only; never connect to a database."""

import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


author = load_module("pedagogy_author", ROOT / "mathbank-db/etl/import_pedagogy.py")
graph = load_module("pedagogy_graph", ROOT / "mathbank-graph/etl/project_from_postgres.py")
PROVENANCE = {"source": "unit-test", "confidence": 0.8, "review_status": "REVIEWED"}


def skill(slug):
    return dict(slug=slug, name=slug, objective="fixture objective", **PROVENANCE)


def edge(start, end, kind="PREREQUISITE_OF", status="REVIEWED"):
    return dict(
        from_skill_slug=start,
        to_skill_slug=end,
        relation_type=kind,
        **{**PROVENANCE, "review_status": status},
    )


class Cursor:
    def __init__(self, existing=(), concepts=()):
        self.calls = []
        self.existing = existing
        self.concepts = concepts
        self.last = ""

    def execute(self, query, parameters=None):
        self.calls.append((query, parameters))
        self.last = query

    def fetchone(self):
        return ("fixture-uuid",)

    def fetchall(self):
        if "FROM knowledge.skill_relation r" in self.last:
            return self.existing
        if "FROM knowledge.concept_relation r" in self.last:
            return self.concepts
        if "SELECT slug, skill_id" in self.last:
            return [("a", "a-id"), ("b", "b-id")]
        if "SELECT slug, concept_id" in self.last:
            return [("concept-fixture", "c-id")]
        if "SELECT canonical_code" in self.last:
            return [("problem-fixture", "p-id")]
        return []


class AuthoringTests(unittest.TestCase):
    def test_complete_manifest_and_nullable_fields(self):
        result = author.validate_manifest(
            {
                "version": 1,
                "skills": [{**skill("a"), "level": None}],
                "skill_concepts": [
                    dict(skill_slug="a", concept_slug="concept-fixture", **PROVENANCE)
                ],
                "skill_relations": [edge("a", "b")],
                "problem_skills": [
                    dict(
                        problem_code="problem-fixture",
                        skill_slug="a",
                        relation_type="REQUIRES",
                        role="primary",
                        importance=0,
                        required_level=5,
                        **PROVENANCE,
                    )
                ],
                "problem_pedagogy": [
                    dict(
                        problem_code="problem-fixture",
                        conceptual_depth=1,
                        number_of_steps=0,
                        **PROVENANCE,
                    )
                ],
            }
        )
        self.assertEqual(len(result["problem_skills"]), 1)
        author.resolve_manifest(Cursor(), result)

    def test_invalid_shapes_and_numbers(self):
        for document in [
            [],
            {"version": True},
            {"version": 2},
            {"version": 1, "typo": []},
            {"version": 1, "skills": {}},
            {"version": 1, "skills": [None]},
        ]:
            with self.subTest(document=document), self.assertRaises(author.ManifestError):
                author.validate_manifest(document)
        for field, values in {
            "confidence": [-0.01, 1.01, True, float("nan"), float("inf"), "0.5"],
            "level": [0, 6, 1.5, True],
            "source": ["", " ", " padded "],
            "review_status": ["reviewed", "APPROVED"],
            "objective": [None, ""],
        }.items():
            for value in values:
                with (
                    self.subTest(field=field, value=value),
                    self.assertRaises(author.ManifestError),
                ):
                    author.validate_manifest(
                        {"version": 1, "skills": [{**skill("a"), field: value}]}
                    )

    def test_duplicate_unknown_fields_relation_and_role(self):
        for rows in [[skill("a"), skill("a")], [{**skill("a"), "unexpected": True}]]:
            with self.assertRaises(author.ManifestError):
                author.validate_manifest({"version": 1, "skills": rows})
        for row in [edge("a", "a"), edge("a", "b", "UNKNOWN")]:
            with self.assertRaises(author.ManifestError):
                author.validate_manifest({"version": 1, "skill_relations": [row]})
        with self.assertRaises(author.ManifestError):
            author.validate_manifest(
                {
                    "version": 1,
                    "problem_skills": [
                        dict(
                            problem_code="p",
                            skill_slug="a",
                            relation_type="REQUIRES",
                            role="PRIMARY",
                            importance=0.5,
                            **PROVENANCE,
                        )
                    ],
                }
            )

    def test_reviewed_cycles_only_and_deep_nonrecursive_dag(self):
        for kind in ["PART_OF", "PREREQUISITE_OF"]:
            with self.assertRaises(author.ManifestError):
                author.validate_cycles([edge("a", "b", kind), edge("b", "a", kind)], [])
            author.validate_cycles([edge("a", "b", kind), edge("b", "a", kind, "PENDING")], [])
        author.assert_acyclic([(str(i), str(i + 1)) for i in range(3000)], "fixture")

    def test_existing_cycles_and_pending_downgrade(self):
        cur = Cursor(existing=[("a", "b", "PREREQUISITE_OF", "REVIEWED")])
        with self.assertRaises(author.ManifestError):
            author.resolve_manifest(
                cur, author.validate_manifest({"version": 1, "skill_relations": [edge("b", "a")]})
            )
        author.resolve_manifest(
            cur,
            author.validate_manifest(
                {
                    "version": 1,
                    "skill_relations": [edge("a", "b", status="REJECTED"), edge("b", "a")],
                }
            ),
        )
        with self.assertRaises(author.ManifestError):
            author.resolve_manifest(
                Cursor(
                    concepts=[
                        ("x", "y", "HAS_SUBCONCEPT", "REVIEWED"),
                        ("x", "y", "PART_OF", "REVIEWED"),
                    ]
                ),
                author.validate_manifest({"version": 1}),
            )

    def test_missing_fk_and_schema(self):
        with self.assertRaisesRegex(author.ManifestError, "unknown concept_slug"):
            author.resolve_manifest(
                Cursor(),
                author.validate_manifest(
                    {
                        "version": 1,
                        "skill_concepts": [
                            dict(skill_slug="a", concept_slug="missing", **PROVENANCE)
                        ],
                    }
                ),
            )
        cur = MagicMock()
        cur.fetchone.return_value = (None,)
        with self.assertRaisesRegex(author.ManifestError, "006_pedagogy"):
            author.require_schema(cur)

    def test_upserts_use_fixed_sql_bound_values_and_natural_keys(self):
        manifest = author.validate_manifest(
            {
                "version": 1,
                "skills": [skill("new-fixture")],
                "problem_skills": [
                    dict(
                        problem_code="problem-fixture",
                        skill_slug="new-fixture",
                        relation_type="TESTS",
                        role="supporting",
                        importance=1,
                        **PROVENANCE,
                    )
                ],
            }
        )
        cur = Cursor()
        author.import_manifest(cur, manifest)
        inserts = [(sql, params) for sql, params in cur.calls if sql.startswith("INSERT")]
        self.assertEqual(len(inserts), 2)
        self.assertIn("ON CONFLICT (slug)", inserts[0][0])
        self.assertIn("RETURNING skill_id", inserts[0][0])
        self.assertIn("ON CONFLICT (problem_id, skill_id, relation_type, role)", inserts[1][0])
        self.assertEqual(inserts[1][1][:2], ["p-id", "fixture-uuid"])
        self.assertNotIn("new-fixture", inserts[0][0])
        self.assertTrue(cur.calls[0][0].startswith("LOCK TABLE"))

    def test_dry_run_read_only_and_offline_no_connection(self):
        manifest = json.dumps({"version": 1})
        for command, expected in [("validate", False), ("import", True)]:
            with (
                patch.object(author.Path, "read_text", return_value=manifest),
                patch.object(author, "connection_options", return_value={}),
                patch.object(author.psycopg, "connect") as connect,
                patch("sys.argv", ["import_pedagogy.py", command, "fixture.json", "--dry-run"]),
            ):
                cur = Cursor()
                connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = cur
                author.main()
                self.assertEqual(connect.called, expected)
                if expected:
                    self.assertIn("READ ONLY", cur.calls[0][0])
                    self.assertFalse(
                        any(
                            sql.startswith(("INSERT", "LOCK", "UPDATE", "DELETE"))
                            for sql, _ in cur.calls
                        )
                    )

    def test_invalid_import_never_upserts(self):
        cur = Cursor()
        with self.assertRaises(author.ManifestError):
            author.import_manifest(
                cur,
                author.validate_manifest(
                    {
                        "version": 1,
                        "skill_concepts": [
                            dict(skill_slug="a", concept_slug="missing", **PROVENANCE)
                        ],
                    }
                ),
            )
        self.assertFalse(any(sql.startswith("INSERT") for sql, _ in cur.calls))


class ProjectionTests(unittest.TestCase):
    def test_named_database_is_used_consistently(self):
        driver = MagicMock()
        target = graph.GraphTarget(driver, "fixture-database")
        graph.ensure_constraints(target, True)
        driver.session.assert_called_once_with(database="fixture-database")
        target.close()
        driver.close.assert_called_once()

    def test_missing_graph_targets_fail_instead_of_skipping_metadata(self):
        driver = MagicMock()
        tx = MagicMock()
        tx.run.return_value.single.return_value = {"written": 0}
        driver.session.return_value.__enter__.return_value.execute_write.side_effect = (
            lambda operation: operation(tx)
        )
        with (
            patch.object(
                graph,
                "_dict_rows",
                side_effect=lambda cur, query, columns: (
                    [{"skill_id": "missing-graph-target"}]
                    if query.endswith("FROM knowledge.skill")
                    else []
                ),
            ),
            self.assertRaisesRegex(RuntimeError, "missing or duplicate canonical"),
        ):
            graph.project_pedagogy(driver, Cursor())

    def test_explicit_whitelist_and_hierarchy_direction(self):
        self.assertEqual(
            graph.semantic_relation("HAS_SUBCONCEPT", "parent", "child"),
            ("PART_OF", "child", "parent"),
        )
        self.assertEqual(
            graph.semantic_relation("PREREQUISITE_OF", "prior", "dependent"),
            ("PREREQUISITE_OF", "prior", "dependent"),
        )
        for kind in ["RELATED_TO", "prerequisite_of", "HAS_CHILD", "x` malicious"]:
            self.assertIsNone(graph.semantic_relation(kind, "a", "b"))

    def test_pedagogy_constraint_is_opt_in(self):
        driver = MagicMock()
        graph.ensure_constraints(driver)
        session = driver.session.return_value.__enter__.return_value
        self.assertFalse(any("Skill" in call.args[0] for call in session.run.call_args_list))
        graph.ensure_constraints(driver, True)
        self.assertIn("Skill", session.run.call_args_list[-1].args[0])

    def test_existing_edges_keep_provenance(self):
        driver = MagicMock()
        for func in [
            graph.project_problem_concept,
            graph.project_problem_technique,
            graph.project_concept_relation,
        ]:
            cur = MagicMock()
            cur.fetchall.return_value = [("a", "b", "PRIMARY", 0.9, "fixture-source", "REVIEWED")]
            func(driver, cur)
            call = driver.session.return_value.__enter__.return_value.run.call_args
            self.assertEqual(call.kwargs["rows"][0]["source"], "fixture-source")
            self.assertIn("r.review_status = row.review_status", call.args[0])

    def test_skill_uuid_merge_and_reviewed_projection(self):
        driver = MagicMock()
        session = driver.session.return_value.__enter__.return_value
        tx = MagicMock()
        tx.run.side_effect = lambda query, **params: MagicMock(
            **{"single.return_value": {"written": len(params.get("rows", []))}}
        )
        session.execute_write.side_effect = lambda fn: fn(tx)

        def rows(cur, query, columns):
            if (
                "FROM knowledge.skill" in query
                and "relation" not in query
                and "concept" not in query
            ):
                return [
                    dict(
                        zip(
                            columns,
                            [
                                "db-uuid",
                                "fixture",
                                "Fixture",
                                "Objective",
                                3,
                                "unit-test",
                                1,
                                "REVIEWED",
                            ],
                        )
                    )
                ]
            return []

        with patch.object(graph, "_dict_rows", side_effect=rows):
            self.assertEqual(graph.project_pedagogy(driver, Cursor()), (1, 0))
        calls = tx.run.call_args_list
        node_query = next(c.args[0] for c in calls if "MERGE (s:Skill" in c.args[0])
        self.assertIn("canonical_id: row.skill_id", node_query)
        self.assertIn("s.review_status", node_query)
        self.assertTrue(any("DELETE r" in c.args[0] for c in calls))
        self.assertEqual(session.execute_write.call_count, 1)

    def test_missing_schema_does_not_swallow_errors(self):
        cur = MagicMock()
        cur.fetchone.return_value = (None,)
        with self.assertRaisesRegex(RuntimeError, "--pedagogy.*006_pedagogy"):
            graph.require_pedagogy_schema(cur)
        cur.execute.side_effect = RuntimeError("connection failure")
        with self.assertRaisesRegex(RuntimeError, "connection failure"):
            graph.require_pedagogy_schema(cur)


if __name__ == "__main__":
    unittest.main()
