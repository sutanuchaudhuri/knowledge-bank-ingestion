"""Import existing question visuals with problem/solution provenance."""
from pathlib import Path
import logging
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "mathbank_data_ingestion/src"))
log = logging.getLogger(__name__)


def source_for_image(path: Path) -> str:
    name = path.name.lower()
    if name.startswith("solution_"):
        return "PDF_SOLUTION_PAGE"
    if name.startswith("answer_"):
        return "PDF_ANSWER_PAGE"
    if name.startswith("problem_"):
        return "PDF_PROBLEM_PAGE"
    return "PDF_PARSED"


def question_images(question_dir: Path) -> list[tuple[Path, str]]:
    images_dir = question_dir / "images"
    return [
        (path.resolve(), source_for_image(path))
        for path in sorted(images_dir.iterdir()) if path.is_file()
        and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".svg"}
    ] if images_dir.is_dir() else []


def store_images(cur, problem_id: str, images: list[tuple[Path, str]]) -> int:
    for ordinal, (path, source) in enumerate(images, start=1):
        cur.execute("""
            INSERT INTO core.problem_image (problem_id, ordinal, local_path, source)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (problem_id, ordinal) DO UPDATE
              SET local_path = EXCLUDED.local_path, source = EXCLUDED.source
            WHERE core.problem_image.local_path IS DISTINCT FROM EXCLUDED.local_path
               OR core.problem_image.source IS DISTINCT FROM EXCLUDED.source
        """, (problem_id, ordinal, str(path), source))
    return len(images)


def mapped_problem_pages(paper_dir: Path) -> dict[int, list[tuple[Path, str]]]:
    from mathbank.crawl.pdf_pages import question_page_numbers

    numbers = sorted(int(q.name[1:]) for q in (paper_dir / "questions").glob("Q[0-9]*")
                     if q.name[1:].isdigit() and (q / "problem.md").is_file())
    if not numbers or numbers != list(range(1, max(numbers) + 1)):
        raise ValueError("Question inventory is not a complete consecutive sequence")
    mapping = question_page_numbers((paper_dir / "problem.pdf").read_bytes(), len(numbers))
    result = {}
    for number, pages in mapping.items():
        images = []
        for page in pages:
            path = paper_dir / "visuals/pages" / f"problem_page_{page:03d}.png"
            if not path.is_file():
                raise ValueError(f"Missing rendered problem page {page}")
            images.append((path.resolve(), "PDF_PROBLEM_PAGE"))
        result[number] = images
    return result


def paper_images(paper_dir: Path) -> dict[int, list[tuple[Path, str]]]:
    questions = {int(q.name[1:]): question_images(q)
                 for q in (paper_dir / "questions").glob("Q[0-9]*") if q.name[1:].isdigit()}
    # Native region crops are already bounded; do not replace them with whole pages.
    if any("region_" in path.name for images in questions.values() for path, _ in images):
        return questions
    if not (paper_dir / "problem.pdf").is_file() or not (paper_dir / "visuals/pages").is_dir():
        return questions
    try:
        mapped = mapped_problem_pages(paper_dir)
    except (ValueError, ImportError) as exc:
        log.warning("%s: exact page mapping unavailable (%s); retaining authored assets",
                    paper_dir.name, str(exc))
        return questions
    for number, images in mapped.items():
        questions[number] = images + [
            (path, source) for path, source in questions.get(number, [])
            if source in {"PDF_SOLUTION_PAGE", "PDF_ANSWER_PAGE"}
        ]
    return questions
