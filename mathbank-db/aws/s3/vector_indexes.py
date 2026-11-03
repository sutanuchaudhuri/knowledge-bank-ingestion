"""S3 Vectors index catalogue (requirement 70 §13 C6 §8b): one entry per vector family.

Every index is float32 / 1536 / cosine. Each `sql` returns `key, embedding::text AS embedding` plus the
metadata columns; `metadata(row)` keeps only ids, codes, enums and numbers (no learner data except the
always-filtered `owner_student_id` of the private artifact index, no free text). `expected_source`
counts the same rows with the same WHERE, so the copy is checked per family. The search.embedding
families partition the table exactly: ACTIVE vectors of a known kind go to their family index and
every other vector goes to `search-archive`, so the per-index counts add up to the table total.
Empty families (theorem, artifact, quiz-question) still get an index.
"""
from __future__ import annotations

from .spec import VectorIndex

MODEL_TAG = "te3small-1536-v1"


def _name(family: str) -> str:
    return f"{family}-{MODEL_TAG}"


def _s(v):
    return None if v is None else str(v)


def _n(v):
    return None if v is None else (int(v) if float(v).is_integer() else float(v))


def _strs(v, cap: int | None = None):
    if v is None:
        return None
    out = sorted({str(x) for x in v if x is not None})
    out = out[:cap] if cap else out
    return out or None          # S3 Vectors rejects empty lists; an absent key filters the same way


def _iso(v):
    return None if v is None else v.isoformat()


# ------------------------------------------------------------------ similarity families (own tables)

_MISCONCEPTION_FROM = """
FROM knowledge.misconception_embedding me
LEFT JOIN knowledge.misconception m ON m.misconception_id = me.misconception_id"""

MISCONCEPTION = VectorIndex(
    name=_name("misconception"),
    sql=f"""
SELECT me.misconception_id::text AS key, me.embedding::text AS embedding,
       CASE WHEN m.is_active THEN 'ACTIVE' ELSE 'INACTIVE' END AS lifecycle,
       ARRAY(SELECT l.taxonomy_node_id FROM knowledge.misconception_taxonomy_link l
              WHERE l.misconception_id = me.misconception_id
              ORDER BY l.taxonomy_node_id LIMIT 16) AS taxonomy_node_ids,
       me.source_text_sha256, me.generated_at
{_MISCONCEPTION_FROM}
ORDER BY me.misconception_id""",
    metadata=lambda r: {"lifecycle": r["lifecycle"], "taxonomy_node_ids": _strs(r["taxonomy_node_ids"], 16),
                        "source_sha256": r["source_text_sha256"], "generated_at": _iso(r["generated_at"])},
    non_filterable=("source_sha256", "generated_at"),
    expected_source=f"SELECT count(*) AS n {_MISCONCEPTION_FROM}",
    note="knowledge.misconception_embedding; taxonomy_node_ids capped at the first 16 (sorted).",
)

_TAXNODE_FROM = """
FROM pedagogy.taxonomy_node_embedding te
LEFT JOIN pedagogy.taxonomy_node n ON n.taxonomy_node_id = te.taxonomy_node_id
LEFT JOIN ingest.content_package cp ON cp.content_package_id = n.content_package_id"""

TAXONOMY_NODE = VectorIndex(
    name=_name("taxonomy-node"),
    sql=f"""
SELECT te.taxonomy_node_id AS key, te.embedding::text AS embedding,
       n.node_type, CASE WHEN n.taxonomy_node_id IS NULL THEN 'DELETED' ELSE 'ACTIVE' END AS lifecycle,
       cp.book_code, n.chapter_number, te.source_text_sha256, te.generated_at
{_TAXNODE_FROM}
ORDER BY te.taxonomy_node_id""",
    metadata=lambda r: {"node_type": r["node_type"], "lifecycle": r["lifecycle"], "book_code": r["book_code"],
                        "chapter_number": _n(r["chapter_number"]), "source_sha256": r["source_text_sha256"],
                        "generated_at": _iso(r["generated_at"])},
    non_filterable=("source_sha256", "generated_at"),
    expected_source=f"SELECT count(*) AS n {_TAXNODE_FROM}",
    filter_key="node_type",
    note="pedagogy.taxonomy_node_embedding; recall is checked within each node_type.",
)

# ------------------------------------------------------------------ search.embedding families

SEARCH_KINDS = {
    "taxonomy-search": ("TAXONOMY_NODE",),
    "problem": ("PROBLEM_STATEMENT",),
    "solution": ("SOLUTION_FULL",),
    "step": ("SOLUTION_STEP",),
    "learning-item": ("LEARNING_ITEM_QUESTION", "LEARNING_ITEM_SKILL_SIGNATURE"),
}
_ALL_KINDS = tuple(k for ks in SEARCH_KINDS.values() for k in ks)


