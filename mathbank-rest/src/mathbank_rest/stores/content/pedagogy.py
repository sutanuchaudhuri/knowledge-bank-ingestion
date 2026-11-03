"""Content store, pedagogy area (requirement 71 WP4; requirement 70 C6 access patterns A14, A15, A21, A22, A24, A26, A27).

Solution DAG, step lookups, published tutoring routes, taxonomy, topic candidates, video transcripts and the cached LLM step hint.

``PedagogyPostgres`` is today's SQL: the route/topic methods call the existing module functions at call time (so monkeypatching
tests keep working), the others carry the SQL that used to sit in ``step_runtime`` / ``step_recovery`` / ``step_tutor``. Methods
that ran inside a caller's transaction take ``conn=``; ``PedagogyDynamoDB`` ignores it.

``PedagogyDynamoDB`` reads ``mb-content`` through ``stores.typed`` (Query/BatchGet only, no scans) and immutable S3 snapshots through
``stores.content.snapshots``. Learner-safe and server-only halves stay separate: learner reads use ``learner.json`` (scrubbed of
``expected_response`` again on read); only ``load_route_program`` also reads ``server.json``.

Names start with a ``stores.READ_PREFIXES`` entry, except ``put_cached_step_hint`` (the one write), which a frozen store blocks.
"""
from __future__ import annotations

import bisect
import hashlib
import importlib
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

from mathbank_rest.models.ddb.content import (
    ContentFacet,
    ContentProblem,
    ContentProblemEnrichment,
    ContentRouterel,
    ContentSoldag,
    ContentSoldagDependenciesItem,
    ContentSoldagPartsItem,
    ContentSoldagStepsItem,
    ContentSoldagStepTechniquesItem,
    ContentStep,
    ContentTaxnode,
)
from mathbank_rest.models.manual.content_pedagogy import (
    ContentHint,
    ContentRouteptr,
    ContentVideo,
    ContentVtranscript,
    RouteLearnerDoc,
    RouteServerDoc,
    VideoTranscriptDoc,
)
from mathbank_rest.stores import typed
from mathbank_rest.stores.content.snapshots import snapshots
from mathbank_rest.stores.errors import ConditionFailed, StoreError

TOPIC_NODE_TYPES = ("CONCEPT", "SUBCONCEPT", "SKILL", "TECHNIQUE")
DAG_STEP_KEYS = ("solution_step_id", "source_step_id", "occurrence", "solution_id", "solution_part_id", "part_label",
                 "global_step_index", "step_index_in_part", "step_text", "step_type", "tutor_role", "concept_node_id",
                 "subconcept_node_id", "skill_node_id", "skill_name", "hint_level", "is_checkpoint")
DAG_PART_KEYS = ("solution_part_id", "solution_id", "part_label", "part_ordinal", "step_count", "source_step_count", "source_page")
DAG_DEP_KEYS = ("from_step_id", "to_step_id", "relationship_type", "logical_dependency", "review_status", "confidence")
DAG_TECH_KEYS = ("solution_step_id", "technique_node_id", "confidence", "review_status")
SEGMENT_KEYS = ("segment_id", "segment_index", "start_ms", "end_ms", "transcript_text", "speaker")
HINT_LEVELS = range(1, 6)


def _safe_instruction(instruction: dict | None) -> dict | None:
    """The learner half of an instruction: never carries the answer key."""
    return None if instruction is None else {k: v for k, v in instruction.items() if k != "expected_response"}


def _scrub(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _scrub(v) for k, v in obj.items() if k != "expected_response"}
    if isinstance(obj, list):
        return [_scrub(v) for v in obj]
    return obj


def _pick(obj: Any, keys: Iterable[str]) -> dict:
    return {k: getattr(obj, k, None) for k in keys}


def _hint_sk(level: int, prompt_version: str) -> str:
    return f"L{int(level)}#{prompt_version}"


def _segment_at(segments: list[dict], at_ms: int) -> dict | None:
    """The segment whose [start_ms, end_ms) contains ``at_ms`` (binary search on start_ms); None in a gap or out of range."""
    i = bisect.bisect_right([s["start_ms"] for s in segments], at_ms) - 1
    return segments[i] if i >= 0 and at_ms < segments[i]["end_ms"] else None


# ======================================================================================================== Postgres

@contextmanager
def _pg(module: str | None, conn):
    """The caller's connection, else a fresh read connection from ``<module>.engine`` (looked up at call time)."""
    if conn is not None:
        yield conn
        return
    engine = importlib.import_module(module or "mathbank_rest.db.postgres").engine
    with engine.connect() as c:
        yield c


