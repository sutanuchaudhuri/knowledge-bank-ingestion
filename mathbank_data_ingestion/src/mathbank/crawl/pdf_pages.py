"""Numbered question-to-page mapping without OCR or model calls."""
from bisect import bisect_right
import re

import pymupdf as fitz


def question_page_numbers(pdf_bytes: bytes, expected_count: int) -> dict[int, list[int]]:
    """Locate complete consecutive question spans; never guess proportional pages."""
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        texts = [page.get_text("text") or "" for page in doc]
    starts = []
    offset = 0
    for page_text in texts:
        starts.append(offset)
        offset += len(page_text) + 1
    combined = "\n".join(texts)
    for pattern in (
        r"(?m)^[ \t]*(?:#{1,6}[ \t]+)?Problem\s+(\d+)\b",
        r"(?m)^(\d{1,2})\.\s+",
        r"(?m)^\((\d{1,2})\)\s+",
    ):
        headings = []
        for match in re.finditer(pattern, combined):
            if int(match.group(1)) == len(headings) + 1:
                headings.append(match)
        if len(headings) != expected_count:
            continue
        result = {}
        for index, heading in enumerate(headings):
            end = headings[index + 1].start() if index + 1 < len(headings) else len(combined)
            first = bisect_right(starts, heading.start()) - 1
            last = bisect_right(starts, max(heading.start(), end - 1)) - 1
            result[index + 1] = list(range(first + 1, last + 2))
        return result
    raise ValueError(f"Cannot locate all {expected_count} numbered PDF page spans")
