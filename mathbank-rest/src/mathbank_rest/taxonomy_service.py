"""Admin CRUD for the four taxonomy entities that had no update/alias/activate-deactivate
surface at all before this module (requirements/45_REST_API_DOCUMENTATION_AND_ADMIN_CRUD_GAPS.md
§5): knowledge.concept, knowledge.technique, knowledge.skill, knowledge.misconception.

Deliberate implementation choice, documented here since it differs from doc 45 §5.2's advisory
recommendation: all four kinds get the same lightweight PATCH (name/description-or-objective/
level), not the heavier pedagogy_admin.py revision-gated governance workflow for skill/
misconception. That workflow also drives Neo4j publish-to-graph semantics for skills; extending
its Kind literal to cover concept/technique/misconception as well would entangle this additive,
low-risk CRUD gap with that larger, already-complex publish pipeline. The acceptance criteria
(APID-7/APID-8: "through a REST call... without going through raw SQL") does not require the
heavier workflow specifically — only that raw SQL is no longer needed.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import text

from mathbank_rest.micro_course_service import record_audit_event

ENTITY_CONFIG: dict[str, dict[str, Any]] = {
    "concepts": {
        "table": "knowledge.concept",
        "id_col": "concept_id",
        "code_col": "slug",
        "name_col": "name",
        "desc_col": "description",
        "has_level": True,
        "lifecycle": "STATUS",  # status column: 'ACTIVE' | 'INACTIVE'
        "alias_kind": "CONCEPT",
        "entity_label": "concept",
    },
    "techniques": {
        "table": "knowledge.technique",
        "id_col": "technique_id",
        "code_col": "slug",
        "name_col": "name",
        "desc_col": "description",
        "has_level": False,
        "lifecycle": "STATUS",
        "alias_kind": "TECHNIQUE",
        "entity_label": "technique",
    },
    "skills": {
        "table": "knowledge.skill",
        "id_col": "skill_id",
        "code_col": "slug",
        "name_col": "name",
        "desc_col": "objective",
        "has_level": True,
        "lifecycle": "IS_ACTIVE",  # is_active boolean column, independent of review_status
        "alias_kind": "SKILL",
        "entity_label": "skill",
    },
    "misconceptions": {
        "table": "knowledge.misconception",
        "id_col": "misconception_id",
        "code_col": "canonical_code",
        "name_col": "name",
        "desc_col": "description",
        "has_level": True,
        "lifecycle": "IS_ACTIVE",
        "alias_kind": "MISCONCEPTION",
        "entity_label": "misconception",
    },
}


class TaxonomyNotFound(ValueError):
    pass


class TaxonomyConflict(RuntimeError):
    pass


def _config(kind: str) -> dict[str, Any]:
    config = ENTITY_CONFIG.get(kind)
    if config is None:
        raise ValueError(f"unknown taxonomy kind: {kind}")
    return config


def _required_text(value: str, field: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValueError(f"{field} is required")
    return value


def list_entities(
    conn,
    kind: str,
    *,
    q: str = "",
    status: str = "ALL",
    review_status: str = "ALL",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List/search an entity kind, optionally filtered by its lifecycle status (concept/
    technique: ACTIVE|INACTIVE|ALL against `status`; skill/misconception: ACTIVE|INACTIVE|ALL
    against `is_active`) and, for skill/misconception, by pre-publication `review_status`.
    Alias matches (requirements/45 APID-9) are included via a correlated EXISTS, so searching
    "AM-GM" finds a technique canonically named something else entirely."""
    if limit < 1 or limit > 200 or offset < 0:
        raise ValueError("limit must be 1..200 and offset must be non-negative")
    config = _config(kind)
    table, id_col, code_col, name_col, desc_col = (
        config["table"], config["id_col"], config["code_col"], config["name_col"], config["desc_col"]
    )
    where = ["1=1"]
    params: dict[str, Any] = {
        "q": f"%{q}%", "alias_kind": config["alias_kind"], "limit": limit, "offset": offset,
    }
    if q:
        where.append(
            f"(e.{name_col} ILIKE :q OR e.{code_col} ILIKE :q OR EXISTS ("
            "SELECT 1 FROM knowledge.entity_alias a WHERE a.entity_kind=:alias_kind "
            f"AND a.entity_id=e.{id_col} AND a.alias ILIKE :q))"
        )
    if config["lifecycle"] == "STATUS" and status != "ALL":
        if status not in ("ACTIVE", "INACTIVE"):
            raise ValueError("status must be ACTIVE, INACTIVE, or ALL")
        where.append("e.status = :status")
        params["status"] = status
    if config["lifecycle"] == "IS_ACTIVE" and status != "ALL":
        if status not in ("ACTIVE", "INACTIVE"):
            raise ValueError("status must be ACTIVE, INACTIVE, or ALL")
        where.append("e.is_active = :is_active")
        params["is_active"] = status == "ACTIVE"
    if config["lifecycle"] == "IS_ACTIVE" and review_status != "ALL":
        where.append("e.review_status = :review_status")
        params["review_status"] = review_status
    level_col = ", e.level" if config["has_level"] else ""
    lifecycle_col = (
        "e.status" if config["lifecycle"] == "STATUS" else "CASE WHEN e.is_active THEN 'ACTIVE' ELSE 'INACTIVE' END"
    )
    review_col = ", e.review_status" if config["lifecycle"] == "IS_ACTIVE" else ""
    rows = conn.execute(
        text(f"""
        SELECT e.{id_col} AS entity_id, e.{code_col} AS code, e.{name_col} AS name,
               e.{desc_col} AS description, {lifecycle_col} AS status,
               e.deactivated_at, e.deactivated_by {level_col} {review_col},
               COALESCE((SELECT array_agg(a.alias ORDER BY a.alias) FROM knowledge.entity_alias a
                         WHERE a.entity_kind=:alias_kind AND a.entity_id=e.{id_col}), ARRAY[]::text[]) AS aliases
        FROM {table} e
        WHERE {" AND ".join(where)}
        ORDER BY e.{name_col}
        LIMIT :limit OFFSET :offset
    """),
        params,
    ).mappings()
    items = [dict(row) for row in rows]
    for item in items:
        item["entity_id"] = str(item["entity_id"])
    return {"items": items, "kind": kind}


