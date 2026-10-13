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
    "concept_relation": ("from_concept_id", "to_concept_id", "relation_type"),
    "problem_skill": ("problem_id", "skill_id", "relation_type", "role"),
    "problem_pedagogy": ("problem_id",),
    "problem_concept": ("problem_id", "concept_id", "role"),
    "problem_technique": ("problem_id", "technique_id", "role"),
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
    "concept_relation": (
        (
            "JOIN knowledge.concept a ON a.concept_id=t.from_concept_id "
            "JOIN knowledge.concept b ON b.concept_id=t.to_concept_id"
        ),
        (
            "a.name || ' -> ' || b.name AS title, "
            "COALESCE(a.description,'') || ' / ' || COALESCE(b.description,'') AS context"
        ),
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
    "problem_concept": (
        "JOIN core.problem p USING(problem_id) JOIN knowledge.concept c USING(concept_id)",
        "p.canonical_code || ' -> ' || c.name AS title, p.statement_text AS context, p.canonical_code AS problem_code",
    ),
    "problem_technique": (
        "JOIN core.problem p USING(problem_id) JOIN knowledge.technique c USING(technique_id)",
        "p.canonical_code || ' -> ' || c.name AS title, p.statement_text AS context, p.canonical_code AS problem_code",
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
            {"PREREQUISITE_OF", "PART_OF", "HAS_SUBCONCEPT", "RELATED_CONCEPT", "RELATED_TO"}
            if kind == "concept_relation"
            else {"PREREQUISITE_OF", "PART_OF", "BUILDS_ON"}
            if kind == "skill_relation"
            else {"REQUIRES", "PRACTICES", "TESTS"}
        )
        if key["relation_type"] not in allowed:
            raise ValueError("Invalid relation type")
    if kind == "problem_skill" and key["role"] not in {"primary", "supporting"}:
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
    for table in KINDS:
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
        enrichment_counts: dict[str, int] = dict(
            conn.execute(
                text("SELECT status,count(*) FROM knowledge.enrichment_job GROUP BY status")
            ).all()
        )
        unenriched = conn.execute(
            text("""
            SELECT count(*) FROM core.problem p WHERE
            NOT EXISTS(SELECT 1 FROM knowledge.problem_skill s WHERE s.problem_id=p.problem_id)
            OR NOT EXISTS(SELECT 1 FROM knowledge.problem_pedagogy d WHERE d.problem_id=p.problem_id)
        """)
        ).scalar_one()
        enrichment_errors = [
            dict(row)
            for row in conn.execute(
                text(
                    "SELECT p.canonical_code,j.attempts,j.last_error,j.updated_at "
                    "FROM knowledge.enrichment_job j JOIN core.problem p USING(problem_id) "
                    "WHERE j.status='FAILED' ORDER BY j.updated_at DESC LIMIT 10"
                )
            ).mappings()
        ]
        relationship_counts: dict[str, int] = dict(
            conn.execute(
                text(
                    "SELECT status,count(*) FROM knowledge.relationship_enrichment_job GROUP BY status"
                )
            ).all()
        )
        relationship_jobs = [
            dict(row)
            for row in conn.execute(
                text("""
            SELECT j.entity_kind,COALESCE(s.slug,c.slug) AS anchor_slug,j.status,
                   j.attempts,j.last_error,j.edges_inserted,j.evidence,j.published_at
            FROM knowledge.relationship_enrichment_job j
            LEFT JOIN knowledge.skill s ON j.entity_kind='skill' AND j.anchor_id=s.skill_id
            LEFT JOIN knowledge.concept c ON j.entity_kind='concept' AND j.anchor_id=c.concept_id
            ORDER BY j.updated_at DESC LIMIT 10
        """)
            ).mappings()
        ]
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
        "enrichment_counts": enrichment_counts,
        "unenriched_problems": unenriched,
        "enrichment_errors": enrichment_errors,
        "relationship_enrichment_counts": relationship_counts,
        "relationship_enrichment_jobs": relationship_jobs,
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
    if before["review_status"] == review_status and before.get("approval_method") != "automatic":
        raise ReviewConflict("The assertion already has this review status.")
    if review_status == "REVIEWED":
        check_reviewed_dependencies(conn, kind, key)
    conn.execute(text("SET LOCAL mathbank.human_review = 'on'"))
    conn.execute(
        text(f"UPDATE knowledge.{kind} SET review_status=:status WHERE {where}"),
        {**key, "status": review_status},
    )
    after = conn.execute(
        text(f"SELECT to_jsonb(t) FROM knowledge.{kind} t WHERE {where}"), key
    ).scalar_one()
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
    builds = conn.execute(
        text("""
        SELECT a.slug,b.slug FROM knowledge.skill_relation r
        JOIN knowledge.skill a ON a.skill_id=r.from_skill_id
        JOIN knowledge.skill b ON b.skill_id=r.to_skill_id
        WHERE r.relation_type='BUILDS_ON' AND r.review_status='REVIEWED'
    """)
    ).all()
    author.assert_acyclic(list(builds), "skill BUILDS_ON")


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


def publish(expected_fingerprint: str, problem_codes: list[str] | None = None) -> dict:
    projector = operator_module("projector")
    author = operator_module("author")
    with engine.begin() as conn:
        lock_authoring(conn)
        current = fingerprint(conn)
        if current != expected_fingerprint:
            raise ReviewConflict("Metadata changed since you loaded it. Reload before publishing.")
        with closing(conn.connection.cursor()) as cursor:
            validate_graph(conn)
            author.resolve_manifest(cursor, author.validate_manifest({"version": 1}))
            projector.ensure_constraints(driver, pedagogy=True)
            target_codes = problem_codes
            if target_codes is None:
                target_codes = list(
                    conn.execute(
                        text("""
                    SELECT p.canonical_code FROM core.problem p
                    WHERE EXISTS(SELECT 1 FROM knowledge.problem_skill s WHERE s.problem_id=p.problem_id)
                       OR EXISTS(SELECT 1 FROM knowledge.problem_pedagogy d WHERE d.problem_id=p.problem_id)
                """)
                    ).scalars()
                )
            if target_codes:
                with driver.session() as session:
                    projection_count = session.run(
                        "MATCH(p:Problem) WHERE p.canonical_code IN $codes RETURN count(p) AS n",
                        codes=target_codes,
                    ).single()
                    if projection_count is None:
                        raise RuntimeError("Graph target-count query returned no result.")
                    projected = projection_count["n"]
                if projected != len(set(target_codes)):
                    projector.project_competitions(driver, cursor)
                    projector.project_papers(driver, cursor)
                    projector.project_problems(driver, cursor, target_codes)
            projector.project_problem_concept(driver, cursor, problem_codes)
            projector.project_problem_technique(driver, cursor, problem_codes)
            skills, edges = projector.project_pedagogy(driver, cursor, problem_codes)
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
        if problem_codes:
            conn.execute(
                text(
                    "UPDATE knowledge.enrichment_job SET published_at=now() WHERE status='COMPLETED' AND problem_id IN "
                    "(SELECT problem_id FROM core.problem WHERE canonical_code=ANY(:codes))"
                ),
                {"codes": problem_codes},
            )
        else:
            conn.execute(
                text(
                    "UPDATE knowledge.enrichment_job SET published_at=now() "
                    "WHERE status='COMPLETED' AND published_at IS NULL"
                )
            )
        conn.execute(
            text(
                "UPDATE knowledge.relationship_enrichment_job SET published_at=now() "
                "WHERE status='COMPLETED' AND published_at IS NULL"
            )
        )
    return {
        "publication": dict(publication),
        "message": "Pedagogical metadata published to Neo4j. Review status is preserved.",
    }


EDITABLE = {
    "skill": {"name", "objective", "level", "source", "confidence"},
    "skill_concept": {"source", "confidence"},
    "skill_relation": {"source", "confidence"},
    "concept_relation": {"strength", "assertion_source"},
    "problem_skill": {"required_level", "importance", "source", "confidence"},
    "problem_pedagogy": {
        "conceptual_depth",
        "technical_load",
        "algebraic_load",
        "insight_required",
        "number_of_steps",
        "prerequisite_depth",
        "estimated_contest_level",
        "source",
        "confidence",
    },
    "problem_concept": {"confidence", "assertion_source"},
    "problem_technique": {"confidence", "assertion_source"},
}


def edit(kind: str, key: dict[str, str], expected_revision: str, changes: dict, note: str) -> dict:
    key = validate_key(kind, key)
    if not changes or not set(changes) <= EDITABLE[kind]:
        raise ValueError("Only editable metadata attributes may be changed.")
    for field, value in changes.items():
        if field in {"confidence", "importance", "strength"}:
            if type(value) not in (int, float) or not 0 <= value <= 1:
                raise ValueError(f"{field} must be a finite number in 0..1")
        elif field in {
            "name",
            "objective",
            "source",
            "assertion_source",
            "estimated_contest_level",
        }:
            if not isinstance(value, str) or not value.strip() or len(value) > 2000:
                raise ValueError(f"{field} must be nonblank text (maximum 2000 characters)")
        elif value is not None:
            lower, upper = (
                (0, 100) if field in {"number_of_steps", "prerequisite_depth"} else (1, 5)
            )
            if type(value) is not int or not lower <= value <= upper:
                raise ValueError(f"{field} has invalid bounds")
    where = " AND ".join(f"{field}=:{field}" for field in KINDS[kind])
    with engine.begin() as conn:
        lock_authoring(conn)
        before = conn.execute(
            text(f"SELECT to_jsonb(t) FROM knowledge.{kind} t WHERE {where} FOR UPDATE"), key
        ).scalar_one_or_none()
        if before is None:
            raise MissingMetadata("Metadata not found")
        if revision(before) != expected_revision:
            raise ReviewConflict("Metadata changed. Reload before editing.")
        conn.execute(text("SET LOCAL mathbank.human_review='on'"))
        assignments = ",".join(f"{field}=:edit_{field}" for field in changes)
        conn.execute(
            text(f"UPDATE knowledge.{kind} SET {assignments} WHERE {where}"),
            {**key, **{f"edit_{k}": v for k, v in changes.items()}},
        )
        after = conn.execute(
            text(f"SELECT to_jsonb(t) FROM knowledge.{kind} t WHERE {where}"), key
        ).scalar_one()
        conn.execute(
            text("""
            INSERT INTO knowledge.pedagogy_review_event
            (entity_kind,entity_key,before_snapshot,after_snapshot,reviewer,review_note)
            VALUES(:kind,CAST(:key AS jsonb),CAST(:before AS jsonb),CAST(:after AS jsonb),:reviewer,:note)
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
        validate_graph(conn)
    return {
        "message": "Admin correction saved and protected from automatic replacement. Publish to update graph.",
        "revision": revision(after),
    }
