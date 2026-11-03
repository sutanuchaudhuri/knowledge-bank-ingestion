"""Content store, learning area (requirement 71 WP4): answer keys, micro-course reader and pinned releases, course assets,
theorems, interaction catalogue (access patterns A16-A20, A23, A31 of requirement 70 C6).

``LearningPostgres`` delegates to today's SQL modules and looks the module functions up at call time, so behaviour and the
tests that monkeypatch those functions are unchanged. ``LearningDynamoDB`` reads ``mb-content`` through ``stores.typed`` and
the immutable S3 release snapshots through ``stores.content.snapshots`` (no scans, no PostgreSQL).

Every method takes the SQL connection first (ignored by the DynamoDB backend, which callers may pass as ``None``).

Answer keys (``LI#<id>/KEY``, ``ACT#<id>/KEY``) are returned only by the ``get_*_key`` / ``get_activity_definition`` grading
lookups and the two ``get_grading_*`` methods, always with strong reads; no reader or listing method ever returns one.
"""
from __future__ import annotations

import copy
from collections.abc import Iterable
from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel, StrictInt, StrictStr
from sqlalchemy import text

from mathbank_rest.models.base import DdbItem
from mathbank_rest.models.ddb.content import (
    ContentAct,
    ContentActKey,
    ContentCatalogptr,
    ContentIinst,
    ContentItplver,
    ContentLiKey,
    ContentMc,
    ContentMcrel,
    ContentTechnique,
    ContentVasset,
)
from mathbank_rest.models.docs.content import CatalogWidgetLibrary, ReleaseSnapshot
from mathbank_rest.models.manual.content_theorem import (
    ContentTheorem,
    ContentTheoremLink,
    ContentTheoremRel,
)
from mathbank_rest.stores import typed
from mathbank_rest.stores.content.snapshots import snapshots
from mathbank_rest.stores.errors import ItemSchemaError

LEARNER_SCHEMA = "micro-course-release/learner/v1"
LINEAGE_RELATIONS = ("DEPENDS_ON", "COROLLARY_OF")
OBJECT_STORE_PREFIX = "object-store:"
_MAX_PAGES = 50


# ------------------------------------------------------------------ lenient views of generated models
# The publisher omits attributes whose value is null, so an unpublished course or a private asset lacks attributes the
# generated models (built from observed items) mark as required.

class _Mc(ContentMc):
    current_published_at: Any = None
    current_release_id: UUID | None = None
    current_release_version: StrictInt | None = None
    current_s3_key: StrictStr | None = None
    current_s3_server_key: StrictStr | None = None
    current_sha256: StrictStr | None = None


class _Vasset(ContentVasset):
    external_url: StrictStr | None = None
    rights_note: StrictStr | None = None
    source_url: StrictStr | None = None
    persistence_mode: StrictStr | None = None
    size: StrictInt | None = None
    source_uri: StrictStr | None = None


class _TaxnodeRef(DdbItem):
    """Name and type of a taxonomy node (the full TAXNODE model belongs to the pedagogy area)."""

    CTX: ClassVar[str] = "content"
    TYPE: ClassVar[str] = "TAXNODE"
    type: str = "TAXNODE"
    name: StrictStr
    node_type: StrictStr


# ------------------------------------------------------------------ helpers shared by both backends

def _errors():
    """The service modules that own the domain exceptions and the public-asset shape (imported late: they import stores)."""
    from mathbank_rest import micro_course_service as courses
    from mathbank_rest import theorem_service as theorems

    return courses, theorems


