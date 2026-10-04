"""Postgres review decisions and explicitly published teaching graph snapshots."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from contextlib import closing
from functools import lru_cache
from pathlib import Path
from uuid import UUID

from sqlalchemy import text

from mathbank_rest.db.graph import driver
from mathbank_rest.db.postgres import engine

KINDS = {
    "skill": ("skill_id",),
    "skill_concept": ("skill_id", "concept_id"),
    "skill_relation": ("from_skill_id", "to_skill_id", "relation_type"),
    "problem_skill": ("problem_id", "skill_id", "relation_type", "role"),
    "problem_pedagogy": ("problem_id",),
}
JOINS = {
    "skill": ("", "t.name AS title, t.objective AS context"),
    "skill_concept": (
        "JOIN knowledge.skill s USING(skill_id) JOIN knowledge.concept c USING(concept_id)",
        "s.name || ' -> ' || c.name AS title, s.objective AS context",
    ),
    "skill_relation": (
        (
            "JOIN knowledge.skill a ON a.skill_id=t.from_skill_id "
            "JOIN knowledge.skill b ON b.skill_id=t.to_skill_id"
        ),
        "a.name || ' -> ' || b.name AS title, a.objective || ' / ' || b.objective AS context",
    ),
    "problem_skill": (
        "JOIN core.problem p USING(problem_id) JOIN knowledge.skill s USING(skill_id)",
        (
            "p.canonical_code || ' -> ' || s.name AS title, "
            "p.statement_text AS context, s.objective AS objective, p.canonical_code AS problem_code"
        ),
    ),
    "problem_pedagogy": (
        "JOIN core.problem p USING(problem_id)",
        "p.canonical_code AS title, p.statement_text AS context, p.canonical_code AS problem_code",
    ),
}
REVIEWER = "shared-admin-api-key"
STARTER_PATH = (
    Path(__file__).resolve().parents[4] / "mathbank-db/data/pedagogy/counting-foundations.v1.json"
)


class ReviewConflict(ValueError):
    """Reload stale metadata or resolve a review dependency before retrying."""


class MissingMetadata(ValueError):
    """The selected assertion no longer exists."""


@lru_cache
def operator_module(name: str):
    root = Path(__file__).resolve().parents[4]
    paths = {
        "author": root / "mathbank-db/etl/import_pedagogy.py",
        "projector": root / "mathbank-graph/etl/project_from_postgres.py",
    }
    spec = importlib.util.spec_from_file_location(f"pedagogy_{name}", paths[name])
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load the shared pedagogy {name} module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def revision(snapshot: dict) -> str:
    return hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def validate_key(kind: str, key: dict[str, str]) -> dict[str, str]:
    if kind not in KINDS or set(key) != set(KINDS[kind]):
        raise ValueError("Invalid metadata kind or natural key")
    result = dict(key)
    for field, value in key.items():
        if field.endswith("_id"):
            result[field] = str(UUID(value))
    if "relation_type" in key:
        allowed = (
            {"PREREQUISITE_OF", "PART_OF", "BUILDS_ON"}
            if kind == "skill_relation"
            else {"REQUIRES", "PRACTICES", "TESTS"}
        )
        if key["relation_type"] not in allowed:
            raise ValueError("Invalid relation type")
    if "role" in key and key["role"] not in {"primary", "supporting"}:
        raise ValueError("Invalid role")
    return result


def lock_authoring(conn) -> None:
    conn.execute(
        text(
            "LOCK TABLE knowledge.skill, knowledge.skill_relation, knowledge.skill_concept, "
            "knowledge.problem_skill, knowledge.problem_pedagogy, knowledge.concept_relation, "
            "knowledge.concept, core.problem IN SHARE ROW EXCLUSIVE MODE"
        )
    )


def fingerprint(conn) -> str:
    digest = hashlib.sha256()
    for table in (*KINDS, "concept_relation"):
        rows = conn.execute(
            text(f"SELECT to_jsonb(t)::text FROM knowledge.{table} t ORDER BY to_jsonb(t)::text")
        ).scalars()
        digest.update(table.encode())
        for row in rows:
            digest.update(row.encode())
            digest.update(b"\n")
    return digest.hexdigest()


def publication_state(conn) -> dict:
    current = fingerprint(conn)
    last = (
        conn.execute(
            text("SELECT * FROM knowledge.pedagogy_publication ORDER BY published_at DESC LIMIT 1")
        )
        .mappings()
        .first()
    )
    return {
        "source_fingerprint": current,
        "last_publication": dict(last) if last else None,
        "needs_publish": last is None or last["source_fingerprint"] != current,
    }


def queue(kind: str, status: str, limit: int, offset: int) -> dict:
    if kind not in KINDS:
        raise ValueError("Invalid metadata kind")
    join, columns = JOINS[kind]
    where = "" if status == "ALL" else "WHERE t.review_status=:status"
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        rows = (
            conn.execute(
                text(
                    f"SELECT to_jsonb(t) AS metadata, {columns} FROM knowledge.{kind} t {join} "
                    f"{where} ORDER BY title, to_jsonb(t)::text LIMIT :limit OFFSET :offset"
                ),
                {"status": status, "limit": limit, "offset": offset},
            )
            .mappings()
            .all()
        )
        total = conn.execute(
            text(f"SELECT count(*) FROM knowledge.{kind} t {where}"), {"status": status}
        ).scalar_one()
        counts: dict[str, dict[str, int]] = {
            table: dict(
                conn.execute(
                    text(
                        f"SELECT review_status, count(*) FROM knowledge.{table} GROUP BY review_status"
                    )
                ).all()
            )
            for table in KINDS
        }
        state = publication_state(conn)
        starter_warning = None
        try:
            starter = starter_items(conn)
        except MissingMetadata as exc:
            starter = []
            starter_warning = str(exc)
    items = []
    for row in rows:
        metadata = row["metadata"]
        items.append(
            {
                **dict(row),
                "key": {field: metadata[field] for field in KINDS[kind]},
                "revision": revision(metadata),
            }
        )
    return {
        "items": items,
        "total": total,
        "counts": counts,
        "starter_pending": sum(item["status"] == "PENDING" for item in starter),
        "starter_warning": starter_warning,
        **state,
    }


def check_reviewed_dependencies(conn, kind: str, key: dict[str, str]) -> None:
    fields = [field for field in key if field in {"skill_id", "from_skill_id", "to_skill_id"}]
    if kind == "skill":
        return
    for field in fields:
        status = conn.execute(
            text("SELECT review_status FROM knowledge.skill WHERE skill_id=:id"), {"id": key[field]}
        ).scalar_one()
        if status != "REVIEWED":
            raise ReviewConflict("Approve the referenced skills before approving this assertion.")


def change_decision(
    conn, kind: str, key: dict[str, str], expected_revision: str, review_status: str, note: str
) -> dict:
    key = validate_key(kind, key)
    where = " AND ".join(f"{field}=:{field}" for field in KINDS[kind])
    before = conn.execute(
        text(f"SELECT to_jsonb(t) FROM knowledge.{kind} t WHERE {where} FOR UPDATE"), key
    ).scalar_one_or_none()
    if before is None:
        raise MissingMetadata("Metadata not found")
    if revision(before) != expected_revision:
        raise ReviewConflict("This assertion changed. Reload it and review the new version.")
    if before["review_status"] == review_status:
        raise ReviewConflict("The assertion already has this review status.")
    if review_status == "REVIEWED":
        check_reviewed_dependencies(conn, kind, key)
    conn.execute(
        text(f"UPDATE knowledge.{kind} SET review_status=:status WHERE {where}"),
        {**key, "status": review_status},
    )
    after = {**before, "review_status": review_status}
    conn.execute(
        text("""
        INSERT INTO knowledge.pedagogy_review_event
            (entity_kind,entity_key,before_snapshot,after_snapshot,reviewer,review_note)
        VALUES (:kind,CAST(:key AS jsonb),CAST(:before AS jsonb),
                CAST(:after AS jsonb),:reviewer,:note)
    """),
        {
            "kind": kind,
            "key": json.dumps(key),
            "before": json.dumps(before),
            "after": json.dumps(after),
            "reviewer": REVIEWER,
            "note": note,
        },
    )
    return after


def validate_graph(conn) -> None:
    author = operator_module("author")
    with closing(conn.connection.cursor()) as cursor:
        author.resolve_manifest(cursor, author.validate_manifest({"version": 1}))


def decide(
    kind: str, key: dict[str, str], expected_revision: str, review_status: str, note: str
) -> dict:
    with engine.begin() as conn:
        lock_authoring(conn)
        after = change_decision(conn, kind, key, expected_revision, review_status, note)
        validate_graph(conn)
    return {
        "review_status": review_status,
        "revision": revision(after),
        "message": "Saved in Postgres. Publish explicitly to update tutoring and graph views.",
    }


def starter_items(conn) -> list[dict]:
    author = operator_module("author")
    manifest = author.validate_manifest(json.loads(STARTER_PATH.read_text()))
    lookup = {
        "skill": dict(conn.execute(text("SELECT slug,skill_id FROM knowledge.skill")).all()),
        "concept": dict(conn.execute(text("SELECT slug,concept_id FROM knowledge.concept")).all()),
        "problem": dict(
            conn.execute(text("SELECT canonical_code,problem_id FROM core.problem")).all()
        ),
    }
    sections = {
        "skill": ("skills", {"slug": ("skill_id", "skill")}),
        "skill_concept": (
            "skill_concepts",
            {
                "skill_slug": ("skill_id", "skill"),
                "concept_slug": ("concept_id", "concept"),
            },
        ),
        "skill_relation": (
            "skill_relations",
            {
                "from_skill_slug": ("from_skill_id", "skill"),
                "to_skill_slug": ("to_skill_id", "skill"),
            },
        ),
        "problem_skill": (
            "problem_skills",
            {
                "problem_code": ("problem_id", "problem"),
                "skill_slug": ("skill_id", "skill"),
            },
        ),
        "problem_pedagogy": ("problem_pedagogy", {"problem_code": ("problem_id", "problem")}),
    }
    items = []
    for kind, (section, references) in sections.items():
        for row in manifest[section]:
            if any(row[field] not in lookup[target] for field, (_, target) in references.items()):
                raise MissingMetadata(
                    "Starter metadata is not fully imported; its bulk action is unavailable."
                )
            key = {
                column: str(lookup[target][row[field]])
                for field, (column, target) in references.items()
            }
            key.update({field: row[field] for field in KINDS[kind] if field in row})
            where = " AND ".join(f"{field}=:{field}" for field in KINDS[kind])
            metadata = conn.execute(
                text(f"SELECT to_jsonb(t) FROM knowledge.{kind} t WHERE {where}"), key
            ).scalar_one_or_none()
            if metadata is None:
                raise MissingMetadata(
                    "Starter metadata is incomplete; import it before bulk review."
                )
            items.append(
                {
                    "kind": kind,
                    "key": key,
                    "expected_revision": revision(metadata),
                    "status": metadata["review_status"],
                }
            )
    return items


def apply_bulk(conn, items: list[dict], status: str, note: str) -> dict:
    identities = [
        (item["kind"], json.dumps(validate_key(item["kind"], item["key"]), sort_keys=True))
        for item in items
    ]
    if len(set(identities)) != len(items):
        raise ValueError("Duplicate assertions in bulk review")
    for item in sorted(items, key=lambda row: row["kind"] != "skill"):
        change_decision(conn, item["kind"], item["key"], item["expected_revision"], status, note)
    validate_graph(conn)
    return {
        "updated": len(items),
        "review_status": status,
        "message": f"Saved {len(items)} decisions atomically in Postgres. Publish to update Neo4j.",
    }


def bulk_decide(items: list[dict], status: str, note: str) -> dict:
    with engine.begin() as conn:
        lock_authoring(conn)
        return apply_bulk(conn, items, status, note)


def approve_starter(expected_fingerprint: str, note: str) -> dict:
    with engine.begin() as conn:
        lock_authoring(conn)
        if fingerprint(conn) != expected_fingerprint:
            raise ReviewConflict("Metadata changed. Reload before approving the starter set.")
        items = [item for item in starter_items(conn) if item["status"] == "PENDING"]
        if not items:
            raise ReviewConflict("No pending starter assertions remain.")
        return apply_bulk(conn, items, "REVIEWED", note)


def history(kind: str, key: dict[str, str]) -> dict:
    key = validate_key(kind, key)
    with engine.connect() as conn:
        rows = (
            conn.execute(
                text("""
            SELECT * FROM knowledge.pedagogy_review_event
            WHERE entity_kind=:kind AND entity_key=CAST(:key AS jsonb)
            ORDER BY reviewed_at DESC LIMIT 50
        """),
                {"kind": kind, "key": json.dumps(key)},
            )
            .mappings()
            .all()
        )
    return {"events": [dict(row) for row in rows]}


def publish(expected_fingerprint: str) -> dict:
    projector = operator_module("projector")
    author = operator_module("author")
    with engine.begin() as conn:
        lock_authoring(conn)
        current = fingerprint(conn)
        if current != expected_fingerprint:
            raise ReviewConflict("Metadata changed since you loaded it. Reload before publishing.")
        with closing(conn.connection.cursor()) as cursor:
            author.resolve_manifest(cursor, author.validate_manifest({"version": 1}))
            projector.ensure_constraints(driver, pedagogy=True)
            skills, edges = projector.project_pedagogy(driver, cursor)
        publication = (
            conn.execute(
                text("""
            INSERT INTO knowledge.pedagogy_publication
                (source_fingerprint,publisher,skills_projected,edges_projected)
            VALUES (:fingerprint,:publisher,:skills,:edges) RETURNING *
        """),
                {"fingerprint": current, "publisher": REVIEWER, "skills": skills, "edges": edges},
            )
            .mappings()
            .one()
        )
    return {
        "publication": dict(publication),
        "message": "Pedagogical metadata published to Neo4j. Review status is preserved.",
    }
