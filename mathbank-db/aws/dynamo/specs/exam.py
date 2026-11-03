"""C2 Quizzes and mock exams → mb-exam-<env> (design: 70_DYNAMODB_AND_S3_VECTORS_ADOPTION_PLAN.md §13 C2).

Learner data lives under PK=STUDENT#<sid> with SK prefix QUIZ#<qid>:
    QUIZ#<qid>                          PAPER (GSI1 = my papers, GSI2 = admin status list)
    QUIZ#<qid>#P#Q#<question_id>        QUESTION (learner-safe fields + tag ids/slugs)
    QUIZ#<qid>#P#RESP#<question_id>     RESPONSE
    QUIZ#<qid>#P#DRAFT#<question_id>    DRAFT (ttl updated_at + 90 d)
    QUIZ#<qid>#S#KEY#<question_id>      QUESTION_SECRET (answer key + solution + inspiration sources; server-only)
    QUIZ#<qid>#T#EVT#<iso μs>#<eid>     RESPONSE_EVENT
    QUIZ#<qid>#T#GEN#<ordinal:06d>      GENERATION_EVENT (ttl created_at + 180 d)
    QUIZ#<qid>#X#DIAG#<version:04d>     DIAGNOSIS
    QEVID#C|T#<id>#<submitted_at>#<rid> QUIZ_EVIDENCE (one per answered question tag)
    POOLSERVED#<pool_question_id>       POOL_SERVED
Pointers: QUIZ#<qid>/OWNER, RESPONSE#<rid>/OWNER. Pool: POOL#<id>/POOL, UNIQUE#content_hash#<sha>/UNIQUE,
POOLCONCEPT#<slug>/<style>#<qtype>#<band>#<id>. Vectors are written by exam-pool-vector-indexer
(vector_state=PENDING on migrated pool items), not by this migration.
"""
from __future__ import annotations

from ..spec import Mapping, Table, iso, ttl_after

# §3: answer keys and question payloads are never projected.
GSI_INCLUDE = ("quiz_id", "style", "title", "status", "created_at", "exam_mode", "agent_framework",
               "question_count", "answered_count", "correct_count", "student_id", "question_type",
               "difficulty_band", "times_served", "topic_key", "concept_slugs", "error_message")

TABLES = [Table("exam", gsis=("GSI1", "GSI2"), stream=True, ttl=True,
                include_gsis=(("GSI1", GSI_INCLUDE), ("GSI2", GSI_INCLUDE)),
                description="C2 quizzes and mock exams (quiz.*)")]

BANDS = {"easy", "medium", "hard", "very_hard"}

# Engine offload policy (> MB_OFFLOAD_THRESHOLD = 16 KiB → s3://mathbank-data-<env>-<account>/offload/exam/…,
# STUDENT# items under …/students/<sid>/…; the attribute is replaced by <attr>_ref).
OFFLOAD = {
    ("exam", "QUESTION"): ("prompt_text", "prompt_latex", "options", "complexity_signals"),
    ("exam", "QUESTION_SECRET"): ("correct_answer", "option_explanations", "revision_log", "inspiration_sources",
                                  "solution_text", "solution_latex", "key_insight", "solution_steps"),
    ("exam", "RESPONSE"): ("raw_response", "grading_feedback"),
    ("exam", "DRAFT"): ("raw_response",),
    ("exam", "GENERATION_EVENT"): ("detail",),
    ("exam", "DIAGNOSIS"): ("pacing_notes", "reasoning_guidance", "improvement_areas"),
    ("exam", "POOL_QUESTION"): ("question",),
}


def _band(v, where: str) -> str | None:
    """§7 pre-check: difficulty_band must be in the vocabulary after lower-casing, else abort."""
    if v is None:
        return None
    b = str(v).strip().lower()
    if b not in BANDS:
        raise ValueError(f"{where}: difficulty_band {v!r} not in {sorted(BANDS)}")
    return b


