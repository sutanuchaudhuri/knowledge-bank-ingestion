"""C6 — published content read model `mb-content-<env>` + immutable S3 release snapshots.

Design: requirement 70 §13 C6 (§1 scope, §3 key schema, §4 write paths, §5 S3 layout, §7 migration).
PostgreSQL stays the authoring source of truth; this module is the backfill of the derived projection:
only published / approved / student-visible rows are projected. Server-only data (answer keys,
solutions, solution DAGs, `server.json` snapshot halves) lives in separate items/objects that never
carry GSI keys (so no index can return them, whatever the projection). Large attributes are offloaded by the
engine (`OFFLOAD`, > 16 KiB → `<attr>_ref`). Standalone objects — release snapshots, catalogue snapshots,
transcripts and student image bytes — go to the content bucket under hash-addressed keys
(`releases/<kind>/<id>/<sha256>/{learner,server}.json`); the pointer items hold `s3_*_key` + sha256.

Backfilled items carry `src_rev = 0` (pipeline.content_revision does not exist yet, so any later
publisher write with a real revision wins) and `version = 1`. `content_sha256` is the sha256 of the
item's canonical JSON payload (keys, GSI keys and bookkeeping excluded), as §7a verification expects.
Tables used only inline (children embedded into an aggregate) get a key-only coverage mapping so their
row counts are still checked.
"""
from __future__ import annotations

import hashlib
import mimetypes
import os

from aws.common import json_bytes, to_ddb
from aws.dynamo.spec import Mapping, S3Put, Table
from aws.s3.vector_indexes import FAMILY_INDEX

T = "content"
TABLES = [Table(T, gsis=("GSI1", "GSI2"), stream=True, ttl=True,
                description="C6 published content read model (PK/SK, GSI1/GSI2 ALL, stream, TTL for QEMB)")]

VERSION = 1
SRC_REV = 0

# Large content attributes → engine offload (s3://mathbank-data-<env>-<account>/offload/content/…, replaced by
# <attr>_ref) when larger than MB_OFFLOAD_THRESHOLD (16 KiB). This replaces the design's hand-rolled 100 KB
# SOLUTION/SOLDAG offload (§1a/§3) with the one engine mechanism; content_sha256 is computed before offload.
OFFLOAD: dict[tuple[str, str], tuple[str, ...]] = {
    (T, "PROBLEM"): ("statement_text", "statement_latex", "concepts", "techniques", "enrichment"),
    (T, "PROBLEM_KEY"): ("official_answer",),
    (T, "SOLUTION"): ("body_markdown", "body_latex"),
    (T, "SOLDAG"): ("steps", "parts", "dependencies", "step_techniques"),
    (T, "STEP"): ("step_text",),
    (T, "LI"): ("question_text", "choices"),
    (T, "LI_KEY"): ("correct_answer", "answer_or_solution_seed"),
    (T, "ACT"): ("prompt", "options"),
    (T, "ACT_KEY"): ("correctness_policy", "source_correctness_policy"),
    (T, "CONCEPT"): ("description", "relations_out", "relations_in"),
    (T, "SKILL"): ("relations_out", "relations_in", "concepts"),
    (T, "MISCONCEPTION"): ("description", "recognition_pattern", "taxonomy_node_ids"),
    (T, "THEOREM"): ("statement_text", "statement_latex", "description", "proof_sketch"),
    (T, "TAXNODE"): ("description", "edges"),
    (T, "SOURCEBOOK"): ("metadata", "sections"),
    (T, "ITPLVER"): ("input_schema", "state_schema", "event_schema", "output_schema", "default_layout",
                     "accessibility_policy"),
    (T, "IINST"): ("instance_config", "initial_state", "success_criteria"),
    (T, "SCENE"): ("scene_json",),
    (T, "HINT"): ("hint_text",),
    (T, "STATS"): ("rows",),
}
_BOOKKEEPING = ("PK", "SK", "type", "version", "src_rev", "content_sha256")
_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


# ------------------------------------------------------------------ helpers

def _sha(obj) -> str:
    return hashlib.sha256(json_bytes(to_ddb(obj))).hexdigest()


def _item(pk: str, sk: str, typ: str, gsi: dict | None = None, **attrs) -> dict:
    """Content item with bookkeeping. `content_sha256` = sha256 of the payload unless given explicitly."""
    body = {k: v for k, v in attrs.items() if v is not None}
    sha = body.pop("content_sha256", None) or _sha(body)
    return {"PK": pk, "SK": sk, "type": typ, **(gsi or {}), **body,
            "version": VERSION, "src_rev": SRC_REV, "content_sha256": sha}


def _yr(v) -> str:
    return f"{int(v):04d}" if v is not None else "0000"


def _num(v, width: int) -> str:
    return f"{int(v):0{width}d}" if v is not None else "0" * width


def _list(v) -> list:
    return list(v) if v else []


def _vec(row: dict, family: str, prefix: str = "v_") -> dict | None:
    keys = row.get(f"{prefix}keys")
    if not keys:
        return None
    return {"index": FAMILY_INDEX[family], "keys": list(keys), "sha256": row.get(f"{prefix}sha"),
            "model": row.get(f"{prefix}model")}


def _coverage(table: str, keys: str, note: str) -> Mapping:
    """Key-only read of a table that is embedded into another item/snapshot (row count check only)."""
    return Mapping(table, T, f"SELECT {keys} FROM {table} ORDER BY {keys}", lambda r: (),
                   expected_source=table, note=f"no own items: {note}")


_ACTIVE_VEC = "r.status = 'ACTIVE' AND e.status = 'ACTIVE' AND em.status = 'ACTIVE'"


def _vec_cte(name: str, kinds: tuple[str, ...], entity_expr: str) -> str:
    """CTE: entity_id → ACTIVE chunk keys / representation content hash / model for one vector family."""
    kinds_sql = ", ".join(f"'{k}'" for k in kinds)
    return f"""{name} AS (
    SELECT {entity_expr} AS entity_id,
           array_agg(c.chunk_id::text ORDER BY c.chunk_id) AS keys,
           string_agg(DISTINCT r.content_hash, ',' ORDER BY r.content_hash) AS sha,
           min(em.model_name) AS model
      FROM search.embedding e
      JOIN search.chunk c ON c.chunk_id = e.chunk_id
      JOIN search.representation r ON r.representation_id = c.representation_id
      JOIN search.embedding_model em ON em.embedding_model_id = e.embedding_model_id
     WHERE {_ACTIVE_VEC} AND r.representation_kind IN ({kinds_sql})
     GROUP BY 1)"""


_PROBLEM_CTX = """
  JOIN core.paper pa ON pa.paper_id = p.paper_id
  JOIN core.competition_edition ed ON ed.edition_id = pa.edition_id
  JOIN core.competition comp ON comp.competition_id = ed.competition_id"""

# db/problem_images.py STUDENT_IMAGE_FILTER (alias i = core.problem_image)
STUDENT_IMAGE_FILTER = """
    i.source NOT IN ('PDF_PARSED', 'AOPS_CRAWL', 'PDF_SOLUTION_PAGE', 'PDF_SOLUTION_FIGURE',
                     'PDF_ANSWER_PAGE', 'AOPS_SOLUTION_DIAGRAM', 'ADMIN_SOLUTION_DIAGRAM')
    AND i.local_path !~* '(^|/)(solution|answer)[_.-]'
    AND i.local_path !~* '(^|/)problem_page_[0-9]+[.]png$'
    AND NOT EXISTS (
        SELECT 1 FROM pedagogy.diagram d
        WHERE d.problem_image_id = i.problem_image_id
          AND d.visibility <> 'STUDENT_PROBLEM'
    )"""

# db/queries.technique_problem_evidence_sql(filter_slug=False)
TECHNIQUE_EVIDENCE = """
WITH step_support AS (
    SELECT s.problem_id,n.technique_id,min(st.confidence) AS confidence
    FROM pedagogy.solution_step_technique st
    JOIN pedagogy.solution_step s USING(solution_step_id)
    JOIN pedagogy.taxonomy_node n ON n.taxonomy_node_id=st.technique_node_id
    JOIN knowledge.technique t ON t.technique_id=n.technique_id
    WHERE TRUE AND s.publication_status='PUBLISHED'
      AND st.review_status='APPROVED'
    GROUP BY s.problem_id,n.technique_id
), technique_evidence AS (
    SELECT pt.problem_id,pt.technique_id,pt.role,pt.confidence
    FROM knowledge.problem_technique pt
    JOIN knowledge.technique t USING(technique_id)
    LEFT JOIN step_support ss USING(problem_id,technique_id)
    WHERE TRUE AND pt.review_status='REVIEWED'
      AND (pt.approval_method='human' OR ss.problem_id IS NOT NULL
        OR NOT EXISTS (SELECT 1 FROM pedagogy.solution_step s WHERE s.problem_id=pt.problem_id))
    UNION ALL
    SELECT ss.problem_id,ss.technique_id,'STEP_SUPPORTED',ss.confidence
    FROM step_support ss
    WHERE NOT EXISTS (SELECT 1 FROM knowledge.problem_technique pt
        WHERE pt.problem_id=ss.problem_id AND pt.technique_id=ss.technique_id)
)
"""


def _local_file(path: str | None) -> str | None:
    """Resolve an operator-host image path (the ingestion dir was renamed to mathbank-data-ingestion)."""
    if not path:
        return None
    cands = [path, path.replace("/mathbank_data_ingestion/", "/mathbank-data-ingestion/"),
             os.path.join(_REPO, path.lstrip("/"))]
    root = os.environ.get("MB_IMAGE_ROOT")
    if root:
        cands.append(os.path.join(root, os.path.basename(path)))
    return next((c for c in cands if os.path.isfile(c)), None)


def _image_version(source: str, path: str) -> str:
    return hashlib.sha256(f"{source}:{path}".encode()).hexdigest()[:12]


def _canon_policy(policy) -> dict:
    """ACT-F03/ACT-S03: one answer-key vocabulary {kind: single|multi|numeric|text|unknown, answer, tolerance}."""
    p = dict(policy or {})
    expl = p.pop("explanation", None)
    if "correct_index" in p:
        kind, answer = "single", p.pop("correct_index")
    elif "correct_option" in p:
        kind, answer = "single", p.pop("correct_option")
    elif "correct_indices" in p or "correct_options" in p:
        kind, answer = "multi", sorted(p.pop("correct_indices", None) or p.pop("correct_options"), key=str)
    elif "correct_value" in p:
        kind, answer = "numeric", p.pop("correct_value")
    elif "correct_text" in p or "accepted_answers" in p:
        kind, answer = "text", p.pop("accepted_answers", None) or [p.pop("correct_text")]
    else:
        kind, answer = "unknown", None
    tol = p.pop("tolerance", 0 if kind == "numeric" else None)
    return {"schema": "activity-key/v1", "kind": kind, "answer": answer, "tolerance": tol,
            "explanation": expl, "extra": p or None}


# ------------------------------------------------------------------ competitions and problems

def _competition(r):
    yield _item("CATALOG#COMPETITION", f"COMP#{r['name']}#{r['competition_id']}", "COMPETITION",
                competition_id=r["competition_id"], external_code=r["external_code"], name=r["name"],
                organization=r["organization"], country=r["country"], level=r["level"])


_PROBLEM_SQL = f"""
WITH {_vec_cte("pv", ("PROBLEM_STATEMENT",), "c.problem_id")}
SELECT p.problem_id, p.canonical_code, p.problem_number, p.statement_text, p.statement_latex, p.answer_type,
       p.official_answer, p.source_url, p.status, p.content_hash, p.difficulty_band, p.classification_status,
       p.created_at, p.updated_at, p.admin_edited_at,
       pa.paper_id, pa.paper_code, pa.paper_type, pa.external_code AS paper_external_code,
       ed.edition_id, ed.year, ed.season, ed.edition_label,
       comp.competition_id, comp.name AS competition_name, comp.external_code AS competition_code,
       comp.level AS competition_level,
       (SELECT json_agg(json_build_object('concept_id', c.concept_id, 'slug', c.slug, 'name', c.name,
                        'role', pc.role, 'confidence', pc.confidence) ORDER BY c.slug, pc.role)
          FROM knowledge.problem_concept pc JOIN knowledge.concept c ON c.concept_id = pc.concept_id
         WHERE pc.problem_id = p.problem_id AND pc.review_status <> 'REJECTED') AS concepts,
       (SELECT json_agg(json_build_object('technique_id', t.technique_id, 'slug', t.slug, 'name', t.name,
                        'role', pt.role, 'confidence', pt.confidence) ORDER BY t.slug, pt.role)
          FROM knowledge.problem_technique pt JOIN knowledge.technique t ON t.technique_id = pt.technique_id
         WHERE pt.problem_id = p.problem_id AND pt.review_status = 'REVIEWED') AS techniques,
       (SELECT json_agg(json_build_object('problem_image_id', i.problem_image_id, 'ordinal', i.ordinal,
                        'source', i.source, 'local_path', i.local_path) ORDER BY i.ordinal, i.problem_image_id)
          FROM core.problem_image i WHERE i.problem_id = p.problem_id AND {STUDENT_IMAGE_FILTER}) AS images,
       (SELECT row_to_json(x) FROM (
            SELECT book_code, source_problem_id, chapter_number, section_number, section_title,
                   source_printed_problem_id, source_editorial_marker, source_numbering_note, source_pdf,
                   source_page_start, source_page_end, problem_requires_diagram, solution_requires_diagram,
                   difficulty_rank_in_section, section_problem_count
              FROM pedagogy.problem_source_ref sr WHERE sr.problem_id = p.problem_id
             ORDER BY sr.book_code, sr.source_problem_id LIMIT 1) x) AS source_ref,
       (SELECT row_to_json(x) FROM (
            SELECT concept_node_id, subconcept_node_id, primary_skill_node_id, solution_step_skill_ids,
                   technique_ids, problem_form, difficulty_band_source_order, solution_step_count,
                   taxonomy_mapping_basis, taxonomy_confidence
              FROM pedagogy.problem_enrichment pe WHERE pe.problem_id = p.problem_id LIMIT 1) x) AS enrichment,
       pv.keys AS v_keys, pv.sha AS v_sha, pv.model AS v_model
  FROM core.problem p {_PROBLEM_CTX}
  LEFT JOIN pv ON pv.entity_id = p.problem_id
 WHERE p.status = 'ACTIVE'
 ORDER BY p.canonical_code"""