def _kinds(kinds) -> str:
    return ", ".join(f"'{k}'" for k in kinds)


_SEARCH_BASE = """
FROM search.embedding e
JOIN search.chunk c ON c.chunk_id = e.chunk_id
JOIN search.representation r ON r.representation_id = c.representation_id
JOIN search.embedding_model em ON em.embedding_model_id = e.embedding_model_id"""

_ACTIVE = "r.status = 'ACTIVE' AND e.status = 'ACTIVE' AND em.status = 'ACTIVE'"


def _active_where(family: str) -> str:
    return f"WHERE {_ACTIVE} AND r.representation_kind IN ({_kinds(SEARCH_KINDS[family])})"


def _problem_ctx(problem_id_expr: str = "c.problem_id") -> str:
    return f"""
LEFT JOIN core.problem p ON p.problem_id = {problem_id_expr}
LEFT JOIN core.paper pa ON pa.paper_id = p.paper_id
LEFT JOIN core.competition_edition ed ON ed.edition_id = pa.edition_id
LEFT JOIN core.competition comp ON comp.competition_id = ed.competition_id"""


def _search_index(family: str, select: str, joins: str, metadata, non_filterable, note: str,
                  filter_key: str | None = None) -> VectorIndex:
    frm = f"{_SEARCH_BASE}{joins}\n{_active_where(family)}"
    return VectorIndex(
        name=_name(family),
        sql=f"SELECT c.chunk_id::text AS key, e.embedding::text AS embedding, {select}{frm}\nORDER BY c.chunk_id",
        metadata=metadata, non_filterable=non_filterable,
        expected_source=f"SELECT count(*) AS n {frm}", filter_key=filter_key, note=note)


TAXONOMY_SEARCH = _search_index(
    "taxonomy-search",
    "n.node_type, n.chapter_number, c.metadata->>'taxonomy_node_id' AS taxonomy_node_id, "
    "r.content_hash, r.representation_id",
    "\nLEFT JOIN pedagogy.taxonomy_node n ON n.taxonomy_node_id = c.metadata->>'taxonomy_node_id'",
    lambda r: {"node_type": r["node_type"], "chapter_number": _n(r["chapter_number"]),
               "taxonomy_node_id": r["taxonomy_node_id"], "content_sha256": r["content_hash"],
               "representation_id": _s(r["representation_id"])},
    ("content_sha256", "representation_id"),
    "search chunks of kind TAXONOMY_NODE (POST /v1/search/concepts).")

PROBLEM = _search_index(
    "problem",
    "comp.external_code AS competition, ed.year, c.problem_id, c.chunk_kind, p.canonical_code, "
    "r.content_hash, c.chunk_ordinal, r.representation_id",
    _problem_ctx(),
    lambda r: {"competition": r["competition"], "year": _n(r["year"]), "problem_id": _s(r["problem_id"]),
               "chunk_kind": r["chunk_kind"], "canonical_code": r["canonical_code"],
               "content_sha256": r["content_hash"], "chunk_ordinal": _n(r["chunk_ordinal"]),
               "representation_id": _s(r["representation_id"])},
    ("canonical_code", "content_sha256", "chunk_ordinal", "representation_id"),
    "PROBLEM_STATEMENT chunks (problem / hybrid search, quiz examples).")

SOLUTION = _search_index(
    "solution",
    "p.problem_id, s.solution_kind, s.verification_status, comp.external_code AS competition, ed.year, "
    "s.solution_id, r.content_hash, c.chunk_ordinal",
    "\nLEFT JOIN core.solution s ON s.solution_id = coalesce(c.solution_id, r.source_entity_id)"
    + _problem_ctx("coalesce(c.problem_id, s.problem_id)"),
    lambda r: {"problem_id": _s(r["problem_id"]), "solution_kind": r["solution_kind"],
               "verification_status": r["verification_status"], "competition": r["competition"],
               "year": _n(r["year"]), "solution_id": _s(r["solution_id"]), "content_sha256": r["content_hash"],
               "chunk_ordinal": _n(r["chunk_ordinal"])},
    ("solution_id", "content_sha256", "chunk_ordinal"),
    "SOLUTION_FULL chunks; server-only (no learner route).")