class PedagogyPostgres:
    """Postgres backend: delegates to the existing SQL (behaviour unchanged)."""

    # ---- A21 / A22: published tutoring routes (route_runtime)
    def find_published_route(self, problem_code: str, *, conn=None) -> dict | None:
        from mathbank_rest import route_runtime

        with _pg("mathbank_rest.route_runtime", conn) as c:
            return route_runtime.select_published(c, problem_code)

    def get_published_route(self, problem_code: str, route_release_id, *, conn=None) -> dict | None:
        """A specific PUBLISHED release of the problem (None when it is another problem's or not published)."""
        with _pg("mathbank_rest.route_runtime", conn) as c:
            row = c.execute(text("""
            SELECT r.* FROM pedagogy.solution_route_release r JOIN core.problem p USING(problem_id)
            WHERE r.route_release_id=:id AND p.canonical_code=:code AND r.status='PUBLISHED'
        """), {"id": route_release_id, "code": problem_code}).mappings().first()
        return dict(row) if row else None

    def list_route_instructions(self, route_release_id, *, conn=None) -> list[dict]:
        """Learner-safe instruction documents of a release, by step."""
        with _pg("mathbank_rest.route_runtime", conn) as c:
            rows = list(c.execute(text("""
            SELECT content FROM pedagogy.solution_step_instruction
            WHERE route_release_id=:r ORDER BY step_index
        """), {"r": route_release_id}).scalars())
        return [_safe_instruction(r) for r in rows]

    def get_route_step_instruction(self, route_release_id, step_index: int, *, conn=None) -> dict | None:
        with _pg("mathbank_rest.route_runtime", conn) as c:
            content = c.execute(text("""
        SELECT content FROM pedagogy.solution_step_instruction WHERE route_release_id=:r AND step_index=:i
    """), {"r": route_release_id, "i": step_index}).scalar()
        return _safe_instruction(content)

    def get_route_step_hint(self, route_release_id, step_index: int, level: int, *, conn=None) -> str | None:
        with _pg("mathbank_rest.route_runtime", conn) as c:
            return c.execute(text("""
        SELECT hint_text FROM pedagogy.route_step_hint
        WHERE route_release_id=:r AND step_index=:i AND hint_level=:level
          AND hint_variant='default' AND misconception_key=''
    """), {"r": route_release_id, "i": step_index, "level": level}).scalar()

    def load_route_program(self, route_release_id, *, conn=None):
        """The full ``RouteProgram`` (server-side: includes ``expected_response``); any release status."""
        from mathbank_rest import route_runtime

        with _pg("mathbank_rest.route_runtime", conn) as c:
            return route_runtime._pg_load_program(c, str(route_release_id))

    # ---- A14: solution DAG
    def get_solution_dag(self, problem_code: str | None = None, *, problem_id: str | None = None, conn=None) -> dict:
        if (problem_code is None) == (problem_id is None):
            raise ValueError("pass exactly one of problem_code / problem_id")
        where, params = (("p.canonical_code = :k", {"k": problem_code}) if problem_code is not None
                         else ("p.problem_id = CAST(:k AS uuid)", {"k": str(problem_id)}))
        with _pg(None, conn) as c:
            steps = [dict(r) for r in c.execute(text(
                "SELECT s.solution_step_id, s.source_step_id, s.occurrence, s.solution_id::text AS solution_id, "
                "       s.solution_part_id, sp.part_label, s.global_step_index, s.step_index_in_part, s.step_text, "
                "       s.step_type, s.tutor_role, s.concept_node_id, s.subconcept_node_id, s.skill_node_id, "
                "       s.skill_name, s.hint_level, s.is_checkpoint, p.problem_id::text AS problem_id, "
                "       p.canonical_code AS problem_code "
                "  FROM pedagogy.solution_step s JOIN pedagogy.solution_part sp USING (solution_part_id) "
                "  JOIN core.problem p ON p.problem_id = s.problem_id "
                f" WHERE {where} AND s.publication_status = 'PUBLISHED' "
                " ORDER BY s.global_step_index, s.solution_step_id"), params).mappings()]
            ids = [s["solution_step_id"] for s in steps]
            solutions = sorted({s["solution_id"] for s in steps})
            parts = [dict(r) for r in c.execute(text(
                "SELECT sp.solution_part_id, sp.solution_id::text AS solution_id, sp.part_label, sp.part_ordinal, "
                "       sp.step_count, sp.source_step_count, sp.source_page "
                "  FROM pedagogy.solution_part sp WHERE sp.solution_id = ANY(CAST(:sol AS uuid[])) "
                " ORDER BY sp.part_ordinal, sp.solution_part_id"), {"sol": solutions}).mappings()] if solutions else []
            deps = [dict(r) for r in c.execute(text(
                "SELECT d.from_step_id, d.to_step_id, d.relationship_type, d.logical_dependency, d.review_status, "
                "       d.confidence "
                "  FROM pedagogy.solution_step_dependency d "
                "  JOIN pedagogy.solution_step a ON a.solution_step_id = d.from_step_id AND a.publication_status = 'PUBLISHED' "
                " WHERE d.to_step_id = ANY(:ids) AND d.review_status <> 'REJECTED' "
                " ORDER BY d.from_step_id, d.to_step_id, d.relationship_type"), {"ids": ids}).mappings()] if ids else []
            techs = [dict(r) for r in c.execute(text(
                "SELECT t.solution_step_id, t.technique_node_id, t.confidence, t.review_status "
                "  FROM pedagogy.solution_step_technique t WHERE t.solution_step_id = ANY(:ids) "
                "   AND t.review_status = 'APPROVED' ORDER BY t.solution_step_id, t.technique_node_id"),
                {"ids": ids}).mappings()] if ids else []
        first = steps[0] if steps else {}
        code, pid = first.get("problem_code", problem_code), first.get("problem_id", problem_id)
        for s in steps:
            del s["problem_id"], s["problem_code"]
        return {"problem_code": code, "problem_id": pid, "solutions": solutions, "parts": parts, "steps": steps,
                "dependencies": deps, "step_techniques": techs}

    # ---- A15: step details / eligibility
    def get_step_details(self, step_ids: Iterable[str], *, include_step_text: bool = False, conn=None) -> dict[str, dict]:
        ids = list(dict.fromkeys(step_ids))
        if not ids:
            return {}
        with _pg(None, conn) as c:
            rows = c.execute(text(
                "SELECT s.solution_step_id, s.problem_id::text AS problem_id, s.solution_id::text AS solution_id, "
                "       s.solution_part_id, s.global_step_index, s.step_type, s.tutor_role, s.hint_level, "
                "       s.is_checkpoint, s.skill_node_id, s.skill_name, s.subconcept_node_id, s.concept_node_id, "
                "       p.canonical_code AS problem_code, s.step_text, (s.publication_status = 'PUBLISHED') AS eligible "
                "  FROM pedagogy.solution_step s JOIN core.problem p ON p.problem_id = s.problem_id "
                " WHERE s.solution_step_id = ANY(:ids)"), {"ids": ids}).mappings()
            out = {r["solution_step_id"]: dict(r) for r in rows}
        if not include_step_text:
            for r in out.values():
                r.pop("step_text")
        return out

    def get_steps_by_ids(self, step_ids: Iterable[str], *, include_step_text: bool = False, conn=None) -> list[dict]:
        """Eligible (published) steps in the order asked; unknown or withdrawn ids are dropped."""
        ids = list(dict.fromkeys(step_ids))
        found = self.get_step_details(ids, include_step_text=include_step_text, conn=conn)
        return [found[i] for i in ids if i in found and found[i]["eligible"]]

    def get_step_recovery_target(self, step_id: str, *, conn=None) -> dict:
        with _pg(None, conn) as c:
            s = c.execute(text(
                "SELECT s.skill_node_id, s.subconcept_node_id, coalesce(s.skill_name, t.name) AS label "
                "  FROM pedagogy.solution_step s LEFT JOIN pedagogy.taxonomy_node t ON t.taxonomy_node_id = s.skill_node_id "
                " WHERE s.solution_step_id = :s"), {"s": step_id}).mappings().one()
        return dict(s)

    def get_step_worked_example(self, step_id: str, *, conn=None) -> dict:
        with _pg(None, conn) as c:
            r = c.execute(text(
                "SELECT s.step_text, s.skill_name, t.description, p.canonical_code, p.statement_text "
                "  FROM pedagogy.solution_step s JOIN core.problem p ON p.problem_id = s.problem_id "
                "  LEFT JOIN pedagogy.taxonomy_node t ON t.taxonomy_node_id = s.skill_node_id "
                " WHERE s.solution_step_id = :s"), {"s": step_id}).mappings().one()
        return dict(r)

    def get_step_origin(self, step_id: str, *, conn=None) -> dict:
        with _pg(None, conn) as c:
            r = c.execute(text(
                "SELECT p.canonical_code, sp.part_label, s.step_index_in_part, s.global_step_index "
                "  FROM pedagogy.solution_step s JOIN pedagogy.solution_part sp USING (solution_part_id) "
                "  JOIN core.problem p ON p.problem_id = s.problem_id WHERE s.solution_step_id = :s"),
                {"s": step_id}).mappings().one()
        return dict(r)

    def get_step_tutor_context(self, step_id: str, *, conn=None) -> dict:
        """Everything the step tutor needs about a step from content (the student's own state is learner data)."""
        with _pg(None, conn) as c:
            row = c.execute(text(
                "SELECT p.statement_text, sp.part_label, s.step_type, s.tutor_role, s.skill_name, s.step_text, "
                "       s.solution_id, s.global_step_index "
                "  FROM pedagogy.solution_step s JOIN pedagogy.solution_part sp USING (solution_part_id) "
                "  JOIN core.problem p ON p.problem_id = s.problem_id "
                " WHERE s.solution_step_id = :s"), {"s": step_id}).mappings().one()
            previous = list(c.execute(text(
                "SELECT step_text FROM pedagogy.solution_step WHERE solution_id = :sol AND global_step_index < :i "
                "AND publication_status = 'PUBLISHED' ORDER BY global_step_index"),
                {"sol": row["solution_id"], "i": row["global_step_index"]}).scalars())
        return {**dict(row), "solution_id": str(row["solution_id"]), "previous_steps": previous}

    # ---- A24: taxonomy
    def get_taxonomy_nodes(self, node_ids: Iterable[str], *, conn=None) -> dict[str, dict]:
        ids = list(dict.fromkeys(node_ids))
        if not ids:
            return {}
        from mathbank_rest.db import step_search

        with _pg(None, conn) as c:
            rows = c.execute(text(step_search._TAXONOMY_DETAILS), {"ids": ids}).mappings()
            return {r["taxonomy_node_id"]: dict(r) for r in rows}

    def list_taxonomy_children(self, parent_id: str, *, conn=None) -> list[dict]:
        with _pg(None, conn) as c:
            ids = list(c.execute(text(
                "SELECT taxonomy_node_id FROM pedagogy.taxonomy_node WHERE parent_node_id = :p "
                "ORDER BY node_type, name, taxonomy_node_id"), {"p": parent_id}).scalars())
            found = self.get_taxonomy_nodes(ids, conn=c)
        return [found[i] for i in ids if i in found]

    def list_taxonomy_nodes(self, node_types: Iterable[str] = TOPIC_NODE_TYPES, *, conn=None) -> list[dict]:
        """``{taxonomy_node_id, name, node_type}`` of every node of the given types, by id."""
        from mathbank_rest.db import topic_pedagogy

        with _pg("mathbank_rest.db.topic_pedagogy", conn) as c:
            return topic_pedagogy._pg_nodes(c, tuple(node_types))

    def list_taxonomy_prerequisite_ids(self, skill_ids: Iterable[str], *, conn=None) -> list[str]:
        """Nodes that are ``PREREQUISITE_OF`` any of the given skills."""
        with _pg(None, conn) as c:
            return list(c.execute(text(
                "SELECT DISTINCT from_node_id FROM pedagogy.taxonomy_edge "
                "WHERE to_node_id=ANY(:skills) AND relationship_type='PREREQUISITE_OF'"),
                {"skills": list(skill_ids)}).scalars())

    def list_topic_candidates(self, node_id: str, *, limit: int = 100, conn=None) -> list[dict]:
        from mathbank_rest.db import topic_pedagogy

        with _pg("mathbank_rest.db.topic_pedagogy", conn) as c:
            return topic_pedagogy._pg_candidates(c, node_id, limit)

    # ---- A26: video transcripts
    def get_video(self, video_asset_id: str, *, conn=None) -> dict | None:
        with _pg(None, conn) as c:
            r = c.execute(text(
                "SELECT video_asset_id::text AS video_asset_id, provider, canonical_url AS url, title, duration_ms, "
                "       review_status, transcript_status FROM pedagogy.video_asset "
                " WHERE video_asset_id = CAST(:v AS uuid) AND review_status = 'APPROVED'"),
                {"v": video_asset_id}).mappings().first()
        return dict(r) if r else None

    def get_video_transcript(self, video_asset_id: str, language_code: str = "en", *, conn=None) -> dict | None:
        with _pg(None, conn) as c:
            t = c.execute(text(
                "SELECT t.transcript_id, t.version, t.language_code FROM pedagogy.video_transcript t "
                "  JOIN pedagogy.video_asset v ON v.video_asset_id = t.video_asset_id "
                " WHERE t.video_asset_id = CAST(:v AS uuid) AND t.language_code = :l AND t.status = 'APPROVED' "
                "   AND v.review_status = 'APPROVED' ORDER BY t.version DESC, t.transcript_id LIMIT 1"),
                {"v": video_asset_id, "l": language_code}).mappings().first()
            if t is None:
                return None
            segments = [dict(r) for r in c.execute(text(
                "SELECT seg.segment_id::text AS segment_id, seg.segment_index, seg.start_ms, seg.end_ms, "
                "       seg.transcript_text, seg.speaker FROM pedagogy.video_transcript_segment seg "
                " WHERE seg.transcript_id = :t AND seg.review_status = 'APPROVED' "
                " ORDER BY seg.start_ms, seg.segment_index, seg.segment_id"), {"t": t["transcript_id"]}).mappings()]
        return {"video_asset_id": str(video_asset_id), "language_code": t["language_code"], "version": t["version"],
                "segments": segments}

    def list_video_segments(self, video_asset_id: str, language_code: str = "en", *, limit: int = 30, conn=None) -> list[dict]:
        doc = self.get_video_transcript(video_asset_id, language_code, conn=conn)
        return [] if doc is None else doc["segments"][:limit]

    def find_video_segment_at(self, video_asset_id: str, at_ms: int, language_code: str = "en", *, conn=None) -> dict | None:
        doc = self.get_video_transcript(video_asset_id, language_code, conn=conn)
        return None if doc is None else _segment_at(doc["segments"], at_ms)

    # ---- A27: cached LLM step hint
    def get_cached_step_hint(self, step_id: str, level: int, prompt_version: str, *, conn=None) -> str | None:
        with _pg(None, conn) as c:
            return c.execute(text(
                "SELECT hint_text FROM pedagogy.step_hint WHERE solution_step_id = :s AND hint_level = :l "
                "AND prompt_version = :v"), {"s": step_id, "l": level, "v": prompt_version}).scalar()

    def list_cached_step_hints(self, step_id: str, below_level: int, prompt_version: str, *, conn=None) -> list[str]:
        with _pg(None, conn) as c:
            return list(c.execute(text(
                "SELECT hint_text FROM pedagogy.step_hint WHERE solution_step_id = :s AND hint_level < :l "
                "AND prompt_version = :v ORDER BY hint_level"),
                {"s": step_id, "l": below_level, "v": prompt_version}).scalars())

    def put_cached_step_hint(self, step_id: str, level: int, prompt_version: str, hint_text: str, model: str, *,
                             leak_checked: bool = True, conn=None) -> bool:
        """Cache a hint once (first writer wins). ``conn`` is the caller's open transaction; without it one is opened."""
        sql = text("INSERT INTO pedagogy.step_hint (solution_step_id, hint_level, prompt_version, hint_text, model) "
                   "VALUES (:s, :l, :v, :t, :m) ON CONFLICT DO NOTHING")
        params = {"s": step_id, "l": level, "v": prompt_version, "t": hint_text, "m": model}
        if conn is not None:
            return conn.execute(sql, params).rowcount == 1
        with importlib.import_module("mathbank_rest.db.postgres").engine.begin() as c:
            return c.execute(sql, params).rowcount == 1


