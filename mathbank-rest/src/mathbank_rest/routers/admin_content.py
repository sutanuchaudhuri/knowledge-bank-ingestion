"""Admin: reconcile the DynamoDB content read model against PostgreSQL (requirement 70 C6 §4a, requirement 71 WP4).

``POST /v1/admin/content/reconcile`` reads the authoritative facts from PostgreSQL (read-only transaction, SQL below),
hands them to ``stores.content.reconcile.reconcile`` and returns its report. Drift is reported, not repaired: the
re-enqueue to the publish queue belongs to the authoring plane (WP10). Admin profile only; the runtime profile has no
PostgreSQL and does not mount this router.

Coverage of the endpoint: facts (existence, ``src_rev``, publication state, listing) for COMPETITION, PROBLEM, ACT,
STEP, LI, TAXNODE and MC; the sampled hash rebuild for COMPETITION and ACT (the other types need the migration's
transforms, which ``scripts/content_parity.py`` runs from a repository checkout for every type); FACET partitions of
STEP/LI on request (``include_facets``); S3 Vectors keys against ``vector_state`` on request (``include_vectors``).
"""
from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Callable, Iterator
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from mathbank_rest.db.postgres import engine
from mathbank_rest.micro_course_service import record_audit_event
from mathbank_rest.security import Actor, admin_actor, require_admin_api_key
from mathbank_rest.stores.content.reconcile import (
    VECTOR_FAMILIES,
    ReconcileReport,
    SourceAggregate,
    is_sampled,
    reconcile,
)

logger = logging.getLogger(__name__)

ContentType = Literal["COMPETITION", "PROBLEM", "ACT", "STEP", "LI", "TAXNODE", "MC"]
SUPPORTED_TYPES: tuple[ContentType, ...] = ("COMPETITION", "PROBLEM", "ACT", "STEP", "LI", "TAXNODE", "MC")
# pipeline.content_revision.aggregate_type per content type (requirement 70 §4a event table)
REV_AGGREGATE = {"COMPETITION": "CATALOG", "PROBLEM": "PROBLEM", "ACT": "ACTIVITY", "STEP": "SOLUTION_DAG",
                 "LI": "LEARNING_ITEM", "TAXNODE": "TAXONOMY", "MC": "MC_RELEASE"}

router = APIRouter(prefix="/v1/admin/content", tags=["admin-content"], dependencies=[Depends(require_admin_api_key)])
_last: dict[str, Any] = {}


class ReconcileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    types: list[ContentType] | None = Field(default=None, description="default: every supported type")
    sample_pct: float = Field(default=5.0, ge=0, le=100, description="share of aggregates whose payload hash is rebuilt; 100 = the weekly full run")
    include_vectors: bool = Field(default=False, description="list S3 Vectors keys per family and compare with vector_state (VECTOR_STORE=s3vectors)")
    include_facets: bool = Field(default=False, description="also reconcile the STEP/LI FACET partitions (one Query per partition)")
    max_diffs: int = Field(default=1000, ge=1, le=10_000)


# ------------------------------------------------------------------ PostgreSQL facts (read-only)

class _Ctx:
    def __init__(self, conn: Any, req: ReconcileRequest, seed: str) -> None:
        self.conn, self.req, self.seed = conn, req, seed
        self.revisions: dict[tuple[str, str], int] = {}
        self.notes: list[str] = []

    def rev(self, type_: str, ident: Any) -> int:
        return self.revisions.get((REV_AGGREGATE[type_], str(ident)), 0)

    def rows(self, sql: str) -> Iterator[dict]:
        yield from (dict(r) for r in self.conn.execute(text(sql)).mappings())

    def sampled(self, pk: str, sk: str) -> bool:
        return is_sampled(pk, sk, self.req.sample_pct, self.seed)


