"""Admin-only reviewed corpus repairs; uploads and generated drafts remain private."""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import struct

import fitz
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from mathbank_rest import runtime_ai
from mathbank_rest.db.problem_images import STUDENT_IMAGE_FILTER


class AuthoringError(ValueError):
    def __init__(self, status: int, message: str):
        self.status = status
        super().__init__(message)


class ProblemBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    statement: str = Field(min_length=10, max_length=20000)
    solution: str = Field(default="", max_length=30000)
    answer: str = Field(default="", max_length=500)
    diagram_required: bool = False


def digest(statement: str) -> str:
    return hashlib.sha256(statement.encode()).hexdigest()


def resolve(conn, code: str, *, lock: bool = False) -> dict:
    row = conn.execute(text(
        "SELECT problem_id,canonical_code,statement_text FROM core.problem "
        "WHERE canonical_code=:code" + (" FOR UPDATE" if lock else "")
    ), {"code": code}).mappings().first()
    if not row:
        raise AuthoringError(404, "Problem not found")
    return dict(row)


def inventory(conn, competition, year, paper, number, query, missing_only, limit, offset):
    params = {"competition": competition, "year": year, "paper": paper,
              "number": number, "query": query, "missing": missing_only,
              "limit": limit + 1, "offset": offset}
    rows = conn.execute(text(f"""
        WITH inventory AS (
            SELECT p.canonical_code,p.problem_number,p.statement_text,p.source_url,
                   c.external_code AS competition,ed.year,pa.paper_code,
                   (SELECT count(*) FROM core.problem_image i WHERE i.problem_id=p.problem_id
                       AND {STUDENT_IMAGE_FILTER}) AS diagram_count,
                   p.statement_text ~* '(diagram|figure|shown below|shown above|pictured)' AS diagram_required
            FROM core.problem p JOIN core.paper pa USING(paper_id)
            JOIN core.competition_edition ed USING(edition_id)
            JOIN core.competition c USING(competition_id)
            WHERE (CAST(:competition AS text) IS NULL OR c.external_code=:competition)
              AND (CAST(:year AS integer) IS NULL OR ed.year=:year)
              AND (CAST(:paper AS text) IS NULL OR pa.paper_code=:paper)
              AND (CAST(:number AS integer) IS NULL OR p.problem_number=:number)
              AND (:query='' OR p.canonical_code ILIKE '%'||:query||'%')
        )
        SELECT *, (diagram_required AND diagram_count=0) AS diagram_missing
        FROM inventory WHERE NOT :missing OR (diagram_required AND diagram_count=0)
        ORDER BY competition,year,paper_code,problem_number LIMIT :limit OFFSET :offset
    """), params).mappings().all()
    return {"items": [dict(row) for row in rows[:limit]], "hasMore": len(rows) > limit,
            "warnings": ["Missing-diagram detection is a statement-text heuristic, not a complete source audit."]}


def save_draft(conn, kind, code, payload, note, origin="ADMIN", object_key=None, expected_hash=None):
    problem = resolve(conn, code) if code else None
    current_hash = digest(problem["statement_text"]) if problem else None
    if kind in ("TEXT_EDIT", "IMAGE") and current_hash != expected_hash:
        raise AuthoringError(409, "Question changed. Reload before saving the edit.")
    if kind == "TEXT_EDIT":
        payload = {**payload, "before_statement": problem["statement_text"]}
    row = conn.execute(text("""
        INSERT INTO ingest.corpus_draft(kind,problem_id,payload,base_hash,note,origin,object_key,provenance)
        VALUES (:kind,:pid,CAST(:payload AS jsonb),:hash,:note,:origin,:key,CAST(:provenance AS jsonb))
        RETURNING draft_id,state,kind,origin,revision,created_at
    """), {"kind": kind, "pid": problem["problem_id"] if problem else None,
           "payload": json.dumps(payload), "hash": current_hash, "note": note,
           "origin": origin, "key": object_key,
           "provenance": json.dumps({"creation_note": note,
               **({"model": runtime_ai.model_name()} if origin == "AI" else {})})}).mappings().one()
    return dict(row)