# ======================================================================================================== DynamoDB

def _pages(model: type, pk: str, **kw) -> Iterator[Any]:
    token = None
    while True:
        page = typed.query(model, pk, limit=200, next_token=token, **kw)
        yield from page.items
        token = page.next_token
        if not token:
            return


def _taxonomy_row(n: ContentTaxnode) -> dict:
    """Same keys as ``step_search._TAXONOMY_DETAILS``."""
    return {"taxonomy_node_id": n.taxonomy_node_id, "node_type": n.node_type, "name": n.name,
            "parent_node_id": n.parent.id_ if n.parent else None, "parent_name": n.parent.name if n.parent else None,
            "chapter_number": n.chapter_number, "section_number": n.section_number, "slug": n.slug,
            "slug_kind": n.slug_kind, "problem_count": n.problem_count, "example_problem_codes": list(n.example_problem_codes)}


def _step_row(s: ContentStep, *, with_text: bool) -> dict:
    row = {"solution_step_id": s.solution_step_id, "problem_id": str(s.problem_id), "solution_id": str(s.solution_id),
           "solution_part_id": s.solution_part_id, "global_step_index": s.global_step_index, "step_type": s.step_type,
           "tutor_role": s.tutor_role, "hint_level": s.hint_level, "is_checkpoint": s.is_checkpoint,
           "skill_node_id": s.skill_node_id, "skill_name": s.skill_name, "subconcept_node_id": s.subconcept_node_id,
           "concept_node_id": s.concept_node_id, "problem_code": s.problem_code}
    if with_text:
        row["step_text"] = s.resolve("step_text")
    return row | {"eligible": bool(s.eligible)}


