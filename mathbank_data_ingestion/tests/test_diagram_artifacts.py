import hashlib
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import repair_diagram_artifacts as repair
import split_pdf_artifacts as splitter

from mathbank.crawl import image_downloader, pdf_parser


def pdf_source():
    with pymupdf.open() as doc:
        first = doc.new_page()
        first.insert_text((40, 100), "1. First problem.")
        first.insert_text((40, 350), "2. Figure on next page.")
        second = doc.new_page()
        second.insert_text((40, 40), "Contest header")
        second.draw_circle((240, 160), 50)
        second.insert_text((235, 95), "M")
        second.insert_text((40, 350), "3. Unrelated question.")
        return doc.tobytes()


def staging():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE questions(question_id TEXT PRIMARY KEY, image_paths TEXT,
          artifact_base_path TEXT, problem_md_path TEXT, solution_md_path TEXT, updated_at TEXT);
        CREATE TABLE visual_assets(asset_id TEXT PRIMARY KEY, question_id TEXT, paper_id TEXT,
          source_side TEXT, asset_type TEXT, page_number INTEGER, local_file_path TEXT,
          bbox_pdf TEXT, drive_asset_url TEXT, created_at TEXT);
    """)
    return conn


HTML = """<div class="mw-parser-output">
<img src="/images/header-logo.png">
<h2><span class="mw-headline" id="Problem">Problem</span></h2>
<p>Question <img src="/images/problem.png"><img src="https://latex.artofproblemsolving.com/x.png"></p>
<h2><span class="mw-headline" id="Solution_1">Solution 1</span></h2>
<p>Worked answer <img src="/images/solution.png"></p>
<h2><span class="mw-headline" id="See_Also">See Also</span></h2>
<p><img src="/images/unrelated.png"></p>
</div>"""


def test_aops_sections_never_mix_problem_solution_and_site_images():
    base = "https://wiki.artofproblemsolving.com/wiki/page"
    assert image_downloader.extract_diagram_urls(HTML, base) == [
        "https://wiki.artofproblemsolving.com/images/problem.png"
    ]
    assert image_downloader.extract_diagram_urls(HTML, base, "solution") == [
        "https://wiki.artofproblemsolving.com/images/solution.png"
    ]
    assert (
        image_downloader.extract_diagram_urls(
            '<div class="mw-parser-output"><img src="/images/a.png"></div>', base
        )
        == []
    )


def test_pdf_parser_does_not_replace_crops_with_proportional_pages(tmp_path, monkeypatch):
    monkeypatch.setattr(
        pdf_parser,
        "extract_markdown",
        lambda *a, **k: SimpleNamespace(
            markdown="1. First problem.\n2. Figure on next page.\n3. Unrelated question.",
            figure_paths=["some-unassigned-docling-image.png"],
            used_fallback=False,
            warnings=[],
        ),
    )
    questions = pdf_parser.parse_pdf_paper(
        "PAPER_SMT_2020_GEOM",
        "SMT",
        pdf_source(),
        None,
        3,
        save_artifacts=False,
        visuals_dir=tmp_path / "visuals",
    )
    assert [len(q.image_urls) for q in questions] == [0, 1, 0]
    assert "problem_figure_" in Path(questions[1].image_urls[0]).name
    assert Path(questions[1].image_urls[0]).is_file()
    assert not any("_page_" in p for q in questions for p in q.image_urls)


def test_repair_updates_artifacts_staging_and_provenance_without_changing_statement(tmp_path):
    paper = tmp_path / "data/crawl_pdf/smt/PAPER_SMT_2020_GEOM"
    paper.mkdir(parents=True)
    (paper / "problem.pdf").write_bytes(pdf_source())
    conn = staging()
    for n in (1, 2, 3):
        code = f"{paper.name}_Q{n:02d}"
        folder = paper / "questions" / f"Q{n:02d}"
        folder.mkdir(parents=True)
        (folder / "problem.md").write_text(
            "Original statement.\n\n---\n\n![old](images/problem_page_001.png)\n"
        )
        crawl = tmp_path / "data/crawl/smt" / code
        crawl.mkdir(parents=True)
        (crawl / "parsed.json").write_text(
            json.dumps({"problem_text": "Original statement.", "image_urls": ["old.png"]})
        )
        conn.execute("INSERT INTO questions(question_id) VALUES (?)", (code,))
    args = SimpleNamespace(apply=True, paper=None, competition=None)
    totals = Counter()
    repair.repair_pdfs(tmp_path, args, conn, totals)
    assert totals["pdf_problem_figures"] == 1
    assert totals["staging_questions_updated"] == 3
    folder = paper / "questions/Q02"
    assert "problem_page_" not in (folder / "problem.md").read_text()
    assert "Original statement." in (folder / "problem.md").read_text()
    record = json.loads(
        (tmp_path / "data/crawl/smt/PAPER_SMT_2020_GEOM_Q02/parsed.json").read_text()
    )
    assert record["problem_text"] == "Original statement."
    assert len(record["problem_image_urls"]) == 1 and not record["solution_image_urls"]
    assert record["diagram_status"] == {"problem": "EXTRACTED", "solution": "SOURCE_MISSING"}
    first = json.loads((paper / "questions/Q01/diagram_status.json").read_text())
    assert first["problem"] == "VERIFIED_NO_GRAPHICS"
    row = conn.execute("SELECT source_side,page_number,bbox_pdf FROM visual_assets").fetchone()
    assert row[0] == "problem" and row[1] == 2
    assert len(json.loads(row[2])) == 4


def test_splitter_uses_question_crops_and_never_copies_pages(tmp_path, monkeypatch):
    monkeypatch.setattr(splitter, "CRAWL_DIR", tmp_path / "crawl")
    monkeypatch.setattr(splitter, "CRAWL_PDF_DIR", tmp_path / "crawl_pdf")
    code = "PAPER_SMT_2020_GEOM_Q02"
    paper = tmp_path / "crawl_pdf/smt/PAPER_SMT_2020_GEOM"
    paper.mkdir(parents=True)
    (paper / "problem.pdf").write_bytes(pdf_source())
    crawl = tmp_path / "crawl/smt" / code
    crawl.mkdir(parents=True)
    (crawl / "parsed.json").write_text(
        json.dumps({"problem_text": "Original statement.", "solution_texts": []})
    )
    conn = staging()
    conn.execute("INSERT INTO questions(question_id) VALUES (?)", (code,))
    status = splitter._process_question(conn, code, "SMT", paper.name, 2, 3, False)
    assert status.endswith("imgs=1")
    paths = json.loads(conn.execute("SELECT image_paths FROM questions").fetchone()[0])
    assert len(paths) == 1 and "problem_figure_" in paths[0]


def test_failed_aops_download_does_not_assign_next_image_to_wrong_source(tmp_path, monkeypatch):
    monkeypatch.setattr(image_downloader, "CRAWL_DIR", tmp_path)
    conn = staging()
    conn.execute("INSERT INTO questions(question_id) VALUES ('TEST_Q01')")

    def download(urls, out_dir, **kwargs):
        out_dir.mkdir(parents=True, exist_ok=True)
        if not urls or "problem.png" in urls[0]:
            return []
        path = out_dir / (hashlib.sha256(urls[0].encode()).hexdigest()[:12] + ".png")
        path.write_bytes(b"fixture")
        return [str(path)]

    monkeypatch.setattr(image_downloader, "download_images", download)
    paths = image_downloader.save_aops_images(
        conn, "TEST_Q01", "AIME", HTML, "https://wiki.artofproblemsolving.com/wiki/page"
    )
    assert len(paths) == 1
    side, url = conn.execute("SELECT source_side,drive_asset_url FROM visual_assets").fetchone()
    assert side == "solution" and url.endswith("/solution.png")


def test_download_errors_are_logged_not_silently_ignored(tmp_path, monkeypatch, caplog):
    from mathbank.crawl.downloader import DownloadError

    def fail(*args, **kwargs):
        raise DownloadError("fixture failure")

    monkeypatch.setattr(image_downloader, "fetch_binary", fail)
    assert image_downloader.download_images(["https://example.test/image.png"], tmp_path) == []
    assert "fixture failure" in caplog.text


def test_offline_aops_reparse_preserves_local_section_assets_without_network(tmp_path, monkeypatch):
    monkeypatch.setattr(image_downloader, "CRAWL_DIR", tmp_path)
    conn = staging()
    conn.execute("INSERT INTO questions(question_id) VALUES ('TEST_Q01')")
    base = "https://wiki.artofproblemsolving.com/wiki/page"
    image_dir = tmp_path / "aime/TEST_Q01/images"
    image_dir.mkdir(parents=True)
    url = "https://wiki.artofproblemsolving.com/images/problem.png"
    image = image_dir / (hashlib.sha256(url.encode()).hexdigest()[:12] + ".png")
    image.write_bytes(b"fixture")
    parsed = image_dir.parent / "parsed.json"
    parsed.write_text(json.dumps({"problem_text": "Original", "image_urls": ["whole-page.png"]}))

    def forbidden(*args, **kwargs):
        raise AssertionError("Offline reparse must not download")

    monkeypatch.setattr(image_downloader, "download_images", forbidden)
    paths = image_downloader.save_aops_images(
        conn, "TEST_Q01", "AIME", HTML, base, download_missing=False
    )
    assert paths == [str(image.resolve())]
    record = json.loads(parsed.read_text())
    assert record["problem_image_urls"] == paths
    assert record["solution_image_urls"] == []
    assert conn.execute("SELECT source_side FROM visual_assets").fetchone()[0] == "problem"
