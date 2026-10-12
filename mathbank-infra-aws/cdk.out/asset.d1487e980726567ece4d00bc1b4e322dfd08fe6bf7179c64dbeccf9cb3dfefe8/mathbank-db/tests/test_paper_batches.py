"""Batch completion requires real question splits and classified coverage."""

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

ETL = Path(__file__).resolve().parents[1] / "etl"
sys.path.insert(0, str(ETL))
spec = importlib.util.spec_from_file_location("paper_batches", ETL / "paper_batches.py")
batches = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batches)


def test_question_artifacts_must_match_numbered_index(tmp_path, monkeypatch):
    monkeypatch.setattr(batches, "PDF_CRAWL_DIR", tmp_path)
    source = {"crawl_dir": "hmmt_feb", "paper_external_code": "PAPER_HMMT_2025_FEB_GEO"}
    paper = tmp_path / source["crawl_dir"] / source["paper_external_code"]
    paper.mkdir(parents=True)
    ids = [
        source["paper_external_code"] + "_Q01",
        source["paper_external_code"] + "_Q02",
    ]
    (paper / "index.json").write_text(json.dumps({"questions": ids}))
    for number in (1, 2):
        folder = paper / "questions" / f"Q{number:02d}"
        folder.mkdir(parents=True)
        (folder / "problem.md").write_text("Compute the triangle area.")
    assert batches.question_codes(source) == ids
    (paper / "questions/Q02/problem.md").unlink()
    with pytest.raises(ValueError, match="Missing question"):
        batches.question_codes(source)


@pytest.mark.parametrize(
    "ids", [[], ["PAPER_SMT_2022_GEOM"], ["PAPER_SMT_2022_GEOM_Q02"]]
)
def test_whole_paper_or_incomplete_parse_is_not_completion(tmp_path, monkeypatch, ids):
    monkeypatch.setattr(batches, "PDF_CRAWL_DIR", tmp_path)
    source = {"crawl_dir": "smt", "paper_external_code": "PAPER_SMT_2022_GEOM"}
    paper = tmp_path / "smt/PAPER_SMT_2022_GEOM"
    paper.mkdir(parents=True)
    (paper / "index.json").write_text(json.dumps({"questions": ids}))
    with pytest.raises(ValueError):
        batches.question_codes(source)


def test_classifier_exit_zero_is_not_sufficient(tmp_path, monkeypatch):
    path = tmp_path / "classifications.db"
    monkeypatch.setattr(batches, "SQLITE_DB", path)
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE questions(question_id,classification_status,taxonomy_mapping_count)"
        )
        conn.execute("INSERT INTO questions VALUES('Q1','SOLUTION_REVIEWED',2)")
        conn.execute("INSERT INTO questions VALUES('Q2','PARTIAL',0)")
    batches.verify_classification(["Q1"])
    with pytest.raises(ValueError, match="1 questions"):
        batches.verify_classification(["Q1", "Q2"])


def test_mapping_loader_is_scoped_to_exact_question_ids(monkeypatch):
    import load_corpus

    cur = MagicMock()
    cur.fetchall.side_effect = [[("Q1", "p1"), ("Q2", "p2")], [("area", "c1")]]
    cur.rowcount = 1
    monkeypatch.setattr(
        load_corpus,
        "read_rows",
        lambda filename: [
            {"Question_ID": "Q1", "Concept_ID": "area"},
            {"Question_ID": "Q2", "Concept_ID": "area"},
        ],
    )
    assert load_corpus.load_problem_concepts(cur, {"Q1"}) == (1, 0)
    writes = [
        call for call in cur.execute.call_args_list if "INSERT INTO" in call.args[0]
    ]
    assert len(writes) == 1
    assert writes[0].args[1][0] == "p1"


def test_resume_retains_ingested_but_unpublished_papers(tmp_path):
    run_id = "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
    conn = MagicMock()
    scope = {"papers": ["done", "ingested-not-published"]}
    conn.execute.return_value.fetchone.return_value = (
        scope,
        {"log_dir": str(tmp_path)},
    )
    conn.execute.return_value.__iter__.return_value = iter([("done",)])
    cur = conn.cursor.return_value.__enter__.return_value
    cur.fetchall.return_value = [
        {"paper_external_code": "ingested-not-published", "ingest_status": "INGESTED"}
    ]
    result_id, rows, directory = batches.snapshot(conn, SimpleNamespace(resume=run_id))
    assert result_id == run_id
    assert rows[0]["ingest_status"] == "INGESTED"
    assert directory == tmp_path


def test_resume_can_retry_only_selected_original_papers(tmp_path):
    run_id = "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (
        {"papers": ["first", "retry", "other"]},
        {"log_dir": str(tmp_path)},
    )
    conn.execute.return_value.__iter__.return_value = iter([])
    cur = conn.cursor.return_value.__enter__.return_value
    cur.fetchall.return_value = [{"paper_external_code": "retry"}]
    _, rows, _ = batches.snapshot(conn, SimpleNamespace(resume=run_id, paper=["retry"]))
    assert rows == [{"paper_external_code": "retry"}]
    assert cur.execute.call_args.args[1] == (["retry"],)
    with pytest.raises(ValueError, match="outside the original"):
        batches.snapshot(conn, SimpleNamespace(resume=run_id, paper=["unregistered"]))


def test_neon_batch_connection_uses_direct_host_for_session_locks(monkeypatch):
    import pdf_pipeline
    monkeypatch.setattr(pdf_pipeline, "_load_env", lambda: {
        "NEON_PG_HOST": "ep-test-pooler.us-east-2.aws.neon.tech",
        "NEON_PG_PASSWORD": "fake",
    })
    connect = MagicMock()
    monkeypatch.setattr(pdf_pipeline.psycopg, "connect", connect)
    pdf_pipeline._connect(direct=True)
    assert "host=ep-test.us-east-2.aws.neon.tech " in connect.call_args.args[0]
    pdf_pipeline._connect()
    assert "host=ep-test-pooler.us-east-2.aws.neon.tech " in connect.call_args.args[0]