def _part_labels(dag: ContentSoldag | None) -> dict[str, str]:
    if dag is None:
        return {}
    return {p.solution_part_id: p.part_label for p in dag.resolve("parts", list[ContentSoldagPartsItem]) or []}


class PedagogyDynamoDB:
    """DynamoDB backend over mb-content (typed models, stores.typed); no scans, no Postgres."""

    # ---- routes (A21, A22)
    def _route_docs(self, rel: ContentRouterel, *, server: bool = False):
        """Learner (and optionally server) snapshot of a release. The snapshot directory is the release's content hash, so a
        pointer that does not match its key is refused; the objects themselves are immutable (cached forever)."""
        keys = (rel.s3_learner_key, rel.s3_server_key) if server else (rel.s3_learner_key,)
        for key in keys:
            if f"/{rel.content_sha256}/" not in key:
                raise StoreError("route snapshot key does not match the release content hash", key=key)
        learner = snapshots.get_model(rel.s3_learner_key, RouteLearnerDoc)
        return (learner, snapshots.get_model(rel.s3_server_key, RouteServerDoc)) if server else learner

    def _release(self, route_release_id) -> ContentRouterel:
        return typed.require(ContentRouterel, f"ROUTEREL#{route_release_id}", "META", consistent=False)

    def _release_row(self, rel: ContentRouterel, learner: RouteLearnerDoc, ptr: ContentRouteptr | None = None) -> dict:
        extra = learner.model_extra or {}
        row = {"route_release_id": rel.route_release_id, "problem_id": rel.problem_id, "solution_id": rel.solution_id,
               "status": rel.status, "release_version": rel.release_version, "approach_name": rel.approach_name,
               "approach_summary": learner.approach_summary, "difficulty_level": rel.difficulty_level,
               "conceptual_load": learner.conceptual_load, "algebraic_load": learner.algebraic_load,
               "insight_load": learner.insight_load,
               "preferred_for_tutoring": ptr.preferred_for_tutoring if ptr else extra.get("preferred_for_tutoring"),
               "route_quality": ptr.route_quality if ptr and ptr.route_quality is not None else extra.get("route_quality"),
               "source_hash": rel.source_hash, "content_hash": rel.source_content_hash,
               "generator_version": rel.generator_version, "published_at": rel.published_at,
               "canonical_code": rel.problem_code}
        return row | ({"verification_status": ptr.verification_status} if ptr else {})

    def find_published_route(self, problem_code: str, *, conn=None) -> dict | None:
        """The preferred published route: the first ROUTE# sort key of the problem (it encodes ``select_published``'s ORDER BY)."""
        page = typed.query(ContentRouteptr, f"PROBLEM#{problem_code}", sk_begins="ROUTE#", limit=1, consistent=False)
        if not page.items:
            return None
        ptr = page.items[0]
        rel = typed.get(ContentRouterel, f"ROUTEREL#{ptr.route_release_id}", "META", consistent=False)
        if rel is None or rel.status != "PUBLISHED":
            return None
        return self._release_row(rel, self._route_docs(rel), ptr)

    def get_published_route(self, problem_code: str, route_release_id, *, conn=None) -> dict | None:
        rel = typed.get(ContentRouterel, f"ROUTEREL#{route_release_id}", "META", consistent=False)
        if rel is None or rel.status != "PUBLISHED" or rel.problem_code != problem_code:
            return None
        return self._release_row(rel, self._route_docs(rel))

    def load_route_learner_view(self, route_release_id, *, conn=None) -> dict:
        """The learner snapshot (instructions without ``expected_response``, hints, requirements, asset links)."""
        return _scrub(self._route_docs(self._release(route_release_id)).model_dump(mode="json"))

    def _learner_steps(self, route_release_id) -> list:
        return sorted(self._route_docs(self._release(route_release_id)).steps, key=lambda s: s.step_index)

    def list_route_instructions(self, route_release_id, *, conn=None) -> list[dict]:
        return [_safe_instruction(s.instruction) for s in self._learner_steps(route_release_id) if s.instruction is not None]

    def get_route_step_instruction(self, route_release_id, step_index: int, *, conn=None) -> dict | None:
        step = next((s for s in self._learner_steps(route_release_id) if s.step_index == step_index), None)
        return None if step is None else _safe_instruction(step.instruction)

    def get_route_step_hint(self, route_release_id, step_index: int, level: int, *, conn=None) -> str | None:
        step = next((s for s in self._learner_steps(route_release_id) if s.step_index == step_index), None)
        if step is None:
            return None
        return next((h["hint_text"] for h in step.hints if h.get("hint_level") == level
                     and h.get("hint_variant", "default") == "default" and not h.get("misconception_key")), None)

    def load_route_program(self, route_release_id, *, conn=None):
        """The full ``RouteProgram``, rebuilt from ``learner.json`` + ``server.json`` (server-side only: it has the answer keys)."""
        from mathbank_rest.route_contracts import RouteProgram

        learner, server = self._route_docs(self._release(route_release_id), server=True)
        expected = {s.step_index: s for s in server.steps}
        steps = []
        for st in sorted(learner.steps, key=lambda s: s.step_index):
            if st.instruction is None:
                continue
            srv = expected.get(st.step_index)
            steps.append({
                "mathematical_result": srv.mathematical_result if srv else None,
                "source_quote": srv.source_quote if srv else None,
                "depends_on": list(srv.depends_on) if srv else [], "produces": list(srv.produces) if srv else [],
                "uses_claims": list(srv.uses_claims) if srv else [],
                "instruction": {**st.instruction, **({"expected_response": srv.expected_response} if srv and srv.expected_response else {})},
                "requirements": [dict(r) for r in st.requirements], "asset_links": [dict(a) for a in st.asset_links],
                "hints": [h["hint_text"] for h in sorted(st.hints, key=lambda h: h["hint_level"])
                          if h["hint_level"] <= 4 and h.get("hint_variant", "default") == "default" and not h.get("misconception_key")],
            })
        return RouteProgram.model_validate({
            "approach_name": learner.approach_name, "approach_summary": learner.approach_summary,
            "difficulty_level": learner.difficulty_level, "conceptual_load": learner.conceptual_load,
            "algebraic_load": learner.algebraic_load, "insight_load": learner.insight_load,
            "steps": steps, "assets": [a.content for a in sorted(server.assets, key=lambda a: a.asset_key)]})

    # ---- A14: solution DAG
    def _code_for_problem_id(self, problem_id: str) -> str | None:
        page = typed.query(ContentProblem, f"PID#{problem_id}", index="GSI1", limit=1, consistent=False)
        return page.items[0].canonical_code if page.items else None

    def get_solution_dag(self, problem_code: str | None = None, *, problem_id: str | None = None, conn=None) -> dict:
        if (problem_code is None) == (problem_id is None):
            raise ValueError("pass exactly one of problem_code / problem_id")
        if problem_code is None:
            problem_code = self._code_for_problem_id(str(problem_id))
        items = list(_pages(ContentSoldag, f"PROBLEM#{problem_code}", sk_begins="SOLDAG#", consistent=False)) if problem_code else []
        steps: list[dict] = []
        parts: list[dict] = []
        deps: list[dict] = []
        techs: list[dict] = []
        for it in items:
            sid, labels = str(it.solution_id), _part_labels(it)
            parts += [_pick(p, DAG_PART_KEYS) | {"solution_id": sid} for p in it.resolve("parts", list[ContentSoldagPartsItem]) or []]
            steps += [_pick(s, DAG_STEP_KEYS) | {"solution_id": sid, "part_label": labels.get(s.solution_part_id)}
                      for s in it.resolve("steps", list[ContentSoldagStepsItem]) or []]
            deps += [_pick(d, DAG_DEP_KEYS) for d in it.resolve("dependencies", list[ContentSoldagDependenciesItem]) or []
                     if d.review_status != "REJECTED"]
            techs += [_pick(t, DAG_TECH_KEYS) for t in it.resolve("step_techniques", list[ContentSoldagStepTechniquesItem]) or []
                      if t.review_status == "APPROVED"]
        steps.sort(key=lambda s: (s["global_step_index"], s["solution_step_id"]))
        parts.sort(key=lambda p: (p["part_ordinal"], p["solution_part_id"]))
        deps.sort(key=lambda d: (d["from_step_id"], d["to_step_id"], d["relationship_type"]))
        techs.sort(key=lambda t: (t["solution_step_id"], t["technique_node_id"]))
        return {"problem_code": problem_code, "problem_id": str(items[0].problem_id) if items else problem_id,
                "solutions": sorted({str(i.solution_id) for i in items}), "parts": parts, "steps": steps,
                "dependencies": deps, "step_techniques": techs}

    def _soldag(self, step: ContentStep) -> ContentSoldag | None:
        return typed.get(ContentSoldag, f"PROBLEM#{step.problem_code}", f"SOLDAG#{step.solution_id}", consistent=False)

    # ---- A15: steps
    def get_step_details(self, step_ids: Iterable[str], *, include_step_text: bool = False, conn=None) -> dict[str, dict]:
        keys = [(f"STEP#{i}", "META") for i in dict.fromkeys(step_ids)]
        return {s.solution_step_id: _step_row(s, with_text=include_step_text)
                for s in typed.batch_get(ContentStep, keys, consistent=False)}

    def get_steps_by_ids(self, step_ids: Iterable[str], *, include_step_text: bool = False, conn=None) -> list[dict]:
        ids = list(dict.fromkeys(step_ids))
        found = self.get_step_details(ids, include_step_text=include_step_text)
        return [found[i] for i in ids if i in found and found[i]["eligible"]]

    def _step(self, step_id: str) -> ContentStep:
        return typed.require(ContentStep, f"STEP#{step_id}", "META", consistent=False)

    def _statement(self, problem_code: str) -> str | None:
        p = typed.get(ContentProblem, f"PROBLEM#{problem_code}", "META", consistent=False)
        return None if p is None else p.resolve("statement_text")

    def get_step_recovery_target(self, step_id: str, *, conn=None) -> dict:
        s = self._step(step_id)
        label = s.skill_name
        if not label:
            node = typed.get(ContentTaxnode, f"TAXNODE#{s.skill_node_id}", "META", consistent=False)
            label = node.name if node else None
        return {"skill_node_id": s.skill_node_id, "subconcept_node_id": s.subconcept_node_id, "label": label}

    def get_step_worked_example(self, step_id: str, *, conn=None) -> dict:
        s = self._step(step_id)
        node = typed.get(ContentTaxnode, f"TAXNODE#{s.skill_node_id}", "META", consistent=False)
        return {"step_text": s.resolve("step_text"), "skill_name": s.skill_name,
                "description": node.resolve("description") if node else None, "canonical_code": s.problem_code,
                "statement_text": self._statement(s.problem_code)}

    def get_step_origin(self, step_id: str, *, conn=None) -> dict:
        s = self._step(step_id)
        return {"canonical_code": s.problem_code, "part_label": _part_labels(self._soldag(s)).get(s.solution_part_id),
                "step_index_in_part": s.step_index_in_part, "global_step_index": s.global_step_index}

    def get_step_tutor_context(self, step_id: str, *, conn=None) -> dict:
        s = self._step(step_id)
        dag = self._soldag(s)
        earlier = [x for x in (dag.resolve("steps", list[ContentSoldagStepsItem]) if dag else None) or []
                   if x.global_step_index < s.global_step_index]
        return {"statement_text": self._statement(s.problem_code), "part_label": _part_labels(dag).get(s.solution_part_id),
                "step_type": s.step_type, "tutor_role": s.tutor_role, "skill_name": s.skill_name,
                "step_text": s.resolve("step_text"), "solution_id": str(s.solution_id),
                "global_step_index": s.global_step_index,
                "previous_steps": [x.step_text for x in sorted(earlier, key=lambda x: x.global_step_index)]}

    # ---- A24: taxonomy
    def get_taxonomy_nodes(self, node_ids: Iterable[str], *, conn=None) -> dict[str, dict]:
        keys = [(f"TAXNODE#{i}", "META") for i in dict.fromkeys(node_ids)]
        return {n.taxonomy_node_id: _taxonomy_row(n) for n in typed.batch_get(ContentTaxnode, keys, consistent=False)}

    def list_taxonomy_children(self, parent_id: str, *, conn=None) -> list[dict]:
        """Children in ``node_type#name`` order (GSI1 ``TAXCHILD#<parent>``)."""
        return [_taxonomy_row(n) for n in _pages(ContentTaxnode, f"TAXCHILD#{parent_id}", index="GSI1")]

    def list_taxonomy_nodes(self, node_types: Iterable[str] = TOPIC_NODE_TYPES, *, conn=None) -> list[dict]:
        out = [{"taxonomy_node_id": n.taxonomy_node_id, "name": n.name, "node_type": n.node_type}
               for t in dict.fromkeys(node_types) for n in _pages(ContentTaxnode, f"TAXTYPE#{t}", index="GSI2")]
        return sorted(out, key=lambda n: n["taxonomy_node_id"])

    def list_taxonomy_prerequisite_ids(self, skill_ids: Iterable[str], *, conn=None) -> list[str]:
        """No ``PREREQUISITE_OF`` edge exists in the migrated taxonomy (only PART_OF / SUPPORTS, stored on the source node), and
        the inverse lookup has no index, so there is nothing to return until the publisher writes such edges."""
        return []

    def list_topic_candidates(self, node_id: str, *, limit: int = 100, conn=None) -> list[dict]:
        """Problems whose published steps exercise a taxonomy node, ordered by code (the ``topic_candidates`` read model).

        Steps come from the STEP facet partitions (``FACET#STEP#<SKILL|SUBCONCEPT|CONCEPT|TECHNIQUE>#<node>``); the problems'
        enrichment gives difficulty and confidence. Only steps that carry vectors have facets, and the problem-level
        PENDING/REJECTED tag exclusion is not visible in mb-content (the publisher withholds those problems instead)."""
        node = typed.get(ContentTaxnode, f"TAXNODE#{node_id}", "META", consistent=False)
        if node is None or node.node_type not in TOPIC_NODE_TYPES:
            return []
        step_ids = [f.entity_id for f in _pages(ContentFacet, f"FACET#STEP#{node.node_type}#{node_id}", consistent=False)]
        steps = [s for s in typed.batch_get(ContentStep, [(f"STEP#{i}", "META") for i in step_ids], consistent=False) if s.eligible]
        skills: dict[str, set[str]] = {}
        for s in steps:
            skills.setdefault(s.problem_code, set()).add(s.skill_node_id)
        codes = sorted(skills)[:limit]
        problems = {p.canonical_code: p for p in typed.batch_get(ContentProblem, [(f"PROBLEM#{c}", "META") for c in codes], consistent=False)}
        out = []
        for code in codes:
            if code not in problems:
                continue
            enr = problems[code].resolve("enrichment", ContentProblemEnrichment | None)
            skill_ids = sorted(skills[code])
            if node.node_type == "TECHNIQUE":
                conf = [t["confidence"] for t in self.get_solution_dag(code)["step_techniques"] if t["technique_node_id"] == node_id]
                confidence = max(conf) if conf else None
            else:
                confidence = enr.taxonomy_confidence if enr else None
            structure = (enr.subconcept_node_id if enr else None, enr.problem_form if enr else None, ",".join(skill_ids))
            out.append({"canonical_code": code, "node_type": node.node_type, "confidence": confidence,
                        "difficulty": enr.difficulty_band_source_order if enr else None, "skill_ids": skill_ids,
                        "structure_key": "|".join(x for x in structure if x)})
        return out

    # ---- A26: video transcripts
    def get_video(self, video_asset_id: str, *, conn=None) -> dict | None:
        v = typed.get(ContentVideo, f"VIDEO#{video_asset_id}", "META", consistent=False)
        if v is None:
            return None
        return {"video_asset_id": v.video_asset_id, "provider": v.provider, "url": v.url, "title": v.title,
                "duration_ms": v.duration_ms, "review_status": v.review_status, "transcript_status": v.transcript_status}

    def get_video_transcript(self, video_asset_id: str, language_code: str = "en", *, conn=None) -> dict | None:
        ptr = typed.get(ContentVtranscript, f"VIDEO#{video_asset_id}", f"TRANSCRIPT#{language_code}", consistent=False)
        if ptr is None:
            return None
        if ptr.s3_key.rsplit("/", 1)[-1].removesuffix(".json") != ptr.sha256:
            raise StoreError("transcript key does not match the pointer's sha256", key=ptr.s3_key)
        doc = snapshots.get_model(ptr.s3_key, VideoTranscriptDoc)
        segments = sorted((_pick(s, SEGMENT_KEYS) for s in doc.segments),
                          key=lambda s: (s["start_ms"], s["segment_index"], s["segment_id"]))
        return {"video_asset_id": doc.video_asset_id, "language_code": doc.language_code, "version": doc.version,
                "segments": segments}

    def list_video_segments(self, video_asset_id: str, language_code: str = "en", *, limit: int = 30, conn=None) -> list[dict]:
        doc = self.get_video_transcript(video_asset_id, language_code)
        return [] if doc is None else doc["segments"][:limit]

    def find_video_segment_at(self, video_asset_id: str, at_ms: int, language_code: str = "en", *, conn=None) -> dict | None:
        doc = self.get_video_transcript(video_asset_id, language_code)
        return None if doc is None else _segment_at(doc["segments"], at_ms)

    # ---- A27: cached LLM step hint (strong reads; first writer wins)
    def get_cached_step_hint(self, step_id: str, level: int, prompt_version: str, *, conn=None) -> str | None:
        item = typed.get(ContentHint, f"HINT#{step_id}", _hint_sk(level, prompt_version), consistent=True)
        return None if item is None or item.invalidated_at is not None else item.resolve("hint_text")

    def list_cached_step_hints(self, step_id: str, below_level: int, prompt_version: str, *, conn=None) -> list[str]:
        keys = [(f"HINT#{step_id}", _hint_sk(lv, prompt_version)) for lv in HINT_LEVELS if lv < below_level]
        items = sorted((i for i in typed.batch_get(ContentHint, keys, consistent=True) if i.invalidated_at is None),
                       key=lambda i: i.hint_level)
        return [i.resolve("hint_text") for i in items]

    def put_cached_step_hint(self, step_id: str, level: int, prompt_version: str, hint_text: str, model: str, *,
                             leak_checked: bool = True, conn=None) -> bool:
        item = ContentHint(
            PK=f"HINT#{step_id}", SK=_hint_sk(level, prompt_version), solution_step_id=step_id, hint_level=level,
            prompt_version=prompt_version, hint_text=hint_text, model=model, leak_checked=leak_checked, src_rev=0,
            content_sha256=hashlib.sha256(hint_text.encode()).hexdigest(), created_at=datetime.now(UTC))
        try:
            typed.put_new(item)
        except ConditionFailed:
            return False
        return True