def _problem(r):
    code, pk = r["canonical_code"], f"PROBLEM#{r['canonical_code']}"
    images = [{"problem_image_id": i["problem_image_id"], "ordinal": i["ordinal"], "source": i["source"],
               "version": _image_version(i["source"], i["local_path"])} for i in _list(r["images"])]
    gsi = {"GSI1PK": f"PID#{r['problem_id']}", "GSI1SK": "META"}
    if r["competition_code"]:
        gsi.update(GSI2PK=f"PLIST#{r['competition_code']}",
                   GSI2SK=f"{_yr(r['year'])}#{r['paper_code']}#{_num(r['problem_number'], 6)}")
    vec = _vec(r, "problem")
    yield _item(pk, "META", "PROBLEM", gsi,
                problem_id=r["problem_id"], canonical_code=code, statement_text=r["statement_text"],
                statement_latex=r["statement_latex"], source_url=r["source_url"],
                difficulty_band=r["difficulty_band"], classification_status=r["classification_status"],
                competition={"competition_id": r["competition_id"], "name": r["competition_name"],
                             "external_code": r["competition_code"], "level": r["competition_level"]},
                year=r["year"], season=r["season"], edition_label=r["edition_label"], paper_id=r["paper_id"],
                paper_code=r["paper_code"], paper_type=r["paper_type"], problem_number=r["problem_number"],
                concepts=_list(r["concepts"]), techniques=_list(r["techniques"]), images=images,
                source_ref=r["source_ref"], enrichment=r["enrichment"],
                search_render_sha256=vec["sha256"] if vec else None, vector_state=vec, visibility="ACTIVE",
                source_content_hash=r["content_hash"], created_at=r["created_at"], updated_at=r["updated_at"],
                admin_edited_at=r["admin_edited_at"])
    yield _item(pk, "KEY#ANSWER", "PROBLEM_KEY", problem_id=r["problem_id"],
                official_answer=r["official_answer"], answer_type=r["answer_type"])


_SOLUTION_SQL = f"""
WITH {_vec_cte("sv", ("SOLUTION_FULL",), "coalesce(c.solution_id, r.source_entity_id)")}
SELECT s.solution_id, s.problem_id, p.canonical_code, s.solution_kind, s.revision, s.body_markdown, s.body_latex,
       s.verification_status, s.created_at, sv.keys AS v_keys, sv.sha AS v_sha, sv.model AS v_model
  FROM core.solution s JOIN core.problem p ON p.problem_id = s.problem_id
  LEFT JOIN sv ON sv.entity_id = s.solution_id
 ORDER BY s.solution_id"""


def _solution(r):
    yield _item(f"PROBLEM#{r['canonical_code']}",
                f"KEY#SOLUTION#{r['solution_kind']}#{_num(r['revision'], 4)}#{r['solution_id']}", "SOLUTION",
                solution_id=r["solution_id"], problem_id=r["problem_id"], solution_kind=r["solution_kind"],
                revision=r["revision"], verification_status=r["verification_status"], created_at=r["created_at"],
                body_markdown=r["body_markdown"], body_latex=r["body_latex"], vector_state=_vec(r, "solution"))


def _tag_ctx(r) -> dict:
    return {"problem_code": r["canonical_code"], "problem_id": r["problem_id"], "year": r["year"],
            "problem_number": r["problem_number"], "competition_name": r["competition_name"]}


def _tag_sk(r) -> str:
    return f"{_yr(r['year'])}#{_num(r['problem_number'], 6)}#{r['canonical_code']}"


_TAG_COLS = "p.canonical_code, p.problem_number, ed.year, comp.name AS competition_name"

_PTAG_CONCEPT_FROM = """knowledge.problem_concept pc JOIN core.problem p ON p.problem_id = pc.problem_id
 WHERE pc.review_status <> 'REJECTED' AND p.status = 'ACTIVE'"""

_PTAG_CONCEPT_SQL = f"""
SELECT DISTINCT ON (pc.problem_id, pc.concept_id)
       pc.problem_id, pc.concept_id, pc.role, pc.confidence, pc.review_status, pc.approval_method,
       pc.assertion_source, c.slug,
       ARRAY(SELECT DISTINCT x.role FROM knowledge.problem_concept x
              WHERE x.problem_id = pc.problem_id AND x.concept_id = pc.concept_id
                AND x.review_status <> 'REJECTED' ORDER BY 1) AS source_roles,
       {_TAG_COLS}
  FROM knowledge.problem_concept pc
  JOIN core.problem p ON p.problem_id = pc.problem_id {_PROBLEM_CTX}
  JOIN knowledge.concept c ON c.concept_id = pc.concept_id
 WHERE pc.review_status <> 'REJECTED' AND p.status = 'ACTIVE'
 ORDER BY pc.problem_id, pc.concept_id, (upper(pc.role) = 'PRIMARY') DESC, pc.confidence DESC NULLS LAST, pc.role"""


def _ptag_concept(r):
    yield _item(f"PROBLEM#{r['canonical_code']}", f"TAG#CONCEPT#{r['concept_id']}", "PTAG",
                {"GSI1PK": f"CONCEPT#{r['concept_id']}", "GSI1SK": _tag_sk(r)},
                tag_kind="CONCEPT", concept_id=r["concept_id"], slug=r["slug"], role=(r["role"] or "").upper(),
                source_roles=_list(r["source_roles"]), confidence=r["confidence"], review_status=r["review_status"],
                approval_method=r["approval_method"], assertion_source=r["assertion_source"], **_tag_ctx(r))


_PTAG_TECHEV_SQL = TECHNIQUE_EVIDENCE + f"""
SELECT DISTINCT ON (te.problem_id, te.technique_id)
       te.problem_id, te.technique_id, te.role, te.confidence, t.slug,
       pt.review_status, pt.approval_method, (pt.problem_id IS NULL) AS step_supported_only,
       ARRAY(SELECT DISTINCT x.role FROM technique_evidence x
              WHERE x.problem_id = te.problem_id AND x.technique_id = te.technique_id ORDER BY 1) AS source_roles,
       {_TAG_COLS}
  FROM technique_evidence te
  JOIN core.problem p ON p.problem_id = te.problem_id {_PROBLEM_CTX}
  JOIN knowledge.technique t ON t.technique_id = te.technique_id
  LEFT JOIN knowledge.problem_technique pt
         ON pt.problem_id = te.problem_id AND pt.technique_id = te.technique_id AND pt.role = te.role
 WHERE p.status = 'ACTIVE'
 ORDER BY te.problem_id, te.technique_id, (upper(te.role) ~ '^PRIMARY') DESC, te.confidence DESC NULLS LAST, te.role"""

_PTAG_TECHEV_EXPECTED = ("(" + TECHNIQUE_EVIDENCE + """
SELECT DISTINCT te.problem_id, te.technique_id FROM technique_evidence te
  JOIN core.problem p ON p.problem_id = te.problem_id WHERE p.status = 'ACTIVE') x""")


def _ptag_techev(r):
    yield _item(f"PROBLEM#{r['canonical_code']}", f"TAG#TECHEV#{r['technique_id']}", "PTAG",
                {"GSI1PK": f"TECHNIQUE#{r['technique_id']}", "GSI1SK": _tag_sk(r)},
                tag_kind="TECHEV", technique_id=r["technique_id"], slug=r["slug"], role=(r["role"] or "").upper(),
                source_roles=_list(r["source_roles"]), confidence=r["confidence"],
                review_status=r["review_status"] or ("STEP_SUPPORTED" if r["step_supported_only"] else None),
                approval_method=r["approval_method"], **_tag_ctx(r))


_PTAG_SKILL_FROM = """knowledge.problem_skill ps JOIN core.problem p ON p.problem_id = ps.problem_id
 WHERE ps.review_status <> 'REJECTED' AND p.status = 'ACTIVE'"""

_PTAG_SKILL_SQL = f"""
SELECT ps.problem_id, ps.skill_id, ps.relation_type, ps.role, ps.required_level, ps.importance, ps.source,
       ps.confidence, ps.review_status, ps.approval_method, k.slug, {_TAG_COLS}
  FROM knowledge.problem_skill ps
  JOIN core.problem p ON p.problem_id = ps.problem_id {_PROBLEM_CTX}
  JOIN knowledge.skill k ON k.skill_id = ps.skill_id
 WHERE ps.review_status <> 'REJECTED' AND p.status = 'ACTIVE'
 ORDER BY ps.problem_id, ps.skill_id, ps.relation_type"""


def _ptag_skill(r):
    yield _item(f"PROBLEM#{r['canonical_code']}", f"TAG#SKILL#{r['skill_id']}#{r['relation_type']}", "PTAG",
                {"GSI1PK": f"SKILL#{r['skill_id']}", "GSI1SK": _tag_sk(r)},
                tag_kind="SKILL", skill_id=r["skill_id"], slug=r["slug"], relation_type=r["relation_type"],
                role=(r["role"] or "").upper(), source_roles=[r["role"]], required_level=r["required_level"],
                importance=r["importance"], source=r["source"], confidence=r["confidence"],
                review_status=r["review_status"], approval_method=r["approval_method"], **_tag_ctx(r))


_IMAGE_FROM = f"""core.problem_image i JOIN core.problem p ON p.problem_id = i.problem_id
 WHERE p.status = 'ACTIVE' AND {STUDENT_IMAGE_FILTER}"""

_IMAGE_SQL = f"""
SELECT i.problem_image_id, i.problem_id, p.canonical_code, i.ordinal, i.source, i.local_path
  FROM {_IMAGE_FROM}
 ORDER BY i.problem_image_id"""


def _image(r):
    path = _local_file(r["local_path"])
    if path is None:          # R3: files missing on this host are reported (manifest rows > items), not projected
        return
    with open(path, "rb") as f:
        data = f.read()
    sha = hashlib.sha256(data).hexdigest()
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    key = f"images/{sha}"
    yield S3Put("content", key, data, content_type=mime)
    yield _item(f"IMAGE#{r['problem_image_id']}", "META", "IMAGE",
                problem_image_id=r["problem_image_id"], problem_id=r["problem_id"], problem_code=r["canonical_code"],
                ordinal=r["ordinal"], source=r["source"], audience="STUDENT", s3_key=key, sha256=sha, mime=mime,
                bytes=len(data), image_version=_image_version(r["source"], r["local_path"]))


# ------------------------------------------------------------------ catalogue: concept / technique / skill / misconception

def _aliases(kind: str, id_expr: str) -> str:
    return (f"ARRAY(SELECT a.alias FROM knowledge.entity_alias a WHERE a.entity_kind = '{kind}' "
            f"AND a.entity_id = {id_expr} ORDER BY a.alias)")


_CONCEPT_SQL = f"""
SELECT c.concept_id, c.slug, c.name, c.description, c.level, c.status, {_aliases('CONCEPT', 'c.concept_id')} AS aliases,
       (SELECT json_agg(json_build_object('relation_id', cr.relation_id, 'concept_id', b.concept_id, 'slug', b.slug,
                        'name', b.name, 'relation_type', cr.relation_type, 'strength', cr.strength,
                        'review_status', cr.review_status) ORDER BY cr.relation_type, b.slug, cr.relation_id)
          FROM knowledge.concept_relation cr JOIN knowledge.concept b ON b.concept_id = cr.to_concept_id
         WHERE cr.from_concept_id = c.concept_id AND cr.review_status <> 'REJECTED') AS relations_out,
       (SELECT json_agg(json_build_object('relation_id', cr.relation_id, 'concept_id', a.concept_id, 'slug', a.slug,
                        'name', a.name, 'relation_type', cr.relation_type, 'strength', cr.strength,
                        'review_status', cr.review_status) ORDER BY cr.relation_type, a.slug, cr.relation_id)
          FROM knowledge.concept_relation cr JOIN knowledge.concept a ON a.concept_id = cr.from_concept_id
         WHERE cr.to_concept_id = c.concept_id AND cr.review_status <> 'REJECTED') AS relations_in
  FROM knowledge.concept c
 WHERE c.status = 'ACTIVE'
 ORDER BY c.concept_id"""


def _concept(r):
    yield _item(f"CONCEPT#{r['concept_id']}", "META", "CONCEPT",
                {"GSI1PK": f"SLUG#CONCEPT#{r['slug']}", "GSI1SK": "META"},
                concept_id=r["concept_id"], slug=r["slug"], name=r["name"], description=r["description"],
                level=r["level"], status=r["status"], aliases=_list(r["aliases"]),
                relations_out=_list(r["relations_out"]), relations_in=_list(r["relations_in"]))


_TECHNIQUE_SQL = f"""
SELECT t.technique_id, t.slug, t.name, t.description, t.status, {_aliases('TECHNIQUE', 't.technique_id')} AS aliases
  FROM knowledge.technique t
 WHERE t.status = 'ACTIVE'
 ORDER BY t.technique_id"""


def _technique(r):
    yield _item(f"TECHNIQUE#{r['technique_id']}", "META", "TECHNIQUE",
                {"GSI1PK": f"SLUG#TECHNIQUE#{r['slug']}", "GSI1SK": "META"},
                technique_id=r["technique_id"], slug=r["slug"], name=r["name"], description=r["description"],
                status=r["status"], aliases=_list(r["aliases"]))