def get_entity(conn, kind: str, code: str) -> dict:
    """Returns every raw column from the underlying table (so e.g. a skill's severity/
    confidence fields are visible) plus a normalized `code`/`name`/`description` triad so
    callers never need to know that `desc_col` is `objective` for skills, `canonical_code`
    is the code column for misconceptions, etc."""
    config = _config(kind)
    table, id_col, code_col, name_col, desc_col = (
        config["table"], config["id_col"], config["code_col"], config["name_col"], config["desc_col"]
    )
    row = conn.execute(
        text(f"SELECT * FROM {table} WHERE {code_col}=:code"), {"code": _required_text(code, "code")}
    ).mappings().one_or_none()
    if row is None:
        raise TaxonomyNotFound(f"{config['entity_label']} not found")
    result = dict(row)
    result[id_col] = str(result[id_col])
    result["code"] = result[code_col]
    result["name"] = result[name_col]
    result["description"] = result[desc_col]
    aliases = conn.execute(
        text("SELECT alias_id, alias, created_at, created_by FROM knowledge.entity_alias "
             "WHERE entity_kind=:kind AND entity_id=:id ORDER BY alias"),
        {"kind": config["alias_kind"], "id": result[id_col]},
    ).mappings()
    result["aliases"] = [dict(a) | {"alias_id": str(a["alias_id"])} for a in aliases]
    return result