def _sk(qid, rest: str = "") -> str:
    return f"QUIZ#{qid}{rest}"


# ---------------------------------------------------------------- quiz.paper → PAPER + PAPER_OWNER

PAPER_SQL = """
SELECT p.quiz_id, p.student_id, p.style, p.title, p.instructions, p.requested_question_count,
       p.requested_question_types, p.target_skill_slugs, p.target_concept_slugs, p.difficulty_band,
       p.generated_by, p.object_key, p.object_sha256, p.status, p.error_message, p.created_at,
       p.started_at, p.submitted_at, p.graded_at, p.exam_mode, p.time_limit_seconds, p.agent_framework,
       p.resume_question_ordinal,
       (SELECT count(*) FROM quiz.question q WHERE q.quiz_id = p.quiz_id)                     AS question_count,
       (SELECT count(*) FROM quiz.response r WHERE r.quiz_id = p.quiz_id)                     AS answered_count,
       (SELECT count(*) FROM quiz.response r WHERE r.quiz_id = p.quiz_id AND r.is_correct)    AS correct_count,
       (SELECT count(*) FROM quiz.exam_diagnosis d WHERE d.quiz_id = p.quiz_id)               AS diagnosis_version
  FROM quiz.paper p
 ORDER BY p.quiz_id
"""


def paper(r: dict):
    qid, sid, created = r["quiz_id"], r["student_id"], iso(r["created_at"])
    item = {k: r[k] for k in (
        "quiz_id", "student_id", "style", "title", "instructions", "requested_question_count",
        "requested_question_types", "target_skill_slugs", "target_concept_slugs", "generated_by",
        "agent_framework", "exam_mode", "time_limit_seconds", "status", "error_message",
        "resume_question_ordinal", "question_count", "answered_count", "correct_count", "diagnosis_version",
        "object_key", "object_sha256", "created_at", "started_at", "submitted_at", "graded_at")}
    item.update({
        "PK": f"STUDENT#{sid}", "SK": _sk(qid), "type": "PAPER",
        "GSI1PK": f"STUDENT#{sid}#PAPERS", "GSI1SK": f"{created}#{qid}",
        "GSI2PK": f"PAPER_STATUS#{r['status']}", "GSI2SK": f"{created}#{qid}",
        "difficulty_band": _band(r["difficulty_band"], f"paper {qid}"),
        "answer_disclosure": "AFTER_SUBMIT" if r["exam_mode"] else "IMMEDIATE",
        "version": 1,
    })
    yield item
    yield {"PK": f"QUIZ#{qid}", "SK": "OWNER", "type": "PAPER_OWNER", "quiz_id": qid, "student_id": sid,
           "created_at": r["created_at"]}


# ---------------------------------------------------------------- quiz.question (+ solution, sources, tags)

