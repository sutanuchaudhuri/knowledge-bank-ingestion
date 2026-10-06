"""Admin import / reconciliation / semantic DAG review (runtime_extension/15, requirements/26 WP3).

Every mutation runs in one transaction that also writes an append-only ``ingest.admin_review_action``
row and, where content changed, a ``pipeline.outbox_event`` that the ``projection_requests`` consumer
turns into a graph/embedding re-projection request. Nothing here writes Neo4j or embeddings directly and
there is no raw Cypher/SQL entry point. Only books with an imported package (today: Prasolov) have
rows; every other corpus returns empty lists until its package is imported (requirements/26 null policy).
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from mathbank_rest.db import textbook_admin

DEPENDENCY_TYPES = ("NEXT", "DEPENDS_ON", "DERIVES_FROM", "USES_RESULT_FROM", "ALTERNATIVE_TO", "BRANCHES_TO",
                    "JOINS_AT", "JUSTIFIES")
CONFLICT_DECISIONS = ("KEEP_EXISTING", "ACCEPT_INCOMING", "MERGE_MANUALLY")
ITEM_DECISIONS = {"APPROVE": "APPROVED", "REJECT": "REJECTED", "NEEDS_REVISION": "NEEDS_REVISION"}
PROJECTION_TARGETS = ("GRAPH_TEXTBOOK_STEPS", "STEP_EMBEDDINGS", "LEARNING_ITEM_EMBEDDINGS", "GRAPH_LEARNING_ITEMS")
PROJECTION_SCOPES = ("BOOK", "PACKAGE", "PROBLEM", "STEP", "LEARNING_ITEM")


class NotFound(LookupError):
    pass


class Invalid(ValueError):
    pass


class Conflict(RuntimeError):
    pass


def _rows(conn: Connection, sql: str, **params: Any) -> list[dict]:
    return [dict(r) for r in conn.execute(text(sql), params).mappings()]


def _one(conn: Connection, sql: str, **params: Any) -> dict | None:
    row = conn.execute(text(sql), params).mappings().first()
    return dict(row) if row else None


def _audit(conn: Connection, target_type: str, target_id: str, action: str, before: Any, after: Any,
           note: str | None) -> int:
    return conn.execute(text(
        "INSERT INTO ingest.admin_review_action (target_type, target_id, action, before_state, after_state, note) "
        "VALUES (:t, :i, :a, CAST(:b AS jsonb), CAST(:af AS jsonb), :n) RETURNING action_id"),
        {"t": target_type, "i": target_id, "a": action, "b": json.dumps(before, default=str),
         "af": json.dumps(after, default=str), "n": note}).scalar_one()


def _outbox(conn: Connection, event_type: str, aggregate_type: str, aggregate_id: str, payload: dict) -> None:
    conn.execute(text(
        "INSERT INTO pipeline.outbox_event (event_type, aggregate_type, aggregate_id, payload) "
        "VALUES (:t, :at, :aid, CAST(:p AS jsonb))"),
        {"t": event_type, "at": aggregate_type, "aid": aggregate_id, "p": json.dumps(payload, default=str)})


# ---------------------------------------------------------------- packages (spec 15 §1-§2)

_PACKAGE_SQL = """
SELECT p.content_package_id::text AS content_package_id, p.package_name, p.package_version, p.book_code,
       p.status, p.status_detail, p.last_scope, p.created_at AS registered_at, p.imported_at, p.updated_at,
       (SELECT count(*) FROM ingest.package_file f WHERE f.content_package_id = p.content_package_id)::int AS files,
       (SELECT count(*) FROM ingest.staging_row s WHERE s.content_package_id = p.content_package_id
           AND s.validation_status = 'REJECTED')::int AS rejected_rows,
       (SELECT count(*) FROM ingest.import_conflict c WHERE c.content_package_id = p.content_package_id
           AND c.resolution_status = 'OPEN')::int AS open_conflicts,
       (SELECT count(*) FROM ingest.import_conflict c WHERE c.content_package_id = p.content_package_id)::int
           AS conflicts,
       (SELECT bool_and(r.reconciled) FROM ingest.reconciliation r
         WHERE r.content_package_id = p.content_package_id AND r.scope = p.last_scope) AS reconciled
  FROM ingest.content_package p