_SKILL_SQL = f"""
SELECT k.skill_id, k.slug, k.name, k.objective, k.level, k.source, k.confidence, k.review_status, k.approval_method,
       {_aliases('SKILL', 'k.skill_id')} AS aliases,
       (SELECT json_agg(json_build_object('skill_id', b.skill_id, 'slug', b.slug, 'name', b.name,
                        'relation_type', sr.relation_type, 'confidence', sr.confidence, 'source', sr.source,
                        'review_status', sr.review_status) ORDER BY sr.relation_type, b.slug)
          FROM knowledge.skill_relation sr JOIN knowledge.skill b ON b.skill_id = sr.to_skill_id
         WHERE sr.from_skill_id = k.skill_id AND sr.review_status <> 'REJECTED') AS relations_out,
       (SELECT json_agg(json_build_object('skill_id', a.skill_id, 'slug', a.slug, 'name', a.name,
                        'relation_type', sr.relation_type, 'confidence', sr.confidence, 'source', sr.source,
                        'review_status', sr.review_status) ORDER BY sr.relation_type, a.slug)
          FROM knowledge.skill_relation sr JOIN knowledge.skill a ON a.skill_id = sr.from_skill_id
         WHERE sr.to_skill_id = k.skill_id AND sr.review_status <> 'REJECTED') AS relations_in,
       (SELECT json_agg(json_build_object('concept_id', c.concept_id, 'slug', c.slug, 'name', c.name,
                        'confidence', sc.confidence, 'source', sc.source, 'review_status', sc.review_status)
                        ORDER BY c.slug)
          FROM knowledge.skill_concept sc JOIN knowledge.concept c ON c.concept_id = sc.concept_id
         WHERE sc.skill_id = k.skill_id AND sc.review_status <> 'REJECTED') AS concepts
  FROM knowledge.skill k
 WHERE k.is_active
 ORDER BY k.skill_id"""


def _skill(r):
    yield _item(f"SKILL#{r['skill_id']}", "META", "SKILL", {"GSI1PK": f"SLUG#SKILL#{r['slug']}", "GSI1SK": "META"},
                skill_id=r["skill_id"], slug=r["slug"], name=r["name"], objective=r["objective"], level=r["level"],
                source=r["source"], confidence=r["confidence"], review_status=r["review_status"],
                approval_method=r["approval_method"], status="ACTIVE", aliases=_list(r["aliases"]),
                relations_out=_list(r["relations_out"]), relations_in=_list(r["relations_in"]),
                concepts=_list(r["concepts"]))


_MISCONCEPTION_SQL = f"""
WITH links AS (
    SELECT misconception_id, array_agg(taxonomy_node_id ORDER BY taxonomy_node_id) AS taxonomy_node_ids
      FROM knowledge.misconception_taxonomy_link GROUP BY misconception_id)
SELECT m.misconception_id, m.canonical_code, m.name, m.description, m.symptom, m.why_wrong, m.correct_model,
       m.recognition_pattern, m.severity, m.level, m.source, m.review_status, m.approval_method, m.approved_at,
       m.created_at, m.updated_at, {_aliases('MISCONCEPTION', 'm.misconception_id')} AS aliases,
       l.taxonomy_node_ids, me.source_text_sha256 AS v_sha, me.model AS v_model,
       CASE WHEN me.misconception_id IS NULL THEN NULL ELSE ARRAY[me.misconception_id::text] END AS v_keys
  FROM knowledge.misconception m
  LEFT JOIN links l ON l.misconception_id = m.misconception_id
  LEFT JOIN knowledge.misconception_embedding me ON me.misconception_id = m.misconception_id
 WHERE m.is_active
 ORDER BY m.misconception_id"""


def _misconception(r):
    yield _item(f"MISCONCEPTION#{r['misconception_id']}", "META", "MISCONCEPTION",
                {"GSI1PK": f"SLUG#MISCONCEPTION#{r['canonical_code']}", "GSI1SK": "META"},
                misconception_id=r["misconception_id"], canonical_code=r["canonical_code"], name=r["name"],
                description=r["description"], symptom=r["symptom"], why_wrong=r["why_wrong"],
                correct_model=r["correct_model"], recognition_pattern=r["recognition_pattern"],
                severity=r["severity"], level=r["level"], source=r["source"], review_status=r["review_status"],
                approval_method=r["approval_method"], approved_at=r["approved_at"], status="ACTIVE",
                aliases=_list(r["aliases"]), taxonomy_node_ids=_list(r["taxonomy_node_ids"]),
                vector_state=_vec(r, "misconception"), created_at=r["created_at"], updated_at=r["updated_at"])


# ------------------------------------------------------------------ catalogue snapshots (S3 + CATALOGPTR)

_CATALOG_SQL = {
    "concept": """
SELECT coalesce(json_agg(json_build_object(
         'concept_id', c.concept_id, 'slug', c.slug, 'name', c.name, 'level', c.level, 'description', c.description,
         'aliases', ARRAY(SELECT a.alias FROM knowledge.entity_alias a WHERE a.entity_kind = 'CONCEPT'
                           AND a.entity_id = c.concept_id ORDER BY a.alias),
         'relations_out', (SELECT coalesce(json_agg(json_build_object('concept_id', cr.to_concept_id,
                           'relation_type', cr.relation_type) ORDER BY cr.relation_type, cr.to_concept_id), '[]')
                             FROM knowledge.concept_relation cr JOIN knowledge.concept b ON b.concept_id = cr.to_concept_id
                            WHERE cr.from_concept_id = c.concept_id AND cr.review_status <> 'REJECTED'
                              AND b.status = 'ACTIVE'))
         ORDER BY c.slug, c.concept_id), '[]') AS items
  FROM knowledge.concept c WHERE c.status = 'ACTIVE'""",
    "technique": """
SELECT coalesce(json_agg(json_build_object(
         'technique_id', t.technique_id, 'slug', t.slug, 'name', t.name, 'description', t.description,
         'aliases', ARRAY(SELECT a.alias FROM knowledge.entity_alias a WHERE a.entity_kind = 'TECHNIQUE'
                           AND a.entity_id = t.technique_id ORDER BY a.alias))
         ORDER BY t.name, t.technique_id), '[]') AS items
  FROM knowledge.technique t WHERE t.status = 'ACTIVE'""",
    "skill": """
SELECT coalesce(json_agg(json_build_object(
         'skill_id', k.skill_id, 'slug', k.slug, 'name', k.name, 'level', k.level,
         'aliases', ARRAY(SELECT a.alias FROM knowledge.entity_alias a WHERE a.entity_kind = 'SKILL'
                           AND a.entity_id = k.skill_id ORDER BY a.alias))
         ORDER BY k.slug, k.skill_id), '[]') AS items
  FROM knowledge.skill k WHERE k.is_active""",
    "misconception": """
SELECT coalesce(json_agg(json_build_object(
         'misconception_id', m.misconception_id, 'canonical_code', m.canonical_code, 'name', m.name,
         'level', m.level, 'severity', m.severity)
         ORDER BY m.canonical_code, m.misconception_id), '[]') AS items
  FROM knowledge.misconception m WHERE m.is_active""",
    "theorem": """
SELECT coalesce(json_agg(json_build_object(
         'theorem_id', t.theorem_id, 'slug', t.slug, 'name', t.name, 'kind', t.kind, 'field', t.field)
         ORDER BY t.slug, t.theorem_id), '[]') AS items
  FROM knowledge.theorem t WHERE t.review_status = 'APPROVED'""",
    "widget-library": """
SELECT json_build_object(
  'interaction_templates', (SELECT coalesce(json_agg(json_build_object(
        'interaction_template_id', t.interaction_template_id, 'template_key', t.template_key, 'name', t.name,
        'interaction_family', t.interaction_family, 'description', t.description,
        'versions', (SELECT coalesce(json_agg(json_build_object('version', v.version, 'status', v.status,
                       'content_hash', v.content_hash, 'published_at', v.published_at) ORDER BY v.version), '[]')
                       FROM visual.interaction_template_version v
                      WHERE v.interaction_template_id = t.interaction_template_id
                        AND v.status IN ('PUBLISHED', 'DEPRECATED')))
        ORDER BY t.template_key), '[]') FROM visual.interaction_template t WHERE t.status = 'ACTIVE'),
  'controls', (SELECT coalesce(json_agg(json_build_object('control_template_id', c.control_template_id,
        'control_key', c.control_key, 'control_type', c.control_type, 'config_schema', c.config_schema,
        'accessibility_schema', c.accessibility_schema) ORDER BY c.control_key), '[]')
        FROM visual.control_template c WHERE c.status = 'ACTIVE'),
  'icons', (SELECT coalesce(json_agg(json_build_object('icon_token_id', i.icon_token_id, 'token_key', i.token_key,
        'icon_class', i.icon_class, 'semantic_role', i.semantic_role, 'asset_id', i.asset_id,
        'accessible_label', i.accessible_label, 'allowed_contexts', i.allowed_contexts) ORDER BY i.token_key), '[]')
        FROM visual.icon_token i WHERE i.status = 'ACTIVE'),
  'animations', (SELECT coalesce(json_agg(json_build_object('animation_template_id', a.animation_template_id,
        'animation_key', a.animation_key, 'name', a.name, 'input_schema', a.input_schema,
        'semantic_output_events', a.semantic_output_events, 'reduced_motion_behavior', a.reduced_motion_behavior)
        ORDER BY a.animation_key), '[]') FROM visual.animation_template a WHERE a.status = 'ACTIVE')
) AS items""",
}


def _catalog(kind: str):
    def transform(r):
        items = r["items"]
        body = {"schema": f"catalog/{kind}/v1", "kind": kind, "items": items}
        sha = hashlib.sha256(json_bytes(body)).hexdigest()
        key = f"catalog/{kind}/{sha}.json"
        count = len(items) if isinstance(items, list) else sum(len(v) for v in items.values())
        yield S3Put("content", key, body)
        yield _item(f"CATALOG#{kind.upper()}", "SNAPSHOT", "CATALOGPTR", kind=kind, s3_key=key, sha256=sha,
                    count=count)
    return transform


# ------------------------------------------------------------------ theorems

_THEOREM_SQL = """
SELECT t.theorem_id, t.slug, t.name, t.kind, t.field, t.statement_text, t.statement_latex, t.description,
       t.proof_sketch, t.source, t.review_status, t.approval_method, t.approved_at, t.created_at, t.updated_at,
       (SELECT json_agg(json_build_object('theorem_source_id', s.theorem_source_id, 'url', s.url, 'label', s.label,
                        'source_type', s.source_type, 'ordinal', s.ordinal) ORDER BY s.ordinal, s.theorem_source_id)
          FROM knowledge.theorem_source s WHERE s.theorem_id = t.theorem_id AND s.review_status = 'APPROVED') AS sources,
       (SELECT json_agg(json_build_object('asset_id', a.asset_id, 'mime', a.mime_type, 'sha256', a.content_hash,
                        'asset_kind', a.asset_kind, 'ordinal', ta.ordinal, 'caption', ta.caption)
                        ORDER BY ta.ordinal, a.asset_id)
          FROM knowledge.theorem_asset ta JOIN visual.asset a ON a.asset_id = ta.asset_id
         WHERE ta.theorem_id = t.theorem_id AND a.validation_status = 'VALID') AS assets,
       CASE WHEN te.theorem_id IS NULL THEN NULL ELSE ARRAY[te.theorem_id::text] END AS v_keys,
       te.source_text_sha256 AS v_sha, te.model AS v_model
  FROM knowledge.theorem t
  LEFT JOIN knowledge.theorem_embedding te ON te.theorem_id = t.theorem_id
 WHERE t.review_status = 'APPROVED'
 ORDER BY t.theorem_id"""


def _theorem(r):
    yield _item(f"THEOREM#{r['theorem_id']}", "META", "THEOREM",
                {"GSI1PK": f"SLUG#THEOREM#{r['slug']}", "GSI1SK": "META"},
                theorem_id=r["theorem_id"], slug=r["slug"], name=r["name"], kind=r["kind"], field=r["field"],
                statement_text=r["statement_text"], statement_latex=r["statement_latex"],
                description=r["description"], proof_sketch=r["proof_sketch"], source=r["source"],
                review_status=r["review_status"], approval_method=r["approval_method"],
                approved_at=r["approved_at"], sources=_list(r["sources"]), assets=_list(r["assets"]),
                vector_state=_vec(r, "theorem"), created_at=r["created_at"], updated_at=r["updated_at"])


_THEOREM_REL_FROM = """knowledge.theorem_relation tr
  JOIN knowledge.theorem a ON a.theorem_id = tr.from_theorem_id AND a.review_status = 'APPROVED'
  JOIN knowledge.theorem b ON b.theorem_id = tr.to_theorem_id AND b.review_status = 'APPROVED'
 WHERE tr.review_status <> 'REJECTED'"""


def _theorem_rel(r):
    yield _item(f"THEOREM#{r['from_theorem_id']}", f"REL#{r['relation_type']}#{r['to_theorem_id']}", "THEOREM_REL",
                relation_id=r["relation_id"], relation_type=r["relation_type"], to_theorem_id=r["to_theorem_id"],
                to_slug=r["to_slug"], to_name=r["to_name"], confidence=r["confidence"],
                review_status=r["review_status"])


_TECH_THEOREM_FROM = """knowledge.technique_theorem tt
  JOIN knowledge.theorem t ON t.theorem_id = tt.theorem_id AND t.review_status = 'APPROVED'
 WHERE tt.review_status <> 'REJECTED'"""


def _theorem_link_technique(r):
    yield _item(f"THEOREM#{r['theorem_id']}", f"LINK#TECHNIQUE#{r['technique_id']}#{r['role']}", "THEOREM_LINK",
                {"GSI2PK": f"THMBY#TECHNIQUE#{r['technique_id']}", "GSI2SK": r["slug"]},
                link_kind="TECHNIQUE", theorem_id=r["theorem_id"], technique_id=r["technique_id"],
                technique_slug=r["technique_slug"], slug=r["slug"], name=r["name"], role=r["role"],
                confidence=r["confidence"])


