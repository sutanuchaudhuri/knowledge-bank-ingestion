"""Replace whole-page references with question-specific figures; no model calls."""

import argparse
import json
import logging
from collections import Counter
from pathlib import Path

from pdf_assets import question_images, source_for_image, store_images
from pdf_pipeline import INGESTION_ROOT, PDF_CRAWL_DIR, _connect
from question_figures import extract_question_figures

log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--paper")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    totals = Counter()
    updates: list[tuple[str, list[tuple[Path, str]], str]] = []
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT canonical_code, problem_id FROM core.problem")
        problems = dict(cur.fetchall())
        cur.execute(
            "SELECT problem_id, local_path, source FROM core.problem_image ORDER BY ordinal"
        )
        existing = {}
        for pid, path, source in cur.fetchall():
            existing.setdefault(pid, []).append((path, source))
        for paper in sorted(PDF_CRAWL_DIR.glob("*/PAPER_*")):
            if args.paper and paper.name != args.paper:
                continue
            if not (paper / "problem.pdf").is_file():
                continue
            codes = {
                int(q.name[1:]): problems[code]
                for q in (paper / "questions").glob("Q[0-9]*")
                if q.name[1:].isdigit()
                for code in [f"{paper.name}_Q{int(q.name[1:]):02d}"]
                if code in problems
            }
            if not codes:
                continue
            # Existing native region extraction has its own verified boundaries.
            if any(
                "problem_region_" in path
                for pid in codes.values()
                for path, _ in existing.get(pid, [])
            ) and not all(
                (
                    paper / "questions" / f"Q{number:02d}" / "image_manifest.json"
                ).is_file()
                for number in codes
            ):
                totals["native_region_papers_preserved"] += 1
                continue
            try:
                figures = extract_question_figures(paper, write=args.apply)
            except (ValueError, FileNotFoundError) as exc:
                log.warning("%s: figures not imported: %s", paper.name, exc)
                totals["unverified_papers"] += 1
                figures = {}
            else:
                totals["verified_papers"] += 1
            for number, pid in codes.items():
                if any(
                    not source.startswith("PDF_") for _, source in existing.get(pid, [])
                ):
                    totals["non_pdf_questions_preserved"] += 1
                    continue
                folder = paper / "questions" / f"Q{number:02d}"
                if (folder / "image_manifest.json").is_file():
                    images = question_images(folder)
                else:
                    images = [
                        (p, "PDF_QUESTION_FIGURE") for p in figures.get(number, [])
                    ]
                    images.extend(
                        (p, source_for_image(p))
                        for path, source in existing.get(pid, [])
                        for p in [Path(path)]
                        if source
                        in {
                            "PDF_SOLUTION_PAGE",
                            "PDF_SOLUTION_FIGURE",
                            "PDF_ANSWER_PAGE",
                        }
                        and p.is_file()
                    )
                totals["questions"] += 1
                totals["question_figures"] += sum(
                    s == "PDF_QUESTION_FIGURE" for _, s in images
                )
                totals["solution_figures"] += sum(
                    s == "PDF_SOLUTION_FIGURE" for _, s in images
                )
                if existing.get(pid, []) == [
                    (str(path), source) for path, source in images
                ]:
                    totals["unchanged_questions"] += 1
                    continue
                if args.apply:
                    updates.append((str(pid), images, "PDF"))
        if not args.paper:
            for manifest in sorted(
                (INGESTION_ROOT / "data/crawl").glob("*/*/image_manifest.json")
            ):
                code = manifest.parent.name
                pid = problems.get(code)
                if pid is None or not (manifest.parent / "problem.html").is_file():
                    continue
                if any(
                    not source.startswith("AOPS_")
                    for _, source in existing.get(pid, [])
                ):
                    totals["non_aops_questions_preserved"] += 1
                    continue
                images = question_images(manifest.parent, source_kind="AOPS")
                totals["aops_questions"] += 1
                totals["aops_problem_figures"] += sum(
                    s == "AOPS_PROBLEM_DIAGRAM" for _, s in images
                )
                totals["aops_solution_figures"] += sum(
                    s == "AOPS_SOLUTION_DIAGRAM" for _, s in images
                )
                if existing.get(pid, []) == [
                    (str(path), source) for path, source in images
                ]:
                    totals["unchanged_questions"] += 1
                    continue
                if args.apply:
                    updates.append((str(pid), images, "AOPS"))
        if args.apply:
            with conn.pipeline():
                for pid, images, source_kind in updates:
                    store_images(cur, pid, images, source_kind=source_kind)
        else:
            conn.rollback()
    print(
        json.dumps(
            {"mode": "applied" if args.apply else "dry-run", **totals}, sort_keys=True
        )
    )


if __name__ == "__main__":
    main()
