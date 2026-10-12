"""Discover the official English Purple Comet archive and register PDF sources."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from pdf_pipeline import CORPUS_DIR, INGESTION_ROOT, PDF_CRAWL_DIR, _connect

sys.path.insert(0, str(INGESTION_ROOT / "src"))
from mathbank.crawl.pdf_format import has_pdf_header

BASE = "https://purplecomet.org"


class ArchiveHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.rows = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"a", "iframe"}:
            value = attrs.get("href" if tag == "a" else "src")
            if value:
                self.links.append(urljoin(BASE, value))
        if tag == "tr":
            self.row = []
        if tag == "td" and self.row is not None:
            self.cell = ""

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data

    def handle_endtag(self, tag):
        if tag == "td" and self.cell is not None:
            self.row.append(" ".join(self.cell.split()))
            self.cell = None
        if tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def parse_html(content: bytes) -> ArchiveHTML:
    page = ArchiveHTML()
    page.feed(content.decode("utf-8"))
    return page


def archive_entries(page: ArchiveHTML) -> list[tuple[int, str]]:
    entries = set()
    for url in page.links:
        match = re.fullmatch(r"/contest/(\d{4})/(MS|HS)", urlparse(url).path)
        if match:
            entries.add((int(match[1]), match[2]))
    if not entries:
        raise ValueError("Official archive contains no contest links")
    return sorted(entries, reverse=True)


def answer_key(page: ArchiveHTML) -> dict[int, str]:
    answers = {}
    for row in page.rows:
        if len(row) == 2 and row[0].isdigit():
            number = int(row[0])
            if number in answers or not row[1]:
                raise ValueError("Duplicate or empty official answer")
            answers[number] = row[1]
    if not answers or sorted(answers) != list(range(1, len(answers) + 1)):
        raise ValueError("Official answer numbers are not contiguous from 1")
    return answers


def official_pdf(page: ArchiveHTML) -> str:
    urls = {
        url
        for url in page.links
        if urlparse(url).hostname == "purplecomet.org"
        and urlparse(url).path.lower().endswith(".pdf")
        and ("english" in url.lower() or "solutions" in url.lower())
    }
    if len(urls) != 1:
        raise ValueError(
            f"Expected exactly one official English PDF, found {len(urls)}"
        )
    return urls.pop()


def fetch(url: str, delay: float) -> bytes:
    if urlparse(url).hostname not in {"purplecomet.org", "www.purplecomet.org"}:
        raise ValueError("Only official Purple Comet sources are supported")
    time.sleep(delay)
    request = urllib.request.Request(
        url, headers={"User-Agent": "MathBank archive ingestion"}
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                if urlparse(response.url).hostname not in {
                    "purplecomet.org",
                    "www.purplecomet.org",
                }:
                    raise ValueError("Archive redirected outside the official host")
                return response.read()
        except (TimeoutError, urllib.error.URLError) as exc:
            if isinstance(exc, urllib.error.HTTPError) and exc.code not in {
                429,
                500,
                502,
                503,
                504,
            }:
                raise
            if attempt == 2:
                raise
            print(
                f"Official archive fetch retry {attempt + 1}/3: {url}: {type(exc).__name__}",
                flush=True,
            )
            time.sleep(2**attempt)
    raise AssertionError("Unreachable archive retry state")


def update_registry(filename: str, key: str, additions: list[dict]) -> None:
    path = CORPUS_DIR / filename
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        rows = list(reader)
    by_key = {row[key]: row for row in rows}
    for addition in additions:
        if addition[key] in by_key:
            by_key[addition[key]].update(addition)
        else:
            row = {field: "" for field in fields}
            row.update(addition)
            rows.append(row)
            by_key[addition[key]] = row
    temporary = path.with_suffix(".csv.tmp")
    with temporary.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def discover(delay: float, year: int | None = None) -> list[dict]:
    sources = []
    for contest_year, division in archive_entries(
        parse_html(fetch(f"{BASE}/answers", delay))
    ):
        if year is not None and contest_year != year:
            continue
        code = f"PAPER_PURPLE_{contest_year}_{division}"
        competition = f"PURPLE_{division}"
        folder = PDF_CRAWL_DIR / competition.lower() / code
        folder.mkdir(parents=True, exist_ok=True)
        manifest = folder / "source.json"
        if manifest.is_file() and (folder / "problem.pdf").is_file():
            cached = json.loads(manifest.read_text())
            if has_pdf_header((folder / "problem.pdf").read_bytes()):
                sources.append(cached)
                print(f"{code}: using validated downloaded source", flush=True)
                continue
        contest_url = f"{BASE}/contest/{contest_year}/{division}"
        answers_url = f"{BASE}/answerlist/{contest_year}/{1 if division == 'MS' else 2}"
        contest = fetch(contest_url, delay)
        answers_html = fetch(answers_url, delay)
        problem_url = official_pdf(parse_html(contest))
        answers = answer_key(parse_html(answers_html))
        problem = fetch(problem_url, delay)
        if not has_pdf_header(problem):
            legacy_url = problem_url.replace(
                "https://purplecomet.org/", "https://www.purplecomet.org/"
            )
            legacy = fetch(legacy_url, delay)
            if has_pdf_header(legacy):
                problem_url, problem = legacy_url, legacy
                print(f"{code}: recovered PDF from official www host", flush=True)
        download_error = None
        if not has_pdf_header(problem):
            download_error = "Official problem endpoint returned HTML/non-PDF"
            print(
                f"{code}: DOWNLOAD FAILED: {download_error}; retained for retry",
                flush=True,
            )
        else:
            (folder / "problem.pdf").write_bytes(problem)
        (folder / "contest.html").write_bytes(contest)
        (folder / "answers.html").write_bytes(answers_html)
        (folder / "answers.json").write_text(json.dumps(answers, indent=2))
        # Older answer-list pages do not link worked solutions. Validate the
        # official naming convention by bytes, never by HTTP 200 alone.
        solution_url = f"{BASE}/files/{contest_year}{division}Solutions.pdf"
        try:
            solution = fetch(solution_url, delay)
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            solution = b""
        if has_pdf_header(solution):
            (folder / "solution.pdf").write_bytes(solution)
        else:
            solution_url = None
            print(
                f"{code}: no worked-solution PDF at official endpoint; answer key retained",
                flush=True,
            )
        source = {
            "paper_external_code": code,
            "competition_external_code": competition,
            "crawl_dir": competition.lower(),
            "problem_url": problem_url,
            "solution_url": solution_url,
            "source_kind": "PDF",
            "expected_count": len(answers),
            "answers_url": answers_url,
            "download_error": download_error,
        }
        (folder / "source.json").write_text(json.dumps(source, indent=2))
        sources.append(source)
        print(
            f"{code}: indexed questions={len(answers)} problem_pdf={not bool(download_error)} worked_solutions={bool(solution_url)}",
            flush=True,
        )
    if not sources:
        raise ValueError("No contests matched the selected year")
    return sources


def register(sources: list[dict]) -> None:
    with _connect() as conn:
        for division in sorted({s["competition_external_code"][-2:] for s in sources}):
            conn.execute(
                "INSERT INTO core.competition(external_code,name,organization,level) "
                "VALUES(%s,%s,'Purple Comet Math Meet',%s) ON CONFLICT(external_code) DO NOTHING",
                (
                    f"PURPLE_{division}",
                    f"Purple Comet {'Middle' if division == 'MS' else 'High'} School",
                    "middle_school" if division == "MS" else "high_school",
                ),
            )
        for source in sources:
            conn.execute(
                "INSERT INTO pipeline.pdf_source(paper_external_code,competition_external_code,"
                "crawl_dir,problem_url,solution_url,source_kind,link_scope) "
                "VALUES(%s,%s,%s,%s,%s,'PDF',%s) "
                "ON CONFLICT(paper_external_code) DO UPDATE SET problem_url=EXCLUDED.problem_url,"
                "solution_url=EXCLUDED.solution_url,updated_at=now()",
                tuple(
                    source[k]
                    for k in (
                        "paper_external_code",
                        "competition_external_code",
                        "crawl_dir",
                        "problem_url",
                        "solution_url",
                    )
                )
                + (
                    "DIRECT_PROBLEM_AND_SOLUTION"
                    if source["solution_url"]
                    else "DIRECT_PROBLEM_ONLY",
                ),
            )
            if source.get("download_error"):
                conn.execute(
                    "UPDATE pipeline.pdf_source SET download_status='FAILED',last_error=%s "
                    "WHERE paper_external_code=%s AND ingest_status!='INGESTED'",
                    (source["download_error"], source["paper_external_code"]),
                )
            else:
                conn.execute(
                    "UPDATE pipeline.pdf_source SET download_status='DOWNLOADED',"
                    "downloaded_at=COALESCE(downloaded_at,now()),last_error=NULL,updated_at=now() "
                    "WHERE paper_external_code=%s AND ingest_status!='INGESTED'",
                    (source["paper_external_code"],),
                )
    refreshed = datetime.now(UTC).date().isoformat()
    update_registry(
        "paper_registry.csv",
        "Paper_ID",
        [
            {
                "Paper_ID": s["paper_external_code"],
                "Competition_ID": s["competition_external_code"],
                "Year_or_Years": re.search(r"\d{4}", s["paper_external_code"])[0],
                "Test_or_Round": s["competition_external_code"][-2:],
                "Link_Scope": "DIRECT_PROBLEM_AND_SOLUTION"
                if s["solution_url"]
                else "DIRECT_PROBLEM_ONLY",
                "Problem_URL": s["problem_url"],
                "Solution_URL": s["solution_url"] or "",
                "Question_Count": str(s["expected_count"]),
                "Source_Record": f"{BASE}/answers",
                "Last_Refresh": refreshed,
                "Year_or_Event_Page_URL": s["answers_url"],
                "Notes": "Official English archive; answer key is not a worked solution.",
            }
            for s in sources
        ],
    )
    update_registry(
        "competition_catalog.csv",
        "Competition_ID",
        [
            {
                "Competition_ID": f"PURPLE_{division}",
                "Competition": f"Purple Comet {'Middle' if division == 'MS' else 'High'} School",
                "Event_or_Round": division,
                "Canonical_Archive_URL": f"{BASE}/answers",
                "Question_Format": "Integer answer, team contest",
                "Notes": "Official English problems and available worked solutions; retain source copyright.",
            }
            for division in sorted(
                {s["competition_external_code"][-2:] for s in sources}
            )
        ],
    )
    print(
        f"Registered {len(sources)} sources; expected questions={sum(s['expected_count'] for s in sources)}",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int)
    parser.add_argument("--delay", type=float, default=1)
    parser.add_argument(
        "--register",
        action="store_true",
        help="Write sources to Postgres and corpus registries",
    )
    parser.add_argument(
        "--extract",
        action="store_true",
        help="Extract page-mapped question/solution artifacts",
    )
    args = parser.parse_args()
    if args.delay < 0:
        parser.error("delay must be nonnegative")
    sources = discover(args.delay, args.year)
    if args.register:
        register(sources)
    if args.extract:
        extract(sources)
    elif any(source.get("download_error") for source in sources):
        raise RuntimeError(
            "Some official problem URLs returned non-PDF content; failures are recorded"
        )


def extract(sources: list[dict]) -> None:
    logs = INGESTION_ROOT / "logs/purple_comet"
    logs.mkdir(exist_ok=True)
    temporary = logs / "tmp"
    temporary.mkdir(exist_ok=True)
    python = str(INGESTION_ROOT / ".venv/bin/python")
    failures = []
    for source in sources:
        paper = source["paper_external_code"]
        folder = PDF_CRAWL_DIR / source["crawl_dir"] / paper
        manifest = folder / "sources.json"
        manifest.write_text(json.dumps([source]))
        command = [
            python,
            "scripts/crawl_pdf_papers.py",
            "--sources-file",
            str(manifest),
            "--require-split",
            "--delay",
            "1",
        ]
        env = {
            **os.environ,
            "MATHBANK_PDF_DEVICE": "cpu",
            "TMPDIR": str(temporary),
            "HF_HOME": str(INGESTION_ROOT / "data/model_cache/huggingface"),
            "TORCH_HOME": str(INGESTION_ROOT / "data/model_cache/torch"),
        }
        try:
            if source.get("download_error"):
                raise ValueError(source["download_error"])
            with (logs / f"{paper}.parse.log").open("a") as output:
                try:
                    subprocess.run(
                        command,
                        cwd=INGESTION_ROOT,
                        env=env,
                        stdout=output,
                        stderr=subprocess.STDOUT,
                        check=True,
                        timeout=900,
                    )
                except subprocess.CalledProcessError:
                    print(
                        f"{paper}: layout parse rejected; explicit native-text retry with retained page images",
                        flush=True,
                    )
                    subprocess.run(
                        [*command, "--native-extraction", "--reparse"],
                        cwd=INGESTION_ROOT,
                        env=env,
                        stdout=output,
                        stderr=subprocess.STDOUT,
                        check=True,
                        timeout=900,
                    )
                subprocess.run(
                    [
                        python,
                        "scripts/split_pdf_artifacts.py",
                        "--paper",
                        paper,
                        "--reprocess",
                    ],
                    cwd=INGESTION_ROOT,
                    env=env,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    check=True,
                    timeout=300,
                )
            from paper_batches import question_codes

            codes = question_codes(source)
            with _connect() as conn:
                conn.execute(
                    "UPDATE pipeline.pdf_source SET download_status='DOWNLOADED',parse_status='PARSED',"
                    "questions_found=%s,downloaded_at=COALESCE(downloaded_at,now()),parsed_at=now(),"
                    "last_error=NULL,updated_at=now() WHERE paper_external_code=%s",
                    (len(codes), paper),
                )
            print(
                f"{paper}: extraction verified questions={len(codes)} including page images",
                flush=True,
            )
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            ValueError,
            OSError,
        ) as exc:
            print(
                f"{paper}: extraction FAILED {exc}; see {logs / (paper + '.parse.log')}",
                flush=True,
            )
            failures.append(paper)
            with _connect() as conn:
                conn.execute(
                    "UPDATE pipeline.pdf_source SET parse_status='FAILED',last_error=%s "
                    "WHERE paper_external_code=%s",
                    (str(exc), paper),
                )
    if failures:
        raise RuntimeError(f"Extraction failed for {len(failures)} papers: {failures}")


if __name__ == "__main__":
    main()
