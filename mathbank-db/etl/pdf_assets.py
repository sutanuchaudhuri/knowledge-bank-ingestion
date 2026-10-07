"""Import existing question visuals with problem/solution provenance."""

import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "mathbank_data_ingestion/src"))
log = logging.getLogger(__name__)
IMAGE_SOURCES = {
    "PDF": [
        "PDF_PARSED",
        "PDF_PROBLEM_PAGE",
        "PDF_SOLUTION_PAGE",
        "PDF_ANSWER_PAGE",
        "PDF_QUESTION_FIGURE",
        "PDF_SOLUTION_FIGURE",
    ],
    "AOPS": ["AOPS_CRAWL", "AOPS_PROBLEM_DIAGRAM", "AOPS_SOLUTION_DIAGRAM"],
}


def source_for_image(path: Path) -> str:
    name = path.name.lower()
    if name.startswith("solution_figure_"):
        return "PDF_SOLUTION_FIGURE"
    if name.startswith("solution_"):
        return "PDF_SOLUTION_PAGE"
    if name.startswith("answer_"):
        return "PDF_ANSWER_PAGE"
    if name.startswith("problem_figure_"):
        return "PDF_QUESTION_FIGURE"
    if name.startswith("problem_"):
        return "PDF_PROBLEM_PAGE"
    return "PDF_PARSED"


def question_images(
    question_dir: Path, *, source_kind: str = "PDF"
) -> list[tuple[Path, str]]:
    if source_kind not in {"PDF", "AOPS"}:
        raise ValueError("Image source kind must be PDF or AOPS")
    manifest = question_dir / "image_manifest.json"
    if manifest.is_file():
        images = []
        for asset in json.loads(manifest.read_text()):
            path = Path(asset["local_path"]).resolve()
            if not path.is_file() or REPO_ROOT not in path.parents:
                raise ValueError(
                    f"{question_dir.name}: manifest image is missing or outside repository"
                )
            if asset["source_side"] not in {"problem", "solution"}:
                raise ValueError(f"{question_dir.name}: invalid image source side")
            images.append(
                (
                    path,
                    (
                        "PDF_QUESTION_FIGURE"
                        if source_kind == "PDF"
                        else "AOPS_PROBLEM_DIAGRAM"
                    )
                    if asset["source_side"] == "problem"
                    else (
                        "PDF_SOLUTION_FIGURE"
                        if source_kind == "PDF"
                        else "AOPS_SOLUTION_DIAGRAM"
                    ),
                )
            )
        return images
    if source_kind == "AOPS":
        log.warning(
            "%s: no source-side manifest; run ingestion repair-diagrams before import",
            question_dir.name,
        )
        return []
    images_dir = question_dir / "images"
    return (
        [
            (path.resolve(), source_for_image(path))
            for path in sorted(images_dir.iterdir())
            if path.is_file()
            and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".svg"}
        ]
        if images_dir.is_dir()
        else []
    )


def store_images(
    cur,
    problem_id: str,
    images: list[tuple[Path, str]],
    *,
    source_kind: str | None = None,
) -> int:
    if source_kind is not None:
        if source_kind not in IMAGE_SOURCES:
            raise ValueError("Image source kind must be PDF or AOPS")
        sources = IMAGE_SOURCES[source_kind]
        if any(source not in sources for _, source in images):
            raise ValueError(
                "Replacement images must belong to the requested source kind"
            )
        cur.execute(
            "DELETE FROM core.problem_image WHERE problem_id=%s AND ordinal>%s "
            "AND source=ANY(%s)",
            (problem_id, len(images), sources),
        )
    for ordinal, (path, source) in enumerate(images, start=1):
        cur.execute(
            """
            INSERT INTO core.problem_image (problem_id, ordinal, local_path, source)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (problem_id, ordinal) DO UPDATE
              SET local_path = EXCLUDED.local_path, source = EXCLUDED.source
            WHERE core.problem_image.source NOT IN ('ADMIN_SOURCE_DIAGRAM','ADMIN_SOLUTION_DIAGRAM')
              AND (core.problem_image.local_path IS DISTINCT FROM EXCLUDED.local_path
               OR core.problem_image.source IS DISTINCT FROM EXCLUDED.source)
        """,
            (problem_id, ordinal, str(path), source),
        )
    return len(images)


def paper_images(paper_dir: Path) -> dict[int, list[tuple[Path, str]]]:
    questions = {
        int(q.name[1:]): question_images(q)
        for q in (paper_dir / "questions").glob("Q[0-9]*")
        if q.name[1:].isdigit()
    }
    if all(
        (paper_dir / "questions" / f"Q{number:02d}" / "image_manifest.json").is_file()
        for number in questions
    ):
        return questions
    # Native region crops are already bounded; do not replace them with whole pages.
    if any(
        "region_" in path.name for images in questions.values() for path, _ in images
    ):
        return questions
    if (paper_dir / "problem.pdf").is_file():
        from question_figures import extract_question_figures

        figures = {}
        try:
            figures = extract_question_figures(paper_dir, write=True)
        except ValueError as exc:
            log.warning("%s: no automatic figures imported (%s)", paper_dir.name, exc)
        solutions = {}
        if (paper_dir / "solution.pdf").is_file():
            try:
                solutions = extract_question_figures(
                    paper_dir,
                    side="solution",
                    expected_count=len(questions),
                    write=True,
                )
            except ValueError as exc:
                log.warning(
                    "%s: no automatic solution figures imported (%s)",
                    paper_dir.name,
                    exc,
                )
        return {
            number: [(path, "PDF_QUESTION_FIGURE") for path in figures.get(number, [])]
            + [(path, "PDF_SOLUTION_FIGURE") for path in solutions.get(number, [])]
            for number in questions
        }
    # Never substitute a source page for a question figure.
    return {
        number: [
            (path, source)
            for path, source in images
            if not path.name.startswith("problem_page_")
        ]
        for number, images in questions.items()
    }
