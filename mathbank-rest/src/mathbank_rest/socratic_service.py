"""Owner-scoped prototype draft persistence; no learner progression or AWS calls."""
from __future__ import annotations

import logging
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from mathbank_rest.db.postgres import engine
from mathbank_rest.socratic_auth import StaffActor, fail
from mathbank_rest.socratic_contracts import (
    CreateWorkflow,
    Program,
    Strategy,
    UpdateWorkflow,
    Validation,
    Workflow,
    WorkflowSummary,
    canonical_json,
    content_digest,
    initial_program,
)

logger = logging.getLogger(__name__)


def database_error() -> HTTPException:
    logger.error("Socratic draft database operation failed; transaction rolled back")
    return fail(503, "SOCRATIC_STORAGE_UNAVAILABLE", "Draft storage is unavailable; no success is assumed.")


def strategies() -> list[Strategy]:
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT code,domain,label,status,phases FROM orchestration.socratic_strategy ORDER BY domain,code"
            )).mappings()
            return [Strategy.model_validate(dict(row)) for row in rows]
    except SQLAlchemyError:
        raise database_error() from None


def resources(q: str, limit: int, offset: int) -> dict:
    # Never load solution bodies or assessment answer keys into the public catalog.
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT p.problem_id::text, p.canonical_code, p.statement_text,
                    coalesce((SELECT jsonb_agg(jsonb_build_object(
                        'solution_id',s.solution_id,'revision',s.revision,
                        'verification_status',s.verification_status) ORDER BY s.solution_id)
                        FROM core.solution s WHERE s.problem_id=p.problem_id),'[]'::jsonb) AS solutions,
                    coalesce((SELECT jsonb_agg(jsonb_build_object(
                        'route_release_id',r.route_release_id,'solution_id',r.solution_id,'status',r.status,
                        'approach_name',r.approach_name) ORDER BY r.route_release_id)
                        FROM pedagogy.solution_route_release r
                        WHERE r.problem_id=p.problem_id AND r.status='PUBLISHED'),'[]'::jsonb) AS routes
                FROM core.problem p
                WHERE (:empty OR p.canonical_code ILIKE :query ESCAPE '\\'
                    OR p.statement_text ILIKE :query ESCAPE '\\')
                ORDER BY p.canonical_code,p.problem_id LIMIT :limit OFFSET :offset
            """), {"empty": not q, "query": "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%",
                   "limit": limit + 1, "offset": offset}).mappings().all()
            return {"resources": [dict(row) for row in rows[:limit]], "has_more": len(rows) > limit}
    except SQLAlchemyError:
        raise database_error() from None


def dependency_snapshot(conn, program: Program, domain: str) -> dict:
    strategy = conn.execute(text("""
        SELECT code,domain,label,status,phases,provenance
        FROM orchestration.socratic_strategy WHERE code=:code
    """), {"code": program.strategy_code}).mappings().first()
    if not strategy or strategy["domain"] != domain:
        raise fail(422, "SOCRATIC_STRATEGY_MISMATCH", "Choose a strategy in this workflow's domain.")
    result: dict = {"strategy": dict(strategy), "source": {}}
    source = program.source
    if not source.problem_code:
        return result
    problem = conn.execute(text("""
        SELECT problem_id,statement_text FROM core.problem WHERE canonical_code=:code FOR SHARE
    """), {"code": source.problem_code}).mappings().first()
    if not problem:
        raise fail(422, "SOCRATIC_SOURCE_INVALID", "The selected source problem is unavailable.")
    result["source"] = {
        "problem_id": str(problem["problem_id"]), "problem_code": source.problem_code,
        "statement_hash": content_digest(problem["statement_text"]),
    }
    if source.solution_id:
        solution = conn.execute(text("""
            SELECT solution_id,revision,body_markdown,body_latex,verification_status,
                   coalesce(nullif(trim(body_markdown),''),body_latex) AS source
            FROM core.solution WHERE solution_id=:id AND problem_id=:problem FOR SHARE
        """), {"id": source.solution_id, "problem": problem["problem_id"]}).mappings().first()
        if not solution or solution["revision"] != source.solution_revision:
            raise fail(409, "SOCRATIC_SOURCE_STALE", "Solution revision changed or does not belong to this problem.")
        result["source"].update({
            "solution_id": str(source.solution_id), "solution_revision": solution["revision"],
            "solution_hash": content_digest(dict(solution) | {"solution_id": str(solution["solution_id"])}),
        })
    if source.route_release_id:
        route = conn.execute(text("""
            SELECT content_hash,source_hash,status FROM pedagogy.solution_route_release
            WHERE route_release_id=:id AND solution_id=:solution AND problem_id=:problem FOR SHARE
        """), {"id": source.route_release_id, "solution": source.solution_id,
               "problem": problem["problem_id"]}).mappings().first()
        if not route or route["status"] != "PUBLISHED":
            raise fail(409, "SOCRATIC_ROUTE_INVALID", "The route must be published and match the exact problem/solution.")
        from mathbank_rest.route_compiler import source_hash

        current_source_hash = source_hash({
            "solution_id": str(source.solution_id), "statement_text": problem["statement_text"],
            "source": solution["source"], "verification_status": solution["verification_status"],
        })
        if route["source_hash"] != current_source_hash:
            raise fail(409, "SOCRATIC_ROUTE_STALE", "The published route predates the current source; choose a current release.")
        result["source"]["route"] = {"route_release_id": str(source.route_release_id), **dict(route)}
    return result


def revision_row(conn, workflow_id: UUID, actor: StaffActor, revision: int | None = None, *, lock=False):
    if lock:
        # Read the revision in a fresh statement after waiting for any previous writer.
        conn.execute(text("""
            SELECT workflow_id FROM orchestration.socratic_workflow
            WHERE workflow_id=:id AND owner_id=:owner FOR UPDATE
        """), {"id": workflow_id, "owner": actor.actor_id})
    row = conn.execute(text("""
        SELECT w.workflow_id,w.owner_id,w.title,w.domain,r.revision,r.content_hash,
               r.program,r.dependencies,r.created_at AS updated_at
        FROM orchestration.socratic_workflow w
        JOIN orchestration.socratic_revision r ON r.workflow_id=w.workflow_id
            AND r.revision=coalesce(:revision,w.revision)
        WHERE w.workflow_id=:id AND w.owner_id=:owner
    """),
        {"id": workflow_id, "owner": actor.actor_id, "revision": revision}).mappings().first()
    if not row:
        raise fail(404, "SOCRATIC_DRAFT_NOT_FOUND", "Draft not found.")
    return row


def dto(row) -> Workflow:
    return Workflow.model_validate({key: row[key] for key in (
        "workflow_id", "title", "domain", "revision", "content_hash", "updated_at", "program",
    )})


def get_workflow(workflow_id: UUID, actor: StaffActor, revision: int | None = None) -> Workflow:
    try:
        with engine.connect() as conn:
            return dto(revision_row(conn, workflow_id, actor, revision))
    except SQLAlchemyError:
        raise database_error() from None


def list_workflows(actor: StaffActor, limit: int, offset: int) -> dict:
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT workflow_id,title,domain,revision,content_hash,updated_at
                FROM orchestration.socratic_workflow WHERE owner_id=:owner
                ORDER BY updated_at DESC,workflow_id LIMIT :limit OFFSET :offset
            """), {"owner": actor.actor_id, "limit": limit + 1, "offset": offset}).mappings().all()
            return {"workflows": [WorkflowSummary.model_validate(dict(row)) for row in rows[:limit]],
                    "has_more": len(rows) > limit}
    except SQLAlchemyError:
        raise database_error() from None