def _vec_exists(entity_col: str, entity_expr: str, kinds: tuple[str, ...]) -> str:
    """The ACTIVE-vector predicate of the migration's ``_vec_cte``: the entity has a vector, so it has FACET items."""
    kinds_sql = ", ".join(f"'{k}'" for k in kinds)
    return f"""EXISTS (SELECT 1 FROM search.embedding e
                   JOIN search.chunk c ON c.chunk_id = e.chunk_id
                   JOIN search.representation r ON r.representation_id = c.representation_id
                   JOIN search.embedding_model em ON em.embedding_model_id = e.embedding_model_id
                  WHERE {entity_col} = {entity_expr} AND r.status = 'ACTIVE' AND e.status = 'ACTIVE' AND em.status = 'ACTIVE'
                    AND r.representation_kind IN ({kinds_sql}))"""


_COMPETITION_SQL = """
SELECT competition_id, external_code, name, organization, country, level FROM core.competition
 ORDER BY name, competition_id"""

_PROBLEM_SQL = """
SELECT p.problem_id, p.canonical_code, (p.status = 'ACTIVE') AS published, comp.external_code AS competition_code
  FROM core.problem p
  JOIN core.paper pa ON pa.paper_id = p.paper_id
  JOIN core.competition_edition ed ON ed.edition_id = pa.edition_id
  JOIN core.competition comp ON comp.competition_id = ed.competition_id
 ORDER BY p.canonical_code"""

# (persistence_mode = 'STATIC' OR source_type = 'PRECOMPILED') AND status = 'ACTIVE' is what the migration projects
_ACT_SQL = """
SELECT activity_id, activity_type, prompt, options, target_skill, target_skill_id, source_problem_id,
       estimated_seconds, source_type, persistence_mode, status, created_at,
       (status = 'ACTIVE') AS published
  FROM activity.definition
 WHERE persistence_mode = 'STATIC' OR source_type = 'PRECOMPILED'
 ORDER BY activity_id"""

_STEP_SQL = f"""
SELECT s.solution_step_id, s.solution_id, s.problem_id, (s.publication_status = 'PUBLISHED') AS published,
       {_vec_exists('c.solution_step_id', 's.solution_step_id', ('SOLUTION_STEP',))} AS has_vec
  FROM pedagogy.solution_step s
  JOIN core.problem p ON p.problem_id = s.problem_id
 ORDER BY s.solution_step_id"""

_LI_SQL = f"""
SELECT li.learning_item_id, li.target_subconcept_node_id,
       (li.review_status = 'APPROVED' AND li.student_visible AND li.no_proof) AS published,
       {_vec_exists('c.learning_item_id', 'li.learning_item_id', ('LEARNING_ITEM_QUESTION', 'LEARNING_ITEM_SKILL_SIGNATURE'))} AS has_vec
  FROM pedagogy.learning_item li
 ORDER BY li.learning_item_id"""

_TAXNODE_SQL = "SELECT taxonomy_node_id, node_type FROM pedagogy.taxonomy_node ORDER BY taxonomy_node_id"

_MC_SQL = """
SELECT c.micro_course_id, c.canonical_code,
       EXISTS (SELECT 1 FROM pedagogy.micro_course_release r
                WHERE r.micro_course_id = c.micro_course_id AND r.status = 'PUBLISHED') AS published
  FROM pedagogy.micro_course c
 WHERE c.is_active
 ORDER BY c.canonical_code"""


def _state(flag: Any) -> Literal["ACTIVE", "WITHDRAWN"]:
    return "ACTIVE" if flag else "WITHDRAWN"


def _competitions(ctx: _Ctx) -> Iterator[SourceAggregate]:
    for r in ctx.rows(_COMPETITION_SQL):
        pk, sk = "CATALOG#COMPETITION", f"COMP#{r['name']}#{r['competition_id']}"
        payload = ({k: r[k] for k in ("competition_id", "external_code", "name", "organization", "country", "level")}
                   if ctx.sampled(pk, sk) else None)
        yield SourceAggregate(type="COMPETITION", pk=pk, sk=sk, id=str(r["competition_id"]), payload=payload,
                              src_rev=ctx.rev("COMPETITION", r["competition_id"]), list_pk=pk)