_THEOREM_TAX_FROM = """knowledge.theorem_taxonomy_link tl
  JOIN knowledge.theorem t ON t.theorem_id = tl.theorem_id AND t.review_status = 'APPROVED'"""


def _theorem_link_taxnode(r):
    yield _item(f"THEOREM#{r['theorem_id']}", f"LINK#TAXNODE#{r['taxonomy_node_id']}", "THEOREM_LINK",
                {"GSI2PK": f"THMBY#TAXNODE#{r['taxonomy_node_id']}", "GSI2SK": r["slug"]},
                link_kind="TAXNODE", theorem_id=r["theorem_id"], taxonomy_node_id=r["taxonomy_node_id"],
                slug=r["slug"], name=r["name"], role=r["role"], derived_via=r["derived_via"])


# ------------------------------------------------------------------ taxonomy (+ TAXSEARCH facets) and source books

# step_search._TAXONOMY_DETAILS problem_count / example_problem_codes, computed set-wise for all nodes.
_TAXONOMY_SQL = f"""
WITH np AS (
    SELECT s.skill_node_id AS node_id, s.problem_id FROM pedagogy.solution_step s
      JOIN pedagogy.taxonomy_node n ON n.taxonomy_node_id = s.skill_node_id AND n.node_type = 'SKILL'
     WHERE s.publication_status = 'PUBLISHED'
    UNION
    SELECT s.subconcept_node_id, s.problem_id FROM pedagogy.solution_step s
      JOIN pedagogy.taxonomy_node n ON n.taxonomy_node_id = s.subconcept_node_id AND n.node_type = 'SUBCONCEPT'
     WHERE s.publication_status = 'PUBLISHED'
    UNION
    SELECT s.concept_node_id, s.problem_id FROM pedagogy.solution_step s
      JOIN pedagogy.taxonomy_node n ON n.taxonomy_node_id = s.concept_node_id AND n.node_type = 'CONCEPT'
     WHERE s.publication_status = 'PUBLISHED'
    UNION
    SELECT t.technique_node_id, s.problem_id FROM pedagogy.solution_step_technique t
      JOIN pedagogy.solution_step s ON s.solution_step_id = t.solution_step_id
      JOIN pedagogy.taxonomy_node n ON n.taxonomy_node_id = t.technique_node_id AND n.node_type = 'TECHNIQUE'
     WHERE s.publication_status = 'PUBLISHED' AND t.review_status = 'APPROVED'
       AND NOT EXISTS (SELECT 1 FROM knowledge.problem_technique rejected
                        WHERE rejected.problem_id = s.problem_id AND rejected.technique_id = n.technique_id
                          AND rejected.review_status = 'REJECTED')
), stats AS (
    SELECT np.node_id, count(*) AS problem_count,
           (array_agg(p.canonical_code ORDER BY p.canonical_code))[1:5] AS example_problem_codes
      FROM np JOIN core.problem p ON p.problem_id = np.problem_id
     GROUP BY np.node_id
), {_vec_cte("tv", ("TAXONOMY_NODE",), "c.metadata->>'taxonomy_node_id'")}
SELECT n.taxonomy_node_id, n.node_type, n.name, n.parent_node_id, parent.name AS parent_name, n.chapter_number,
       n.section_number, n.source_basis, n.description, n.concept_id, n.skill_id, n.technique_id, n.theorem_id,
       n.updated_at, cp.book_code,
       coalesce(kc.slug, ks.slug, kt.slug) AS slug,
       CASE WHEN kc.slug IS NOT NULL THEN 'concept' WHEN ks.slug IS NOT NULL THEN 'skill'
            WHEN kt.slug IS NOT NULL THEN 'technique' END AS slug_kind,
       coalesce(st.problem_count, 0) AS problem_count, st.example_problem_codes,
       (SELECT json_agg(json_build_object('to_node_id', e.to_node_id, 'relationship_type', e.relationship_type,
                        'confidence', e.confidence, 'source_basis', e.source_basis)
                        ORDER BY e.relationship_type, e.to_node_id)
          FROM pedagogy.taxonomy_edge e WHERE e.from_node_id = n.taxonomy_node_id) AS edges,
       CASE WHEN ne.taxonomy_node_id IS NULL THEN NULL ELSE ARRAY[ne.taxonomy_node_id] END AS v_keys,
       ne.source_text_sha256 AS v_sha, ne.model AS v_model,
       tv.keys AS s_keys, tv.sha AS s_sha, tv.model AS s_model
  FROM pedagogy.taxonomy_node n
  LEFT JOIN pedagogy.taxonomy_node parent ON parent.taxonomy_node_id = n.parent_node_id
  LEFT JOIN ingest.content_package cp ON cp.content_package_id = n.content_package_id
  LEFT JOIN knowledge.concept kc ON kc.concept_id = n.concept_id
  LEFT JOIN knowledge.skill ks ON ks.skill_id = n.skill_id
  LEFT JOIN knowledge.technique kt ON kt.technique_id = n.technique_id
  LEFT JOIN stats st ON st.node_id = n.taxonomy_node_id
  LEFT JOIN pedagogy.taxonomy_node_embedding ne ON ne.taxonomy_node_id = n.taxonomy_node_id
  LEFT JOIN tv ON tv.entity_id = n.taxonomy_node_id
 ORDER BY n.taxonomy_node_id"""


def _facet(unit: str, dim: str, value, entity_id: str, **proj) -> dict:
    return _item(f"FACET#{unit}#{dim}#{value}", str(entity_id), "FACET", unit=unit, dim=dim, value=str(value),
                 entity_id=entity_id, **proj)


def _taxonomy(r):
    nid = r["taxonomy_node_id"]
    gsi = {"GSI2PK": f"TAXTYPE#{r['node_type']}",
           "GSI2SK": f"{_num(r['chapter_number'], 3)}#{r['section_number'] or ''}#{nid}"}
    if r["parent_node_id"]:
        gsi.update(GSI1PK=f"TAXCHILD#{r['parent_node_id']}", GSI1SK=f"{r['node_type']}#{r['name']}")
    search_vec = _vec(r, "taxonomy-search", "s_")
    yield _item(f"TAXNODE#{nid}", "META", "TAXNODE", gsi,
                taxonomy_node_id=nid, name=r["name"], node_type=r["node_type"],
                parent={"id": r["parent_node_id"], "name": r["parent_name"]} if r["parent_node_id"] else None,
                chapter_number=r["chapter_number"], section_number=r["section_number"], book_code=r["book_code"],
                source_basis=r["source_basis"], description=r["description"], concept_id=r["concept_id"],
                skill_id=r["skill_id"], technique_id=r["technique_id"], theorem_id=r["theorem_id"],
                slug=r["slug"], slug_kind=r["slug_kind"], problem_count=r["problem_count"],
                example_problem_codes=_list(r["example_problem_codes"]), edges=_list(r["edges"]),
                lifecycle="ACTIVE", vector_state=_vec(r, "taxonomy-node"), search_vector_state=search_vec,
                eligible=True, updated_at=r["updated_at"])
    if search_vec:
        proj = dict(node_type=r["node_type"], chapter_number=r["chapter_number"], vector_keys=search_vec["keys"])
        yield _facet("TAXSEARCH", "NODETYPE", r["node_type"], nid, **proj)
        if r["chapter_number"] is not None:
            yield _facet("TAXSEARCH", "CHAPTER", r["chapter_number"], nid, **proj)


_SOURCEBOOK_SQL = """
SELECT b.book_code, b.external_book_id, b.title, b.author, b.translator_editor, b.competition_id, b.edition_id,
       b.metadata, b.updated_at,
       (SELECT json_agg(json_build_object('chapter_number', cs.chapter_number, 'section_number', cs.section_number,
                        'chapter_title', cs.chapter_title, 'section_title', cs.section_title, 'paper_id', cs.paper_id)
                        ORDER BY cs.chapter_number, cs.section_number)
          FROM pedagogy.chapter_section cs WHERE cs.book_code = b.book_code) AS sections
  FROM pedagogy.source_book b
 ORDER BY b.book_code"""


def _sourcebook(r):
    yield _item(f"SOURCEBOOK#{r['book_code']}", "META", "SOURCEBOOK",
                book_code=r["book_code"], external_book_id=r["external_book_id"], title=r["title"],
                author=r["author"], translator_editor=r["translator_editor"], competition_id=r["competition_id"],
                edition_id=r["edition_id"], metadata=r["metadata"], sections=_list(r["sections"]),
                updated_at=r["updated_at"])


# ------------------------------------------------------------------ solution DAG (server-only) and STEP + facets

_SOLDAG_SQL = """
SELECT d.solution_id, d.problem_id, p.canonical_code,
       (SELECT json_agg(json_build_object('solution_part_id', sp.solution_part_id, 'source_part_id', sp.source_part_id,
                        'occurrence', sp.occurrence, 'book_code', sp.book_code, 'part_label', sp.part_label,
                        'part_ordinal', sp.part_ordinal, 'step_count', sp.step_count,
                        'source_step_count', sp.source_step_count, 'source_page', sp.source_page,
                        'part_text_normalized', sp.part_text_normalized)
                        ORDER BY sp.part_ordinal, sp.solution_part_id)
          FROM pedagogy.solution_part sp WHERE sp.solution_id = d.solution_id) AS parts,
       (SELECT json_agg(json_build_object('solution_step_id', s.solution_step_id, 'source_step_id', s.source_step_id,
                        'occurrence', s.occurrence, 'solution_part_id', s.solution_part_id,
                        'global_step_index', s.global_step_index, 'step_index_in_part', s.step_index_in_part,
                        'step_text', s.step_text, 'step_type', s.step_type, 'tutor_role', s.tutor_role,
                        'concept_node_id', s.concept_node_id, 'subconcept_node_id', s.subconcept_node_id,
                        'skill_node_id', s.skill_node_id, 'skill_name', s.skill_name, 'hint_level', s.hint_level,
                        'is_checkpoint', s.is_checkpoint, 'source_previous_step_id', s.source_previous_step_id,
                        'source_next_step_id', s.source_next_step_id, 'source_page', s.source_page,
                        'source_metadata', s.source_metadata)
                        ORDER BY s.global_step_index, s.solution_step_id)
          FROM pedagogy.solution_step s
         WHERE s.solution_id = d.solution_id AND s.publication_status = 'PUBLISHED') AS steps,
       (SELECT json_agg(json_build_object('from_step_id', dep.from_step_id, 'to_step_id', dep.to_step_id,
                        'relationship_type', dep.relationship_type, 'logical_dependency', dep.logical_dependency,
                        'confidence', dep.confidence, 'source_type', dep.source_type,
                        'review_status', dep.review_status, 'approval_method', dep.approval_method,
                        'metadata', dep.metadata)
                        ORDER BY dep.from_step_id, dep.to_step_id, dep.relationship_type)
          FROM pedagogy.solution_step_dependency dep
          JOIN pedagogy.solution_step a ON a.solution_step_id = dep.from_step_id AND a.publication_status = 'PUBLISHED'
          JOIN pedagogy.solution_step b ON b.solution_step_id = dep.to_step_id AND b.publication_status = 'PUBLISHED'
         WHERE a.solution_id = d.solution_id AND dep.review_status <> 'REJECTED') AS dependencies,
       (SELECT json_agg(json_build_object('solution_step_id', t.solution_step_id,
                        'technique_node_id', t.technique_node_id, 'confidence', t.confidence,
                        'source_type', t.source_type, 'evidence', t.evidence,
                        'derivation_version', t.derivation_version, 'review_status', t.review_status,
                        'approval_method', t.approval_method, 'approved_at', t.approved_at)
                        ORDER BY t.solution_step_id, t.technique_node_id)
          FROM pedagogy.solution_step_technique t
          JOIN pedagogy.solution_step s ON s.solution_step_id = t.solution_step_id AND s.publication_status = 'PUBLISHED'
         WHERE s.solution_id = d.solution_id AND t.review_status = 'APPROVED') AS step_techniques
  FROM (SELECT DISTINCT solution_id, problem_id FROM pedagogy.solution_step
         WHERE publication_status = 'PUBLISHED') d
  JOIN core.problem p ON p.problem_id = d.problem_id
 ORDER BY d.solution_id"""


def _soldag(r):
    yield _item(f"PROBLEM#{r['canonical_code']}", f"SOLDAG#{r['solution_id']}", "SOLDAG",
                solution_id=r["solution_id"], problem_id=r["problem_id"], problem_code=r["canonical_code"],
                step_count=len(_list(r["steps"])), parts=_list(r["parts"]), steps=_list(r["steps"]),
                dependencies=_list(r["dependencies"]), step_techniques=_list(r["step_techniques"]))


_STEP_SQL = f"""
WITH {_vec_cte("sv", ("SOLUTION_STEP",), "c.solution_step_id")}
SELECT s.solution_step_id, s.problem_id, p.canonical_code, s.solution_id, s.solution_part_id, s.book_code,
       s.global_step_index, s.step_index_in_part, s.step_type, s.tutor_role, s.hint_level, s.is_checkpoint,
       s.skill_node_id, s.subconcept_node_id, s.concept_node_id, s.skill_name, s.step_text, s.updated_at,
       ARRAY(SELECT t.technique_node_id FROM pedagogy.solution_step_technique t
              WHERE t.solution_step_id = s.solution_step_id AND t.review_status = 'APPROVED'
              ORDER BY t.technique_node_id) AS technique_node_ids,
       sv.keys AS v_keys, sv.sha AS v_sha, sv.model AS v_model
  FROM pedagogy.solution_step s
  JOIN core.problem p ON p.problem_id = s.problem_id
  LEFT JOIN sv ON sv.entity_id = s.solution_step_id
 WHERE s.publication_status = 'PUBLISHED'
 ORDER BY s.solution_step_id"""


