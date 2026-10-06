"""Student-safe diagram metadata shared by corpus, coaching and image routes."""
from sqlalchemy import text

# Historic PDF_PARSED rows may still point to solution/answer pages.
STUDENT_IMAGE_FILTER = """
    i.source NOT IN ('PDF_SOLUTION_PAGE', 'PDF_ANSWER_PAGE')
    AND i.local_path !~* '(^|/)(solution|answer)[_.-]'
    AND NOT EXISTS (
        SELECT 1 FROM pedagogy.diagram d
        WHERE d.problem_image_id = i.problem_image_id
          AND d.visibility <> 'STUDENT_PROBLEM'
    )
"""


def list_images(conn, code: str) -> list[dict]:
    rows = conn.execute(text(f"""
        SELECT i.problem_image_id::text AS problem_image_id, i.ordinal, i.source
        FROM core.problem_image i JOIN core.problem p USING (problem_id)
        WHERE p.canonical_code = :code AND {STUDENT_IMAGE_FILTER}
        ORDER BY i.ordinal
    """), {"code": code}).mappings()
    result = []
    for row in rows:
        image = dict(row)
        image["url"] = f"/v1/problem-images/{image['problem_image_id']}"
        image["alt"] = f"{code} - source problem {'page' if image['source'] == 'PDF_PROBLEM_PAGE' else 'diagram'} {image['ordinal']}"
        image["markdown"] = f"![{image['alt']}](/api/rest/solve/images/{image['problem_image_id']})"
        result.append(image)
    return result
