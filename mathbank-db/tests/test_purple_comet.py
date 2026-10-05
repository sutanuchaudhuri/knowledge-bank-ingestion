"""Official archive contracts and strict question/image completeness."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "etl"))
import paper_batches as batches
import purple_comet as purple


def test_archive_discovery_deduplicates_only_contest_links():
    page = purple.parse_html(
        b'<a href="/contest/2026/MS">MS</a><a href="/contest/2026/MS">again</a>'
        b'<a href="/contest/2005/HS">HS</a><a href="/results/2026">results</a>'
    )
    assert purple.archive_entries(page) == [(2026, "MS"), (2005, "HS")]


@pytest.mark.parametrize(
    "rows",
    [
        b"<tr><td>2</td><td>7</td></tr>",
        b"<tr><td>1</td><td></td></tr>",
        b"<tr><td>1</td><td>7</td></tr><tr><td>1</td><td>8</td></tr>",
    ],
)
def test_answer_key_rejects_missing_duplicate_and_empty_numbers(rows):
    with pytest.raises(ValueError):
        purple.answer_key(purple.parse_html(b"<table>" + rows + b"</table>"))


def test_official_pdf_uses_embedded_english_document_not_guessed_url():
    assert (
        purple.official_pdf(
            purple.parse_html(b'<iframe src="/files/2026MS_English.pdf"></iframe>')
        )
        == "https://purplecomet.org/files/2026MS_English.pdf"
    )
    with pytest.raises(ValueError):
        purple.official_pdf(
            purple.parse_html(
                b'<iframe src="https://untrusted.test/paper_English.pdf">'
            )
        )


def test_registration_preserves_unrelated_state_and_marks_bad_source(monkeypatch):
    conn = MagicMock()
    monkeypatch.setattr(purple, "_connect", lambda: conn)
    monkeypatch.setattr(purple, "update_registry", lambda *args: None)
    purple.register(
        [
            {
                "paper_external_code": "PAPER_PURPLE_2026_MS",
                "competition_external_code": "PURPLE_MS",
                "crawl_dir": "purple_ms",
                "problem_url": "https://purplecomet.org/files/problem.pdf",
                "solution_url": None,
                "expected_count": 2,
                "answers_url": "https://purplecomet.org/answers",
                "download_error": "Not a PDF",
            }
        ]
    )
    calls = conn.__enter__.return_value.execute.call_args_list
    assert any("download_status='FAILED'" in call.args[0] for call in calls)
    assert not any("ingest_status='PENDING'" in call.args[0] for call in calls)


def test_purple_completeness_requires_problem_and_solution_page_images(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(batches, "PDF_CRAWL_DIR", tmp_path)
    source = {
        "crawl_dir": "purple_ms",
        "competition_external_code": "PURPLE_MS",
        "paper_external_code": "PAPER_PURPLE_2026_MS",
        "solution_url": "https://purplecomet.org/s.pdf",
        "expected_count": 2,
    }
    folder = tmp_path / source["crawl_dir"] / source["paper_external_code"]
    folder.mkdir(parents=True)
    ids = [source["paper_external_code"] + f"_Q{n:02d}" for n in (1, 2)]
    (folder / "index.json").write_text(json.dumps({"questions": ids}))
    (folder / "answers.json").write_text(json.dumps({"1": "7", "2": "9"}))
    (folder / "page_spans.json").write_text(
        json.dumps({side: {"1": [1], "2": [1]} for side in ("problem", "solution")})
    )
    for number in (1, 2):
        q = folder / "questions" / f"Q{number:02d}"
        (q / "images").mkdir(parents=True)
        (q / "problem.md").write_text("A synthetic test question.")
        (q / "solution.md").write_text("A synthetic test explanation.")
        for side in ("problem", "solution"):
            (q / "images" / f"{side}_page_001.png").write_bytes(b"synthetic image")
    assert batches.question_codes(source) == ids
    (folder / "questions/Q02/images/solution_page_001.png").unlink()
    with pytest.raises(ValueError, match="missing required solution images"):
        batches.question_codes(source)