QUESTION_SQL = """
SELECT q.question_id, q.quiz_id, p.student_id, q.ordinal, q.question_type, q.prompt_text, q.prompt_latex,
       q.options, q.correct_answer, q.points, q.inspired_by_problem_id, q.diagram_object_key, q.diagram_sha256,
       q.created_at, q.revision_log, q.difficulty_band, q.option_explanations, q.complexity_signals,
       q.pool_question_id,
       s.question_id IS NOT NULL AS has_solution, s.solution_text, s.solution_latex, s.key_insight,
       s.object_key AS solution_object_key, s.object_sha256 AS solution_object_sha256,
       s.created_at AS solution_created_at, s.solution_steps, s.step_count,
       COALESCE((SELECT json_agg(json_build_object('rank', qs.rank, 'problem_id', qs.problem_id,
                                                   'canonical_code', pr.canonical_code, 'note', qs.note)
                                 ORDER BY qs.rank, qs.problem_id)
                   FROM quiz.question_source qs JOIN core.problem pr ON pr.problem_id = qs.problem_id
                  WHERE qs.question_id = q.question_id), '[]'::json)                         AS inspiration_sources,
       ARRAY(SELECT qc.concept_id::text FROM quiz.question_concept qc
              WHERE qc.question_id = q.question_id ORDER BY qc.concept_id)                    AS concept_ids,
       ARRAY(SELECT c.slug FROM quiz.question_concept qc JOIN knowledge.concept c USING (concept_id)
              WHERE qc.question_id = q.question_id ORDER BY c.slug)                           AS concept_slugs,
       ARRAY(SELECT qt.technique_id::text FROM quiz.question_technique qt
              WHERE qt.question_id = q.question_id ORDER BY qt.technique_id)                  AS technique_ids,
       ARRAY(SELECT t.slug FROM quiz.question_technique qt JOIN knowledge.technique t USING (technique_id)
              WHERE qt.question_id = q.question_id ORDER BY t.slug)                           AS technique_slugs,
       ARRAY(SELECT qk.skill_id::text FROM quiz.question_skill qk
              WHERE qk.question_id = q.question_id ORDER BY qk.skill_id)                      AS skill_ids,
       ARRAY(SELECT k.slug FROM quiz.question_skill qk JOIN knowledge.skill k USING (skill_id)
              WHERE qk.question_id = q.question_id ORDER BY k.slug)                           AS skill_slugs
  FROM quiz.question q
  JOIN quiz.paper p ON p.quiz_id = q.quiz_id
  LEFT JOIN quiz.solution s ON s.question_id = q.question_id
 ORDER BY q.quiz_id, q.ordinal
"""


def question(r: dict):
    qid, sid, qn = r["quiz_id"], r["student_id"], r["question_id"]
    pk = f"STUDENT#{sid}"
    band = _band(r["difficulty_band"], f"question {qn}")
    q = {k: r[k] for k in (
        "question_id", "quiz_id", "student_id", "ordinal", "question_type", "prompt_text", "prompt_latex",
        "options", "points", "diagram_object_key", "diagram_sha256", "inspired_by_problem_id",
        "pool_question_id", "complexity_signals", "created_at")}
    q.update({"PK": pk, "SK": _sk(qid, f"#P#Q#{qn}"), "type": "QUESTION", "difficulty_band": band})
    for tag in ("concept_ids", "concept_slugs", "technique_ids", "technique_slugs", "skill_ids", "skill_slugs"):
        q[tag] = list(r[tag] or []) or None      # string set semantics; empty sets are omitted
    yield q

    secret = {
        "PK": pk, "SK": _sk(qid, f"#S#KEY#{qn}"), "type": "QUESTION_SECRET",
        "question_id": qn, "quiz_id": qid, "student_id": sid,
        "correct_answer": r["correct_answer"], "option_explanations": r["option_explanations"],
        "revision_log": r["revision_log"],
        "inspiration_sources": r["inspiration_sources"] or [],
    }
    if r["has_solution"]:
        secret.update({k: r[k] for k in (
            "solution_text", "solution_latex", "key_insight", "solution_steps", "step_count",
            "solution_object_key", "solution_object_sha256", "solution_created_at")})
    yield secret


# ---------------------------------------------------------------- embedded children (row-count verification only)

def _embedded(_r: dict):
    return ()


SOLUTION_SQL = "SELECT question_id FROM quiz.solution ORDER BY question_id"
SOURCE_SQL = "SELECT question_id, problem_id, rank FROM quiz.question_source ORDER BY question_id, rank, problem_id"
SKILL_SQL = "SELECT question_id, skill_id FROM quiz.question_skill ORDER BY question_id, skill_id"


# ---------------------------------------------------------------- question_concept / question_technique → QUIZ_EVIDENCE

def _evidence_sql(table: str, col: str) -> str:
    return f"""
SELECT j.question_id, j.{col} AS tag_id, q.quiz_id, p.student_id, r.response_id, r.is_correct,
       r.submitted_at, COALESCE(q.difficulty_band, p.difficulty_band) AS difficulty_band
  FROM quiz.{table} j
  JOIN quiz.question q ON q.question_id = j.question_id
  JOIN quiz.paper p ON p.quiz_id = q.quiz_id
  LEFT JOIN quiz.response r ON r.question_id = j.question_id
 ORDER BY j.question_id, j.{col}
"""