def _required_text(value: str, field: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValueError(f"{field} is required")
    return value


def _plain(value: Any) -> Any:
    """A document resolved from an item is a model or plain JSON: return JSON-shaped Python."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", by_alias=True, exclude_unset=True)
    return value


def _pages(model: type[DdbItem], pk: str, **kwargs: Any) -> Iterable[Any]:
    """All items of a key-condition query, page by page (bounded)."""
    token = None
    for _ in range(_MAX_PAGES):
        page = typed.query(model, pk, limit=200, next_token=token, **kwargs)
        yield from page.items
        token = page.next_token
        if not token:
            return


def _by_ordinal(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: r.get("ordinal") if r.get("ordinal") is not None else 0)


def _targets(targets: list[dict], role: str) -> list[dict]:
    return [{k: t.get(k) for k in ("target_type", "name", "slug")} for t in targets if t.get("role") == role]


# ------------------------------------------------------------------ reader payload (learner.json -> public reader shape)

_STATE_KEYS = ("state_id", "module_id", "module_key", "state_key", "ordinal", "state_type", "title", "objective",
               "student_instruction", "estimated_seconds", "required", "skippable")
_ASSET_KEYS = ("asset_id", "asset_kind", "title", "source_url", "mime_type", "object_size_bytes", "ordinal",
               "presentation_role", "sequence_position", "video_url", "duration_ms")
_QA_KEYS = ("context_type", "question_pattern", "approved_content", "concept_id", "technique_id", "skill_id",
            "misconception_id")
_ITEM_KEYS = ("learning_item_id", "question_text", "choices", "purpose", "ordinal", "required", "sequence_position")
_SEGMENT_KEYS = ("segment_id", "start_ms", "end_ms", "transcript_text", "speaker", "segment_index")
_INTERACTION_KEYS = ("interaction_instance_id", "canonical_code", "title", "instance_config", "initial_state",
                     "learning_objective", "success_criteria", "template_version", "template_key", "interaction_family",
                     "default_layout", "allowed_controls", "allowed_icons", "accessibility_policy", "scene_json",
                     "rendered_video_asset_id", "ordinal", "required", "sequence_position")
_ACTIVITY_KEYS = ("activity_id", "activity_type", "prompt", "options", "ordinal", "purpose", "required",
                  "sequence_position")
_TRANSITION_KEYS = ("from_state_id", "to_state_id", "transition_type", "condition_type", "condition_payload", "priority")
_MODULE_KEYS = ("module_id", "module_key", "ordinal", "title", "objective", "estimated_seconds", "required")


def _pick(row: dict, keys: tuple[str, ...]) -> dict:
    return {k: row.get(k) for k in keys}


def _project_state(state: dict) -> dict:
    """One snapshot state in exactly the shape ``_assemble_course_reader_payload`` builds (answer keys never present)."""
    from mathbank_rest.micro_course_service import _build_state_items, _learner_options

    out = _pick(state, _STATE_KEYS)
    out["assets"] = [{**_pick(a, _ASSET_KEYS), "private_object": bool(a.get("private_object"))}
                     for a in state.get("assets") or []]
    out["qa_contexts"] = [_pick(q, _QA_KEYS) for q in state.get("qa_contexts") or []]
    out["learning_items"] = [_pick(i, _ITEM_KEYS) for i in state.get("learning_items") or []]
    out["transcript_segments"] = [_pick(s, _SEGMENT_KEYS) for s in state.get("transcript_segments") or []]
    out["interactions"] = [_pick(i, _INTERACTION_KEYS) for i in state.get("interactions") or []]
    out["activities"] = [{**_pick(a, _ACTIVITY_KEYS), "options": _learner_options(a.get("options"))}
                         for a in state.get("activities") or []]
    out["items"] = _build_state_items(out)
    return out


def reader_payload(snapshot: dict) -> dict:
    """The reader payload of a ``micro-course-release/learner/v1`` snapshot; same shape as the Postgres assembler's
    public reader (approved-only content, no answer keys, no storage ``uri``)."""
    if snapshot.get("schema") != LEARNER_SCHEMA:
        raise ItemSchemaError("unexpected release snapshot schema", schema=snapshot.get("schema"))
    course, release = snapshot["course"], snapshot["release"]
    targets = _by_ordinal(snapshot.get("targets") or [])
    payload = {
        "micro_course_id": course["micro_course_id"], "canonical_code": course["canonical_code"],
        "title": course["title"], "description": course["description"], "metadata": course.get("metadata"),
        "estimated_minutes": course.get("estimated_minutes"), "difficulty_level": course.get("difficulty_level"),
        "release_id": release["release_id"], "version": release["version"],
        "learning_objectives": release.get("learning_objectives"),
        "prerequisite_summary": release.get("prerequisite_summary"),
        "primary_targets": _targets(targets, "PRIMARY"),
        "prerequisite_targets": _targets(targets, "PREREQUISITE"),
        "modules": [_pick(m, _MODULE_KEYS) for m in snapshot.get("modules") or []],
        "states": [_project_state(s) for s in snapshot.get("states") or []],
        "transitions": [_pick(t, _TRANSITION_KEYS) for t in snapshot.get("transitions") or []],
    }
    return copy.deepcopy(payload)       # the parsed snapshot is shared through the LRU: never hand out its nested objects


def snapshot_asset_ids(snapshot: dict) -> set[str]:
    """Assets a learner may fetch from a release: its state assets and the rendered videos of its approved scenes."""
    ids: set[str] = set()
    for state in snapshot.get("states") or []:
        ids.update(str(a["asset_id"]) for a in state.get("assets") or [])
        ids.update(str(i["rendered_video_asset_id"]) for i in state.get("interactions") or []
                   if i.get("rendered_video_asset_id"))
    return ids


# ------------------------------------------------------------------ PostgreSQL backend

class LearningPostgres:
    """Postgres backend: delegates to the existing SQL modules (behaviour unchanged)."""

    backend = "postgres"

    # A16 / A17: grading lookups
    def get_learning_item_key(self, conn, learning_item_id: str) -> dict | None:
        row = conn.execute(
            text("SELECT learning_item_id, correct_answer, answer_or_solution_seed "
                 "FROM pedagogy.learning_item WHERE learning_item_id=:id"),
            {"id": str(learning_item_id)},
        ).mappings().one_or_none()
        if row is None:
            return None
        return {"learning_item_id": str(row["learning_item_id"]), "correct_answer": row["correct_answer"],
                "answer_or_solution_seed": row["answer_or_solution_seed"]}

    def get_activity_definition(self, conn, activity_id: str) -> dict | None:
        row = conn.execute(
            text("SELECT activity_id, activity_type, prompt, options, target_skill, estimated_seconds, source_type, "
                 "persistence_mode FROM activity.definition WHERE activity_id=:id"),
            {"id": str(activity_id)},
        ).mappings().one_or_none()
        return None if row is None else {**row, "activity_id": str(row["activity_id"])}

    def get_activity_key(self, conn, activity_id: str) -> dict | None:
        row = conn.execute(
            text("SELECT activity_id, correctness_policy FROM activity.definition WHERE activity_id=:id"),
            {"id": str(activity_id)},
        ).mappings().one_or_none()
        if row is None:
            return None
        return {"activity_id": str(row["activity_id"]), "correctness_policy": row["correctness_policy"] or {}}

    def get_grading_item(self, conn, release_id: str, state_id: str, learning_item_id: str):
        courses, _ = _errors()
        return courses.lookup_grading_item(conn, state_id, learning_item_id)

    def get_grading_activity(self, conn, release_id: str, activity_id: str):
        courses, _ = _errors()
        return courses.lookup_grading_activity(conn, release_id, activity_id)

    # A18 / A19 / A20
    def list_published_micro_courses(self, conn, limit: int = 50, offset: int = 0) -> list[dict]:
        courses, _ = _errors()
        return courses.list_published_courses(conn, limit, offset)

    def get_micro_course_reader(self, conn, canonical_code: str) -> dict:
        courses, _ = _errors()
        return courses.get_published_course(conn, canonical_code)

    def get_pinned_micro_course_reader(self, conn, release_id: str) -> dict:
        """The reader payload of one release (the one an enrollment is pinned to), whatever its status."""
        courses, _ = _errors()
        course = conn.execute(
            text("""
            SELECT c.micro_course_id, c.canonical_code, c.title, c.description, c.metadata,
                   c.estimated_minutes, c.difficulty_level, r.release_id, r.version,
                   r.learning_objectives, r.prerequisite_summary
            FROM pedagogy.micro_course c
            JOIN pedagogy.micro_course_release r ON r.micro_course_id=c.micro_course_id
            WHERE r.release_id=:release_id
        """),
            {"release_id": str(release_id)},
        ).mappings().one_or_none()
        if course is None:
            raise courses.MicroCourseNotFound("micro-course release not found")
        return courses._assemble_course_reader_payload(conn, course)

    def get_course_asset(self, conn, canonical_code: str, asset_id: str) -> dict:
        courses, _ = _errors()
        return courses.get_published_asset(conn, canonical_code, asset_id)

    # A23: theorems
    def get_theorem_by_slug(self, conn, slug: str) -> dict:
        _, theorems = _errors()
        return theorems.get_theorem(conn, slug, include_unapproved=False)

    def get_theorem_prerequisites(self, conn, slug: str, max_depth: int = 4) -> dict:
        _, theorems = _errors()
        return theorems.get_theorem_prerequisites(conn, slug, max_depth=max_depth, include_unapproved=False)

    def get_theorems_for_technique(self, conn, technique_slug: str) -> dict:
        _, theorems = _errors()
        return theorems.get_theorems_for_technique(conn, technique_slug)

    def list_theorems_for_taxonomy_node(self, conn, taxonomy_node_id: str) -> dict:
        _, theorems = _errors()
        return theorems.list_theorems_for_taxonomy_node(conn, taxonomy_node_id)

    def get_theorem_asset(self, conn, slug: str, asset_id: str) -> dict:
        _, theorems = _errors()
        return theorems.get_published_theorem_asset(conn, slug, asset_id)

    # A31: interaction catalogue
    def get_interaction_template_version(self, conn, template_key: str, version: int) -> dict | None:
        row = conn.execute(
            text("""
            SELECT v.interaction_template_version_id, v.interaction_template_id, t.template_key,
                   t.name AS template_name, t.interaction_family, t.description AS template_description,
                   v.version, v.input_schema, v.state_schema, v.event_schema, v.output_schema, v.default_layout,
                   v.allowed_controls, v.allowed_icons, v.diagnostic_capabilities, v.animation_slots,
                   v.accessibility_policy, v.content_hash, v.status, v.published_at
            FROM visual.interaction_template_version v
            JOIN visual.interaction_template t USING (interaction_template_id)
            WHERE t.template_key=:key AND v.version=:version AND v.status IN ('PUBLISHED', 'DEPRECATED')
        """),
            {"key": template_key, "version": int(version)},
        ).mappings().one_or_none()
        if row is None:
            return None
        return {**row, "interaction_template_version_id": str(row["interaction_template_version_id"]),
                "interaction_template_id": str(row["interaction_template_id"])}

    def get_interaction_instance(self, conn, interaction_instance_id: str) -> dict | None:
        row = conn.execute(
            text("""
            SELECT i.interaction_instance_id, i.interaction_template_version_id, t.template_key,
                   v.version AS template_version, i.canonical_code, i.title, i.instance_config, i.initial_state,
                   i.learning_objective, i.success_criteria, i.review_status, i.content_hash, i.approved_at
            FROM visual.interaction_instance i
            JOIN visual.interaction_template_version v USING (interaction_template_version_id)
            JOIN visual.interaction_template t USING (interaction_template_id)
            WHERE i.interaction_instance_id=:id
        """),
            {"id": str(interaction_instance_id)},
        ).mappings().one_or_none()
        if row is None:
            return None
        return {**row, "interaction_instance_id": str(row["interaction_instance_id"]),
                "interaction_template_version_id": str(row["interaction_template_version_id"])}

    def get_widget_library(self, conn) -> dict:
        courses, _ = _errors()
        return courses.get_widget_library(conn)


# ------------------------------------------------------------------ DynamoDB backend

class LearningDynamoDB:
    """DynamoDB backend over mb-content (typed models, stores.typed) and the immutable S3 release snapshots."""

    backend = "dynamodb"

    # ---- A16 / A17: answer keys (strong reads, grading only)
    def get_learning_item_key(self, conn, learning_item_id: str) -> dict | None:
        key = typed.get(ContentLiKey, f"LI#{learning_item_id}", "KEY", consistent=True)
        if key is None:
            return None
        return {"learning_item_id": key.learning_item_id, "correct_answer": key.resolve("correct_answer"),
                "answer_or_solution_seed": key.resolve("answer_or_solution_seed")}

    def get_activity_definition(self, conn, activity_id: str) -> dict | None:
        act = typed.get(ContentAct, f"ACT#{activity_id}", "META", consistent=True)
        if act is None:
            return None
        return {"activity_id": str(act.activity_id), "activity_type": act.activity_type,
                "prompt": act.resolve("prompt"), "options": act.resolve("options") or [],
                "target_skill": act.target_skill, "estimated_seconds": act.estimated_seconds,
                "source_type": act.source_type, "persistence_mode": act.persistence_mode}

    def get_activity_key(self, conn, activity_id: str) -> dict | None:
        key = typed.get(ContentActKey, f"ACT#{activity_id}", "KEY", consistent=True)
        if key is None:
            return None
        canonical = _plain(key.resolve("correctness_policy"))
        source = _plain(key.resolve("source_correctness_policy"))
        return {"activity_id": str(key.activity_id),
                "correctness_policy": source if source is not None else _legacy_policy(canonical),
                "canonical_policy": canonical}

    def get_grading_item(self, conn, release_id: str, state_id: str, learning_item_id: str) -> dict | None:
        """The item as served in the pinned release (membership and choices from its snapshot) with its key (strong read)."""
        state = _state_of(_pinned_snapshot(release_id), state_id)
        item = next((i for i in (state or {}).get("learning_items") or []
                     if str(i["learning_item_id"]) == str(learning_item_id)), None)
        if item is None:
            return None
        key = self.get_learning_item_key(conn, learning_item_id) or {}
        return {"learning_item_id": str(item["learning_item_id"]), "choices": copy.deepcopy(item.get("choices")),
                "correct_answer": key.get("correct_answer"), "answer_or_solution_seed": key.get("answer_or_solution_seed")}

    def get_grading_activity(self, conn, release_id: str, activity_id: str) -> dict | None:
        """The activity attached anywhere in the pinned release, with its definition and key (strong reads)."""
        for state in _pinned_snapshot(release_id).get("states") or []:
            member = next((a for a in state.get("activities") or [] if str(a["activity_id"]) == str(activity_id)), None)
            if member is None:
                continue
            key = self.get_activity_key(conn, activity_id)
            if key is None:
                return None
            definition = self.get_activity_definition(conn, activity_id)
            return {"state_id": state["state_id"],
                    "activity_type": definition["activity_type"] if definition else member.get("activity_type"),
                    "options": definition["options"] if definition else copy.deepcopy(member.get("options")),
                    "correctness_policy": key["correctness_policy"]}
        return None

    # ---- A18: catalogue of published courses
    def list_published_micro_courses(self, conn, limit: int = 50, offset: int = 0) -> list[dict]:
        if limit < 1 or limit > 200 or offset < 0:
            raise ValueError("limit must be 1..200 and offset must be non-negative")
        rows = [mc for mc in _pages(_Mc, "CATALOG#MC", index="GSI2") if mc.status == "ACTIVE" and mc.current_release_id]
        rows.sort(key=lambda mc: (mc.title, mc.canonical_code))     # the index orders by "<title>#<code>"; SQL by (title, code)
        return [_catalogue_row(mc) for mc in rows[offset:offset + limit]]

    # ---- A19: reader and pinned releases
    def get_micro_course_reader(self, conn, canonical_code: str) -> dict:
        return reader_payload(_learner_snapshot(_published_mc(canonical_code).current_s3_key))

    def get_pinned_micro_course_reader(self, conn, release_id: str) -> dict:
        """The release an enrollment is pinned to (PUBLISHED, SUPERSEDED or RETIRED): its own snapshot, whatever the
        course's current release is now."""
        return reader_payload(_pinned_snapshot(release_id))

    # ---- A20: course asset
    def get_course_asset(self, conn, canonical_code: str, asset_id: str) -> dict:
        courses, _ = _errors()
        try:
            mc = _published_mc(canonical_code)
        except courses.MicroCourseNotFound:
            raise courses.MicroCourseNotFound("published course asset not found") from None
        asset_id = str(asset_id)
        if asset_id not in snapshot_asset_ids(_learner_snapshot(mc.current_s3_key)):
            raise courses.MicroCourseNotFound("published course asset not found")
        asset = typed.get(_Vasset, f"VASSET#{asset_id}", "META", consistent=False)
        if asset is None or asset.validation_status != "VALID":
            raise courses.MicroCourseNotFound("published course asset not found")
        if not (asset.source_uri or "").startswith(OBJECT_STORE_PREFIX):
            raise courses.MicroCourseConflict("course asset is not stored in the private object store")
        return {"object_key": asset.source_uri.removeprefix(OBJECT_STORE_PREFIX), "mime_type": asset.mime,
                "content_hash": asset.sha256, "object_size_bytes": asset.size}

    # ---- A23: theorems
    def get_theorem_by_slug(self, conn, slug: str) -> dict:
        _, theorems = _errors()
        t = _theorem(slug)
        return {
            "theorem_id": t.theorem_id, "slug": t.slug, "name": t.name, "kind": t.kind, "field": t.field,
            "statement_text": t.statement_text, "statement_latex": t.statement_latex, "description": t.description,
            "proof_sketch": t.proof_sketch, "source": t.source, "review_status": t.review_status,
            "approval_method": t.approval_method, "approved_at": t.approved_at, "created_at": t.created_at,
            "updated_at": t.updated_at,
            "sources": [{"theorem_source_id": s.theorem_source_id, "url": s.url, "label": s.label,
                         "source_type": s.source_type, "ordinal": s.ordinal, "review_status": "APPROVED"}
                        for s in sorted(t.sources, key=lambda s: s.ordinal)],
            "assets": [theorems._public_asset(t.slug, a) for a in _theorem_assets(t)],
            "taxonomy_links": _taxonomy_links(t),
        }

    def get_theorem_prerequisites(self, conn, slug: str, max_depth: int = 4) -> dict:
        """DEPENDS_ON / COROLLARY_OF walk toward the axioms, at most ``max_depth`` hops, cycle-safe per path; one row per
        (depth, theorem) like the recursive SQL, ordered by depth then name."""
        if max_depth < 1 or max_depth > 10:
            raise ValueError("max_depth must be 1..10")
        start = _theorem(slug)
        edges: dict[str, list[str]] = {}

        def out_edges(theorem_id: str) -> list[str]:
            if theorem_id not in edges:
                edges[theorem_id] = [r.to_theorem_id for relation in LINEAGE_RELATIONS
                                     for r in _pages(ContentTheoremRel, f"THEOREM#{theorem_id}", sk_begins=f"REL#{relation}#")]
            return edges[theorem_id]

        reached: set[tuple[int, str]] = set()
        frontier = [(start.theorem_id, (start.theorem_id,))]
        for depth in range(1, max_depth + 1):
            nxt = []
            for node, path in frontier:
                for to_id in out_edges(node):
                    if to_id not in path:
                        reached.add((depth, to_id))
                        nxt.append((to_id, (*path, to_id)))
            frontier = nxt
            if not frontier:
                break
        found = {t.theorem_id: t for t in typed.batch_get(ContentTheorem, [(f"THEOREM#{i}", "META") for _, i in reached],
                                                         consistent=False) if t.review_status == "APPROVED"}
        rows = sorted(({"depth": d, "theorem_id": i, "slug": found[i].slug, "name": found[i].name, "kind": found[i].kind}
                       for d, i in reached if i in found), key=lambda r: (r["depth"], r["name"]))
        return {"theorem": {"slug": start.slug, "name": start.name}, "prerequisites": rows}

    def get_theorems_for_technique(self, conn, technique_slug: str) -> dict:
        page = typed.query(ContentTechnique, f"SLUG#TECHNIQUE#{technique_slug}", index="GSI1", limit=1)
        if not page.items:
            return {"items": []}
        links = list(_pages(ContentTheoremLink, f"THMBY#TECHNIQUE#{page.items[0].technique_id}", index="GSI2"))
        return {"items": _link_rows(links, with_field=False)}

    def list_theorems_for_taxonomy_node(self, conn, taxonomy_node_id: str) -> dict:
        links = list(_pages(ContentTheoremLink, f"THMBY#TAXNODE#{taxonomy_node_id}", index="GSI2"))
        return {"items": _link_rows(links, with_field=True)}

    def get_theorem_asset(self, conn, slug: str, asset_id: str) -> dict:
        _, theorems = _errors()
        try:
            theorem = _theorem(slug)
        except theorems.TheoremNotFound:
            raise theorems.TheoremNotFound("theorem asset not found") from None
        asset = next((a for a in _theorem_assets(theorem) if a["asset_id"] == str(asset_id)), None)
        if asset is None:
            raise theorems.TheoremNotFound("theorem asset not found")
        if not str(asset["uri"]).startswith(OBJECT_STORE_PREFIX):
            raise theorems.TheoremConflict("theorem asset is not stored in the private object store")
        return {"object_key": asset["uri"].removeprefix(OBJECT_STORE_PREFIX), "mime_type": asset["mime_type"],
                "content_hash": asset["content_hash"], "object_size_bytes": asset["object_size_bytes"]}

    # ---- A31: interaction catalogue
    def get_interaction_template_version(self, conn, template_key: str, version: int) -> dict | None:
        item = typed.get(ContentItplver, f"ITPL#{template_key}", f"V#{int(version):04d}", consistent=False)
        return None if item is None or item.status not in ("PUBLISHED", "DEPRECATED") else _template_version(item)

    def get_interaction_instance(self, conn, interaction_instance_id: str) -> dict | None:
        item = typed.get(ContentIinst, f"IINST#{interaction_instance_id}", "META", consistent=False)
        if item is None:
            return None
        return {"interaction_instance_id": str(item.interaction_instance_id),
                "interaction_template_version_id": str(item.interaction_template_version_id),
                "template_key": item.template_key, "template_version": item.template_version,
                "canonical_code": item.canonical_code, "title": item.title,
                "instance_config": _plain(item.resolve("instance_config")),
                "initial_state": _plain(item.resolve("initial_state")),
                "learning_objective": item.learning_objective,
                "success_criteria": _plain(item.resolve("success_criteria")),
                "review_status": item.review_status, "content_hash": item.source_content_hash,
                "approved_at": item.approved_at}

    def get_widget_library(self, conn) -> dict:
        """The published widget library (catalogue snapshot) in the admin ``/templates`` shape; the snapshot holds only
        PUBLISHED/DEPRECATED template versions, so DRAFT versions are not listed."""
        pointer = typed.get(ContentCatalogptr, "CATALOG#WIDGET-LIBRARY", "SNAPSHOT", consistent=True)
        if pointer is None:
            return {"templates": [], "controls": [], "icons": [], "animations": []}
        library = snapshots.get_model(pointer.s3_key, CatalogWidgetLibrary).items
        templates = []
        for template in sorted(library.interaction_templates, key=lambda t: t.template_key):
            ids = {v.template_version: str(v.interaction_template_version_id)
                   for v in _pages(ContentItplver, f"ITPL#{template.template_key}")}
            for version in sorted(template.versions, key=lambda v: v["version"]):
                templates.append({
                    "interaction_template_id": str(template.interaction_template_id), "template_key": template.template_key,
                    "interaction_family": template.interaction_family, "status": "ACTIVE",
                    "interaction_template_version_id": ids.get(version["version"]),
                    "version": version["version"], "version_status": version["status"]})
        return {
            "templates": templates,
            "controls": [{"control_key": c.control_key, "control_type": c.control_type, "status": "ACTIVE"}
                         for c in sorted(library.controls, key=lambda c: c.control_key)],
            "icons": [{"token_key": i.token_key, "icon_class": i.icon_class, "accessible_label": i.accessible_label,
                       "status": "ACTIVE"} for i in sorted(library.icons, key=lambda i: i.token_key)],
            "animations": [{"animation_key": a.animation_key, "name": a.name, "status": "ACTIVE"}
                           for a in sorted(library.animations, key=lambda a: a.animation_key)],
        }


# ------------------------------------------------------------------ DynamoDB helpers

def _published_mc(canonical_code: str) -> _Mc:
    courses, _ = _errors()
    code = _required_text(canonical_code, "canonical_code")
    mc = typed.get(_Mc, f"MC#{code}", "META", consistent=False)
    if mc is None or mc.status != "ACTIVE" or not mc.current_s3_key:
        raise courses.MicroCourseNotFound("published micro-course not found")
    return mc


def _learner_snapshot(key: str) -> dict:
    return snapshots.get_model(key, ReleaseSnapshot)


def _pinned_snapshot(release_id: str) -> dict:
    courses, _ = _errors()
    release = typed.get(ContentMcrel, f"MCREL#{release_id}", "META", consistent=False)
    if release is None:
        raise courses.MicroCourseNotFound("micro-course release not found")
    return _learner_snapshot(release.s3_learner_key)


def _state_of(snapshot: dict, state_id: str) -> dict | None:
    return next((s for s in snapshot.get("states") or [] if str(s["state_id"]) == str(state_id)), None)


def _catalogue_row(mc: _Mc) -> dict:
    extra = mc.model_extra or {}
    count = extra.get("state_count")
    if count is None:
        count = len(_learner_snapshot(mc.current_s3_key).get("states") or [])
    targets = _by_ordinal([t.model_dump(mode="json", by_alias=True) for t in mc.targets])
    return {
        "canonical_code": mc.canonical_code, "title": mc.title, "description": mc.description,
        "metadata": mc.metadata.model_dump(mode="json", by_alias=True, exclude_unset=True),
        "estimated_minutes": mc.estimated_minutes, "difficulty_level": extra.get("difficulty_level"),
        "release_id": str(mc.current_release_id), "version": mc.current_release_version,
        "state_count": count, "primary_targets": _targets(targets, "PRIMARY"),
    }


def _legacy_policy(canonical: dict | None) -> dict:
    """Rebuild the ``activity.definition.correctness_policy`` vocabulary from the canonical key when the source is absent."""
    if not canonical:
        return {}
    policy = dict(canonical.get("extra") or {})
    kind, answer = canonical.get("kind"), canonical.get("answer")
    if kind == "single":
        policy["correct_index"] = answer
    elif kind == "multi":
        policy["correct_indices"] = answer
    elif kind == "numeric":
        policy["correct_value"] = answer
        if canonical.get("tolerance"):
            policy["tolerance"] = canonical["tolerance"]
    elif kind == "text":
        policy["accepted_answers"] = answer
    if canonical.get("explanation") is not None:
        policy["explanation"] = canonical["explanation"]
    return policy


def _theorem(slug: str) -> ContentTheorem:
    _, theorems = _errors()
    page = typed.query(ContentTheorem, f"SLUG#THEOREM#{slug}", index="GSI1", limit=1)
    if not page.items or page.items[0].review_status != "APPROVED":
        raise theorems.TheoremNotFound(f"theorem '{slug}' not found")
    return page.items[0]


def _theorem_assets(theorem: ContentTheorem) -> list[dict]:
    """VALID diagrams of a theorem, with what ``theorem_service._public_asset`` and the content route need."""
    found = {str(a.asset_id): a for a in typed.batch_get(
        _Vasset, [(f"VASSET#{a.asset_id}", "META") for a in theorem.assets], consistent=False)}
    out = []
    for ref in sorted(theorem.assets, key=lambda a: a.ordinal):
        asset = found.get(ref.asset_id)
        if asset is None or asset.validation_status != "VALID":
            continue
        out.append({
            "asset_id": ref.asset_id, "ordinal": ref.ordinal, "caption": ref.caption, "mime_type": asset.mime,
            "uri": asset.source_uri or asset.external_url or "", "source_url": asset.source_url,
            "content_hash": asset.sha256, "object_size_bytes": asset.size,
        })
    return out


def _taxonomy_links(theorem: ContentTheorem) -> list[dict]:
    links = list(_pages(ContentTheoremLink, f"THEOREM#{theorem.theorem_id}", sk_begins="LINK#TAXNODE#"))
    nodes = {n.PK.removeprefix("TAXNODE#"): n for n in typed.batch_get(
        _TaxnodeRef, [(f"TAXNODE#{link.taxonomy_node_id}", "META") for link in links], consistent=False)}
    rows = [{"taxonomy_node_id": link.taxonomy_node_id, "role": link.role,
             "node_type": nodes[link.taxonomy_node_id].node_type, "name": nodes[link.taxonomy_node_id].name}
            for link in links if link.taxonomy_node_id in nodes]
    return sorted(rows, key=lambda r: (r["role"], r["name"]))


def _link_rows(links: list[ContentTheoremLink], *, with_field: bool) -> list[dict]:
    theorems = {t.theorem_id: t for t in typed.batch_get(
        ContentTheorem, [(f"THEOREM#{link.theorem_id}", "META") for link in links], consistent=False)
        if t.review_status == "APPROVED"}
    rows = []
    for link in links:
        theorem = theorems.get(link.theorem_id)
        if theorem is not None:
            row = {"slug": theorem.slug, "name": theorem.name, "kind": theorem.kind}
            if with_field:
                row["field"] = theorem.field
            rows.append({**row, "role": link.role})
    if with_field:
        return sorted(rows, key=lambda r: (0 if r["role"] == "PRIMARY" else 1, r["name"]))
    return sorted(rows, key=lambda r: (r["role"], r["name"]))


def _template_version(item: ContentItplver) -> dict:
    return {
        "interaction_template_version_id": str(item.interaction_template_version_id),
        "interaction_template_id": str(item.interaction_template_id), "template_key": item.template_key,
        "template_name": item.template_name, "interaction_family": item.interaction_family,
        "template_description": item.template_description, "version": item.template_version,
        **{attr: _plain(item.resolve(attr)) for attr in ("input_schema", "state_schema", "event_schema", "output_schema",
                                                           "default_layout", "accessibility_policy")},
        "allowed_controls": list(item.allowed_controls), "allowed_icons": list(item.allowed_icons),
        "diagnostic_capabilities": list(item.diagnostic_capabilities), "animation_slots": list(item.animation_slots),
        "content_hash": item.source_content_hash, "status": item.status, "published_at": item.published_at,
    }