def command_replay(conn, actor: StaffActor, operation: str, key: str, request_hash: str):
    # Transaction-scoped advisory lock also serializes first-use duplicate create requests.
    conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:scope,0))"),
                 {"scope": canonical_json([actor.actor_id, operation, key])})
    row = conn.execute(text("""
        SELECT request_hash,workflow_id,revision FROM orchestration.socratic_command
        WHERE owner_id=:owner AND operation=:operation AND idempotency_key=:key
    """), {"owner": actor.actor_id, "operation": operation, "key": key}).mappings().first()
    if row:
        if row["request_hash"] != request_hash:
            raise fail(409, "SOCRATIC_IDEMPOTENCY_CONFLICT", "This idempotency key was used with different input.")
        return dto(revision_row(conn, row["workflow_id"], actor, row["revision"]))
    return None


def record_revision(conn, actor: StaffActor, workflow_id: UUID, revision: int, digest: str,
                    program: Program, dependencies: dict, operation: str, key: str, request_hash: str):
    source = program.source
    conn.execute(text("""
        INSERT INTO orchestration.socratic_revision
        (workflow_id,revision,content_hash,author_id,strategy_code,program,dependencies,
         problem_id,solution_id,solution_revision,route_release_id)
        VALUES (:id,:revision,:hash,:owner,:strategy,CAST(:program AS jsonb),CAST(:dependencies AS jsonb),
                :problem,:solution,:solution_revision,:route)
    """), {"id": workflow_id, "revision": revision, "hash": digest, "owner": actor.actor_id,
           "strategy": program.strategy_code, "program": canonical_json(program.model_dump(mode="json")),
           "dependencies": canonical_json(dependencies),
           "problem": dependencies["source"].get("problem_id"), "solution": source.solution_id,
           "solution_revision": source.solution_revision, "route": source.route_release_id})
    conn.execute(text("""
        INSERT INTO orchestration.socratic_command
        (owner_id,operation,idempotency_key,request_hash,workflow_id,revision)
        VALUES (:owner,:operation,:key,:request_hash,:id,:revision)
    """), {"owner": actor.actor_id, "operation": operation, "key": key,
           "request_hash": request_hash, "id": workflow_id, "revision": revision})
    evidence = canonical_json({"revision": revision, "content_hash": digest, "prototype_only": True})
    conn.execute(text("""
        INSERT INTO audit.action_log(actor_type,actor_id,action,entity_type,entity_id,after_state,request_id)
        VALUES ('ADMIN',:owner,'SOCRATIC_DRAFT_SAVED','SOCRATIC_WORKFLOW',:id,CAST(:evidence AS jsonb),:key)
    """), {"owner": actor.actor_id, "id": str(workflow_id), "evidence": evidence, "key": key})
    conn.execute(text("""
        INSERT INTO pipeline.outbox_event(event_type,aggregate_type,aggregate_id,payload)
        VALUES ('SOCRATIC_DRAFT_SAVED','SOCRATIC_WORKFLOW',:id,CAST(:evidence AS jsonb))
    """), {"id": str(workflow_id), "evidence": evidence})


