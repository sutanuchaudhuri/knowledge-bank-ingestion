"""ARML offline contracts; no network, classification, or paid model calls."""
import json
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "etl"))
import arml_archive as archive
import arml_queue as queue
import embed_corpus as embed


class DependencyTests(unittest.TestCase):
    def connection(self, status="COMPLETED", failed=0, completed=2, items=None, missing_vectors=0):
        papers = ["PAPER_PURPLE_2026_MS", "PAPER_PURPLE_2026_HS"]
        row = ("PAPER_BATCH", status, 2, completed, failed, {"papers": papers})
        items = items if items is not None else [
            (p, "COMPLETED", {"graph_verified": True, "classification_status": "COMPLETED"}) for p in papers]
        conn = MagicMock()
        conn.execute.side_effect = [
            MagicMock(fetchone=lambda: row), [(p,) for p in papers],
            MagicMock(fetchall=lambda: items), MagicMock(fetchone=lambda: (0,)),
            MagicMock(fetchone=lambda: (missing_vectors,))]
        return conn

    def test_complete_dependency(self):
        self.assertTrue(queue.dependency_ready(self.connection(), "run"))

    def test_purple_without_complete_scoped_vectors_never_releases(self):
        self.assertFalse(queue.dependency_ready(self.connection(missing_vectors=1), "run"))

    def test_failed_and_incomplete_never_release(self):
        for status, failed, completed in [("FAILED", 0, 2), ("IN_PROGRESS", 0, 2),
                                         ("COMPLETED", 1, 2), ("COMPLETED", 0, 1)]:
            self.assertFalse(queue.dependency_ready(self.connection(status, failed, completed), "run"))

    def test_unverified_graph_never_releases(self):
        self.assertFalse(queue.dependency_ready(self.connection(items=[
            ("PAPER_PURPLE_2026_MS", "COMPLETED", {"graph_verified": False}),
            ("PAPER_PURPLE_2026_HS", "COMPLETED", {"graph_verified": True})]), "run"))

    def test_subset_pilot_never_releases(self):
        conn = self.connection()
        conn.execute.side_effect = [
            MagicMock(fetchone=lambda: ("PAPER_BATCH", "COMPLETED", 1, 1, 0,
                                       {"papers": ["PAPER_PURPLE_2026_MS"]})),
            [("PAPER_PURPLE_2026_MS",), ("PAPER_PURPLE_2026_HS",)]]
        self.assertFalse(queue.dependency_ready(conn, "run"))

    def test_non_purple_dependency_rejected(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = (
            "PAPER_BATCH", "COMPLETED", 1, 1, 0, {"papers": ["PAPER_SMT_2026_TEAM"]})
        with self.assertRaises(ValueError):
            queue.dependency_ready(conn, "run")

    def test_waiting_queue_cannot_download_or_execute_paid_stages(self):
        conn = MagicMock()
        with patch.object(queue, "dependency_ready", return_value=False), \
             patch.object(queue.time, "sleep", side_effect=InterruptedError("stop waiting")), \
             patch.object(queue, "download") as download, \
             patch.object(queue, "command") as command, \
             patch.object(queue, "import_and_classify") as classify:
            with self.assertRaises(InterruptedError):
                queue.run(conn, "arml-run", "purple-run", 60)
        download.assert_not_called()
        command.assert_not_called()
        classify.assert_not_called()
        self.assertIn("status='QUEUED'", conn.execute.call_args_list[0].args[0])


class VectorScopeTests(unittest.TestCase):
    def test_exact_paper_scope_on_problems_and_solutions(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        embed.build_representations_and_chunks(cur, "profile", None, ["PAPER_ARML_2015_TEAM"])
        calls = cur.execute.call_args_list
        self.assertEqual(len(calls), 2)
        for call in calls:
            self.assertIn("external_code=ANY(%s)", call.args[0])
            self.assertEqual(call.args[1], [["PAPER_ARML_2015_TEAM"]])

    def test_unscoped_backfill_preserved(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        embed.build_representations_and_chunks(cur, "profile", None)
        self.assertTrue(all("external_code=ANY" not in call.args[0] for call in cur.execute.call_args_list))

    def test_pending_scope_and_provider_failure_are_durable(self):
        cur, conn = MagicMock(), MagicMock()
        cur.fetchone.return_value = ["run"]
        cur.fetchall.return_value = [("chunk", "text", "hash", "representation")]
        with patch.object(embed, "OpenAI") as client:
            client.return_value.embeddings.create.side_effect = RuntimeError("provider unavailable")
            self.assertEqual(embed.embed_pending_chunks(cur, conn, "model", None, ["PAPER_ARML_2015_TEAM"]), (0, 1))
        selection = cur.execute.call_args_list[1]
        self.assertIn("r.status='ACTIVE'", selection.args[0])
        self.assertIn("e.status='ACTIVE'", selection.args[0])
        self.assertEqual(selection.args[1], ["model", ["PAPER_ARML_2015_TEAM"], ["PAPER_ARML_2015_TEAM"]])
        self.assertEqual(cur.execute.call_args_list[-1].args[1][0], "FAILED")

    def test_incomplete_provider_response_fails_explicitly(self):
        cur, conn = MagicMock(), MagicMock()
        cur.fetchone.return_value = ["run"]
        cur.fetchall.return_value = [("chunk", "text", "hash", "representation")]
        with patch.object(embed, "OpenAI") as client:
            client.return_value.embeddings.create.return_value.data = []
            with self.assertRaisesRegex(RuntimeError, "incomplete"):
                embed.embed_pending_chunks(cur, conn, "model", None, ["PAPER_ARML_2015_TEAM"])


class LayoutTests(unittest.TestCase):
    def test_missing_toc_fails(self):
        doc = MagicMock()
        doc.get_toc.return_value = []
        with self.assertRaises(ValueError):
            archive.plan(doc)

    def test_power_context_and_local_included(self):
        doc = MagicMock()
        doc.__len__.return_value = 20
        doc.get_toc.return_value = [
            [1, "I ARML Contests", 1], [2, "2015 Contest", 2],
            [3, "Team Problems and Solutions", 3],
            [1, "II ARML Local Contests", 6], [2, "ARML Local 2015", 7],
            [3, "Team Problems and Solutions", 8],
            [1, "III ARML Power Contests", 11], [2, "February 2015 (Test)", 12],
            [3, "Problems", 13], [3, "Solutions", 17]]
        result = archive.plan(doc)
        self.assertEqual({r["competition_external_code"] for r in result}, {"ARML", "ARML_LOCAL", "ARML_POWER"})
        self.assertEqual(result[-1]["start"], 12)
        self.assertTrue(result[-1]["contextual"])
        self.assertTrue(all(re.fullmatch(r"PAPER_[A-Z]+_\d{4}_.+", r["paper_external_code"])
                            for r in result))
        self.assertEqual(result[1]["paper_external_code"], "PAPER_ARML_2015_LOCAL_TEAM")
        self.assertEqual(result[2]["paper_external_code"], "PAPER_ARML_2015_POWER_FEBRUARY")


if __name__ == "__main__":
    unittest.main()
