import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/crawl_unmapped.py"
spec = importlib.util.spec_from_file_location("crawl_missing_text", SCRIPT)
crawler = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = crawler
spec.loader.exec_module(crawler)


def staging():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE questions(question_id TEXT PRIMARY KEY,exam_level TEXT,
          aops_question_url TEXT,problem_text_latex TEXT,problem_text_raw TEXT,
          solution_text_latex TEXT,all_solutions_json TEXT,answer_value TEXT,
          parse_warnings TEXT,classification_status TEXT);
        CREATE TABLE unmapped_questions(question_id TEXT PRIMARY KEY,exam_level TEXT,
          problem_url TEXT,mapping_status TEXT);
    """)
    return conn


def test_missing_text_queue_includes_concept_mapped_questions_not_in_unmapped_table():
    conn = staging()
    conn.execute("""INSERT INTO questions(question_id,exam_level,aops_question_url,
                   classification_status) VALUES ('AIME_1983_Q03','AIME','https://example.test',
                                                'FINE_CONCEPT_MAPPED')""")
    assert crawler._fetch_queue(conn, 10, "AIME", False, missing_text=True) == [
        ("AIME_1983_Q03", "AIME", "https://example.test")
    ]
    assert crawler._fetch_queue(conn, 10, "AIME", False) == []


def test_missing_queue_excludes_existing_text_and_absent_urls():
    conn = staging()
    conn.execute(
        "INSERT INTO questions VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("good", "AIME", "https://example.test", "Find x.", None, None, None, None, None, "MAPPED"),
    )
    conn.execute("INSERT INTO questions(question_id,exam_level) VALUES ('no-url','AIME')")
    conn.execute(
        "INSERT INTO questions(question_id,exam_level,aops_question_url,problem_text_latex,"
        "problem_text_raw) VALUES ('raw-only','AIME','https://example.test','','Find x.')"
    )
    assert crawler._fetch_queue(conn, 10, None, False, missing_text=True) == []


def test_placeholder_text_is_recoverable_and_existing_content_is_preserved():
    conn = staging()
    conn.execute(
        "INSERT INTO questions VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            "Q",
            "AIME",
            "https://example.test",
            " [Placeholder] Q",
            None,
            "Reviewed solution",
            '["Reviewed solution"]',
            "5",
            None,
            "MAPPED",
        ),
    )
    assert len(crawler._fetch_queue(conn, 10, None, False, missing_text=True)) == 1
    crawler._persist_question_text(
        conn,
        "Q",
        {"problem_text": "Find x.", "solution_texts": ["Other solution"], "answer_value": "2"},
    )
    assert conn.execute(
        "SELECT problem_text_latex,solution_text_latex,all_solutions_json,answer_value,"
        "classification_status FROM questions"
    ).fetchone() == ("Find x.", "Reviewed solution", '["Reviewed solution"]', "5", "MAPPED")


def test_empty_cached_parse_is_not_a_successful_crawl(tmp_path, monkeypatch):
    monkeypatch.setattr(crawler, "CRAWL_DIR", tmp_path)
    folder = tmp_path / "aime/AIME_1985_Q09"
    folder.mkdir(parents=True)
    path = folder / "parsed.json"
    path.write_text(json.dumps({"problem_text": ""}))
    assert not crawler._already_crawled(folder.name, "AIME")
    path.write_text(json.dumps({"problem_text": "Find x."}))
    assert crawler._already_crawled(folder.name, "AIME")


def test_missing_text_repair_does_not_requeue_mapping_work():
    conn = staging()
    conn.execute("ALTER TABLE unmapped_questions ADD COLUMN next_action TEXT")
    conn.execute("ALTER TABLE unmapped_questions ADD COLUMN notes TEXT")
    conn.execute(
        "INSERT INTO unmapped_questions VALUES ('Q','AIME','https://example.test','MAPPED','DONE','Reviewed')"
    )
    crawler._update_db(conn, "Q", "CRAWLED", preserve_mapping=True)
    crawler._update_db(conn, "Q", "FAILED", error="blocked", preserve_mapping=True)
    assert conn.execute(
        "SELECT mapping_status,next_action,notes FROM unmapped_questions"
    ).fetchone() == ("MAPPED", "DONE", "Reviewed")
    crawler._update_db(conn, "Q", "CRAWLED")
    assert conn.execute("SELECT mapping_status,next_action FROM unmapped_questions").fetchone() == (
        "CRAWLED",
        "CLASSIFY",
    )


def test_repaired_artifacts_preserve_question_figure_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(crawler, "CRAWL_DIR", tmp_path)
    folder = tmp_path / "aime/Q"
    folder.mkdir(parents=True)
    (folder / "parsed.json").write_text(
        json.dumps({"question_id": "Q", "problem_text": "", "problem_images": ["crop.png"]})
    )
    parsed = crawler.parse_aops_page(
        '<div class="mw-parser-output"><h2>Problem</h2><p>Find x.</p></div>',
        "Q",
        "https://example.test/Q",
    )
    crawler._save_artifacts(parsed, "AIME")
    record = json.loads((folder / "parsed.json").read_text())
    assert record["problem_text"] == "Find x."
    assert record["problem_images"] == ["crop.png"]


def test_text_persistence_does_not_require_classification_or_change_existing_mapping():
    conn = staging()
    conn.execute("INSERT INTO questions(question_id,classification_status) VALUES ('Q','MAPPED')")
    crawler._persist_question_text(
        conn,
        "Q",
        {
            "problem_text": "Find $x$.",
            "solution_texts": ["Then $x=2$."],
            "answer_value": "2",
        },
    )
    assert conn.execute(
        "SELECT problem_text_latex,solution_text_latex,classification_status FROM questions"
    ).fetchone() == ("Find $x$.", "Then $x=2$.", "MAPPED")
    with pytest.raises(ValueError, match="empty"):
        crawler._persist_question_text(conn, "Q", {"problem_text": ""})