def update_entity(
    conn, kind: str, code: str, *, name: str | None = None, description: str | None = None,
    level: int | None = None, actor: str,
) -> dict:
    """Lightweight update — no revision/optimistic-concurrency gate (see module docstring for
    why this differs from the heavier pedagogy_admin.py governance pattern)."""
    config = _config(kind)
    table, id_col, code_col, name_col, desc_col = (
        config["table"], config["id_col"], config["code_col"], config["name_col"], config["desc_col"]
    )
    row = conn.execute(
        text(f"SELECT {id_col} AS id, {name_col} AS name, {desc_col} AS description"
             + (", level" if config["has_level"] else "")
             + f" FROM {table} WHERE {code_col}=:code FOR UPDATE"),
        {"code": _required_text(code, "code")},
    ).mappings().one_or_none()
    if row is None:
        raise TaxonomyNotFound(f"{config['entity_label']} not found")
    before = dict(row)
    sets = []
    params: dict[str, Any] = {"id": str(row["id"])}
    if name is not None:
        sets.append(f"{name_col}=:name")
        params["name"] = _required_text(name, "name")
    if description is not None:
        sets.append(f"{desc_col}=:description")
        params["description"] = description
    if level is not None:
        if not config["has_level"]:
            raise ValueError(f"{config['entity_label']} has no level field")
        sets.append("level=:level")
        params["level"] = level
    if not sets:
        raise ValueError("at least one of name, description, level must be supplied")
    conn.execute(text(f"UPDATE {table} SET {', '.join(sets)} WHERE {id_col}=:id"), params)
    record_audit_event(
        conn, "ADMIN", actor, "TAXONOMY_ENTITY_UPDATED", config["entity_label"].upper(), str(row["id"]),
        before_state=before, after_state={k: v for k, v in params.items() if k != "id"},
    )
    return get_entity(conn, kind, code)


def _entity_row_for_lifecycle(conn, config: dict, code: str) -> dict:
    table, id_col, code_col = config["table"], config["id_col"], config["code_col"]
    lifecycle_col = "status" if config["lifecycle"] == "STATUS" else "is_active"
    row = conn.execute(
        text(f"SELECT {id_col} AS id, {lifecycle_col} AS lifecycle FROM {table} "
             f"WHERE {code_col}=:code FOR UPDATE"),
        {"code": _required_text(code, "code")},
    ).mappings().one_or_none()
    if row is None:
        raise TaxonomyNotFound(f"{config['entity_label']} not found")
    return row


def _guard_published_reference(conn, config: dict, entity_id: str) -> None:
    """Block deactivating an entity that is still the PRIMARY canonical target of a
    published micro-course release (requirements/45 APID-11), mirroring the existing
    micro-course identity-immutability pattern rather than inventing a new one."""
    target_col = {"concepts": "concept_id", "techniques": "technique_id", "skills": "skill_id"}.get(
        next(k for k, v in ENTITY_CONFIG.items() if v is config), None
    )
    if target_col is None:
        return  # misconceptions are not a micro_course_target target_type
    blocking = conn.execute(
        text(f"""
            SELECT c.canonical_code, r.version
            FROM pedagogy.micro_course_target t
            JOIN pedagogy.micro_course c ON c.micro_course_id=t.micro_course_id
            JOIN pedagogy.micro_course_release r ON r.micro_course_id=c.micro_course_id AND r.status='PUBLISHED'
            WHERE t.{target_col}=:id AND t.role='PRIMARY'
            LIMIT 1
        """),
        {"id": entity_id},
    ).mappings().one_or_none()
    if blocking is not None:
        raise TaxonomyConflict(
            f"Cannot deactivate: still the primary target of published micro-course "
            f"{blocking['canonical_code']} v{blocking['version']}"
        )


def deactivate_entity(conn, kind: str, code: str, actor: str, *, reason: str | None = None) -> dict:
    config = _config(kind)
    row = _entity_row_for_lifecycle(conn, config, code)
    entity_id = str(row["id"])
    active = row["lifecycle"] == "ACTIVE" if config["lifecycle"] == "STATUS" else bool(row["lifecycle"])
    if not active:
        raise TaxonomyConflict(f"{config['entity_label']} is already deactivated")
    _guard_published_reference(conn, config, entity_id)
    table, id_col = config["table"], config["id_col"]
    actor = _required_text(actor, "actor")
    if config["lifecycle"] == "STATUS":
        conn.execute(
            text(f"UPDATE {table} SET status='INACTIVE', deactivated_at=now(), deactivated_by=:actor "
                 f"WHERE {id_col}=:id"),
            {"id": entity_id, "actor": actor},
        )
    else:
        conn.execute(
            text(f"UPDATE {table} SET is_active=false, deactivated_at=now(), deactivated_by=:actor "
                 f"WHERE {id_col}=:id"),
            {"id": entity_id, "actor": actor},
        )
    record_audit_event(
        conn, "ADMIN", actor, "TAXONOMY_ENTITY_DEACTIVATED", config["entity_label"].upper(), entity_id,
        before_state={"active": True}, after_state={"active": False, "reason": reason},
    )
    return {"code": code, "status": "INACTIVE"}


