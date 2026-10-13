"""Observed per-paper coverage; paper batch completion is not end-to-end completion."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired
from sqlalchemy import text

from mathbank_rest.db.graph import driver
from mathbank_rest.db.postgres import engine

logger = logging.getLogger(__name__)

INVENTORY = """
    SELECT coalesce(t.external_code,s.paper_external_code) AS paper_external_code,
           coalesce(c.external_code,s.competition_external_code) AS competition_external_code,
           t.paper_id, t.question_count, ed.year, s.source_kind, s.download_status,
           s.parse_status,s.ingest_status,s.downloaded_at,s.parsed_at,s.ingested_at,
           s.questions_found,s.last_error,s.updated_at
    FROM core.paper t
    JOIN core.competition_edition ed USING(edition_id)
    JOIN core.competition c USING(competition_id)
    FULL JOIN pipeline.pdf_source s ON s.paper_external_code=t.external_code
"""


def coverage_status(done: int, total: int, *, failed: int = 0, active: int = 0) -> str:
    if total > 0 and done == total:
        return "COMPLETED"
    if failed:
        return "FAILED"
    if active:
        return "IN_PROGRESS"
    return "PARTIAL" if done else "PENDING"


def stage(
    status: str,
    completed: int = 0,
    expected: int | None = None,
    recorded_at=None,
    error: str | None = None,
) -> dict:
    return {
        "status": status,
        "completed": completed,
        "expected": expected,
        "recorded_at": recorded_at,
        "error": error,
    }


def list_jobs(
    *, competition: str | None = None, paper: str | None = None, limit: int = 50, offset: int = 0
) -> dict:
    params = {"competition": competition, "paper": paper, "limit": limit, "offset": offset}
    where = """
        WHERE (CAST(:competition AS text) IS NULL OR competition_external_code=:competition)
          AND (CAST(:paper AS text) IS NULL OR paper_external_code ILIKE :paper)
    """
    params["paper"] = f"%{paper}%" if paper else None
    with engine.connect() as conn:
        competitions = [
            dict(r)
            for r in conn.execute(
                text(
                    f"WITH inventory AS ({INVENTORY}) SELECT competition_external_code,count(*) AS papers "
                    "FROM inventory GROUP BY 1 ORDER BY 1"
                )
            ).mappings()
        ]
        total = conn.execute(
            text(f"WITH inventory AS ({INVENTORY}) SELECT count(*) FROM inventory {where}"), params
        ).scalar_one()
        items = [
            dict(r)
            for r in conn.execute(
                text(f"""
            WITH inventory AS ({INVENTORY}), page AS (
                SELECT * FROM inventory {where}
                ORDER BY competition_external_code, year DESC NULLS LAST,paper_external_code
                LIMIT :limit OFFSET :offset
            )
            SELECT p.*,w.status AS batch_status,w.metrics AS batch_metrics,w.run_id,
                   w.started_at,w.completed_at,w.attempt_count,w.last_error AS batch_error,
                   w.item_type AS work_type,r.heartbeat_at,r.status AS run_status
            FROM page p LEFT JOIN LATERAL (
                SELECT * FROM pipeline.work_item WHERE item_key=p.paper_external_code
                ORDER BY started_at DESC NULLS LAST,completed_at DESC NULLS LAST LIMIT 1
            ) w ON true LEFT JOIN pipeline.run r USING(run_id)
        """),
                params,
            ).mappings()
        ]
        ids = [r["paper_id"] for r in items if r["paper_id"]]
        jobs = (
            [
                dict(r)
                for r in conn.execute(
                    text("""
            SELECT w.item_key,w.item_type,w.status,w.run_id,w.started_at,w.completed_at,
                   w.attempt_count,w.last_error,w.metrics,r.heartbeat_at
            FROM pipeline.work_item w JOIN pipeline.run r USING(run_id)
            WHERE w.item_key=ANY(:papers)
            ORDER BY w.started_at DESC NULLS LAST
        """),
                    {"papers": [p["paper_external_code"] for p in items]},
                ).mappings()
            ]
            if items
            else []
        )
        problems = (
            [
                dict(r)
                for r in conn.execute(
                    text("""
            SELECT p.paper_id,p.problem_id,p.canonical_code,
              (SELECT count(*) FROM core.solution s WHERE s.problem_id=p.problem_id) AS solutions,
              (SELECT count(*) FROM core.problem_image i WHERE i.problem_id=p.problem_id) AS images,
              (SELECT count(*) FROM knowledge.problem_concept a
               WHERE a.problem_id=p.problem_id) AS concept_edges,
              (SELECT count(*) FROM knowledge.problem_technique a
               WHERE a.problem_id=p.problem_id) AS technique_edges,
              (SELECT count(*) FROM knowledge.problem_skill a
               WHERE a.problem_id=p.problem_id AND a.review_status='REVIEWED') AS skill_edges,
              EXISTS(SELECT 1 FROM knowledge.problem_pedagogy d
               WHERE d.problem_id=p.problem_id AND d.review_status='REVIEWED') AS difficulty,
              j.status AS pedagogy_status,j.updated_at AS pedagogy_at,j.published_at,j.last_error
            FROM core.problem p LEFT JOIN knowledge.enrichment_job j USING(problem_id)
            WHERE p.paper_id=ANY(:ids)
        """),
                    {"ids": ids},
                ).mappings()
            ]
            if ids
            else []
        )
        vectors = (
            [
                dict(r)
                for r in conn.execute(
                    text("""
            WITH entities AS (
                SELECT paper_id,'PROBLEM' AS kind,problem_id AS id,
                  regexp_replace('[Problem] ' || statement_text,'[[:space:]]+$','') AS rendered
                FROM core.problem
                WHERE paper_id=ANY(:ids)
                UNION ALL SELECT p.paper_id,'SOLUTION',s.solution_id,
                  regexp_replace('[Solution] ' || s.body_markdown,'[[:space:]]+$','')
                FROM core.solution s JOIN core.problem p USING(problem_id)
                WHERE p.paper_id=ANY(:ids)
            )
            SELECT x.paper_id,x.kind,x.id,
                count(DISTINCT r.representation_id) AS representations,
                count(DISTINCT ch.chunk_id) AS chunks,
                count(DISTINCT ch.chunk_id) FILTER (WHERE e.embedding_id IS NOT NULL) AS embedded,
                max(e.generated_at) AS embedded_at,
                count(DISTINCT j.embedding_job_id) FILTER (WHERE j.status='FAILED') AS failed,
                count(DISTINCT j.embedding_job_id) FILTER (WHERE j.status='IN_PROGRESS') AS active,
                max(j.last_error) FILTER (WHERE j.status='FAILED') AS vector_error
            FROM entities x LEFT JOIN search.representation r
              ON r.source_entity_type=x.kind AND r.source_entity_id=x.id AND r.status='ACTIVE'
                AND r.rendered_text=x.rendered
            LEFT JOIN search.chunk ch USING(representation_id)
            LEFT JOIN search.embedding e ON e.chunk_id=ch.chunk_id AND e.status='ACTIVE'
              AND e.embedding_model_id IN (SELECT embedding_model_id FROM search.embedding_model
                WHERE status='ACTIVE' AND provider='openai' AND model_name='text-embedding-3-small')
            LEFT JOIN search.embedding_job j ON j.representation_id=r.representation_id
              AND j.embedding_model_id IN (SELECT embedding_model_id FROM search.embedding_model
                WHERE status='ACTIVE' AND provider='openai' AND model_name='text-embedding-3-small')
            GROUP BY x.paper_id,x.kind,x.id
        """),
                    {"ids": ids},
                ).mappings()
            ]
            if ids
            else []
        )
        assertions = (
            [
                dict(r)
                for r in conn.execute(
                    text("""
            SELECT p.paper_id,p.problem_id,'TESTS' AS kind,a.concept_id AS target,
                   a.role,a.review_status,a.assertion_source AS source,a.confidence
            FROM knowledge.problem_concept a JOIN core.problem p USING(problem_id)
            WHERE paper_id=ANY(:ids)
            UNION ALL SELECT p.paper_id,p.problem_id,'USES_TECHNIQUE',a.technique_id,
                   a.role,a.review_status,a.assertion_source,a.confidence
            FROM knowledge.problem_technique a JOIN core.problem p USING(problem_id)
            WHERE paper_id=ANY(:ids)
        """),
                    {"ids": ids},
                ).mappings()
            ]
            if ids
            else []
        )
        skills = (
            [
                dict(r)
                for r in conn.execute(
                    text("""
            SELECT p.paper_id,p.problem_id,a.skill_id,a.relation_type,a.role,
                   a.review_status,a.approval_method
            FROM knowledge.problem_skill a JOIN core.problem p USING(problem_id)
            WHERE paper_id=ANY(:ids) AND a.review_status='REVIEWED'
        """),
                    {"ids": ids},
                ).mappings()
            ]
            if ids
            else []
        )
        anchors = (
            [
                dict(r)
                for r in conn.execute(
                    text("""
            WITH anchors AS (
              SELECT DISTINCT p.paper_id,'skill' AS kind,a.skill_id AS id
              FROM knowledge.problem_skill a JOIN core.problem p USING(problem_id)
              JOIN knowledge.skill k USING(skill_id)
              WHERE p.paper_id=ANY(:ids) AND k.review_status='REVIEWED'
              UNION SELECT DISTINCT p.paper_id,'concept',a.concept_id
              FROM knowledge.problem_concept a JOIN core.problem p USING(problem_id)
              JOIN knowledge.concept k USING(concept_id)
              WHERE p.paper_id=ANY(:ids) AND k.status='ACTIVE'
            )
            SELECT a.*,j.status,j.updated_at,j.published_at,j.last_error
            FROM anchors a LEFT JOIN knowledge.relationship_enrichment_job j
              ON j.entity_kind=a.kind AND j.anchor_id=a.id
        """),
                    {"ids": ids},
                ).mappings()
            ]
            if ids
            else []
        )
        anchor_ids = [a["id"] for a in anchors]
        relations = (
            [
                dict(r)
                for r in conn.execute(
                    text("""
            SELECT 'skill' AS kind,from_skill_id AS src,to_skill_id AS dst,
                   relation_type,review_status,approval_method
            FROM knowledge.skill_relation
            WHERE (from_skill_id=ANY(:anchors) OR to_skill_id=ANY(:anchors))
              AND review_status='REVIEWED'
            UNION ALL
            SELECT 'concept',from_concept_id,to_concept_id,relation_type,
                   review_status,approval_method
            FROM knowledge.concept_relation
            WHERE (from_concept_id=ANY(:anchors) OR to_concept_id=ANY(:anchors))
              AND review_status='REVIEWED'
              AND relation_type IN ('HAS_SUBCONCEPT','PART_OF','PREREQUISITE_OF','BUILDS_ON')
        """),
                    {"anchors": anchor_ids},
                ).mappings()
            ]
            if anchor_ids
            else []
        )
    observed_at = datetime.now(UTC)
    graph_rows, warnings = graph_inventory(problems)
    graph_relations, relation_warnings = relationship_inventory(anchors)
    warnings.extend(relation_warnings)
    for item in items:
        pid = item["paper_id"]
        ps = [p for p in problems if p["paper_id"] == pid]
        vs = [v for v in vectors if v["paper_id"] == pid]
        expected_edges = {assertion_key(a) for a in assertions if a["paper_id"] == pid}
        expected_skills = {skill_key(a) for a in skills if a["paper_id"] == pid}
        build_item(item, ps, vs, expected_edges, expected_skills, graph_rows, observed_at)
        item["jobs"] = [j for j in jobs if j["item_key"] == item["paper_external_code"]]
        apply_relationships(
            item, [a for a in anchors if a["paper_id"] == pid], relations, graph_relations
        )
    return {
        "items": items,
        "total": total,
        "competitions": competitions,
        "observed_at": observed_at,
        "warnings": warnings,
    }


def assertion_key(a: dict) -> tuple:
    return (
        str(a["problem_id"]),
        a["kind"],
        str(a["target"]),
        a["role"],
        a["review_status"],
        a["source"],
        float(a["confidence"]) if a["confidence"] is not None else None,
    )


def skill_key(a: dict) -> tuple:
    return (
        str(a["problem_id"]),
        str(a["skill_id"]),
        a["relation_type"],
        a["role"],
        a["review_status"],
        a["approval_method"],
    )


def graph_inventory(problems: list[dict]) -> tuple[dict | None, list[str]]:
    if not problems:
        return {}, []
    try:
        with driver.session() as session:
            rows = [
                dict(r)
                for r in session.run(
                    """
                MATCH (p:Problem) WHERE p.canonical_id IN $ids
                OPTIONAL MATCH (p)-[r:TESTS|USES_TECHNIQUE|REQUIRES|PRACTICES]->(t)
                WHERE t:Concept OR t:Technique OR t:Skill
                RETURN p.canonical_id AS id,p.pedagogy_review_status AS pedagogy_status,
                  collect(CASE WHEN r IS NULL THEN null ELSE
                    [type(r),t.canonical_id,r.role,r.review_status,r.source,r.confidence,
                     r.approval_method,CASE WHEN t:Skill THEN 'skill' ELSE 'corpus' END]
                  END) AS edges
            """,
                    ids=[str(p["problem_id"]) for p in problems],
                )
            ]
        return {r["id"]: r for r in rows}, []
    except (Neo4jError, ServiceUnavailable, SessionExpired) as exc:
        logger.exception("Admin job graph observation failed")
        return None, [f"Neo4j unavailable; graph stages are UNKNOWN ({type(exc).__name__})."]


def relation_key(kind, src, dst, relation, status, method):
    if relation == "HAS_SUBCONCEPT":
        src, dst, relation = dst, src, "PART_OF"
    return kind, str(src), str(dst), relation, status, method


def relationship_inventory(anchors):
    if not anchors:
        return set(), []
    try:
        with driver.session() as session:
            rows = session.run(
                """
                MATCH (a)-[r:PART_OF|PREREQUISITE_OF|BUILDS_ON]->(b)
                WHERE ((a:Skill AND b:Skill) OR (a:Concept AND b:Concept))
                  AND (a.canonical_id IN $ids OR b.canonical_id IN $ids)
                  AND r.review_status='REVIEWED'
                RETURN CASE WHEN a:Skill THEN 'skill' ELSE 'concept' END AS kind,
                  a.canonical_id AS src,b.canonical_id AS dst,type(r) AS relation,
                  r.review_status AS status,r.approval_method AS method
            """,
                ids=[str(a["id"]) for a in anchors],
            )
            return {tuple(r.values()) for r in rows}, []
    except (Neo4jError, ServiceUnavailable, SessionExpired) as exc:
        logger.exception("Admin taxonomy graph observation failed")
        return None, [f"Taxonomy graph observation unavailable ({type(exc).__name__})."]


def apply_relationships(item, anchors, relations, actual):
    ids = {str(a["id"]) for a in anchors}
    expected = {
        relation_key(
            r["kind"],
            r["src"],
            r["dst"],
            r["relation_type"],
            r["review_status"],
            r["approval_method"],
        )
        for r in relations
        if str(r["src"]) in ids or str(r["dst"]) in ids
    }
    graph_edges = {r for r in actual if r[1] in ids or r[2] in ids} if actual is not None else None
    done = sum(a["status"] == "COMPLETED" and a["published_at"] is not None for a in anchors)
    status = coverage_status(
        done,
        len(anchors),
        failed=sum(a["status"] == "FAILED" for a in anchors),
        active=sum(a["status"] == "IN_PROGRESS" for a in anchors),
    )
    if actual is None:
        status = "UNKNOWN"
    elif status == "COMPLETED" and graph_edges != expected:
        status = "PARTIAL"
    item["stages"]["relationships"] = stage(
        status,
        done,
        len(anchors),
        max((a["updated_at"] for a in anchors if a["updated_at"]), default=None),
    )
    item["metrics"].update(
        {
            "relationship_anchors": len(anchors),
            "published_relationship_anchors": done,
            "reviewed_taxonomy_edges": len(expected),
            "graph_taxonomy_edges": len(graph_edges) if graph_edges is not None else None,
        }
    )
    item["errors"].extend(a["last_error"] for a in anchors if a["last_error"])
    update_overall(item)


def build_item(item, problems, vectors, expected_edges, expected_skills, graph_rows, now):
    n = len(problems)
    expected = max(n, item.get("question_count") or 0, item.get("questions_found") or 0)
    classified = sum(bool(p["concept_edges"] or p["technique_edges"]) for p in problems)
    taught = sum(bool(p["skill_edges"] and p["difficulty"]) for p in problems)
    published = sum(
        bool(p["published_at"] and p["pedagogy_status"] == "COMPLETED") for p in problems
    )
    complete_entities = sum(v["chunks"] > 0 and v["embedded"] == v["chunks"] for v in vectors)
    metrics = item.get("batch_metrics") or {}
    stages = {
        "download": stage(
            item.get("download_status") or "NOT_TRACKED", recorded_at=item.get("downloaded_at")
        ),
        "parse": stage(
            item.get("parse_status") or "NOT_TRACKED", recorded_at=item.get("parsed_at")
        ),
        "ingest": stage(coverage_status(n, expected), n, expected, item.get("ingested_at")),
        "classify": stage(coverage_status(classified, expected), classified, expected),
        "vectors": stage(
            coverage_status(
                complete_entities,
                len(vectors),
                failed=sum(v.get("failed", 0) for v in vectors),
                active=sum(v.get("active", 0) for v in vectors),
            ),
            complete_entities,
            len(vectors),
            max((v["embedded_at"] for v in vectors if v["embedded_at"]), default=None),
        ),
        "graph": stage("UNKNOWN" if graph_rows is None else "PENDING", 0, expected),
        "pedagogy": stage(
            coverage_status(
                taught,
                expected,
                failed=sum(p["pedagogy_status"] == "FAILED" for p in problems),
                active=sum(p["pedagogy_status"] == "IN_PROGRESS" for p in problems),
            ),
            taught,
            expected,
            max((p["pedagogy_at"] for p in problems if p["pedagogy_at"]), default=None),
        ),
        "pedagogy_graph": stage("UNKNOWN" if graph_rows is None else "PENDING", 0, expected),
    }
    if (
        metrics.get("classification_status") == "COMPLETED"
        and metrics.get("questions") == expected
        and expected > 0
    ):
        # The verified classifier can finish before its batch exports mappings to Postgres.
        stages["classify"] = stage("COMPLETED", expected, expected)
    node_count = corpus_edges = teaching_edges = 0
    if graph_rows is not None:
        actual_edges, actual_skills = set(), set()
        graph_taught = 0
        for p in problems:
            identity = str(p["problem_id"])
            row = graph_rows.get(identity)
            if not row:
                continue
            node_count += 1
            graph_taught += row["pedagogy_status"] == "REVIEWED" and bool(p["difficulty"])
            for kind, target, role, status, source, confidence, method, category in row["edges"]:
                if category == "skill" and status == "REVIEWED":
                    teaching_edges += 1
                    actual_skills.add((identity, target, kind, role, status, method))
                elif category == "corpus":
                    corpus_edges += 1
                    actual_edges.add((identity, kind, target, role, status, source, confidence))
        corpus_ok = (
            node_count == expected
            and expected > 0
            and actual_edges == expected_edges
            and corpus_edges == len(expected_edges)
            and classified == expected
        )
        teaching_ok = (
            taught == expected
            and expected > 0
            and graph_taught == expected
            and published == expected
            and actual_skills == expected_skills
            and teaching_edges == len(expected_skills)
        )
        stages["graph"] = stage(
            "COMPLETED"
            if corpus_ok
            else coverage_status(node_count, expected)
            if node_count < expected
            else "PARTIAL",
            node_count,
            expected,
        )
        stages["pedagogy_graph"] = stage(
            "COMPLETED" if teaching_ok else "PARTIAL" if graph_taught else "PENDING",
            graph_taught,
            expected,
        )
    aliases = {"split": "parse", "classified": "classify", "export": "classify"}
    current = metrics.get("stage") or item.get("work_type")
    active_stage = aliases.get(current, current)
    if (
        active_stage in stages
        and item.get("batch_status") in {"FAILED", "IN_PROGRESS"}
        and stages[active_stage]["status"] != "COMPLETED"
    ):
        stalled = (
            item.get("heartbeat_at") is None or (now - item["heartbeat_at"]).total_seconds() > 120
        )
        stages[active_stage]["status"] = (
            "FAILED"
            if item["batch_status"] == "FAILED"
            else "STALLED"
            if stalled or item.get("run_status") != "IN_PROGRESS"
            else "IN_PROGRESS"
        )
        stages[active_stage]["error"] = item.get("batch_error")
    for name in ("download", "parse", "ingest"):
        if item.get(f"{name}_status") == "FAILED":
            stages[name]["status"] = "FAILED"
            stages[name]["error"] = item.get("last_error")
    for name, timestamps in metrics.get("stage_times", {}).items():
        mapped = aliases.get(name, name)
        if mapped in stages:
            stages[mapped]["started_at"] = timestamps.get("started_at")
            stages[mapped]["finished_at"] = timestamps.get("completed_at")
            if stages[mapped]["recorded_at"] is None:
                stages[mapped]["recorded_at"] = timestamps.get("completed_at")
    item["stages"] = stages
    update_overall(item)
    item["metrics"] = {
        "problems": n,
        "solutions": sum(p["solutions"] for p in problems),
        "images": sum(p["images"] for p in problems),
        "classified_problems": classified,
        "verified_classifier_problems": stages["classify"]["completed"],
        "concept_edges": sum(p["concept_edges"] for p in problems),
        "technique_edges": sum(p["technique_edges"] for p in problems),
        "reviewed_skill_edges": sum(p["skill_edges"] for p in problems),
        "pedagogy_problems": taught,
        "published_pedagogy_jobs": published,
        "representations": sum(v["representations"] for v in vectors),
        "chunks": sum(v["chunks"] for v in vectors),
        "embedded_chunks": sum(v["embedded"] for v in vectors),
        "vector_entities": len(vectors),
        "complete_vector_entities": complete_entities,
        "graph_problem_nodes": node_count if graph_rows is not None else None,
        "graph_corpus_edges": corpus_edges if graph_rows is not None else None,
        "graph_skill_edges": teaching_edges if graph_rows is not None else None,
    }
    item["errors"] = list(
        dict.fromkeys(
            [
                e
                for e in [
                    item.get("last_error"),
                    item.get("batch_error"),
                    *(p["last_error"] for p in problems),
                    *(v.get("vector_error") for v in vectors),
                ]
                if e
            ]
        )
    )


def update_overall(item):
    states = [s["status"] for s in item["stages"].values()]
    item["overall_status"] = (
        "COMPLETED"
        if all(s in {"COMPLETED", "DOWNLOADED", "PARSED"} for s in states)
        else "FAILED"
        if "FAILED" in states
        else "STALLED"
        if "STALLED" in states
        else "IN_PROGRESS"
        if "IN_PROGRESS" in states
        else "PARTIAL"
        if item["stages"]["ingest"]["completed"]
        else "PENDING"
    )
