"""Explicit staff review of missing figures, question edits and original draft questions."""
from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from mathbank_rest import corpus_authoring as runtime
from mathbank_rest import object_store
from mathbank_rest.db.postgres import engine
from mathbank_rest.security import require_admin_api_key

router = APIRouter(prefix="/v1/admin/corpus", tags=["admin-corpus"],
                   dependencies=[Depends(require_admin_api_key)])


class DraftRequest(runtime.ProblemBody):
    kind: Literal["TEXT_EDIT", "NEW_PROBLEM"]
    problem_code: str | None = Field(default=None, max_length=200)
    expected_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    note: str = Field(min_length=3, max_length=2000)


class ImageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    problem_code: str = Field(min_length=1, max_length=200)
    side: Literal["problem", "solution"]
    mime_type: Literal["image/png", "image/jpeg"]
    data_base64: str = Field(min_length=1, max_length=7_000_000)
    note: str = Field(min_length=3, max_length=2000)
    rights_confirmed: Literal[True]
    expected_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    theme: str = Field(min_length=5, max_length=2000)
    confirm_paid: Literal[True]


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    decision: Literal["APPROVED", "REJECTED"]
    note: str = Field(min_length=3, max_length=2000)
    expected_revision: int = Field(ge=1)


class DraftUpdate(runtime.ProblemBody):
    note: str = Field(min_length=3, max_length=2000)
    expected_revision: int = Field(ge=1)


def run(fn, *args, **kwargs):
    try:
        with engine.begin() as conn:
            return fn(conn, *args, **kwargs)
    except runtime.AuthoringError as exc:
        raise HTTPException(exc.status, detail=str(exc)) from None
    except object_store.ObjectStoreError:
        raise HTTPException(503, detail="Private image storage is unavailable.") from None
    except ProgrammingError as exc:
        if getattr(exc.orig, "sqlstate", None) == "42P01" or getattr(exc.orig, "pgcode", None) == "42P01":
            raise HTTPException(503, detail="Corpus authoring schema is unavailable. Apply migration 025 to the intended database.") from None
        raise


@router.get("/problems")
def problems(competition: str | None = None, year: int | None = None,
             paper: str | None = None, number: int | None = None, q: str = "",
             missing_only: bool = True, limit: Annotated[int, Query(ge=1, le=100)] = 20,
             offset: Annotated[int, Query(ge=0)] = 0):
    return run(runtime.inventory, competition, year, paper, number, q, missing_only, limit, offset)


@router.get("/problems/{code}")
def detail(code: str):
    def load(conn):
        problem = runtime.resolve(conn, code)
        problem["expected_hash"] = runtime.digest(problem["statement_text"])
        return problem
    return run(load)


@router.post("/drafts", status_code=201)
def create_draft(body: DraftRequest):
    if body.kind == "TEXT_EDIT" and not body.problem_code:
        raise HTTPException(422, detail="Select the canonical problem before editing.")
    if body.kind == "NEW_PROBLEM" and body.problem_code:
        raise HTTPException(422, detail="New problems must not claim an official contest identity.")
    payload = body.model_dump(exclude={"kind", "problem_code", "note", "expected_hash"})
    return run(runtime.save_draft, body.kind, body.problem_code, payload, body.note,
               expected_hash=body.expected_hash)


@router.put("/drafts/{draft_id}")
def update_draft(draft_id: UUID, body: DraftUpdate):
    def update(conn):
        row = conn.execute(text("SELECT kind,state,revision FROM ingest.corpus_draft "
                                "WHERE draft_id=:id FOR UPDATE"), {"id": draft_id}).mappings().first()
        if not row:
            raise runtime.AuthoringError(404, "Draft not found")
        if row["state"] != "DRAFT" or row["kind"] != "NEW_PROBLEM":
            raise runtime.AuthoringError(409, "Only pending new-problem drafts can be edited.")
        if row["revision"] != body.expected_revision:
            raise runtime.AuthoringError(409, "Draft changed. Reload before editing.")
        import json
        conn.execute(text("UPDATE ingest.corpus_draft SET payload=CAST(:payload AS jsonb),note=:note,revision=revision+1 "
                          "WHERE draft_id=:id"),
                     {"id": draft_id, "payload": json.dumps(body.model_dump(exclude={"note", "expected_revision"})),
                      "note": body.note})
        return {"draft_id": str(draft_id), "state": "DRAFT", "revision": row["revision"] + 1}
    return run(update)


@router.post("/images", status_code=201)
def upload(body: ImageRequest):
    def save(conn):
        problem = runtime.resolve(conn, body.problem_code)
        if runtime.digest(problem["statement_text"]) != body.expected_hash:
            raise runtime.AuthoringError(409, "Question changed. Reload before uploading a source figure.")
        data = runtime.image_bytes(body.data_base64, body.mime_type)
        stored = object_store.put_bytes(data, "png")
        try:
            return runtime.save_draft(conn, "IMAGE", body.problem_code,
                {"side": body.side, "mime_type": "image/png", "rights_confirmed": True},
                body.note, object_key=stored["object_key"], expected_hash=body.expected_hash)
        except Exception:
            object_store.delete_object(stored["object_key"])
            raise
    return run(save)


@router.post("/generate", status_code=201)
def generate(body: GenerateRequest):
    run(lambda conn: conn.execute(text("SELECT draft_id FROM ingest.corpus_draft LIMIT 0")).all())
    try:
        payload = runtime.generate_problem(body.theme)
    except runtime.AuthoringError as exc:
        raise HTTPException(exc.status, detail=str(exc)) from None
    return run(runtime.save_draft, "NEW_PROBLEM", None, payload,
               "Explicit AI draft: " + body.theme, origin="AI")


@router.get("/drafts")
def drafts(state: Literal["DRAFT", "APPROVED", "REJECTED"] = "DRAFT",
           limit: Annotated[int, Query(ge=1, le=100)] = 20,
           offset: Annotated[int, Query(ge=0)] = 0):
    def load(conn):
        rows = conn.execute(text("""
            SELECT d.draft_id,d.kind,d.state,d.origin,d.payload,d.note,d.review_note,
                   d.created_at,d.revision,d.provenance,p.canonical_code
            FROM ingest.corpus_draft d LEFT JOIN core.problem p USING(problem_id)
            WHERE d.state=:state ORDER BY d.created_at DESC LIMIT :limit OFFSET :offset
        """), {"state": state, "limit": limit + 1, "offset": offset}).mappings().all()
        return {"items": [dict(row) for row in rows[:limit]], "hasMore": len(rows) > limit}
    return run(load)


@router.get("/drafts/{draft_id}/image")
def draft_image(draft_id: UUID):
    def load(conn):
        key = conn.execute(text("SELECT object_key FROM ingest.corpus_draft WHERE draft_id=:id "
                                "AND kind='IMAGE'"), {"id": draft_id}).scalar()
        if not key:
            raise runtime.AuthoringError(404, "Image draft not found")
        return object_store.read_bytes(key)
    return Response(run(load), media_type="image/png",
                    headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.post("/drafts/{draft_id}/review")
def review(draft_id: UUID, body: ReviewRequest):
    return run(runtime.review, draft_id, body.decision, body.note, body.expected_revision)