def reactivate_entity(conn, kind: str, code: str, actor: str) -> dict:
    config = _config(kind)
    row = _entity_row_for_lifecycle(conn, config, code)
    entity_id = str(row["id"])
    active = row["lifecycle"] == "ACTIVE" if config["lifecycle"] == "STATUS" else bool(row["lifecycle"])
    if active:
        raise TaxonomyConflict(f"{config['entity_label']} is already active")
    table, id_col = config["table"], config["id_col"]
    actor = _required_text(actor, "actor")
    if config["lifecycle"] == "STATUS":
        conn.execute(
            text(f"UPDATE {table} SET status='ACTIVE', deactivated_at=NULL, deactivated_by=NULL WHERE {id_col}=:id"),
            {"id": entity_id},
        )
    else:
        conn.execute(
            text(f"UPDATE {table} SET is_active=true, deactivated_at=NULL, deactivated_by=NULL WHERE {id_col}=:id"),
            {"id": entity_id},
        )
    record_audit_event(
        conn, "ADMIN", actor, "TAXONOMY_ENTITY_REACTIVATED", config["entity_label"].upper(), entity_id,
        before_state={"active": False}, after_state={"active": True},
    )
    return {"code": code, "status": "ACTIVE"}


def list_aliases(conn, kind: str, code: str) -> list[dict]:
    config = _config(kind)
    entity = get_entity(conn, kind, code)
    return entity["aliases"]


def add_alias(conn, kind: str, code: str, alias: str, actor: str) -> dict:
    config = _config(kind)
    row = conn.execute(
        text(f"SELECT {config['id_col']} AS id FROM {config['table']} WHERE {config['code_col']}=:code"),
        {"code": _required_text(code, "code")},
    ).mappings().one_or_none()
    if row is None:
        raise TaxonomyNotFound(f"{config['entity_label']} not found")
    entity_id = str(row["id"])
    alias = _required_text(alias, "alias")
    alias_id = str(uuid4())
    try:
        # A SAVEPOINT (not the outer transaction) absorbs the duplicate-key error, so a caller
        # that converts this into a 409 and keeps using the same connection/transaction for
        # other work (as this module's own tests do) isn't left with a poisoned transaction.
        with conn.begin_nested():
            conn.execute(
                text("INSERT INTO knowledge.entity_alias (alias_id, entity_kind, entity_id, alias, created_by) "
                     "VALUES (:alias_id, :kind, :entity_id, :alias, :actor)"),
                {"alias_id": alias_id, "kind": config["alias_kind"], "entity_id": entity_id, "alias": alias,
                 "actor": _required_text(actor, "actor")},
            )
    except Exception as exc:  # IntegrityError for duplicate (entity_kind, entity_id, alias)
        if "entity_alias" in str(exc).lower() and "unique" in str(exc).lower():
            raise TaxonomyConflict(f"alias '{alias}' already exists for this {config['entity_label']}") from exc
        raise
    record_audit_event(
        conn, "ADMIN", actor, "TAXONOMY_ALIAS_ADDED", config["entity_label"].upper(), entity_id,
        after_state={"alias": alias},
    )
    return {"alias_id": alias_id, "alias": alias}


def remove_alias(conn, kind: str, code: str, alias_id: str, actor: str) -> None:
    config = _config(kind)
    row = conn.execute(
        text(f"SELECT {config['id_col']} AS id FROM {config['table']} WHERE {config['code_col']}=:code"),
        {"code": _required_text(code, "code")},
    ).mappings().one_or_none()
    if row is None:
        raise TaxonomyNotFound(f"{config['entity_label']} not found")
    entity_id = str(row["id"])
    deleted = conn.execute(
        text("DELETE FROM knowledge.entity_alias WHERE alias_id=:alias_id AND entity_kind=:kind "
             "AND entity_id=:entity_id RETURNING alias"),
        {"alias_id": alias_id, "kind": config["alias_kind"], "entity_id": entity_id},
    ).mappings().one_or_none()
    if deleted is None:
        raise TaxonomyNotFound("alias not found")
    record_audit_event(
        conn, "ADMIN", actor, "TAXONOMY_ALIAS_REMOVED", config["entity_label"].upper(), entity_id,
        before_state={"alias": deleted["alias"]},
    )