def _problems(ctx: _Ctx) -> Iterator[SourceAggregate]:
    for r in ctx.rows(_PROBLEM_SQL):
        active = bool(r["published"]) and bool(r["competition_code"])
        yield SourceAggregate(
            type="PROBLEM", pk=f"PROBLEM#{r['canonical_code']}", sk="META", id=r["canonical_code"],
            state=_state(r["published"]), src_rev=ctx.rev("PROBLEM", r["problem_id"]),
            list_index="GSI2" if active else None, list_pk=f"PLIST#{r['competition_code']}" if active else None)


def _activities(ctx: _Ctx) -> Iterator[SourceAggregate]:
    cols = ("activity_id", "activity_type", "prompt", "options", "target_skill", "target_skill_id", "source_problem_id",
            "estimated_seconds", "source_type", "persistence_mode", "status", "created_at")
    for r in ctx.rows(_ACT_SQL):
        pk = f"ACT#{r['activity_id']}"
        payload = {k: r[k] for k in cols} if r["published"] and ctx.sampled(pk, "META") else None
        yield SourceAggregate(type="ACT", pk=pk, sk="META", id=str(r["activity_id"]), state=_state(r["published"]),
                              src_rev=ctx.rev("ACT", r["activity_id"]), payload=payload)


def _steps(ctx: _Ctx) -> Iterator[SourceAggregate]:
    for r in ctx.rows(_STEP_SQL):
        sid = r["solution_step_id"]
        yield SourceAggregate(type="STEP", pk=f"STEP#{sid}", sk="META", id=sid, state=_state(r["published"]),
                              src_rev=ctx.rev("STEP", r["solution_id"]))
        if ctx.req.include_facets:
            yield SourceAggregate(type="FACET", pk=f"FACET#STEP#PROBLEM#{r['problem_id']}", sk=str(sid),
                                  state=_state(r["published"] and r["has_vec"]), id=sid,
                                  list_pk=f"FACET#STEP#PROBLEM#{r['problem_id']}", src_rev=ctx.rev("STEP", r["solution_id"]))


def _learning_items(ctx: _Ctx) -> Iterator[SourceAggregate]:
    for r in ctx.rows(_LI_SQL):
        lid = r["learning_item_id"]
        rev = ctx.rev("LI", lid)
        yield SourceAggregate(type="LI", pk=f"LI#{lid}", sk="META", id=lid, state=_state(r["published"]), src_rev=rev)
        node = r["target_subconcept_node_id"]
        if ctx.req.include_facets and node is not None:
            pk = f"FACET#LI#TARGET_SUBCONCEPT#{node}"
            yield SourceAggregate(type="FACET", pk=pk, sk=str(lid), id=lid, list_pk=pk, src_rev=rev,
                                  state=_state(r["published"] and r["has_vec"]))


def _taxonomy(ctx: _Ctx) -> Iterator[SourceAggregate]:
    for r in ctx.rows(_TAXNODE_SQL):
        nid = r["taxonomy_node_id"]
        yield SourceAggregate(type="TAXNODE", pk=f"TAXNODE#{nid}", sk="META", id=nid, src_rev=ctx.rev("TAXNODE", nid),
                              list_index="GSI2", list_pk=f"TAXTYPE#{r['node_type']}")


def _micro_courses(ctx: _Ctx) -> Iterator[SourceAggregate]:
    for r in ctx.rows(_MC_SQL):
        code = r["canonical_code"]
        yield SourceAggregate(type="MC", pk=f"MC#{code}", sk="META", id=code, state=_state(r["published"]),
                              src_rev=ctx.rev("MC", r["micro_course_id"]),
                              list_index="GSI2" if r["published"] else None, list_pk="CATALOG#MC" if r["published"] else None)


_BUILDERS: dict[str, Callable[[_Ctx], Iterator[SourceAggregate]]] = {
    "COMPETITION": _competitions, "PROBLEM": _problems, "ACT": _activities, "STEP": _steps, "LI": _learning_items,
    "TAXNODE": _taxonomy, "MC": _micro_courses,
}


