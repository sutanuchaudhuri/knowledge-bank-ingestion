"""Student-safe diagram metadata shared by corpus, coaching and image routes."""
import hashlib

from sqlalchemy import text

# Legacy imports have no verified problem/solution provenance.
STUDENT_IMAGE_FILTER = """
    i.source NOT IN ('PDF_PARSED', 'AOPS_CRAWL', 'PDF_SOLUTION_PAGE', 'PDF_SOLUTION_FIGURE',
                     'PDF_ANSWER_PAGE', 'AOPS_SOLUTION_DIAGRAM', 'ADMIN_SOLUTION_DIAGRAM')
    AND i.local_path !~* '(^|/)(solution|answer)[_.-]'
    AND i.local_path !~* '(^|/)problem_page_[0-9]+[.]png$'
    AND NOT EXISTS (
        SELECT 1 FROM pedagogy.diagram d
        WHERE d.problem_image_id = i.problem_image_id
          AND d.visibility <> 'STUDENT_PROBLEM'
    )
"""


def list_images(conn, code: str) -> list[dict]:
    rows = conn.execute(text(f"""
        SELECT i.problem_image_id::text AS problem_image_id, i.ordinal, i.source,
               i.local_path AS asset_path
        FROM core.problem_image i JOIN core.problem p USING (problem_id)
        WHERE p.canonical_code = :code AND {STUDENT_IMAGE_FILTER}
        ORDER BY i.ordinal
    """), {"code": code}).mappings()
    result = []
    for row in rows:
        image = dict(row)
        path = image.pop("asset_path")
        image["version"] = hashlib.sha256(f"{image['source']}:{path}".encode()).hexdigest()[:12]
        image["url"] = f"/v1/problem-images/{image['problem_image_id']}?v={image['version']}"
        image["alt"] = f"{code} - source problem diagram {image['ordinal']}"
        image["markdown"] = f"![{image['alt']}](/api/rest/solve/images/{image['problem_image_id']}?v={image['version']})"
        result.append(image)
    return result
