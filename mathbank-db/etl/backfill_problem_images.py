"""Repair PDF image references only; no corpus text, embeddings, OCR or model calls."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import logging

from pdf_assets import paper_images, store_images
from pdf_pipeline import PDF_CRAWL_DIR, _connect


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Commit image-reference repairs")
    parser.add_argument("--paper", help="Restrict to one paper external code")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    totals = Counter()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT canonical_code, problem_id FROM core.problem")
            problems = dict(cur.fetchall())
            cur.execute("SELECT problem_id, ordinal, local_path, source FROM core.problem_image ORDER BY ordinal")
            existing = {}
            for pid, ordinal, path, source in cur.fetchall():
                existing.setdefault(pid, []).append((ordinal, path, source))
            for paper_dir in sorted(PDF_CRAWL_DIR.glob("*/PAPER_*")):
                if args.paper and paper_dir.name != args.paper:
                    continue
                codes = {n: problems[code] for q in (paper_dir / "questions").glob("Q[0-9]*")
                         if q.name[1:].isdigit()
                         for n in [int(q.name[1:])]
                         for code in [f"{paper_dir.name}_Q{n:02d}"] if code in problems}
                if not codes:
                    continue
                visuals = paper_images(paper_dir)
                totals["papers"] += 1
                for number, pid in codes.items():
                    images = visuals.get(number, [])
                    if not images:
                        totals["questions_without_local_assets"] += 1
                        logging.warning("%s_Q%02d: no local image assets", paper_dir.name, number)
                        continue
                    totals["questions_with_assets"] += 1
                    totals["image_references"] += len(images)
                    totals["problem_page_references"] += sum(s == "PDF_PROBLEM_PAGE" for _, s in images)
                    desired = [(n, str(path), source) for n, (path, source) in enumerate(images, 1)]
                    if existing.get(pid, []) == desired:
                        totals["unchanged_questions"] += 1
                        continue
                    if any(source not in {"PDF_PARSED", "PDF_PROBLEM_PAGE", "PDF_SOLUTION_PAGE", "PDF_ANSWER_PAGE"}
                           for _, _, source in existing.get(pid, [])):
                        totals["protected_questions"] += 1
                        logging.warning("%s_Q%02d: non-PDF provenance protected", paper_dir.name, number)
                        continue
                    totals["changed_questions"] += 1
                    if args.apply:
                        # Only remove stale ordinals owned by the PDF importer.
                        with conn.pipeline():
                            cur.execute("""
                                DELETE FROM core.problem_image
                                WHERE problem_id = %s AND ordinal > %s
                                  AND source IN ('PDF_PARSED', 'PDF_PROBLEM_PAGE',
                                                 'PDF_SOLUTION_PAGE', 'PDF_ANSWER_PAGE')
                            """, (pid, len(images)))
                            store_images(cur, str(pid), images)
            if not args.apply:
                conn.rollback()
    print(json.dumps({"mode": "applied" if args.apply else "dry-run", **totals}, sort_keys=True))


if __name__ == "__main__":
    main()