STEP = _search_index(
    "step",
    "c.skill_node_id, c.subconcept_node_id, c.concept_node_id, st.step_type, st.tutor_role, st.is_checkpoint, "
    "st.hint_level, c.problem_id, st.book_code, c.solution_step_id, r.content_hash, p.canonical_code, "
    "ARRAY(SELECT t.technique_node_id FROM pedagogy.solution_step_technique t "
    "WHERE t.solution_step_id = c.solution_step_id AND t.review_status = 'APPROVED' "
    "ORDER BY t.technique_node_id LIMIT 8) AS technique_node_ids",
    "\nLEFT JOIN pedagogy.solution_step st ON st.solution_step_id = c.solution_step_id"
    "\nLEFT JOIN core.problem p ON p.problem_id = c.problem_id",
    lambda r: {"skill_node_id": r["skill_node_id"], "subconcept_node_id": r["subconcept_node_id"],
               "concept_node_id": r["concept_node_id"], "step_type": r["step_type"], "tutor_role": r["tutor_role"],
               "is_checkpoint": r["is_checkpoint"], "hint_level": _n(r["hint_level"]),
               "problem_id": _s(r["problem_id"]), "technique_node_ids": _strs(r["technique_node_ids"], 8),
               "book_code": r["book_code"], "solution_step_id": r["solution_step_id"],
               "content_sha256": r["content_hash"], "problem_code": r["canonical_code"]},
    ("solution_step_id", "content_sha256", "problem_code"),
    "SOLUTION_STEP chunks (step search, practice).")

LEARNING_ITEM = _search_index(
    "learning-item",
    "r.representation_kind AS kind, c.skill_node_id AS target_skill_node_id, "
    "c.subconcept_node_id AS target_subconcept_node_id, li.transformed_form, li.transformation_type, "
    "li.difficulty_direction, li.source_problem_id, c.learning_item_id, r.content_hash, "
    "ARRAY(SELECT a.solution_step_id FROM pedagogy.learning_item_step_anchor a "
    "WHERE a.learning_item_id = c.learning_item_id ORDER BY a.solution_step_id LIMIT 8) AS anchor_step_ids",
    "\nLEFT JOIN pedagogy.learning_item li ON li.learning_item_id = c.learning_item_id",
    lambda r: {"kind": r["kind"], "target_skill_node_id": r["target_skill_node_id"],
               "target_subconcept_node_id": r["target_subconcept_node_id"],
               "transformed_form": r["transformed_form"], "transformation_type": r["transformation_type"],
               "difficulty_direction": r["difficulty_direction"], "source_problem_id": _s(r["source_problem_id"]),
               "anchor_step_ids": _strs(r["anchor_step_ids"], 8), "learning_item_id": r["learning_item_id"],
               "content_sha256": r["content_hash"]},
    ("learning_item_id", "content_sha256"),
    "LEARNING_ITEM_QUESTION + LEARNING_ITEM_SKILL_SIGNATURE chunks (recovery practice).")

_ARCHIVE_FROM = f"{_SEARCH_BASE}\nWHERE NOT ({_ACTIVE} AND r.representation_kind IN ({_kinds(_ALL_KINDS)}))"

SEARCH_ARCHIVE = VectorIndex(
    name=_name("search-archive"),
    sql=f"""SELECT c.chunk_id::text AS key, e.embedding::text AS embedding,
       r.representation_kind AS kind, r.status || '/' || e.status || '/' || em.status AS status, r.representation_id
{_ARCHIVE_FROM}
ORDER BY c.chunk_id""",
    metadata=lambda r: {"kind": r["kind"], "status": r["status"], "representation_id": _s(r["representation_id"])},
    non_filterable=("representation_id",),
    expected_source=f"SELECT count(*) AS n {_ARCHIVE_FROM}",
    note="every search.embedding row not in an ACTIVE family (rollback/GC only).",
)

# ------------------------------------------------------------------ empty families (created empty)

_THEOREM_FROM = """
FROM knowledge.theorem_embedding te
LEFT JOIN knowledge.theorem t ON t.theorem_id = te.theorem_id"""

THEOREM = VectorIndex(
    name=_name("theorem"),
    sql=f"""
SELECT te.theorem_id::text AS key, te.embedding::text AS embedding, t.review_status, t.slug,
       te.source_text_sha256,
       ARRAY(SELECT l.taxonomy_node_id FROM knowledge.theorem_taxonomy_link l
              WHERE l.theorem_id = te.theorem_id ORDER BY 1) AS taxonomy_node_ids,
       ARRAY(SELECT tt.technique_id::text FROM knowledge.technique_theorem tt
              WHERE tt.theorem_id = te.theorem_id AND tt.review_status <> 'REJECTED' ORDER BY 1) AS technique_ids
{_THEOREM_FROM}
ORDER BY te.theorem_id""",
    metadata=lambda r: {"review_status": r["review_status"], "taxonomy_node_ids": _strs(r["taxonomy_node_ids"]),
                        "technique_ids": _strs(r["technique_ids"]), "slug": r["slug"],
                        "source_sha256": r["source_text_sha256"]},
    non_filterable=("slug", "source_sha256"),
    expected_source=f"SELECT count(*) AS n {_THEOREM_FROM}",
)