def _evidence(kind: str, id_attr: str):
    def fn(r: dict):
        if r["response_id"] is None or r["is_correct"] is None:
            return
        yield {"PK": f"STUDENT#{r['student_id']}",
               "SK": f"QEVID#{kind}#{r['tag_id']}#{iso(r['submitted_at'])}#{r['response_id']}",
               "type": "QUIZ_EVIDENCE", id_attr: r["tag_id"], "student_id": r["student_id"],
               "response_id": r["response_id"], "quiz_id": r["quiz_id"], "question_id": r["question_id"],
               "is_correct": r["is_correct"], "attempted_at": r["submitted_at"],
               "difficulty_band": _band(r["difficulty_band"], f"evidence {r['response_id']}")}
    return fn


# ---------------------------------------------------------------- quiz.response → RESPONSE + RESPONSE_OWNER

RESPONSE_SQL = """
SELECT r.response_id, r.question_id, r.quiz_id, r.student_id, q.ordinal, r.response_type, r.raw_response,
       r.object_key, r.object_sha256, r.is_correct, r.grading_method, r.grading_confidence, r.grading_feedback,
       r.time_spent_seconds, r.submitted_at
  FROM quiz.response r
  JOIN quiz.question q ON q.question_id = r.question_id
 ORDER BY r.response_id
"""


def response(r: dict):
    qid, sid, qn = r["quiz_id"], r["student_id"], r["question_id"]
    item = dict(r)
    item.update({"PK": f"STUDENT#{sid}", "SK": _sk(qid, f"#P#RESP#{qn}"), "type": "RESPONSE",
                 "regrades": [], "version": 1})
    yield item
    yield {"PK": f"RESPONSE#{r['response_id']}", "SK": "OWNER", "type": "RESPONSE_OWNER",
           "response_id": r["response_id"], "student_id": sid, "quiz_id": qid, "question_id": qn}


# ---------------------------------------------------------------- quiz.response_draft → DRAFT

DRAFT_SQL = """
SELECT d.quiz_id, d.question_id, p.student_id, d.student_id AS draft_student_id, d.raw_response, d.updated_at
  FROM quiz.response_draft d
  JOIN quiz.paper p ON p.quiz_id = d.quiz_id
 ORDER BY d.quiz_id, d.question_id
"""


def draft(r: dict):
    if r["draft_student_id"] != r["student_id"]:
        raise ValueError(f"draft {r['quiz_id']}/{r['question_id']}: student_id differs from paper owner")
    yield {"PK": f"STUDENT#{r['student_id']}", "SK": _sk(r["quiz_id"], f"#P#DRAFT#{r['question_id']}"),
           "type": "DRAFT", "quiz_id": r["quiz_id"], "question_id": r["question_id"],
           "student_id": r["student_id"], "raw_response": r["raw_response"], "updated_at": r["updated_at"],
           "ttl": ttl_after(r["updated_at"], 90)}


# ---------------------------------------------------------------- quiz.response_event → RESPONSE_EVENT

EVENT_SQL = """
SELECT e.event_id, e.quiz_id, e.question_id, e.student_id, q.ordinal, e.event_type, e.option_key,
       e.client_timestamp_ms, e.created_at
  FROM quiz.response_event e
  JOIN quiz.question q ON q.question_id = e.question_id
 ORDER BY e.quiz_id, e.created_at, e.event_id
"""


def response_event(r: dict):
    item = dict(r)
    item.update({"PK": f"STUDENT#{r['student_id']}",
                 "SK": _sk(r["quiz_id"], f"#T#EVT#{iso(r['created_at'])}#{r['event_id']}"),
                 "type": "RESPONSE_EVENT"})
    yield item


# ---------------------------------------------------------------- quiz.generation_event → GENERATION_EVENT