def _step(r):
    sid, vec = r["solution_step_id"], _vec(r, "step")
    techs = _list(r["technique_node_ids"])
    proj = dict(problem_id=r["problem_id"], skill_node_id=r["skill_node_id"],
                subconcept_node_id=r["subconcept_node_id"], concept_node_id=r["concept_node_id"],
                step_type=r["step_type"], tutor_role=r["tutor_role"], is_checkpoint=r["is_checkpoint"],
                hint_level=r["hint_level"], technique_node_ids=techs)
    yield _item(f"STEP#{sid}", "META", "STEP",
                solution_step_id=sid, problem_code=r["canonical_code"], solution_id=r["solution_id"],
                solution_part_id=r["solution_part_id"], book_code=r["book_code"],
                global_step_index=r["global_step_index"], step_index_in_part=r["step_index_in_part"],
                skill_name=r["skill_name"], step_text=r["step_text"], eligible=True, vector_state=vec,
                updated_at=r["updated_at"], **proj)
    if not vec:
        return
    proj["vector_keys"] = vec["keys"]
    for dim, value in (("PROBLEM", r["problem_id"]), ("SKILL", r["skill_node_id"]),
                       ("SUBCONCEPT", r["subconcept_node_id"]), ("CONCEPT", r["concept_node_id"])):
        if value is not None:
            yield _facet("STEP", dim, value, sid, **proj)
    for t in techs:
        yield _facet("STEP", "TECHNIQUE", t, sid, **proj)


# ------------------------------------------------------------------ learning items (+ server-only keys) and facets

_LI_WHERE = "li.review_status = 'APPROVED' AND li.student_visible AND li.no_proof"

_LI_SQL = f"""
WITH {_vec_cte("lv", ("LEARNING_ITEM_QUESTION", "LEARNING_ITEM_SKILL_SIGNATURE"), "c.learning_item_id")}
SELECT li.learning_item_id, li.source_transformation_id, li.occurrence, li.book_code, li.source_problem_id,
       p.canonical_code AS source_problem_code, li.parent_learning_item_id, li.transformation_type,
       li.transformed_form, li.target_concept_node_id, li.target_subconcept_node_id, li.target_skill_node_id,
       li.difficulty_direction, li.question_text, li.choices, li.correct_answer, li.answer_or_solution_seed,
       li.generation_mode, li.solution_part_label, li.requires_source_problem, li.diagram_strategy,
       li.approval_method, li.approved_at, li.updated_at,
       ARRAY(SELECT a.solution_step_id FROM pedagogy.learning_item_step_anchor a
              WHERE a.learning_item_id = li.learning_item_id
              ORDER BY a.anchor_ordinal, a.solution_step_id) AS anchor_step_ids,
       lv.keys AS v_keys, lv.sha AS v_sha, lv.model AS v_model
  FROM pedagogy.learning_item li
  LEFT JOIN core.problem p ON p.problem_id = li.source_problem_id
  LEFT JOIN lv ON lv.entity_id = li.learning_item_id
 WHERE {_LI_WHERE}
 ORDER BY li.learning_item_id"""


def _learning_item(r):
    lid, vec = r["learning_item_id"], _vec(r, "learning-item")
    anchors = _list(r["anchor_step_ids"])
    proj = dict(source_problem_id=r["source_problem_id"], transformed_form=r["transformed_form"],
                transformation_type=r["transformation_type"], target_skill_node_id=r["target_skill_node_id"],
                target_subconcept_node_id=r["target_subconcept_node_id"],
                difficulty_direction=r["difficulty_direction"], anchor_step_ids=anchors)
    yield _item(f"LI#{lid}", "META", "LI",
                learning_item_id=lid, source_transformation_id=r["source_transformation_id"],
                occurrence=r["occurrence"], book_code=r["book_code"], source_problem_code=r["source_problem_code"],
                parent_learning_item_id=r["parent_learning_item_id"],
                target_concept_node_id=r["target_concept_node_id"], question_text=r["question_text"],
                choices=r["choices"], generation_mode=r["generation_mode"],
                solution_part_label=r["solution_part_label"], requires_source_problem=r["requires_source_problem"],
                diagram_strategy=r["diagram_strategy"], approval_method=r["approval_method"],
                approved_at=r["approved_at"], eligible=True, vector_state=vec, updated_at=r["updated_at"], **proj)
    yield _item(f"LI#{lid}", "KEY", "LI_KEY", learning_item_id=lid, correct_answer=r["correct_answer"],
                answer_or_solution_seed=r["answer_or_solution_seed"])
    if not vec:
        return
    proj["vector_keys"] = vec["keys"]
    for a in anchors:
        yield _facet("LI", "ANCHOR", a, lid, **proj)
    for dim, value in (("TARGET_SKILL", r["target_skill_node_id"]),
                       ("TARGET_SUBCONCEPT", r["target_subconcept_node_id"])):
        if value is not None:
            yield _facet("LI", dim, value, lid, **proj)


# ------------------------------------------------------------------ activities (STATIC / PRECOMPILED) + server-only keys

_ACT_WHERE = "(persistence_mode = 'STATIC' OR source_type = 'PRECOMPILED') AND status = 'ACTIVE'"


def _activity(r):
    aid = r["activity_id"]
    yield _item(f"ACT#{aid}", "META", "ACT",
                activity_id=aid, activity_type=r["activity_type"], prompt=r["prompt"], options=r["options"],
                target_skill=r["target_skill"], target_skill_id=r["target_skill_id"],
                source_problem_id=r["source_problem_id"], estimated_seconds=r["estimated_seconds"],
                source_type=r["source_type"], persistence_mode=r["persistence_mode"], status=r["status"],
                created_at=r["created_at"])
    yield _item(f"ACT#{aid}", "KEY", "ACT_KEY", activity_id=aid,
                correctness_policy=_canon_policy(r["correctness_policy"]),
                source_correctness_policy=r["correctness_policy"])


# ------------------------------------------------------------------ visual

_ITPLVER_WHERE = "v.status IN ('PUBLISHED', 'DEPRECATED')"


def _itplver(r):
    yield _item(f"ITPL#{r['template_key']}", f"V#{_num(r['version'], 4)}", "ITPLVER",
                interaction_template_version_id=r["interaction_template_version_id"],
                interaction_template_id=r["interaction_template_id"], template_key=r["template_key"],
                template_name=r["template_name"], interaction_family=r["interaction_family"],
                template_description=r["template_description"], template_version=r["version"],
                input_schema=r["input_schema"], state_schema=r["state_schema"], event_schema=r["event_schema"],
                output_schema=r["output_schema"], default_layout=r["default_layout"],
                allowed_controls=r["allowed_controls"], allowed_icons=r["allowed_icons"],
                diagnostic_capabilities=r["diagnostic_capabilities"], animation_slots=r["animation_slots"],
                accessibility_policy=r["accessibility_policy"], source_content_hash=r["content_hash"],
                status=r["status"], published_at=r["published_at"])


def _junction_ids(kind: str) -> str:
    return (f"ARRAY(SELECT j.{kind}_id::text FROM visual.interaction_instance_{kind} j "
            f"WHERE j.interaction_instance_id = i.interaction_instance_id ORDER BY 1) AS {kind}_ids")


def _iinst(r):
    yield _item(f"IINST#{r['interaction_instance_id']}", "META", "IINST",
                interaction_instance_id=r["interaction_instance_id"],
                interaction_template_version_id=r["interaction_template_version_id"],
                template_key=r["template_key"], template_version=r["template_version"],
                canonical_code=r["canonical_code"], title=r["title"], instance_config=r["instance_config"],
                initial_state=r["initial_state"], learning_objective=r["learning_objective"],
                success_criteria=r["success_criteria"], feedback_policy_id=r["feedback_policy_id"],
                scene_spec_id=r["scene_spec_id"], source_content_hash=r["content_hash"],
                review_status=r["review_status"], approved_at=r["approved_at"],
                concept_ids=_list(r["concept_ids"]), skill_ids=_list(r["skill_ids"]),
                technique_ids=_list(r["technique_ids"]), misconception_ids=_list(r["misconception_ids"]))


def _scene(r):
    yield _item(f"SCENE#{r['scene_spec_id']}", "META", "SCENE",
                scene_spec_id=r["scene_spec_id"], canonical_code=r["canonical_code"], scene_version=r["version"],
                scene_schema_version=r["scene_schema_version"], scene_json=r["scene_json"],
                source_content_hash=r["content_hash"], status=r["status"], approved_at=r["approved_at"],
                rendered_video_asset_id=r["rendered_video_asset_id"])


def _vasset(r):
    uri = r["uri"] or ""
    external = uri.startswith(("http://", "https://"))
    yield _item(f"VASSET#{r['asset_id']}", "META", "VASSET",
                asset_id=r["asset_id"], mime=r["mime_type"], sha256=r["content_hash"], size=r["object_size_bytes"],
                kind=r["asset_kind"], title=r["title"], source_url=r["source_url"], rights_note=r["rights_note"],
                persistence_mode=r["persistence_mode"], validation_status=r["validation_status"],
                source_problem_id=r["source_problem_id"], diagram_id=r["diagram_id"],
                external_url=uri if external else None, private_object=uri.startswith("object-store:"),
                source_uri=None if external else uri)


# ------------------------------------------------------------------ micro-course releases (immutable S3 snapshots)