def create_workflow(body: CreateWorkflow, actor: StaffActor, key: str) -> Workflow:
    request_hash = content_digest(body.model_dump(mode="json"))
    try:
        with engine.begin() as conn:
            replay = command_replay(conn, actor, "CREATE", key, request_hash)
            if replay:
                return replay
            strategy = conn.execute(text("""
                SELECT code FROM orchestration.socratic_strategy WHERE domain=:domain ORDER BY code LIMIT 1
            """), {"domain": body.domain}).scalar()
            if not strategy:
                raise fail(422, "SOCRATIC_DOMAIN_INVALID", "Choose a registered Socratic domain.")
            program = initial_program(strategy)
            dependencies = dependency_snapshot(conn, program, body.domain)
            digest = content_digest({"title": body.title, "domain": body.domain,
                                     "program": program.model_dump(mode="json"), "dependencies": dependencies})
            workflow_id = uuid4()
            conn.execute(text("""
                INSERT INTO orchestration.socratic_workflow
                (workflow_id,owner_id,title,domain,revision,content_hash)
                VALUES (:id,:owner,:title,:domain,1,:hash)
            """), {"id": workflow_id, "owner": actor.actor_id, "title": body.title,
                   "domain": body.domain, "hash": digest})
            record_revision(conn, actor, workflow_id, 1, digest, program, dependencies, "CREATE", key, request_hash)
            return dto(revision_row(conn, workflow_id, actor))
    except SQLAlchemyError:
        raise database_error() from None


def update_workflow(workflow_id: UUID, body: UpdateWorkflow, actor: StaffActor, key: str) -> Workflow:
    request_hash = content_digest(body.model_dump(mode="json"))
    operation = "UPDATE:" + str(workflow_id)
    try:
        with engine.begin() as conn:
            replay = command_replay(conn, actor, operation, key, request_hash)
            if replay:
                return replay
            row = revision_row(conn, workflow_id, actor, lock=True)
            if row["content_hash"] != body.expected_hash:
                raise fail(409, "SOCRATIC_DRAFT_STALE", "Draft changed; reload before saving.")
            dependencies = dependency_snapshot(conn, body.program, row["domain"])
            old_source = Program.model_validate(row["program"]).source
            if body.program.source == old_source and dependencies["source"] != row["dependencies"]["source"]:
                raise fail(409, "SOCRATIC_SOURCE_STALE", "Source content changed; explicitly reselect its revision.")
            digest = content_digest({"title": row["title"], "domain": row["domain"],
                                     "program": body.program.model_dump(mode="json"), "dependencies": dependencies})
            revision = row["revision"] + 1
            record_revision(conn, actor, workflow_id, revision, digest, body.program,
                            dependencies, operation, key, request_hash)
            conn.execute(text("""
                UPDATE orchestration.socratic_workflow SET revision=:revision,
                content_hash=:hash,updated_at=clock_timestamp() WHERE workflow_id=:id AND owner_id=:owner
            """), {"revision": revision, "hash": digest, "id": workflow_id, "owner": actor.actor_id})
            return dto(revision_row(conn, workflow_id, actor))
    except SQLAlchemyError:
        raise database_error() from None


def validate_workflow(workflow_id: UUID, expected_hash: str, actor: StaffActor) -> Validation:
    try:
        with engine.begin() as conn:
            row = revision_row(conn, workflow_id, actor)
            if row["content_hash"] != expected_hash:
                raise fail(409, "SOCRATIC_DRAFT_STALE", "Draft changed; reload before validating.")
            program = Program.model_validate(row["program"])
            dependencies = dependency_snapshot(conn, program, row["domain"])
            findings = []
            if dependencies != row["dependencies"]:
                findings.append("Source dependencies changed; save a new explicitly selected revision.")
            if not program.source.solution_id:
                findings.append("Select an explicit canonical solution revision.")
            reachable = {program.entry}
            for _ in program.nodes:
                reachable |= {edge.to_key for edge in program.edges if edge.from_key in reachable}
            if any(node.key not in reachable for node in program.nodes):
                findings.append("Every authored node must be reachable from START.")
            if not any(node.key in reachable and node.type == "COMPLETE" for node in program.nodes):
                findings.append("No reachable completion.")
            from mathbank_rest.socratic_preview import activity_findings

            findings += activity_findings(conn, program, row["dependencies"]["source"].get("problem_id"))
            return Validation(valid=not findings, findings=findings)
    except SQLAlchemyError:
        raise database_error() from None
