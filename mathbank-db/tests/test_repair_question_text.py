import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "etl"))
from repair_question_text import (
    apply_record,
    local_record,
    missing_text,
    validate_source_bundle,
)


def test_source_bundle_validates_every_entry_before_any_write():
    url = "https://example.test/Q"
    entry = {
        "url": url,
        "status": 200,
        "html": '<div class="mw-parser-output"><h2>Problem</h2><p>Find x.</p></div>',
    }
    assert validate_source_bundle({"Q": entry}, {"Q": url})["Q"].has_problem
    with pytest.raises(ValueError, match="outside the selected scope"):
        validate_source_bundle({"OTHER": entry}, {"Q": url})
    with pytest.raises(ValueError, match="URL/status"):
        validate_source_bundle({"Q": {**entry, "status": 429}}, {"Q": url})
    with pytest.raises(ValueError, match="URL/status"):
        validate_source_bundle({"Q": entry}, {"Q": "https://example.test/OTHER"})
    with pytest.raises(ValueError, match="no problem statement"):
        validate_source_bundle({"Q": {**entry, "html": "<p>Blocked</p>"}}, {"Q": url})


def test_repair_preserves_existing_staging_solution():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE questions(question_id TEXT,solution_text_latex TEXT,all_solutions_json TEXT)"
    )
    conn.execute(
        "INSERT INTO questions VALUES ('Q','Reviewed solution','[\"Reviewed solution\"]')"
    )
    apply_record(
        MagicMock(),
        conn,
        "pid",
        "Q",
        "Known statement",
        {"solution_texts": ["New source solution"]},
        write=True,
    )
    assert conn.execute(
        "SELECT solution_text_latex,all_solutions_json FROM questions"
    ).fetchone() == (
        "Reviewed solution",
        '["Reviewed solution"]',
    )


def test_missing_text_never_rejects_short_real_math():
    assert (
        missing_text(None) and missing_text(" ") and missing_text("[Placeholder] AIME")
    )
    assert not missing_text("Find $x$.")


def test_corrupt_cached_html_does_not_become_a_statement(tmp_path):
    (tmp_path / "parsed.json").write_text(
        json.dumps({"problem_text": "", "question_id": "Q"})
    )
    (tmp_path / "problem.html").write_text("\ufffd compressed bytes")
    assert local_record(tmp_path, "Q", "https://example.test")["problem_text"] == ""


def test_reparse_uses_explicit_problem_section_and_preserves_diagram_manifest_fields(
    tmp_path,
):
    (tmp_path / "parsed.json").write_text(
        json.dumps({"problem_text": "", "image_urls": ["crop.png"]})
    )
    (tmp_path / "problem.html").write_text(
        '<div class="mw-parser-output"><h2>Problem</h2><p>Find $x$.</p>'
        "<h2>Solution</h2><p>Then $x=2$.</p></div>"
    )
    record = local_record(tmp_path, "Q", "https://example.test")
    assert record["problem_text"] == "Find $x$."
    assert record["solution_texts"] == ["Then $x=2$."]
    assert record["image_urls"] == ["crop.png"]


def test_source_question_mismatch_fails_explicitly(tmp_path):
    (tmp_path / "parsed.json").write_text(
        json.dumps({"question_id": "OTHER", "problem_text": "Find x"})
    )
    with pytest.raises(ValueError, match="mismatch"):
        local_record(tmp_path, "Q", None)


def test_repairs_statement_without_touching_classification_or_images():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE questions(question_id TEXT,problem_text_latex TEXT,problem_text_raw TEXT,"
        "solution_text_latex TEXT,all_solutions_json TEXT,classification_status TEXT,image_paths TEXT)"
    )
    conn.execute("INSERT INTO questions VALUES ('Q',NULL,NULL,NULL,NULL,'MAPPED','[]')")
    cur = MagicMock()
    result = apply_record(
        cur,
        conn,
        "pid",
        "Q",
        "[Placeholder] Q",
        {"problem_text": "Find $x$.", "solution_texts": ["Then $x=2$."]},
        write=True,
    )
    assert result["statements_updated"] == 1
    assert conn.execute(
        "SELECT problem_text_latex,classification_status,image_paths FROM questions"
    ).fetchone() == (
        "Find $x$.",
        "MAPPED",
        "[]",
    )
    calls = [call.args[0] for call in cur.execute.call_args_list]
    assert "content_hash" in calls[0]
    assert "WHERE NOT %s" in calls[1]


def test_audit_is_read_only_and_known_statement_is_not_overwritten():
    cur, staging = MagicMock(), MagicMock()
    apply_record(
        cur,
        staging,
        "pid",
        "Q",
        "Original source.",
        {"problem_text": "Other."},
        write=True,
    )
    cur.execute.assert_not_called()
    staging.execute.assert_not_called()
    apply_record(
        cur,
        staging,
        "pid",
        "Q",
        "[Placeholder]",
        {"problem_text": "Source."},
        write=False,
    )
    cur.execute.assert_not_called()