# learner.json = the reader/runtime payload (_assemble_course_reader_payload, approved-only) with every answer key
# removed (ACT-F01/PMC-F01); server.json = agent policies, answer keys and raw asset URIs. Aliases: r = release,
# c = course. The snapshot freezes learning items, activities, transcripts and markers as of publish (PVD-S01).
_MC_LEARNER = """json_build_object(
  'schema', 'micro-course-release/learner/v1',
  'course', json_build_object('micro_course_id', c.micro_course_id, 'canonical_code', c.canonical_code,
      'title', c.title, 'description', c.description, 'estimated_minutes', c.estimated_minutes,
      'difficulty_level', c.difficulty_level, 'metadata', c.metadata),
  'release', json_build_object('release_id', r.release_id, 'version', r.version,
      'parent_release_id', r.parent_release_id, 'learning_objectives', r.learning_objectives,
      'prerequisite_summary', r.prerequisite_summary, 'published_at', r.published_at,
      'source_content_hash', r.content_hash),
  'targets', (SELECT coalesce(json_agg(json_build_object('target_type', t.target_type, 'role', t.role,
      'ordinal', t.ordinal, 'concept_id', t.concept_id, 'technique_id', t.technique_id, 'skill_id', t.skill_id,
      'theorem_id', t.theorem_id, 'name', coalesce(kc.name, kt.name, ks.name, th.name),
      'slug', coalesce(kc.slug, kt.slug, ks.slug, th.slug)) ORDER BY t.role, t.ordinal, t.target_type), '[]')
      FROM pedagogy.micro_course_target t
      LEFT JOIN knowledge.concept kc ON kc.concept_id = t.concept_id
      LEFT JOIN knowledge.technique kt ON kt.technique_id = t.technique_id
      LEFT JOIN knowledge.skill ks ON ks.skill_id = t.skill_id
      LEFT JOIN knowledge.theorem th ON th.theorem_id = t.theorem_id
     WHERE t.micro_course_id = c.micro_course_id),
  'modules', (SELECT coalesce(json_agg(json_build_object('module_id', m.module_id, 'module_key', m.module_key,
      'ordinal', m.ordinal, 'title', m.title, 'objective', m.objective, 'estimated_seconds', m.estimated_seconds,
      'required', m.required) ORDER BY m.ordinal, m.module_key), '[]')
      FROM pedagogy.micro_course_module m WHERE m.release_id = r.release_id),
  'states', (SELECT coalesce(json_agg(json_build_object(
      'state_id', s.state_id, 'module_id', s.module_id, 'module_key', sm.module_key, 'state_key', s.state_key,
      'ordinal', s.ordinal, 'state_type', s.state_type, 'title', s.title, 'objective', s.objective,
      'student_instruction', s.student_instruction, 'estimated_seconds', s.estimated_seconds,
      'required', s.required, 'skippable', s.skippable,
      'assets', (SELECT coalesce(json_agg(json_build_object('asset_id', a.asset_id, 'asset_kind', a.asset_kind,
          'title', a.title, 'source_url', a.source_url, 'mime_type', a.mime_type,
          'object_size_bytes', a.object_size_bytes, 'content_hash', a.content_hash, 'ordinal', sa.ordinal,
          'presentation_role', sa.presentation_role, 'sequence_position', sa.sequence_position,
          'private_object', starts_with(a.uri, 'object-store:'), 'video_asset_id', v.video_asset_id,
          'video_url', v.canonical_url, 'duration_ms', v.duration_ms) ORDER BY sa.ordinal, a.asset_id), '[]')
          FROM pedagogy.micro_course_state_asset sa JOIN visual.asset a ON a.asset_id = sa.asset_id
          LEFT JOIN pedagogy.video_asset v ON v.visual_asset_id = a.asset_id AND v.review_status = 'APPROVED'
         WHERE sa.state_id = s.state_id AND a.validation_status = 'VALID'),
      'qa_contexts', (SELECT coalesce(json_agg(json_build_object('qa_context_id', q.qa_context_id,
          'context_type', q.context_type, 'question_pattern', q.question_pattern,
          'approved_content', q.approved_content, 'concept_id', q.concept_id, 'technique_id', q.technique_id,
          'skill_id', q.skill_id, 'misconception_id', q.misconception_id, 'priority', q.priority)
          ORDER BY q.priority DESC, q.qa_context_id), '[]')
          FROM pedagogy.state_qa_context q WHERE q.state_id = s.state_id AND q.review_status = 'APPROVED'),
      'learning_items', (SELECT coalesce(json_agg(json_build_object('learning_item_id', li.learning_item_id,
          'question_text', li.question_text, 'choices', li.choices, 'transformed_form', li.transformed_form,
          'diagram_strategy', li.diagram_strategy, 'purpose', si.purpose, 'ordinal', si.ordinal,
          'required', si.required, 'sequence_position', si.sequence_position) ORDER BY si.ordinal, li.learning_item_id), '[]')
          FROM pedagogy.micro_course_state_learning_item si
          JOIN pedagogy.learning_item li ON li.learning_item_id = si.learning_item_id
         WHERE si.state_id = s.state_id AND li.review_status = 'APPROVED' AND li.student_visible),
      'transcript_segments', (SELECT coalesce(json_agg(json_build_object('segment_id', seg.segment_id,
          'video_asset_id', vt.video_asset_id, 'language_code', tr.language_code, 'transcript_version', tr.version,
          'start_ms', seg.start_ms, 'end_ms', seg.end_ms, 'transcript_text', seg.transcript_text,
          'speaker', seg.speaker, 'segment_index', seg.segment_index)
          ORDER BY seg.start_ms, seg.segment_index, seg.segment_id), '[]')
          FROM pedagogy.micro_course_state_asset sa
          JOIN pedagogy.video_asset vt ON vt.visual_asset_id = sa.asset_id
          JOIN pedagogy.video_transcript tr ON tr.video_asset_id = vt.video_asset_id
          JOIN pedagogy.video_transcript_segment seg ON seg.transcript_id = tr.transcript_id
         WHERE sa.state_id = s.state_id AND tr.status = 'APPROVED' AND seg.review_status = 'APPROVED'),
      'interactions', (SELECT coalesce(json_agg(json_build_object(
          'interaction_instance_id', i.interaction_instance_id, 'canonical_code', i.canonical_code,
          'title', i.title, 'instance_config', i.instance_config, 'initial_state', i.initial_state,
          'learning_objective', i.learning_objective, 'success_criteria', i.success_criteria,
          'template_version', iv.version, 'template_key', it.template_key,
          'interaction_family', it.interaction_family, 'default_layout', iv.default_layout,
          'allowed_controls', iv.allowed_controls, 'allowed_icons', iv.allowed_icons,
          'accessibility_policy', iv.accessibility_policy, 'scene_json', sc.scene_json,
          'rendered_video_asset_id', sc.rendered_video_asset_id, 'ordinal', sx.ordinal, 'required', sx.required,
          'sequence_position', sx.sequence_position) ORDER BY sx.ordinal, i.interaction_instance_id), '[]')
          FROM pedagogy.micro_course_state_interaction sx
          JOIN visual.interaction_instance i ON i.interaction_instance_id = sx.interaction_instance_id
          JOIN visual.interaction_template_version iv
            ON iv.interaction_template_version_id = i.interaction_template_version_id
          JOIN visual.interaction_template it ON it.interaction_template_id = iv.interaction_template_id
          LEFT JOIN visual.scene_spec sc ON sc.scene_spec_id = i.scene_spec_id AND sc.status = 'APPROVED'
         WHERE sx.state_id = s.state_id AND i.review_status = 'APPROVED' AND iv.status = 'PUBLISHED'),
      'activities', (SELECT coalesce(json_agg(json_build_object('activity_id', ad.activity_id,
          'activity_type', ad.activity_type, 'prompt', ad.prompt, 'options', ad.options,
          'estimated_seconds', ad.estimated_seconds, 'ordinal', sx.ordinal, 'purpose', sx.purpose,
          'required', sx.required, 'sequence_position', sx.sequence_position) ORDER BY sx.ordinal, ad.activity_id), '[]')
          FROM pedagogy.micro_course_state_activity sx JOIN activity.definition ad ON ad.activity_id = sx.activity_id
         WHERE sx.state_id = s.state_id),
      'concepts', (SELECT coalesce(json_agg(json_build_object('concept_id', b.concept_id, 'role', b.role,
          'importance', b.importance) ORDER BY b.concept_id, b.role), '[]')
          FROM pedagogy.micro_course_state_concept b WHERE b.state_id = s.state_id),
      'techniques', (SELECT coalesce(json_agg(json_build_object('technique_id', b.technique_id, 'role', b.role,
          'importance', b.importance) ORDER BY b.technique_id, b.role), '[]')
          FROM pedagogy.micro_course_state_technique b WHERE b.state_id = s.state_id),
      'skills', (SELECT coalesce(json_agg(json_build_object('skill_id', b.skill_id, 'role', b.role,
          'required_level', b.required_level) ORDER BY b.skill_id, b.role), '[]')
          FROM pedagogy.micro_course_state_skill b WHERE b.state_id = s.state_id),
      'misconceptions', (SELECT coalesce(json_agg(json_build_object('misconception_id', b.misconception_id,
          'role', b.role) ORDER BY b.misconception_id, b.role), '[]')
          FROM pedagogy.micro_course_state_misconception b WHERE b.state_id = s.state_id),
      'timeline_markers', (SELECT coalesce(json_agg(json_build_object('marker_id', mk.marker_id,
          'video_asset_id', mk.video_asset_id, 'timestamp_ms', mk.timestamp_ms, 'marker_type', mk.marker_type,
          'learning_item_id', mk.learning_item_id, 'activity_id', mk.activity_id,
          'intervention_id', mk.intervention_id, 'note', mk.note) ORDER BY mk.timestamp_ms, mk.marker_id), '[]')
          FROM pedagogy.video_timeline_marker mk WHERE mk.state_id = s.state_id AND mk.review_status = 'APPROVED')
      ) ORDER BY s.ordinal, s.state_key), '[]')
      FROM pedagogy.micro_course_state s
      LEFT JOIN pedagogy.micro_course_module sm ON sm.module_id = s.module_id
     WHERE s.release_id = r.release_id),
  'transitions', (SELECT coalesce(json_agg(json_build_object('transition_id', x.transition_id,
      'from_state_id', x.from_state_id, 'to_state_id', x.to_state_id, 'transition_type', x.transition_type,
      'condition_type', x.condition_type, 'condition_payload', x.condition_payload, 'priority', x.priority)
      ORDER BY x.from_state_id, x.priority, x.transition_id), '[]')
      FROM pedagogy.micro_course_transition x WHERE x.release_id = r.release_id AND x.review_status = 'APPROVED'),
  'interventions', (SELECT coalesce(json_agg(json_build_object('intervention_id', iv.intervention_id,
      'canonical_code', iv.canonical_code, 'name', iv.name, 'target_misconception_id', iv.target_misconception_id,
      'target_skill_id', iv.target_skill_id, 'target_technique_id', iv.target_technique_id,
      'entry_state_id', iv.entry_state_id,
      'steps', (SELECT coalesce(json_agg(json_build_object('ordinal', st.ordinal, 'step_type', st.step_type,
          'prompt_text', st.prompt_text, 'asset_id', st.asset_id, 'learning_item_id', st.learning_item_id,
          'activity_id', st.activity_id, 'expected_response_type', st.expected_response_type)
          ORDER BY st.ordinal, st.intervention_step_id), '[]')
          FROM pedagogy.intervention_step st WHERE st.intervention_id = iv.intervention_id))
      ORDER BY iv.canonical_code, iv.intervention_id), '[]')
      FROM pedagogy.intervention_script iv WHERE iv.release_id = r.release_id AND iv.review_status = 'APPROVED')
)"""

_MC_SERVER = """json_build_object(
  'schema', 'micro-course-release/server/v1',
  'release_id', r.release_id, 'agent_policy', r.agent_policy,
  'state_agent_policies', (SELECT coalesce(json_agg(json_build_object('state_id', s.state_id,
      'state_key', s.state_key, 'agent_policy', s.agent_policy) ORDER BY s.ordinal, s.state_key), '[]')
      FROM pedagogy.micro_course_state s WHERE s.release_id = r.release_id),
  'learning_item_keys', (SELECT coalesce(json_agg(json_build_object('learning_item_id', li.learning_item_id,
      'correct_answer', li.correct_answer, 'answer_or_solution_seed', li.answer_or_solution_seed)
      ORDER BY li.learning_item_id), '[]')
      FROM pedagogy.learning_item li
     WHERE li.learning_item_id IN (SELECT si.learning_item_id FROM pedagogy.micro_course_state_learning_item si
                                     JOIN pedagogy.micro_course_state s ON s.state_id = si.state_id
                                    WHERE s.release_id = r.release_id)),
  'activity_keys', (SELECT coalesce(json_agg(json_build_object('activity_id', ad.activity_id,
      'correctness_policy', ad.correctness_policy) ORDER BY ad.activity_id), '[]')
      FROM activity.definition ad
     WHERE ad.activity_id IN (SELECT sx.activity_id FROM pedagogy.micro_course_state_activity sx
                                JOIN pedagogy.micro_course_state s ON s.state_id = sx.state_id
                               WHERE s.release_id = r.release_id)),
  'asset_sources', (SELECT coalesce(json_agg(json_build_object('asset_id', a.asset_id, 'uri', a.uri)
      ORDER BY a.asset_id), '[]')
      FROM visual.asset a
     WHERE a.asset_id IN (SELECT sa.asset_id FROM pedagogy.micro_course_state_asset sa
                            JOIN pedagogy.micro_course_state s ON s.state_id = sa.state_id
                           WHERE s.release_id = r.release_id))
)"""

_MC_RELEASE_WHERE = """(r.status = 'PUBLISHED' OR (r.status IN ('SUPERSEDED', 'RETIRED') AND EXISTS (
        SELECT 1 FROM learner.micro_course_enrollment en WHERE en.release_id = r.release_id)))"""

_MCREL_SQL = f"""
SELECT r.release_id, r.version, r.status, r.content_hash, r.published_at, r.approved_at, c.canonical_code,
       c.micro_course_id, {_MC_LEARNER} AS learner, {_MC_SERVER} AS server
  FROM pedagogy.micro_course_release r
  JOIN pedagogy.micro_course c ON c.micro_course_id = r.micro_course_id
 WHERE {_MC_RELEASE_WHERE}
 ORDER BY r.release_id"""


def _mc_snapshot(release_id, learner: dict, server: dict) -> tuple[str, str, str, int, int]:
    for k in server.get("activity_keys") or []:
        k["canonical_policy"] = _canon_policy(k.get("correctness_policy"))
    lb, sb = json_bytes(learner), json_bytes(server)
    sha = hashlib.sha256(json_bytes({"learner": learner, "server": server})).hexdigest()
    base = f"releases/micro-course/{release_id}/{sha}"
    return sha, f"{base}/learner.json", f"{base}/server.json", len(lb), len(sb)


def _mcrel(r):
    sha, lkey, skey, lbytes, sbytes = _mc_snapshot(r["release_id"], r["learner"], r["server"])
    yield S3Put("content", lkey, r["learner"])
    yield S3Put("content", skey, r["server"])
    yield _item(f"MCREL#{r['release_id']}", "META", "MCREL",
                {"GSI1PK": f"MCRELS#{r['canonical_code']}", "GSI1SK": _num(r["version"], 4)},
                release_id=r["release_id"], micro_course_id=r["micro_course_id"], canonical_code=r["canonical_code"],
                status=r["status"], release_version=r["version"], content_sha256=sha,
                source_content_hash=r["content_hash"], s3_learner_key=lkey, s3_server_key=skey,
                learner_bytes=lbytes, server_bytes=sbytes, published_at=r["published_at"],
                approved_at=r["approved_at"])


_MC_SQL = f"""
SELECT c.micro_course_id, c.canonical_code, c.title, c.description, c.estimated_minutes, c.difficulty_level,
       c.metadata, c.created_at, c.updated_at,
       (SELECT coalesce(json_agg(json_build_object('target_type', t.target_type, 'role', t.role, 'ordinal', t.ordinal,
            'concept_id', t.concept_id, 'technique_id', t.technique_id, 'skill_id', t.skill_id,
            'theorem_id', t.theorem_id, 'name', coalesce(kc.name, kt.name, ks.name, th.name),
            'slug', coalesce(kc.slug, kt.slug, ks.slug, th.slug)) ORDER BY t.role, t.ordinal, t.target_type), '[]')
          FROM pedagogy.micro_course_target t
          LEFT JOIN knowledge.concept kc ON kc.concept_id = t.concept_id
          LEFT JOIN knowledge.technique kt ON kt.technique_id = t.technique_id
          LEFT JOIN knowledge.skill ks ON ks.skill_id = t.skill_id
          LEFT JOIN knowledge.theorem th ON th.theorem_id = t.theorem_id
         WHERE t.micro_course_id = c.micro_course_id) AS targets,
       r.release_id, r.version AS release_version, r.published_at,
       CASE WHEN r.release_id IS NULL THEN NULL ELSE {_MC_LEARNER} END AS learner,
       CASE WHEN r.release_id IS NULL THEN NULL ELSE {_MC_SERVER} END AS server
  FROM pedagogy.micro_course c
  LEFT JOIN LATERAL (SELECT * FROM pedagogy.micro_course_release r0
                      WHERE r0.micro_course_id = c.micro_course_id AND r0.status = 'PUBLISHED'
                      ORDER BY r0.version DESC, r0.release_id LIMIT 1) r ON true
 WHERE c.is_active
 ORDER BY c.canonical_code"""


def _mc(r):
    cur = {}
    if r["release_id"] is not None:
        sha, lkey, skey, _, _ = _mc_snapshot(r["release_id"], r["learner"], r["server"])
        cur = dict(current_release_id=r["release_id"], current_release_version=r["release_version"],
                   current_sha256=sha, current_s3_key=lkey, current_s3_server_key=skey,
                   current_published_at=r["published_at"])
    yield _item(f"MC#{r['canonical_code']}", "META", "MC",
                {"GSI2PK": "CATALOG#MC", "GSI2SK": f"{r['title']}#{r['canonical_code']}"} if cur else None,
                micro_course_id=r["micro_course_id"], canonical_code=r["canonical_code"], title=r["title"],
                description=r["description"], estimated_minutes=r["estimated_minutes"],
                difficulty_level=r["difficulty_level"], metadata=r["metadata"], targets=_list(r["targets"]),
                status="ACTIVE" if cur else "UNPUBLISHED", created_at=r["created_at"], updated_at=r["updated_at"],
                **cur)