GEN_SQL = """
SELECT g.event_id, g.quiz_id, p.student_id, g.ordinal, g.phase, g.status, g.question_ordinal, g.detail,
       g.created_at
  FROM quiz.generation_event g
  JOIN quiz.paper p ON p.quiz_id = g.quiz_id
 ORDER BY g.quiz_id, g.ordinal
"""


def generation_event(r: dict):
    item = dict(r)
    item.update({"PK": f"STUDENT#{r['student_id']}", "SK": _sk(r["quiz_id"], f"#T#GEN#{r['ordinal']:06d}"),
                 "type": "GENERATION_EVENT", "ttl": ttl_after(r["created_at"], 180)})
    yield item


# ---------------------------------------------------------------- quiz.exam_diagnosis → DIAGNOSIS

DIAG_SQL = """
SELECT d.quiz_id, p.student_id, d.time_management_verdict, d.pacing_notes, d.reasoning_guidance,
       d.improvement_areas, d.generated_by, d.created_at
  FROM quiz.exam_diagnosis d
  JOIN quiz.paper p ON p.quiz_id = d.quiz_id
 ORDER BY d.quiz_id
"""


def diagnosis(r: dict):
    item = dict(r)
    item.update({"PK": f"STUDENT#{r['student_id']}", "SK": _sk(r["quiz_id"], "#X#DIAG#0001"),
                 "type": "DIAGNOSIS", "version": 1})
    yield item


# ---------------------------------------------------------------- quiz.question_pool → POOL_QUESTION + UNIQUE + POOL_CONCEPT

POOL_SQL = """
SELECT pool_question_id, content_hash, style, question_type, difficulty_band, topic_key, concept_slugs,
       technique_slugs, question, source_quiz_id, generated_by, times_served, last_served_at, created_at
  FROM quiz.question_pool
 ORDER BY pool_question_id
"""


def pool(r: dict):
    pid, status = r["pool_question_id"], "ACTIVE"
    band = _band(r["difficulty_band"], f"pool {pid}")
    bkey = band or "NONE"
    item = {k: r[k] for k in ("pool_question_id", "content_hash", "style", "question_type", "topic_key",
                              "source_quiz_id", "generated_by", "times_served", "last_served_at", "created_at")}
    item.update({
        "PK": f"POOL#{pid}", "SK": "POOL", "type": "POOL_QUESTION",
        "GSI1PK": f"POOLKEY#{r['style']}#{r['question_type']}#{bkey}",
        "GSI1SK": f"{status}#{int(r['times_served']):08d}#{pid}",
        "GSI2PK": f"POOL_STATUS#{status}", "GSI2SK": f"{iso(r['created_at'])}#{pid}",
        "difficulty_band": band, "concept_slugs": list(r["concept_slugs"] or []) or None,
        "technique_slugs": list(r["technique_slugs"] or []) or None,
        "question": r["question"],
        "status": status, "vector_state": "PENDING", "version": 1,
    })
    yield item
    yield {"PK": f"UNIQUE#content_hash#{r['content_hash']}", "SK": "UNIQUE", "type": "UNIQUE",
           "pool_question_id": pid}
    for slug in sorted(set(r["concept_slugs"] or [])):
        yield {"PK": f"POOLCONCEPT#{slug}", "SK": f"{r['style']}#{r['question_type']}#{bkey}#{pid}",
               "type": "POOL_CONCEPT", "pool_question_id": pid, "concept_slug": slug, "status": status}


# ---------------------------------------------------------------- derived: POOL_SERVED (question.pool_question_id ⋈ paper)