"""


def list_packages(conn: Connection, book: str | None = None) -> list[dict]:
    where = " WHERE p.book_code = :book" if book else ""
    packages = _rows(conn, _PACKAGE_SQL + where + " ORDER BY p.book_code, p.package_name", book=book)
    pending = {(r["scope_id"], r["target"]): r["n"] for r in _rows(conn, """
        SELECT scope_id, target, count(*)::int AS n FROM pipeline.projection_request
         WHERE status = 'PENDING' AND scope_type = 'BOOK' GROUP BY 1, 2""")}
    for p in packages:
        p["postgres"] = p["status"] in ("POSTGRES_COMPLETE", "EMBEDDING", "GRAPH_PROJECTING", "COMPLETED")
        p["pending_projection"] = sorted(t for (scope, t) in pending if scope == p["book_code"])
    return packages


def package_detail(conn: Connection, package_id: str) -> dict:
    package = _one(conn, _PACKAGE_SQL + " WHERE p.content_package_id = CAST(:p AS uuid)", p=package_id)
    if not package:
        raise NotFound(package_id)
    package["reconciliation"] = _rows(conn, """
        SELECT entity_type, source_count, valid_count, imported_count, created_count, updated_count,
               unchanged_count, rejected_count, conflict_count, present_in_db, reconciled, reconciled_at
          FROM ingest.reconciliation WHERE content_package_id = CAST(:p AS uuid) AND scope = :s
         ORDER BY entity_type""", p=package_id, s=package["last_scope"])
    package["staging"] = _rows(conn, """
        SELECT entity_type, validation_status, count(*)::int AS rows,
               count(*) FILTER (WHERE validation_warnings <> '[]'::jsonb)::int AS with_warnings
          FROM ingest.staging_row WHERE content_package_id = CAST(:p AS uuid)
         GROUP BY 1, 2 ORDER BY 1, 2""", p=package_id)
    package["conflict_summary"] = _rows(conn, """
        SELECT entity_type, conflict_type, severity, resolution_status, count(*)::int AS count
          FROM ingest.import_conflict WHERE content_package_id = CAST(:p AS uuid)
         GROUP BY 1, 2, 3, 4 ORDER BY 1, 2, 4""", p=package_id)
    package["files"] = _rows(conn, """
        SELECT relative_path, file_role, row_count, byte_size, sha256 FROM ingest.package_file
         WHERE content_package_id = CAST(:p AS uuid) ORDER BY relative_path""", p=package_id)
    package["status_history"] = _rows(conn, """
        SELECT from_status, to_status, scope, detail, created_at FROM ingest.package_status_event
         WHERE content_package_id = CAST(:p AS uuid) ORDER BY created_at DESC, event_id DESC LIMIT 50""",
        p=package_id)
    return package


def validation_issues(conn: Connection, package_id: str, *, entity_type: str | None = None,
                      kind: str = "ALL", limit: int = 50, offset: int = 0) -> dict:
    """Staging rows that were rejected or carry warnings (spec 15 §3)."""
    cond = {"REJECTED": "validation_status = 'REJECTED'",
            "WARNINGS": "validation_warnings <> '[]'::jsonb",
            "ALL": "(validation_status = 'REJECTED' OR validation_warnings <> '[]'::jsonb)"}[kind]
    where = f"content_package_id = CAST(:p AS uuid) AND {cond}" + (" AND entity_type = :e" if entity_type else "")
    total = conn.execute(text(f"SELECT count(*) FROM ingest.staging_row WHERE {where}"),
                         {"p": package_id, "e": entity_type}).scalar_one()
    items = _rows(conn, f"""
        SELECT staging_row_id, source_file, source_row_number, entity_type, external_id, validation_status,
               validation_errors, validation_warnings, target_key
          FROM ingest.staging_row WHERE {where}
         ORDER BY validation_status DESC, entity_type, source_file, source_row_number LIMIT :n OFFSET :o""",
        p=package_id, e=entity_type, n=limit, o=offset)
    return {"total": total, "items": items}


def list_conflicts(conn: Connection, package_id: str, *, entity_type: str | None = None,
                   resolution_status: str | None = None, limit: int = 50, offset: int = 0) -> dict:
    where = "content_package_id = CAST(:p AS uuid)"
    where += " AND entity_type = :e" if entity_type else ""
    where += " AND resolution_status = :r" if resolution_status else ""
    params = {"p": package_id, "e": entity_type, "r": resolution_status}
    total = conn.execute(text(f"SELECT count(*) FROM ingest.import_conflict WHERE {where}"), params).scalar_one()
    items = _rows(conn, f"""
        SELECT conflict_id, entity_type, external_id, conflict_type, severity, detail, resolution_status,
               resolution, decision, decided_at, updated_at
          FROM ingest.import_conflict WHERE {where}
         ORDER BY CASE severity WHEN 'ERROR' THEN 0 WHEN 'WARNING' THEN 1 ELSE 2 END, entity_type, conflict_id
         LIMIT :n OFFSET :o""", **params, n=limit, o=offset)
    return {"total": total, "items": items}


def decide_conflict(conn: Connection, conflict_id: int, decision: str, note: str | None) -> dict:
    """Record keep-existing / accept-incoming / merge-manually (spec 15 §4). The decision is recorded,
    not executed: ACCEPT_INCOMING / MERGE_MANUALLY are applied by the next package re-import or a DAG edit."""
    if decision not in CONFLICT_DECISIONS:
        raise Invalid(f"decision must be one of {CONFLICT_DECISIONS}")
    before = _one(conn, "SELECT conflict_id, resolution_status, decision, resolution FROM ingest.import_conflict "
                        "WHERE conflict_id = :c FOR UPDATE", c=conflict_id)
    if not before:
        raise NotFound(str(conflict_id))
    after = _one(conn, """
        UPDATE ingest.import_conflict SET decision = :d, decided_at = now(), resolution_status = 'RESOLVED',
               resolution = :n, updated_at = now()
         WHERE conflict_id = :c
        RETURNING conflict_id, entity_type, external_id, conflict_type, severity, resolution_status, resolution,
                  decision, decided_at""", c=conflict_id, d=decision, n=note or decision)
    after["action_id"] = _audit(conn, "IMPORT_CONFLICT", str(conflict_id), decision, before, after, note)
    return after


# ---------------------------------------------------------------- reconciliation (spec 15 §5-§6)

def reconciliation(conn: Connection, book: str, include_graph: bool = True, driver=None) -> dict:
    cov = textbook_admin.coverage(conn, book, include_graph=include_graph, driver=driver)
    graph_rows, embedding_rows = [], []
    for row in cov["matrix"]:
        stores = row.get("expected") or ()
        if "graph" in stores:
            expected = row.get("graph_expected", row.get("postgres"))
            actual = row.get("graph")
            graph_rows.append({
                "entity": row["entity"], "expected": expected, "actual": actual,
                "missing": None if actual is None else max((expected or 0) - actual, 0),
                "extra_or_stale": None if actual is None else max(actual - (expected or 0), 0)})
        if "vector" in stores:
            done = row.get("vector")
            embedding_rows.append({"entity": row["entity"], "expected": row.get("postgres"), "completed": done,
                                   "missing": None if done is None else max((row.get("postgres") or 0) - done, 0)})
    profile = _one(conn, """
        SELECT m.provider, m.model_name, m.dimensions, m.activated_at,
               count(e.embedding_id) FILTER (WHERE e.status = 'ACTIVE')::int AS active_embeddings
          FROM search.embedding_model m LEFT JOIN search.embedding e USING (embedding_model_id)
         WHERE m.status = 'ACTIVE' GROUP BY 1, 2, 3, 4 ORDER BY 5 DESC LIMIT 1""")
    jobs = {r["status"]: r["n"] for r in _rows(conn, "SELECT status, count(*)::int AS n FROM search.embedding_job "
                                                       "GROUP BY 1")}
    return {"book_code": book, "graph_ok": cov["graph_ok"], "graph_error": cov["graph_error"],
            "graph": graph_rows, "embeddings": embedding_rows,
            "active_embedding": profile, "embedding_jobs": jobs, "failed_embedding_jobs": jobs.get("FAILED", 0),
            "metadata_profile_version": _metadata_profile(conn),
            "projection_requests": list_projection_requests(conn, status="PENDING")}


def _metadata_profile(conn: Connection) -> list[dict]:
    """Preprocessing (metadata/chunking) profiles behind ACTIVE representations, e.g. textbook_steps v1."""
    return _rows(conn, """
        SELECT pp.name, pp.version, count(*)::int AS representations
          FROM search.representation r JOIN search.preprocessing_profile pp USING (preprocessing_profile_id)
         WHERE r.status = 'ACTIVE' GROUP BY 1, 2 ORDER BY 1, 2""")


def list_projection_requests(conn: Connection, status: str | None = None, limit: int = 100) -> list[dict]:
    where = " WHERE status = :s" if status else ""
    return _rows(conn, f"""
        SELECT projection_request_id::text AS projection_request_id, target, scope_type, scope_id, reason,
               status, requested_at, requested_by, completed_at, completed_by
          FROM pipeline.projection_request{where} ORDER BY requested_at DESC LIMIT :n""", s=status, n=limit)


def request_projection(conn: Connection, target: str, scope_type: str, scope_id: str, note: str | None) -> dict:
    """"Reproject missing" (spec 15 §5): enqueue only; operators drain with the existing projectors."""
    if target not in PROJECTION_TARGETS or scope_type not in PROJECTION_SCOPES:
        raise Invalid("unknown projection target or scope")
    row = _one(conn, """
        INSERT INTO pipeline.projection_request (target, scope_type, scope_id, reason, requested_by)
        VALUES (:t, :st, :sid, 'ADMIN_REPROJECT', 'admin')
        ON CONFLICT (target, scope_type, scope_id) WHERE status = 'PENDING' DO NOTHING
        RETURNING projection_request_id::text AS projection_request_id, status""",
        t=target, st=scope_type, sid=scope_id)
    created = row is not None
    if not created:
        row = _one(conn, """
            SELECT projection_request_id::text AS projection_request_id, status FROM pipeline.projection_request
             WHERE target = :t AND scope_type = :st AND scope_id = :sid AND status = 'PENDING'""",
            t=target, st=scope_type, sid=scope_id)
    _audit(conn, "PROJECTION_REQUEST", row["projection_request_id"], "REQUEST", None,
           {"target": target, "scope_type": scope_type, "scope_id": scope_id, "created": created}, note)
    return {**row, "target": target, "scope_type": scope_type, "scope_id": scope_id, "created": created}


# ---------------------------------------------------------------- learning items

def review_learning_item(conn: Connection, item_id: str, decision: str, note: str | None) -> dict:
    status = ITEM_DECISIONS.get(decision)
    if not status:
        raise Invalid(f"decision must be one of {tuple(ITEM_DECISIONS)}")
    before = _one(conn, """
        SELECT learning_item_id, review_status, student_visible, approval_method FROM pedagogy.learning_item
         WHERE learning_item_id = :i FOR UPDATE""", i=item_id)
    if not before:
        raise NotFound(item_id)
    after = _one(conn, """
        UPDATE pedagogy.learning_item SET review_status = :s, student_visible = (:s = 'APPROVED'),
               approval_method = 'human', approved_at = CASE WHEN :s = 'APPROVED' THEN now() END,
               updated_at = now()
         WHERE learning_item_id = :i
        RETURNING learning_item_id, review_status, student_visible, approval_method, approved_at, book_code""",
        i=item_id, s=status)
    if before["review_status"] != status or before["student_visible"] != after["student_visible"]:
        event = "LEARNING_ITEM_PUBLISHED" if status == "APPROVED" else "LEARNING_ITEM_WITHDRAWN"
        _outbox(conn, event, "learning_item", item_id,
                {"book_code": after["book_code"], "review_status": status, "approval_method": "human"})
    after["action_id"] = _audit(conn, "LEARNING_ITEM", item_id, decision, before, after, note)
    return after


# ---------------------------------------------------------------- semantic DAG review (spec 15 §7)

def _problem(conn: Connection, code: str) -> dict:
    row = _one(conn, """
        SELECT p.problem_id::text AS problem_id, p.canonical_code AS code, s.solution_id::text AS solution_id
          FROM core.problem p
          LEFT JOIN LATERAL (SELECT solution_id FROM pedagogy.solution_step st WHERE st.problem_id = p.problem_id
                              LIMIT 1) s ON true
         WHERE p.canonical_code = :c""", c=code)
    if not row:
        raise NotFound(code)
    return row


def problem_dag(conn: Connection, code: str) -> dict:
    problem = _problem(conn, code)
    steps = _rows(conn, """
        SELECT st.solution_step_id, st.solution_part_id, st.global_step_index, st.step_index_in_part, st.step_type,
               st.tutor_role, st.skill_node_id, st.skill_name, st.is_checkpoint, st.admin_edited_at,
               left(st.step_text, 400) AS step_text
          FROM pedagogy.solution_step st WHERE st.problem_id = CAST(:p AS uuid)
         ORDER BY st.global_step_index, st.solution_step_id""", p=problem["problem_id"])
    deps = _rows(conn, """
        SELECT d.from_step_id, d.to_step_id, d.relationship_type, d.logical_dependency, d.confidence, d.source_type,
               d.review_status, d.approval_method
          FROM pedagogy.solution_step_dependency d
          JOIN pedagogy.solution_step s ON s.solution_step_id = d.to_step_id
         WHERE s.problem_id = CAST(:p AS uuid) ORDER BY d.from_step_id, d.to_step_id, d.relationship_type""",
        p=problem["problem_id"])
    review = _one(conn, """
        SELECT status, note, reviewed_by, reviewed_at FROM pedagogy.solution_dag_review
         WHERE solution_id = CAST(:s AS uuid)""", s=problem["solution_id"]) if problem["solution_id"] else None
    actions = _rows(conn, """
        SELECT action_id, target_type, target_id, action, note, created_at FROM ingest.admin_review_action
         WHERE (target_type = 'SOLUTION_DAG' AND target_id = :p)
            OR (target_type IN ('SOLUTION_STEP', 'STEP_DEPENDENCY') AND target_id LIKE :prefix)
         ORDER BY created_at DESC LIMIT 50""", p=problem["problem_id"],
        prefix=f"{code}%")
    return {**problem, "steps": steps, "dependencies": deps, "review": review, "actions": actions,
            "dependency_types": list(DEPENDENCY_TYPES)}


def _step(conn: Connection, step_id: str, lock: bool = False) -> dict:
    row = _one(conn, f"""
        SELECT st.solution_step_id, st.problem_id::text AS problem_id, p.canonical_code AS code, st.book_code,
               st.skill_node_id, st.skill_name, st.is_checkpoint, st.content_package_id::text AS content_package_id
          FROM pedagogy.solution_step st JOIN core.problem p USING (problem_id)
         WHERE st.solution_step_id = :s{' FOR UPDATE OF st' if lock else ''}""", s=step_id)
    if not row:
        raise NotFound(step_id)
    return row


def _step_changed(conn: Connection, step: dict, change: str) -> None:
    _outbox(conn, "SOLUTION_STEP_CHANGED", "solution_step", step["solution_step_id"],
            {"book_code": step["book_code"], "problem_id": step["problem_id"], "change": change})


def edit_step(conn: Connection, step_id: str, *, skill_node_id: str | None = None,
              is_checkpoint: bool | None = None, note: str | None = None) -> dict:
    if skill_node_id is None and is_checkpoint is None:
        raise Invalid("nothing to change")
    before = _step(conn, step_id, lock=True)
    skill_name = before["skill_name"]
    if skill_node_id is not None:
        skill = _one(conn, "SELECT name FROM pedagogy.taxonomy_node WHERE taxonomy_node_id = :n "
                           "AND node_type = 'SKILL'", n=skill_node_id)
        if not skill:
            raise Invalid(f"{skill_node_id} is not a SKILL taxonomy node")
        skill_name = skill["name"]
    conn.execute(text("""
        UPDATE pedagogy.solution_step SET skill_node_id = coalesce(:sk, skill_node_id),
               skill_name = :sn, is_checkpoint = coalesce(:cp, is_checkpoint),
               admin_edited_at = now(), updated_at = now()
         WHERE solution_step_id = :s"""), {"sk": skill_node_id, "sn": skill_name, "cp": is_checkpoint, "s": step_id})
    after = _step(conn, step_id)
    _step_changed(conn, after, "STEP_EDITED")
    target = f"{after['code']}|{step_id}"
    after["action_id"] = _audit(conn, "SOLUTION_STEP", target, "EDIT", before, after, note)
    return after


def _would_cycle(conn: Connection, problem_id: str, from_step: str, to_step: str) -> bool:
    """True if a hard DEPENDS_ON from_step -> to_step closes a cycle (to_step already reaches from_step)."""
    return bool(conn.execute(text("""
        WITH RECURSIVE reach(step_id) AS (
            SELECT CAST(:to AS text)
            UNION
            SELECT d.to_step_id FROM pedagogy.solution_step_dependency d JOIN reach r ON d.from_step_id = r.step_id
              JOIN pedagogy.solution_step s ON s.solution_step_id = d.to_step_id
             WHERE d.relationship_type = 'DEPENDS_ON' AND d.review_status <> 'REJECTED'
               AND s.problem_id = CAST(:p AS uuid))
        SELECT EXISTS (SELECT 1 FROM reach WHERE step_id = :from)"""),
        {"to": to_step, "from": from_step, "p": problem_id}).scalar())


def upsert_dependency(conn: Connection, from_step_id: str, to_step_id: str, relationship_type: str, *,
                      previous_type: str | None = None, logical_dependency: str | None = None,
                      note: str | None = None) -> dict:
    """Create an edge or change its type (e.g. DEPENDS_ON -> ALTERNATIVE_TO to mark an alternative branch).
    Admin edges are approval_method='human' so the importer never overwrites them."""
    if relationship_type not in DEPENDENCY_TYPES or (previous_type and previous_type not in DEPENDENCY_TYPES):
        raise Invalid(f"relationship_type must be one of {DEPENDENCY_TYPES}")
    if from_step_id == to_step_id:
        raise Invalid("a step cannot depend on itself")
    src, dst = _step(conn, from_step_id), _step(conn, to_step_id)
    if src["problem_id"] != dst["problem_id"]:
        raise Invalid("both steps must belong to the same problem")
    key = {"f": from_step_id, "t": to_step_id}
    before = None
    if previous_type:
        before = _one(conn, """
            SELECT from_step_id, to_step_id, relationship_type, logical_dependency, review_status, approval_method
              FROM pedagogy.solution_step_dependency
             WHERE from_step_id = :f AND to_step_id = :t AND relationship_type = :r FOR UPDATE""", **key,
            r=previous_type)
        if not before:
            raise NotFound(f"{from_step_id} -[{previous_type}]-> {to_step_id}")
    if relationship_type == "DEPENDS_ON" and _would_cycle(conn, src["problem_id"], from_step_id, to_step_id):
        raise Conflict("this DEPENDS_ON edge would create a prerequisite cycle")
    if previous_type and previous_type != relationship_type:
        conn.execute(text("DELETE FROM pedagogy.solution_step_dependency "
                          "WHERE from_step_id = :f AND to_step_id = :t AND relationship_type = :r"),
                     {**key, "r": previous_type})
    after = _one(conn, """
        INSERT INTO pedagogy.solution_step_dependency (from_step_id, to_step_id, relationship_type,
               logical_dependency, source_type, review_status, approval_method, content_package_id, metadata)
        VALUES (:f, :t, :r, :ld, 'ADMIN_REVIEWED', 'REVIEWED', 'human', CAST(:pkg AS uuid),
                jsonb_build_object('previous_type', CAST(:prev AS text)))
        ON CONFLICT (from_step_id, to_step_id, relationship_type) DO UPDATE SET
               logical_dependency = coalesce(EXCLUDED.logical_dependency,
                                             pedagogy.solution_step_dependency.logical_dependency),
               source_type = 'ADMIN_REVIEWED', review_status = 'REVIEWED', approval_method = 'human'
        RETURNING from_step_id, to_step_id, relationship_type, logical_dependency, review_status, approval_method""",
        **key, r=relationship_type, ld=logical_dependency or (before or {}).get("logical_dependency"),
        pkg=dst["content_package_id"], prev=previous_type)
    _step_changed(conn, dst, "DEPENDENCY_CHANGED")
    target = f"{dst['code']}|{from_step_id}->{to_step_id}"
    after["action_id"] = _audit(conn, "STEP_DEPENDENCY", target, "CHANGE_TYPE" if before else "CREATE",
                                before, after, note)
    return after


def reject_dependency(conn: Connection, from_step_id: str, to_step_id: str, relationship_type: str,
                      note: str | None) -> dict:
    before = _one(conn, """
        SELECT from_step_id, to_step_id, relationship_type, review_status, approval_method
          FROM pedagogy.solution_step_dependency
         WHERE from_step_id = :f AND to_step_id = :t AND relationship_type = :r FOR UPDATE""",
        f=from_step_id, t=to_step_id, r=relationship_type)
    if not before:
        raise NotFound(f"{from_step_id} -[{relationship_type}]-> {to_step_id}")
    after = _one(conn, """
        UPDATE pedagogy.solution_step_dependency SET review_status = 'REJECTED', approval_method = 'human'
         WHERE from_step_id = :f AND to_step_id = :t AND relationship_type = :r
        RETURNING from_step_id, to_step_id, relationship_type, review_status, approval_method""",
        f=from_step_id, t=to_step_id, r=relationship_type)
    dst = _step(conn, to_step_id)
    _step_changed(conn, dst, "DEPENDENCY_REJECTED")
    after["action_id"] = _audit(conn, "STEP_DEPENDENCY", f"{dst['code']}|{from_step_id}->{to_step_id}", "REJECT",
                                before, after, note)
    return after


def review_dag(conn: Connection, code: str, status: str, note: str | None) -> dict:
    if status not in ("APPROVED", "NEEDS_REVISION"):
        raise Invalid("status must be APPROVED or NEEDS_REVISION")
    problem = _problem(conn, code)
    if not problem["solution_id"]:
        raise Invalid("this problem has no imported solution steps")
    before = _one(conn, "SELECT status, note FROM pedagogy.solution_dag_review WHERE solution_id = CAST(:s AS uuid)",
                  s=problem["solution_id"])
    after = _one(conn, """
        INSERT INTO pedagogy.solution_dag_review (solution_id, problem_id, status, note)
        VALUES (CAST(:s AS uuid), CAST(:p AS uuid), :st, :n)
        ON CONFLICT (solution_id) DO UPDATE SET status = EXCLUDED.status, note = EXCLUDED.note,
               reviewed_at = now(), reviewed_by = 'admin'
        RETURNING status, note, reviewed_by, reviewed_at""",
        s=problem["solution_id"], p=problem["problem_id"], st=status, n=note)
    after["action_id"] = _audit(conn, "SOLUTION_DAG", problem["problem_id"], status, before, after, note)
    return {**problem, "review": after}


def list_actions(conn: Connection, target_type: str | None = None, limit: int = 100) -> list[dict]:
    where = " WHERE target_type = :t" if target_type else ""
    return _rows(conn, f"""
        SELECT action_id, target_type, target_id, action, before_state, after_state, note, actor, created_at
          FROM ingest.admin_review_action{where} ORDER BY created_at DESC, action_id DESC LIMIT :n""",
        t=target_type, n=limit)