# ------------------------------------------------------------------ tutoring route releases (immutable S3 snapshots)

# learner.json = what route_runtime.current_view/assist serve (instruction without expected_response, the published
# hint library, requirements, asset links); server.json = expected responses, the proof graph and the assets
# (which carry expected answers / correct models). One row per PUBLISHED release, aggregated with json_agg.
_ROUTE_SQL = """
SELECT r.route_release_id, r.solution_id, r.problem_id, p.canonical_code, s.verification_status, r.release_version,
       r.source_hash, r.content_hash, r.approach_name, r.difficulty_level, r.preferred_for_tutoring, r.route_quality,
       r.status, r.generator_version, r.published_at,
       json_build_object(
         'schema', 'route-release/learner/v1', 'route_release_id', r.route_release_id, 'problem_id', r.problem_id,
         'problem_code', p.canonical_code, 'solution_id', r.solution_id, 'release_version', r.release_version,
         'approach_name', r.approach_name, 'approach_summary', r.approach_summary,
         'difficulty_level', r.difficulty_level, 'conceptual_load', r.conceptual_load,
         'algebraic_load', r.algebraic_load, 'insight_load', r.insight_load,
         'preferred_for_tutoring', r.preferred_for_tutoring, 'route_quality', r.route_quality,
         'published_at', r.published_at,
         'steps', (SELECT coalesce(json_agg(json_build_object(
              'step_index', st.step_index, 'step_id', st.step_id, 'instruction_version', i.instruction_version,
              'instruction_content_hash', i.content_hash, 'instruction', i.content - 'expected_response',
              'hints', (SELECT coalesce(json_agg(json_build_object('hint_level', h.hint_level,
                   'hint_variant', h.hint_variant, 'misconception_key', h.misconception_key,
                   'content_hash', h.content_hash, 'hint_text', h.hint_text)
                   ORDER BY h.hint_level, h.hint_variant, h.misconception_key), '[]')
                   FROM pedagogy.route_step_hint h
                  WHERE h.route_release_id = st.route_release_id AND h.step_index = st.step_index),
              'requirements', (SELECT coalesce(json_agg(json_build_object('taxonomy_node_id', q.taxonomy_node_id,
                   'role', q.role, 'required_level', q.required_level, 'importance', q.importance,
                   'blocking', q.blocking, 'proposed_node_type', q.proposed_node_type,
                   'proposed_name', q.proposed_name, 'proposed_description', q.proposed_description)
                   ORDER BY q.taxonomy_node_id, q.role), '[]')
                   FROM pedagogy.solution_step_requirement q
                  WHERE q.route_release_id = st.route_release_id AND q.step_index = st.step_index),
              'asset_links', (SELECT coalesce(json_agg(json_build_object('asset_key', l.asset_key, 'role', l.role)
                   ORDER BY l.asset_key, l.role), '[]')
                   FROM pedagogy.route_asset_link l
                  WHERE l.route_release_id = st.route_release_id AND l.step_index = st.step_index))
              ORDER BY st.step_index), '[]')
              FROM pedagogy.route_step st
              LEFT JOIN LATERAL (SELECT si.instruction_version, si.content_hash, si.content
                                   FROM pedagogy.solution_step_instruction si
                                  WHERE si.route_release_id = st.route_release_id AND si.step_index = st.step_index
                                  ORDER BY si.instruction_version DESC LIMIT 1) i ON true
             WHERE st.route_release_id = r.route_release_id)
       ) AS learner,
       json_build_object(
         'schema', 'route-release/server/v1', 'route_release_id', r.route_release_id, 'source_hash', r.source_hash,
         'content_hash', r.content_hash, 'generator_version', r.generator_version,
         'steps', (SELECT coalesce(json_agg(json_build_object(
              'step_index', st.step_index, 'expected_response', i.content -> 'expected_response',
              'mathematical_result', st.mathematical_result, 'source_quote', st.source_quote,
              'depends_on', st.depends_on, 'produces', st.produces, 'uses_claims', st.uses_claims,
              'generation_metadata', st.generation_metadata) ORDER BY st.step_index), '[]')
              FROM pedagogy.route_step st
              LEFT JOIN LATERAL (SELECT si.content FROM pedagogy.solution_step_instruction si
                                  WHERE si.route_release_id = st.route_release_id AND si.step_index = st.step_index
                                  ORDER BY si.instruction_version DESC LIMIT 1) i ON true
             WHERE st.route_release_id = r.route_release_id),
         'assets', (SELECT coalesce(json_agg(json_build_object('asset_key', a.asset_key, 'asset_id', a.asset_id,
              'asset_kind', a.asset_kind, 'content_hash', a.content_hash, 'content', a.content)
              ORDER BY a.asset_key), '[]')
              FROM pedagogy.route_asset a WHERE a.route_release_id = r.route_release_id)
       ) AS server
  FROM pedagogy.solution_route_release r
  JOIN core.problem p ON p.problem_id = r.problem_id
  JOIN core.solution s ON s.solution_id = r.solution_id
 WHERE r.status = 'PUBLISHED'
 ORDER BY r.route_release_id"""


def _route_ptr_sk(r) -> str:
    """Ascending SK order == select_published ORDER BY preferred DESC, route_quality DESC NULLS LAST,
    difficulty_level, release_version DESC, route_release_id."""
    pref = 9 - (1 if r["preferred_for_tutoring"] else 0)
    q = r["route_quality"]
    inv_q = 9999 if q is None else 9998 - max(0, min(9998, int(round(float(q) * 1000))))
    inv_v = 999999 - int(r["release_version"])
    return f"ROUTE#{pref}#{inv_q:04d}#{_num(r['difficulty_level'], 2)}#{inv_v:06d}#{r['route_release_id']}"


def _route_release(r):
    learner, server = r["learner"], r["server"]
    sha = hashlib.sha256(json_bytes({"learner": learner, "server": server})).hexdigest()
    base = f"releases/route/{r['route_release_id']}/{sha}"
    lkey, skey = f"{base}/learner.json", f"{base}/server.json"
    yield S3Put("content", lkey, learner)
    yield S3Put("content", skey, server)
    yield _item(f"ROUTEREL#{r['route_release_id']}", "META", "ROUTEREL",
                route_release_id=r["route_release_id"], problem_id=r["problem_id"], problem_code=r["canonical_code"],
                solution_id=r["solution_id"], status=r["status"], release_version=r["release_version"],
                approach_name=r["approach_name"], difficulty_level=r["difficulty_level"],
                step_count=len(learner.get("steps") or []), content_sha256=sha,
                source_content_hash=r["content_hash"], source_hash=r["source_hash"],
                generator_version=r["generator_version"], s3_learner_key=lkey, s3_server_key=skey,
                published_at=r["published_at"])
    yield _item(f"PROBLEM#{r['canonical_code']}", _route_ptr_sk(r), "ROUTEPTR",
                route_release_id=r["route_release_id"], solution_id=r["solution_id"],
                verification_status=r["verification_status"], preferred_for_tutoring=r["preferred_for_tutoring"],
                route_quality=r["route_quality"], difficulty_level=r["difficulty_level"],
                release_version=r["release_version"])


# ------------------------------------------------------------------ videos and transcripts

def _video(r):
    yield _item(f"VIDEO#{r['video_asset_id']}", "META", "VIDEO",
                video_asset_id=r["video_asset_id"], visual_asset_id=r["visual_asset_id"], provider=r["provider"],
                external_video_id=r["external_video_id"], url=r["canonical_url"], title=r["title"],
                creator_name=r["creator_name"], channel_name=r["channel_name"], duration_ms=r["duration_ms"],
                transcript_status=r["transcript_status"], review_status=r["review_status"],
                approved_at=r["approved_at"])


def _seg_tags(kind: str) -> str:
    return (f"'{kind}s', (SELECT coalesce(json_agg(json_build_object('{kind}_id', x.{kind}_id, 'role', x.role, "
            f"'confidence', x.confidence) ORDER BY x.{kind}_id, x.role), '[]') FROM pedagogy.video_segment_{kind} x "
            f"WHERE x.segment_id = seg.segment_id AND x.review_status = 'APPROVED')")


_TRANSCRIPT_FROM = """pedagogy.video_transcript t
  JOIN pedagogy.video_asset v ON v.video_asset_id = t.video_asset_id
 WHERE t.status = 'APPROVED' AND v.review_status = 'APPROVED'"""

_TRANSCRIPT_SQL = f"""
SELECT DISTINCT ON (t.video_asset_id, t.language_code)
       t.transcript_id, t.video_asset_id, t.version, t.language_code, t.source_type, t.content_hash, t.reviewed_at,
       (SELECT coalesce(json_agg(json_build_object('segment_id', seg.segment_id, 'segment_index', seg.segment_index,
            'start_ms', seg.start_ms, 'end_ms', seg.end_ms, 'transcript_text', seg.transcript_text,
            'speaker', seg.speaker, 'segment_hash', seg.segment_hash,
            {_seg_tags('concept')}, {_seg_tags('misconception')}, {_seg_tags('skill')}, {_seg_tags('technique')})
            ORDER BY seg.start_ms, seg.segment_index, seg.segment_id), '[]')
          FROM pedagogy.video_transcript_segment seg
         WHERE seg.transcript_id = t.transcript_id AND seg.review_status = 'APPROVED') AS segments
  FROM {_TRANSCRIPT_FROM}
 ORDER BY t.video_asset_id, t.language_code, t.version DESC, t.transcript_id"""


def _transcript(r):
    body = {"schema": "video-transcript/v1", "transcript_id": str(r["transcript_id"]),
            "video_asset_id": str(r["video_asset_id"]), "language_code": r["language_code"],
            "version": r["version"], "source_type": r["source_type"], "content_hash": r["content_hash"],
            "segments": r["segments"]}
    sha = hashlib.sha256(json_bytes(body)).hexdigest()
    key = f"video/{r['video_asset_id']}/{r['language_code']}/v{r['version']}/{sha}.json"
    yield S3Put("content", key, body)
    yield _item(f"VIDEO#{r['video_asset_id']}", f"TRANSCRIPT#{r['language_code']}", "VTRANSCRIPT",
                transcript_id=r["transcript_id"], language_code=r["language_code"], transcript_version=r["version"],
                s3_key=key, sha256=sha, segment_count=len(r["segments"] or []),
                source_content_hash=r["content_hash"], reviewed_at=r["reviewed_at"])


# ------------------------------------------------------------------ runtime hint cache, stats, vector index pointers

def _hint(r):
    yield _item(f"HINT#{r['solution_step_id']}", f"L{r['hint_level']}#{r['prompt_version']}", "HINT",
                solution_step_id=r["solution_step_id"], hint_level=r["hint_level"],
                prompt_version=r["prompt_version"], hint_text=r["hint_text"], model=r["model"],
                leak_checked=r["leak_checked"], created_at=r["created_at"])


# db/queries.corpus_coverage, materialised once (publisher keeps it current with ADD deltas).
_STATS_SQL = """
SELECT coalesce(json_agg(x ORDER BY x.competition), '[]') AS rows FROM (
    SELECT comp.name AS competition,
           count(DISTINCT pa.paper_id) AS papers,
           count(DISTINCT p.problem_id) AS problems,
           count(DISTINCT pc.problem_id) AS problems_with_concept,
           count(DISTINCT pt.problem_id) AS problems_with_technique
      FROM core.competition comp
      JOIN core.competition_edition ed ON ed.competition_id = comp.competition_id
      JOIN core.paper pa ON pa.edition_id = ed.edition_id
      JOIN core.problem p ON p.paper_id = pa.paper_id
      LEFT JOIN knowledge.problem_concept pc ON pc.problem_id = p.problem_id
      LEFT JOIN knowledge.problem_technique pt ON pt.problem_id = p.problem_id
     GROUP BY comp.name) x"""


def _stats(r):
    yield _item("STATS#CORPUS", "COVERAGE", "STATS", rows=_list(r["rows"]))


_VINDEX_FAMILIES = [f for f in FAMILY_INDEX if f != "search-archive"]


def _vindex(r):
    for fam in _VINDEX_FAMILIES:
        yield _item(f"VINDEX#{fam}", "ACTIVE", "VINDEX", family=fam, index_name=FAMILY_INDEX[fam],
                    model=r["model_name"], dims=r["dimensions"], distance=r["distance_metric"],
                    activated_at=r["activated_at"])


# ------------------------------------------------------------------ mappings

def _m(name, sql, transform, expected, note=""):
    return Mapping(name, T, sql, transform, expected_source=expected, note=note)