_ARTIFACT_FROM = """
FROM artifact_runtime.artifact_embedding ae
LEFT JOIN artifact_runtime.artifact_bundle b ON b.artifact_bundle_id = ae.artifact_bundle_id
LEFT JOIN artifact_runtime.artifact_request q ON q.artifact_request_id = b.artifact_request_id"""


def _tags(tag_type: str) -> str:
    return (f"ARRAY(SELECT g.tag FROM artifact_runtime.artifact_search_tag g WHERE g.artifact_bundle_id = "
            f"ae.artifact_bundle_id AND g.tag_type = '{tag_type}' ORDER BY g.tag)")


ARTIFACT_PUBLIC = VectorIndex(
    name=_name("artifact-public"),
    sql=f"""
SELECT ae.artifact_bundle_id::text AS key, ae.embedding::text AS embedding, b.subject, b.status,
       {_tags('concept')} AS concept_tags, {_tags('skill')} AS skill_tags, {_tags('theorem')} AS theorem_tags,
       ae.search_text_sha256
{_ARTIFACT_FROM}
WHERE b.status = 'PUBLISHED'
ORDER BY ae.artifact_bundle_id""",
    metadata=lambda r: {"subject": r["subject"], "status": r["status"], "concept_tags": _strs(r["concept_tags"]),
                        "skill_tags": _strs(r["skill_tags"]), "theorem_tags": _strs(r["theorem_tags"]),
                        "search_text_sha256": r["search_text_sha256"]},
    non_filterable=("search_text_sha256",),
    expected_source=f"SELECT count(*) AS n {_ARTIFACT_FROM}\nWHERE b.status = 'PUBLISHED'",
)

ARTIFACT_PRIVATE = VectorIndex(
    name=_name("artifact-private"),
    sql=f"""
SELECT ae.artifact_bundle_id::text AS key, ae.embedding::text AS embedding, q.owner_student_id, b.subject,
       b.status, ae.search_text_sha256
{_ARTIFACT_FROM}
WHERE b.status IS DISTINCT FROM 'PUBLISHED'
ORDER BY ae.artifact_bundle_id""",
    metadata=lambda r: {"owner_student_id": _s(r["owner_student_id"]), "subject": r["subject"],
                        "status": r["status"], "search_text_sha256": r["search_text_sha256"]},
    non_filterable=("search_text_sha256",),
    expected_source=f"SELECT count(*) AS n {_ARTIFACT_FROM}\nWHERE b.status IS DISTINCT FROM 'PUBLISHED'",
    note="owner-scoped: every query filters owner_student_id; erasure deletes the student's keys.",
)

# quiz.question_pool has no embedding column today, so the index is created empty and filled by the
# vector-sync worker once pool questions are embedded.
QUIZ_QUESTION = VectorIndex(
    name=_name("quiz-question"),
    sql="""
SELECT q.pool_question_id::text AS key, NULL::text AS embedding, q.style, q.question_type, q.difficulty_band,
       q.concept_slugs, encode(sha256(convert_to(q.topic_key, 'UTF8')), 'hex') AS topic_key_sha256
FROM quiz.question_pool q
WHERE false
ORDER BY q.pool_question_id""",
    metadata=lambda r: {"style": r["style"], "question_type": r["question_type"],
                        "difficulty_band": r["difficulty_band"], "concept_slugs": _strs(r["concept_slugs"]),
                        "topic_key_sha256": r["topic_key_sha256"]},
    non_filterable=("topic_key_sha256",),
    expected_source="SELECT count(*) AS n FROM quiz.question_pool q WHERE false",
    note="no source vectors (quiz.question_pool has no embedding column).",
)

INDEXES: list[VectorIndex] = [
    MISCONCEPTION, TAXONOMY_NODE, TAXONOMY_SEARCH, PROBLEM, SOLUTION, STEP, LEARNING_ITEM, SEARCH_ARCHIVE,
    THEOREM, ARTIFACT_PUBLIC, ARTIFACT_PRIVATE, QUIZ_QUESTION,
]

# family → index name; the content read model writes one VINDEX#<family>/ACTIVE pointer per read family.
FAMILY_INDEX: dict[str, str] = {ix.name[: -len(MODEL_TAG) - 1]: ix.name for ix in INDEXES}