def _revisions(ctx: _Ctx) -> None:
    if ctx.conn.execute(text("SELECT to_regclass('pipeline.content_revision')")).scalar() is None:
        ctx.notes.append("pipeline.content_revision does not exist yet: src_rev is compared against 0, the backfill value")
        return
    for r in ctx.rows("SELECT aggregate_type, aggregate_id::text AS aggregate_id, rev FROM pipeline.content_revision"):
        ctx.revisions[(r["aggregate_type"], r["aggregate_id"])] = int(r["rev"])


def build_sources(conn: Any, req: ReconcileRequest, seed: str) -> tuple[list[SourceAggregate], list[str]]:
    """Source aggregates for the requested types from an open (read-only) connection; also the notes to report."""
    ctx = _Ctx(conn, req, seed)
    _revisions(ctx)
    out: list[SourceAggregate] = []
    for t in req.types or SUPPORTED_TYPES:
        out.extend(_BUILDERS[t](ctx))
    return out, ctx.notes


def _read_sources(req: ReconcileRequest, seed: str) -> tuple[list[SourceAggregate], list[str]]:
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        return build_sources(conn, req, seed)


# ------------------------------------------------------------------ vectors and audit

_FAMILY_FOR_TYPE: dict[str, list[str]] = {}
for _family, (_type, _attr) in VECTOR_FAMILIES.items():
    _FAMILY_FOR_TYPE.setdefault(_type, []).append(_family)


def _vector_keys(req: ReconcileRequest) -> dict[str, list[str]]:
    from mathbank_rest.vector_catalog import Family
    from mathbank_rest.vector_store import get_vector_store

    store = get_vector_store()
    types = req.types or SUPPORTED_TYPES
    families = [f for t in types for f in _FAMILY_FOR_TYPE.get(t, ()) if f != "solution"]
    return {f: list(store.keys(Family(f))) for f in families}


def _audit(actor: Actor, req: ReconcileRequest, report: ReconcileReport) -> None:
    after = {"actor": actor.id, "types": req.types or list(SUPPORTED_TYPES), "sample_pct": req.sample_pct,
             "ok": report.ok, "diff_count": report.diff_count, "by_kind": report.by_kind()}
    with engine.begin() as conn:
        record_audit_event(conn, "ADMIN", actor.id, "CONTENT_RECONCILE", "content", "mb-content", after_state=after)


# ------------------------------------------------------------------ routes

@router.post("/reconcile", response_model=ReconcileReport, summary="Reconcile mb-content against PostgreSQL")
def reconcile_content(body: ReconcileRequest, actor: Annotated[Actor, Depends(admin_actor("publish"))]) -> ReconcileReport:
    """Compare existence, `src_rev`, publication state and listing of every aggregate (plus a sampled hash rebuild and,
    on request, S3 Vectors keys) with `mb-content`. Read-only on both sides; the call itself is audited."""
    seed = dt.datetime.now(dt.UTC).date().isoformat()
    sources, notes = _read_sources(body, seed)
    vectors = _vector_keys(body) if body.include_vectors else None
    report = reconcile(sources, sample_pct=body.sample_pct, sample_seed=seed, vector_keys_by_family=vectors,
                       max_diffs=body.max_diffs)
    report.notes[:0] = notes
    _audit(actor, body, report)
    _last.clear()
    _last.update(actor=actor.id, at=report.started_at, ok=report.ok, diff_count=report.diff_count,
                 by_kind=report.by_kind(), types=[t.type for t in report.types])
    logger.info("content reconcile by %s: ok=%s diffs=%d", actor.id, report.ok, report.diff_count)
    return report


@router.get("/reconcile/status", summary="Summary of the last reconcile run served by this process")
def reconcile_status(_actor: Annotated[Actor, Depends(admin_actor())]) -> dict:
    """In-process memory only: a new Lambda container starts empty. Persisted daily reports are written by the
    `mb-content-reconcile` job to `s3://mathbank-data-<env>/content/reconcile/<date>.json`."""
    return {"last_run": dict(_last) or None}