POOL_SERVED_SQL = """
WITH pairs AS (
    SELECT p.student_id, q.pool_question_id, p.quiz_id, p.created_at, FALSE AS write_back
      FROM quiz.question q JOIN quiz.paper p ON p.quiz_id = q.quiz_id
     WHERE q.pool_question_id IS NOT NULL
    UNION ALL
    SELECT p.student_id, qp.pool_question_id, p.quiz_id, p.created_at, TRUE AS write_back
      FROM quiz.question_pool qp JOIN quiz.paper p ON p.quiz_id = qp.source_quiz_id
)
SELECT student_id, pool_question_id,
       (array_agg(quiz_id ORDER BY created_at, quiz_id))[1] AS first_quiz_id,
       min(created_at)                                       AS first_served_at,
       bool_or(write_back)                                   AS write_back
  FROM pairs
 GROUP BY student_id, pool_question_id
 ORDER BY student_id, pool_question_id
"""


def pool_served(r: dict):
    yield {"PK": f"STUDENT#{r['student_id']}", "SK": f"POOLSERVED#{r['pool_question_id']}",
           "type": "POOL_SERVED", "student_id": r["student_id"], "pool_question_id": r["pool_question_id"],
           "first_quiz_id": r["first_quiz_id"], "first_served_at": r["first_served_at"],
           "origin": "WRITE_BACK" if r["write_back"] else "SERVED"}


MAPPINGS = [
    Mapping("quiz.paper", "exam", PAPER_SQL, paper, expected_source="quiz.paper",
            note="PAPER + PAPER_OWNER; counters, answer_disclosure, diagnosis_version computed in SQL"),
    Mapping("quiz.question", "exam", QUESTION_SQL, question, expected_source="quiz.question",
            note="QUESTION (+tags) + QUESTION_SECRET (answer key, solution, inspiration_sources)"),
    Mapping("quiz.solution", "exam", SOLUTION_SQL, _embedded, expected_source="quiz.solution",
            note="embedded in QUESTION_SECRET by quiz.question; count check only"),
    Mapping("quiz.question_source", "exam", SOURCE_SQL, _embedded, expected_source="quiz.question_source",
            note="embedded as QUESTION_SECRET.inspiration_sources[]; count check only"),
    Mapping("quiz.question_concept", "exam", _evidence_sql("question_concept", "concept_id"),
            _evidence("C", "concept_id"), expected_source="quiz.question_concept",
            note="tags embedded on QUESTION; QUIZ_EVIDENCE QEVID#C# for answered questions"),
    Mapping("quiz.question_technique", "exam", _evidence_sql("question_technique", "technique_id"),
            _evidence("T", "technique_id"), expected_source="quiz.question_technique",
            note="tags embedded on QUESTION; QUIZ_EVIDENCE QEVID#T# for answered questions"),
    Mapping("quiz.question_skill", "exam", SKILL_SQL, _embedded, expected_source="quiz.question_skill",
            note="embedded as QUESTION.skill_ids/slugs; no evidence items (design: C/T only)"),
    Mapping("quiz.response", "exam", RESPONSE_SQL, response, expected_source="quiz.response",
            note="RESPONSE + RESPONSE_OWNER"),
    Mapping("quiz.response_draft", "exam", DRAFT_SQL, draft, expected_source="quiz.response_draft",
            note="DRAFT, ttl updated_at + 90 d"),
    Mapping("quiz.response_event", "exam", EVENT_SQL, response_event, expected_source="quiz.response_event",
            note="RESPONSE_EVENT ordered by created_at"),
    Mapping("quiz.generation_event", "exam", GEN_SQL, generation_event, expected_source="quiz.generation_event",
            note="GENERATION_EVENT, ttl created_at + 180 d"),
    Mapping("quiz.exam_diagnosis", "exam", DIAG_SQL, diagnosis, expected_source="quiz.exam_diagnosis",
            note="DIAGNOSIS version 0001"),
    Mapping("quiz.question_pool", "exam", POOL_SQL, pool, expected_source="quiz.question_pool",
            note="POOL_QUESTION + UNIQUE#content_hash sentinel + POOL_CONCEPT; vectors via indexer stream"),
    Mapping("quiz.pool_served", "exam", POOL_SERVED_SQL, pool_served,
            note="derived POOL_SERVED history per learner from question.pool_question_id and pool.source_quiz_id"),
]