def image_bytes(encoded: str, mime: str) -> bytes:
    if mime not in ("image/png", "image/jpeg"):
        raise AuthoringError(415, "Upload PNG or JPEG; SVG and documents are not accepted.")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise AuthoringError(422, "Invalid image encoding") from None
    if not 0 < len(data) <= 5 * 1024 * 1024:
        raise AuthoringError(413, "Image must be between 1 byte and 5 MB.")
    magic = b"\x89PNG\r\n\x1a\n" if mime == "image/png" else b"\xff\xd8\xff"
    if not data.startswith(magic):
        raise AuthoringError(415, "Image type does not match its contents.")
    width, height = image_dimensions(data, mime)
    if not width or not height or width * height > 16_000_000:
        raise AuthoringError(413, "Image dimensions exceed 16 megapixels.")
    try:
        pixmap = fitz.Pixmap(data)
        if (pixmap.width, pixmap.height) != (width, height):
            raise AuthoringError(422, "Decoded image dimensions do not match its header.")
        if pixmap.n - pixmap.alpha > 3:
            pixmap = fitz.Pixmap(fitz.csRGB, pixmap)
        normalized = pixmap.tobytes("png")
        if len(normalized) > 25 * 1024 * 1024:
            raise AuthoringError(413, "Normalized image exceeds the 25 MB storage limit.")
        return normalized
    except (RuntimeError, ValueError) as exc:
        if isinstance(exc, AuthoringError):
            raise
        raise AuthoringError(422, "Image cannot be decoded.") from None


def image_dimensions(data: bytes, mime: str) -> tuple[int, int]:
    if mime == "image/png":
        if len(data) >= 24 and data[12:16] == b"IHDR":
            return struct.unpack(">II", data[16:24])
    else:
        offset = 2
        while offset + 4 <= len(data) and data[offset] == 0xFF:
            while offset < len(data) and data[offset] == 0xFF:
                offset += 1
            if offset >= len(data):
                break
            marker = data[offset]
            offset += 1
            if marker in (0xDA, 0xD9):
                break
            if marker == 0x01 or 0xD0 <= marker <= 0xD7:
                continue
            if offset + 2 > len(data):
                break
            length = int.from_bytes(data[offset:offset + 2], "big")
            if length < 2 or offset + length > len(data):
                break
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                          0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF) and length >= 7:
                height, width = struct.unpack(">HH", data[offset + 3:offset + 7])
                return width, height
            offset += length
    raise AuthoringError(422, "Image dimensions cannot be read.")


def generate_problem(theme: str) -> dict:
    from openai import OpenAIError

    try:
        response = runtime_ai.client().chat.completions.create(
            model=runtime_ai.model_name(), temperature=0.4, max_tokens=8000,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content":
                 "Write an original competition-style practice problem, not a copied official question. "
                 "Return JSON with statement, solution, answer and diagram_required=false. "
                 "Use Markdown and dollar-delimited LaTeX. The question must be self-contained without "
                 "an image. Include a worked solution for staff review. This is an unverified draft, "
                 "never claim correctness certification or official contest provenance."},
                {"role": "user", "content": theme},
            ],
        )
    except (OpenAIError, RuntimeError):
        raise AuthoringError(502, "Problem generation unavailable; no draft was published.") from None
    try:
        body = ProblemBody.model_validate_json(response.choices[0].message.content or "")
    except (ValueError, IndexError):
        raise AuthoringError(502, "Generation returned an invalid problem draft.") from None
    if not body.solution or body.diagram_required:
        raise AuthoringError(502, "Generated draft must include a solution and need no missing diagram.")
    return body.model_dump()