MAPPINGS: list[Mapping] = [
    # competitions and problems
    _m("core.competition", """
SELECT competition_id, external_code, name, organization, country, level FROM core.competition
 ORDER BY name, competition_id""", _competition, "core.competition"),
    _coverage("core.competition_edition", "edition_id", "denormalised into PROBLEM (year, season, edition_label)"),
    _coverage("core.paper", "paper_id", "denormalised into PROBLEM (paper_code, paper_type)"),
    _m("core.problem", _PROBLEM_SQL, _problem, "core.problem WHERE status = 'ACTIVE'",
       "PROBLEM (learner-safe) + PROBLEM_KEY (server-only official_answer/answer_type)"),
    _m("core.solution", _SOLUTION_SQL, _solution, "core.solution s JOIN core.problem p ON p.problem_id = s.problem_id",
       "SOLUTION (server-only); body offloaded to S3 above 100 KB"),
    _m("core.problem_image", _IMAGE_SQL, _image, _IMAGE_FROM,
       "STUDENT_IMAGE_FILTER subset; bytes → content bucket images/<sha256>; files missing on this host are skipped"),
    _coverage("pedagogy.diagram", "diagram_id", "visibility input of STUDENT_IMAGE_FILTER; student diagrams are problem images"),
    _m("knowledge.problem_concept", _PTAG_CONCEPT_SQL, _ptag_concept,
       "(SELECT DISTINCT pc.problem_id, pc.concept_id FROM " + _PTAG_CONCEPT_FROM + ") x",
       "PTAG CONCEPT; non-REJECTED; rows differing only in role merged per (problem, concept)"),
    _m("knowledge.problem_technique", _PTAG_TECHEV_SQL, _ptag_techev, _PTAG_TECHEV_EXPECTED,
       "PTAG TECHEV = technique_problem_evidence_sql(filter_slug=False), one per (problem, technique)"),
    _m("knowledge.problem_skill", _PTAG_SKILL_SQL, _ptag_skill, _PTAG_SKILL_FROM, "PTAG SKILL; non-REJECTED"),
    _m("stats.corpus_coverage", _STATS_SQL, _stats, None, "STATS#CORPUS/COVERAGE rollup (queries.corpus_coverage)"),

    # catalogue
    _m("knowledge.concept", _CONCEPT_SQL, _concept, "knowledge.concept WHERE status = 'ACTIVE'"),
    _m("knowledge.technique", _TECHNIQUE_SQL, _technique, "knowledge.technique WHERE status = 'ACTIVE'"),
    _m("knowledge.skill", _SKILL_SQL, _skill, "knowledge.skill WHERE is_active"),
    _m("knowledge.misconception", _MISCONCEPTION_SQL, _misconception, "knowledge.misconception WHERE is_active"),
    _coverage("knowledge.entity_alias", "alias_id", "aliases[] on CONCEPT/TECHNIQUE/SKILL/MISCONCEPTION"),
    _coverage("knowledge.concept_relation", "relation_id", "relations_out[]/relations_in[] on CONCEPT"),
    _coverage("knowledge.skill_relation", "from_skill_id, to_skill_id, relation_type",
              "relations_out[]/relations_in[] on SKILL"),
    _coverage("knowledge.skill_concept", "skill_id, concept_id", "concepts[] on SKILL"),
    *[_m(f"catalog.{kind}", sql, _catalog(kind), None, f"S3 catalog/{kind}/<sha256>.json + CATALOGPTR")
      for kind, sql in _CATALOG_SQL.items()],

    # theorems
    _m("knowledge.theorem", _THEOREM_SQL, _theorem, "knowledge.theorem WHERE review_status = 'APPROVED'"),
    _m("knowledge.theorem_relation", f"""
SELECT tr.relation_id, tr.from_theorem_id, tr.to_theorem_id, tr.relation_type, tr.confidence, tr.review_status,
       b.slug AS to_slug, b.name AS to_name
  FROM {_THEOREM_REL_FROM}
 ORDER BY tr.relation_id""", _theorem_rel, _THEOREM_REL_FROM),
    _m("knowledge.technique_theorem", f"""
SELECT tt.technique_id, tt.theorem_id, tt.role, tt.confidence, t.slug, t.name, k.slug AS technique_slug
  FROM {_TECH_THEOREM_FROM.replace(' WHERE', ' LEFT JOIN knowledge.technique k ON k.technique_id = tt.technique_id WHERE')}
 ORDER BY tt.theorem_id, tt.technique_id, tt.role""", _theorem_link_technique, _TECH_THEOREM_FROM),
    _m("knowledge.theorem_taxonomy_link", f"""
SELECT tl.theorem_id, tl.taxonomy_node_id, tl.role, tl.derived_via, t.slug, t.name
  FROM {_THEOREM_TAX_FROM}
 ORDER BY tl.theorem_id, tl.taxonomy_node_id""", _theorem_link_taxnode, _THEOREM_TAX_FROM),
    _coverage("knowledge.theorem_source", "theorem_source_id", "sources[] (APPROVED) on THEOREM"),
    _coverage("knowledge.theorem_asset", "theorem_id, asset_id", "assets[] (VALID) on THEOREM"),

    # taxonomy and source books
    _m("pedagogy.taxonomy_node", _TAXONOMY_SQL, _taxonomy, "pedagogy.taxonomy_node",
       "TAXNODE (+ FACET TAXSEARCH for nodes with taxonomy-search vectors)"),
    _coverage("pedagogy.taxonomy_edge", "from_node_id, to_node_id, relationship_type", "edges[] on TAXNODE"),
    _coverage("pedagogy.problem_enrichment", "problem_id", "enrichment on PROBLEM"),
    _coverage("pedagogy.problem_source_ref", "book_code, source_problem_id", "source_ref on PROBLEM"),
    _m("pedagogy.source_book", _SOURCEBOOK_SQL, _sourcebook, "pedagogy.source_book"),
    _coverage("pedagogy.chapter_section", "book_code, chapter_number, section_number", "sections[] on SOURCEBOOK"),

    # solution DAG, steps, learning items
    _m("pedagogy.solution_step#soldag", _SOLDAG_SQL, _soldag,
       "(SELECT DISTINCT solution_id FROM pedagogy.solution_step WHERE publication_status = 'PUBLISHED') x",
       "SOLDAG per solution with published steps (server-only); S3 above 100 KB"),
    _m("pedagogy.solution_step", _STEP_SQL, _step,
       "pedagogy.solution_step s JOIN core.problem p ON p.problem_id = s.problem_id "
       "WHERE s.publication_status = 'PUBLISHED'", "STEP + FACET STEP (PROBLEM/SKILL/SUBCONCEPT/CONCEPT/TECHNIQUE)"),
    _coverage("pedagogy.solution_part", "solution_part_id", "parts[] in SOLDAG"),
    _coverage("pedagogy.solution_step_dependency", "from_step_id, to_step_id, relationship_type",
              "dependencies[] in SOLDAG"),
    _coverage("pedagogy.solution_step_technique", "solution_step_id, technique_node_id",
              "step_techniques[] in SOLDAG, technique_node_ids[] on STEP"),
    _m("pedagogy.learning_item", _LI_SQL, _learning_item, f"pedagogy.learning_item li WHERE {_LI_WHERE}",
       "LI (learner-safe) + LI_KEY (server-only) + FACET LI (ANCHOR/TARGET_SKILL/TARGET_SUBCONCEPT)"),
    _coverage("pedagogy.learning_item_step_anchor", "learning_item_id, solution_step_id", "anchor_step_ids[] on LI"),

    # activities
    _m("activity.definition", f"""
SELECT activity_id, activity_type, prompt, options, correctness_policy, target_skill, target_skill_id,
       source_problem_id, estimated_seconds, source_type, persistence_mode, status, created_at
  FROM activity.definition WHERE {_ACT_WHERE}
 ORDER BY activity_id""", _activity, f"activity.definition WHERE {_ACT_WHERE}",
       "ACT + ACT_KEY (canonical correctness_policy); SESSION/EPHEMERAL definitions belong to C3"),

    # visual
    _coverage("visual.interaction_template", "interaction_template_id", "template fields on ITPLVER + widget library"),
    _m("visual.interaction_template_version", f"""
SELECT v.interaction_template_version_id, v.interaction_template_id, t.template_key, t.name AS template_name,
       t.interaction_family, t.description AS template_description, v.version, v.input_schema, v.state_schema,
       v.event_schema, v.output_schema, v.default_layout, v.allowed_controls, v.allowed_icons,
       v.diagnostic_capabilities, v.animation_slots, v.accessibility_policy, v.content_hash, v.status, v.published_at
  FROM visual.interaction_template_version v
  JOIN visual.interaction_template t ON t.interaction_template_id = v.interaction_template_id
 WHERE {_ITPLVER_WHERE}
 ORDER BY t.template_key, v.version""", _itplver, f"visual.interaction_template_version v WHERE {_ITPLVER_WHERE}"),
    _coverage("visual.control_template", "control_template_id", "widget-library snapshot"),
    _coverage("visual.icon_token", "icon_token_id", "widget-library snapshot"),
    _coverage("visual.animation_template", "animation_template_id", "widget-library snapshot"),
    _m("visual.interaction_instance", f"""
SELECT i.interaction_instance_id, i.interaction_template_version_id, t.template_key, v.version AS template_version,
       i.canonical_code, i.title, i.instance_config, i.initial_state, i.learning_objective, i.success_criteria,
       i.feedback_policy_id, i.scene_spec_id, i.content_hash, i.review_status, i.approved_at,
       {_junction_ids('concept')}, {_junction_ids('skill')}, {_junction_ids('technique')},
       {_junction_ids('misconception')}
  FROM visual.interaction_instance i
  JOIN visual.interaction_template_version v ON v.interaction_template_version_id = i.interaction_template_version_id
  JOIN visual.interaction_template t ON t.interaction_template_id = v.interaction_template_id
 WHERE i.review_status = 'APPROVED'
 ORDER BY i.interaction_instance_id""", _iinst, "visual.interaction_instance WHERE review_status = 'APPROVED'"),
    *[_coverage(f"visual.interaction_instance_{k}", f"interaction_instance_id, {k}_id, role", f"{k}_ids[] on IINST")
      for k in ("concept", "skill", "technique", "misconception")],
    _m("visual.scene_spec", """
SELECT scene_spec_id, canonical_code, version, scene_schema_version, scene_json, content_hash, status, approved_at,
       rendered_video_asset_id
  FROM visual.scene_spec WHERE status = 'APPROVED'
 ORDER BY scene_spec_id""", _scene, "visual.scene_spec WHERE status = 'APPROVED'"),
    _m("visual.asset", """
SELECT asset_id, uri, mime_type, content_hash, source_problem_id, diagram_id, persistence_mode, validation_status,
       asset_kind, title, source_url, rights_note, object_size_bytes
  FROM visual.asset WHERE validation_status = 'VALID'
 ORDER BY asset_id""", _vasset, "visual.asset WHERE validation_status = 'VALID'"),

    # micro-courses
    _m("pedagogy.micro_course", _MC_SQL, _mc, "pedagogy.micro_course WHERE is_active",
       "MC catalogue item + current PUBLISHED release pointer"),
    _m("pedagogy.micro_course_release", _MCREL_SQL, _mcrel,
       f"pedagogy.micro_course_release r WHERE {_MC_RELEASE_WHERE}",
       "MCREL + S3 releases/micro-course/<release_id>/<sha256>/{learner,server}.json; PUBLISHED + pinned historic"),
    _coverage("pedagogy.micro_course_target", "micro_course_id, target_type, role, ordinal", "targets[] on MC + snapshot"),
    *[_coverage(f"pedagogy.{t}", keys, "micro-course release snapshot") for t, keys in (
        ("micro_course_module", "module_id"), ("micro_course_state", "state_id"),
        ("micro_course_transition", "transition_id"), ("micro_course_state_activity", "state_id, activity_id"),
        ("micro_course_state_asset", "state_id, asset_id"),
        ("micro_course_state_interaction", "state_id, interaction_instance_id"),
        ("micro_course_state_learning_item", "state_id, learning_item_id"),
        ("micro_course_state_concept", "state_id, concept_id, role"),
        ("micro_course_state_skill", "state_id, skill_id, role"),
        ("micro_course_state_technique", "state_id, technique_id, role"),
        ("micro_course_state_misconception", "state_id, misconception_id, role"),
        ("state_qa_context", "qa_context_id"), ("intervention_script", "intervention_id"),
        ("intervention_step", "intervention_step_id"), ("video_timeline_marker", "marker_id"))],

    # tutoring routes
    _m("pedagogy.solution_route_release", _ROUTE_SQL, _route_release,
       "pedagogy.solution_route_release WHERE status = 'PUBLISHED'",
       "ROUTEREL + ROUTEPTR + S3 releases/route/<route_release_id>/<sha256>/{learner,server}.json"),
    *[_coverage(f"pedagogy.{t}", keys, "route release snapshot") for t, keys in (
        ("route_step", "route_release_id, step_index"),
        ("solution_step_instruction", "route_release_id, step_index"),
        ("route_step_hint", "route_release_id, step_index, hint_level, hint_variant, misconception_key"),
        ("solution_step_requirement", "route_release_id, step_index, taxonomy_node_id, role"),
        ("route_asset", "route_release_id, asset_key"),
        ("route_asset_link", "route_release_id, step_index, asset_key, role"))],

    # videos
    _m("pedagogy.video_asset", """
SELECT video_asset_id, visual_asset_id, provider, external_video_id, canonical_url, title, creator_name, channel_name,
       duration_ms, transcript_status, review_status, approved_at
  FROM pedagogy.video_asset WHERE review_status = 'APPROVED'
 ORDER BY video_asset_id""", _video, "pedagogy.video_asset WHERE review_status = 'APPROVED'"),
    _m("pedagogy.video_transcript", _TRANSCRIPT_SQL, _transcript,
       f"(SELECT DISTINCT t.video_asset_id, t.language_code FROM {_TRANSCRIPT_FROM}) x",
       "latest APPROVED transcript per (video, language) → S3 video/<id>/<lang>/v<version>/<sha256>.json"),
    _coverage("pedagogy.video_transcript_segment", "segment_id", "segments[] in transcript JSON"),
    *[_coverage(f"pedagogy.video_segment_{k}", f"segment_id, {k}_id, role", "segment tags in transcript JSON")
      for k in ("concept", "misconception", "skill", "technique")],

    # runtime hint cache and vector index pointers
    _m("pedagogy.step_hint", """
SELECT solution_step_id, hint_level, prompt_version, hint_text, model, leak_checked, created_at
  FROM pedagogy.step_hint
 ORDER BY solution_step_id, hint_level, prompt_version""", _hint, "pedagogy.step_hint",
       "HINT runtime cache (reverse-copied to PG on rollback)"),
    _m("search.embedding_model#vindex", """
SELECT embedding_model_id, model_name, dimensions, distance_metric, activated_at
  FROM search.embedding_model WHERE status = 'ACTIVE'
 ORDER BY embedding_model_id""", _vindex, None, "VINDEX#<family>/ACTIVE per S3 Vectors read family"),
]