def review(conn, draft_id, decision, note, expected_revision=1):
    draft = conn.execute(text("SELECT * FROM ingest.corpus_draft WHERE draft_id=:id FOR UPDATE"),
                         {"id": draft_id}).mappings().first()
    if not draft:
        raise AuthoringError(404, "Draft not found")
    if draft["revision"] != expected_revision:
        raise AuthoringError(409, "Draft changed. Reload and review the latest version before publishing.")
    if draft["state"] != "DRAFT":
        if draft["state"] == decision and draft["review_note"] == note:
            code = conn.execute(text("SELECT canonical_code FROM core.problem WHERE problem_id=:id"),
                                {"id": draft["problem_id"]}).scalar() if decision == "APPROVED" and draft["problem_id"] else None
            return {"draft_id": str(draft_id), "state": decision, "canonical_code": code,
                    "warning": "Already reviewed; no duplicate publication."}
        raise AuthoringError(409, "This draft was already reviewed")
    payload = draft["payload"]
    code = None
    if decision == "APPROVED":
        if draft["kind"] == "NEW_PROBLEM":
            body = ProblemBody.model_validate(payload)
            if body.diagram_required:
                raise AuthoringError(422, "New problem needs a diagram. Make the draft self-contained before approval.")
            if not body.solution:
                raise AuthoringError(422, "A new problem needs a worked solution for review.")
            identifier = str(draft_id).replace("-", "").upper()
            code = f"GENERATED_{identifier}_Q01"
            # A dedicated nonofficial paper per draft avoids official contest-number collisions.
            competition = conn.execute(text("""
                INSERT INTO core.competition(external_code,name,organization)
                VALUES ('MATHBANK_GENERATED','MathBank authored practice','MathBank')
                ON CONFLICT (external_code) DO UPDATE SET external_code=EXCLUDED.external_code
                RETURNING competition_id
            """)).scalar_one()
            edition = conn.execute(text("""
                INSERT INTO core.competition_edition(competition_id,year,season,edition_label)
                VALUES (:id,extract(year FROM now())::int,'AUTHORED','Practice')
                ON CONFLICT (competition_id,year,season,edition_label)
                DO UPDATE SET edition_label=EXCLUDED.edition_label RETURNING edition_id
            """), {"id": competition}).scalar_one()
            paper = conn.execute(text("""
                INSERT INTO core.paper(edition_id,external_code,paper_code,official)
                VALUES (:id,:code,:code,false) RETURNING paper_id
            """), {"id": edition, "code": f"AUTHORED_{identifier}"}).scalar_one()
            pid = conn.execute(text("""
                INSERT INTO core.problem(paper_id,problem_number,canonical_code,statement_text,
                                         official_answer,content_hash,admin_edited_at)
                VALUES (:paper,1,:code,:statement,:answer,:hash,clock_timestamp()) RETURNING problem_id
            """), {"paper": paper, "code": code, "statement": body.statement,
                   "answer": body.answer or None, "hash": digest(body.statement)}).scalar_one()
            conn.execute(text("""
                INSERT INTO core.solution(problem_id,solution_kind,body_markdown,verification_status)
                VALUES (:id,'ADMIN_AUTHORED',:body,'UNVERIFIED')
            """), {"id": pid, "body": body.solution})
            conn.execute(text("UPDATE ingest.corpus_draft SET problem_id=:pid WHERE draft_id=:id"),
                         {"pid": pid, "id": draft_id})
        else:
            problem = conn.execute(text("SELECT * FROM core.problem WHERE problem_id=:id FOR UPDATE"),
                                   {"id": draft["problem_id"]}).mappings().one()
            code = problem["canonical_code"]
            if digest(problem["statement_text"]) != draft["base_hash"]:
                raise AuthoringError(409, "Source question changed. Create a new draft after reloading.")
            if draft["kind"] == "TEXT_EDIT":
                statement = payload["statement"]
                conn.execute(text("""
                    UPDATE core.problem SET statement_text=:statement,content_hash=:hash,
                        statement_latex=NULL,updated_at=now(),admin_edited_at=clock_timestamp()
                    WHERE problem_id=:id
                """), {"statement": statement, "hash": digest(statement), "id": problem["problem_id"]})
                conn.execute(text("""
                    UPDATE search.representation SET status='STALE'
                    WHERE representation_id IN (
                        SELECT representation_id FROM search.chunk WHERE problem_id=:id
                    ) AND representation_kind='PROBLEM_STATEMENT'
                """), {"id": problem["problem_id"]})
            else:
                ordinal = conn.execute(text("SELECT coalesce(max(ordinal),0)+1 FROM core.problem_image "
                                            "WHERE problem_id=:id"), {"id": problem["problem_id"]}).scalar_one()
                conn.execute(text("""
                    INSERT INTO core.problem_image(problem_id,ordinal,local_path,source)
                    VALUES (:id,:ordinal,:path,:source)
                """), {"id": problem["problem_id"], "ordinal": ordinal,
                       "path": "object-store:" + draft["object_key"],
                       "source": "ADMIN_SOURCE_DIAGRAM" if payload["side"] == "problem" else "ADMIN_SOLUTION_DIAGRAM"})
    conn.execute(text("""
        UPDATE ingest.corpus_draft SET state=:state,review_note=:note,reviewed_at=now()
        WHERE draft_id=:id
    """), {"state": decision, "note": note, "id": draft_id})
    return {"draft_id": str(draft_id), "state": decision, "canonical_code": code,
            "warning": "Human approval is not mathematical certification. No paid indexing or graph publication was run."}
