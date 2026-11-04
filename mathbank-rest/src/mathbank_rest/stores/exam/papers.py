"""Exam store, papers area (requirement 71 WP6; requirement 70 C2 access patterns A1-A11 and A18, write paths of section 4).

Quizzes and mock exams of one learner: the paper, its questions and answer keys, drafts, responses, interaction and generation events,
the post-exam diagnosis and the per-tag quiz evidence that mastery is blended from.

``PapersPostgres`` delegates to ``quiz_runtime`` at call time (behaviour unchanged, monkeypatching tests keep working). ``PapersDynamoDB``
is the ``mb-exam`` implementation on ``ExamUnitOfWork`` and the typed models of ``models/manual/exam_papers.py``. A method is a read
exactly when its name starts with a ``stores.READ_PREFIXES`` entry.

Rules of the DynamoDB side (the design's sections 4 and 6):

* one transaction per operation; the paper's ``version`` and status are transaction conditions: a lost version race is retried up to
  3 times WITHOUT grading again, a status mismatch is 409 ``EXAM_NOT_EDITABLE``, a duplicate respond is 409 ``ALREADY_ANSWERED`` and
  writes no second evidence item;
* the learner's partition is the only thing a request can reach (``STUDENT#<sid>`` from the verified identity): a foreign paper id is
  404; no scans, no PostgreSQL;
* answer keys live in ``QUESTION_SECRET`` items, outside the key range every learner-reachable read uses (``...#P#`` stops before
  ``...#S#``), and the learner views are built from an allow-list (``quiz_logic.learner_question``);
* content references (concept / technique / skill slugs, problem codes and their source enrichment) are read BEFORE the transaction;
  a cross-table ``ConditionCheck`` on the learner's profile guards paper creation;
* the pool is a separate area of the composed store: finalize calls ``link_or_insert_pool_question`` per new question before its
  transaction and adds ``build_pool_serve_ops`` to it (both through ``getattr``: skipped while the pool area does not provide them).

Known differences from PostgreSQL (all in the WP6 report): the paper's status machine is enforced by conditions (respond/progress need
READY/IN_PROGRESS, GENERATING is not submittable, submit goes straight to GRADED, ``get_review`` is a pure read, the last practice answer
grades the paper); an exam-mode respond returns only ``{saved, question_id, answered_count}``; ``difficulty_band`` must be in the
vocabulary; diagnoses are versioned (``get_diagnosis`` returns the latest); inspiration sources are de-duplicated with rank = position.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel

from mathbank_rest import mastery, stores
from mathbank_rest import quiz_logic as ql
from mathbank_rest.config import settings
from mathbank_rest.models.ddb.content import ContentProblem
from mathbank_rest.models.ddb.exam import ExamPaperOwner, ExamResponseOwner
from mathbank_rest.models.manual import exam_papers as ep
from mathbank_rest.quiz_logic import QuizError
from mathbank_rest.stores import ddb, typed
from mathbank_rest.stores.errors import ValidationFailed
from mathbank_rest.stores.exam.uow import CTX, ExamUnitOfWork, with_retries

LOG = logging.getLogger(__name__)

PAGE = 200
RACE_ATTEMPTS = 3
LEARNER_CTX = "learner"
_HI = "\uffff"
HEADER_FIELDS = ("quiz_id", "student_id", "style", "title", "instructions", "requested_question_count", "requested_question_types",
                 "target_skill_slugs", "target_concept_slugs", "difficulty_band", "generated_by", "object_key", "object_sha256", "status",
                 "error_message", "created_at", "started_at", "submitted_at", "graded_at", "exam_mode", "time_limit_seconds",
                 "agent_framework", "resume_question_ordinal")


def _qr():
    from mathbank_rest import quiz_runtime

    return quiz_runtime


# ------------------------------------------------------------------------------------------------ postgres

class PapersPostgres:
    """Postgres backend: calls today's functions at call time (monkeypatched tests keep working)."""

    def start_paper(self, student_id: UUID, **kwargs: Any) -> UUID:
        return _qr().start_paper(student_id, **kwargs)

    def import_paper(self, student_id: UUID, **kwargs: Any) -> dict:
        return _qr().import_paper(student_id, **kwargs)

    def generate_quiz(self, student_id: UUID, **kwargs: Any) -> dict:
        return _qr().generate_quiz(student_id, **kwargs)

    def finalize_paper(self, quiz_id: UUID, student_id: UUID, **kwargs: Any) -> dict:
        return _qr().finalize_paper(quiz_id, student_id, **kwargs)

    def fail_paper(self, quiz_id: UUID, student_id: UUID, error_message: str) -> dict:
        return _qr().fail_paper(quiz_id, student_id, error_message)

    def get_quiz(self, quiz_id: UUID, student_id: UUID) -> dict:
        return _qr().get_quiz(quiz_id, student_id)

    def list_my_quizzes(self, student_id: UUID, *, limit: int = 20) -> list[dict]:
        return _qr().list_my_quizzes(student_id, limit=limit)

    def get_paper_header(self, quiz_id: UUID, student_id: UUID) -> dict:
        qr = _qr()
        with qr.engine.connect() as conn:
            return qr._require_owned_paper(conn, quiz_id, student_id)

    def save_exam_progress(self, quiz_id: UUID, student_id: UUID, **kwargs: Any) -> dict:
        return _qr().save_exam_progress(quiz_id, student_id, **kwargs)

    def submit_response(self, quiz_id: UUID, question_id: UUID, student_id: UUID, **kwargs: Any) -> dict:
        return _qr().submit_response(quiz_id, question_id, student_id, **kwargs)

    def log_response_event(self, quiz_id: UUID, question_id: UUID, student_id: UUID, **kwargs: Any) -> dict:
        return _qr().log_response_event(quiz_id, question_id, student_id, **kwargs)

    def get_response_events(self, quiz_id: UUID, student_id: UUID) -> list[dict]:
        return _qr().get_response_events(quiz_id, student_id)

    def post_generation_event(self, quiz_id: UUID, **kwargs: Any) -> None:
        return _qr().post_generation_event(quiz_id, **kwargs)

    def list_generation_events(self, quiz_id: UUID, student_id: UUID, *, since_ordinal: int = 0) -> list[dict]:
        return _qr().list_generation_events(quiz_id, student_id, since_ordinal=since_ordinal)

    def submit_exam(self, quiz_id: UUID, student_id: UUID) -> dict:
        return _qr().submit_exam(quiz_id, student_id)

    def get_review(self, quiz_id: UUID, student_id: UUID) -> dict:
        return _qr().get_review(quiz_id, student_id)

    def write_diagnosis(self, quiz_id: UUID, student_id: UUID, **kwargs: Any) -> dict:
        return _qr().write_diagnosis(quiz_id, student_id, **kwargs)

    def get_diagnosis(self, quiz_id: UUID, student_id: UUID) -> dict:
        return _qr().get_diagnosis(quiz_id, student_id)

    def get_paper_for_diagnosis(self, quiz_id: UUID, student_id: UUID) -> dict:
        return _qr().get_paper_for_diagnosis(quiz_id, student_id)

    def get_quiz_evidence(self, student_id: UUID, kind: str, tag_id: UUID) -> list[dict]:
        return _qr().get_quiz_evidence_rows(student_id, kind, tag_id)

    def get_difficulty_distribution(self, *, concept_slug: str | None = None, technique_slug: str | None = None) -> dict:
        return _qr().get_difficulty_distribution(concept_slug=concept_slug, technique_slug=technique_slug)


# ------------------------------------------------------------------------------------------------ helpers

class _PaperMoved(Exception):
    """The paper's version or status changed between the read and the commit (server-derived: re-read and retry)."""


class _DuplicateOrdinal(Exception):
    """A generation event with this ordinal exists already (a retried POST: a no-op)."""


def _plain(value: Any) -> Any:
    """A model attribute as the JSON the PostgreSQL columns returned (nested models to dicts, lists and dicts recursively)."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", by_alias=True, exclude_unset=True)
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    return value


def _val(item: Any, attr: str) -> Any:
    """An attribute that may live in S3 (``<attr>_ref``), resolved and as plain JSON."""
    return _plain(item.resolve(attr))


def _status_in(*statuses: str) -> ddb.Cond:
    ph = {f":gs{i}": s for i, s in enumerate(statuses)}
    return ddb.Cond(f"#gst IN ({', '.join(ph)})", {"#gst": "status"}, ph)


def _time(iso: str | dt.datetime | None) -> dt.datetime | None:
    if iso is None or isinstance(iso, dt.datetime):
        return iso
    return dt.datetime.fromisoformat(iso)


def _missing(what: str = "no quiz with that id for this student") -> QuizError:
    return QuizError("NOT_FOUND", what, status_code=404)


def _paper_range(quiz_id: Any, upto: str) -> tuple[str, str]:
    base = ep.paper_sk(quiz_id)
    return f"{base}#P#", f"{base}#{upto}#{_HI}"


# content references: read before the transaction, from the content read model ------------------------------------------------

def _content_index(kind: str) -> dict:
    from mathbank_rest.models.docs.content import CatalogConcept, CatalogSkill, CatalogTechnique
    from mathbank_rest.stores.content.catalog import _catalogue

    model = {"concept": CatalogConcept, "technique": CatalogTechnique, "skill": CatalogSkill}[kind]
    return _catalogue(kind, model)[1]


def _resolve_slugs(kind: str, slugs: list[str]) -> dict[str, dict]:
    """``{slug: {id, slug, name, description}}`` for the slugs that exist; unknown slugs are dropped, as the SQL did. The content
    store's own ``resolve_slugs`` is used when it has one, else the catalogue snapshot (cached by object key)."""
    slugs = list(dict.fromkeys(s for s in slugs if s))
    if not slugs:
        return {}
    own = getattr(stores.get_store("content"), "resolve_slugs", None)
    if callable(own):
        return own(kind, slugs)
    index = _content_index(kind)["slug"]
    return {s: {"id": str(getattr(i, f"{kind}_id")), "slug": s, "name": i.name, "description": getattr(i, "description", "") or ""}
            for s in slugs if (i := index.get(s)) is not None}


def _problem_ids(codes: list[str]) -> dict[str, str]:
    """canonical_code -> problem_id from the PROBLEM items of the content read model (unknown codes are absent)."""
    codes = list(dict.fromkeys(c for c in codes if c))
    if not codes:
        return {}
    items = typed.batch_get(ContentProblem, [(f"PROBLEM#{c}", "META") for c in codes], consistent=False)
    return {i.canonical_code: str(i.problem_id) for i in items}


def _source_rows(codes: list[str]) -> dict[str, dict]:
    """canonical_code -> {competition, year, source_url} (review enrichment) through the content store."""
    codes = list(dict.fromkeys(c for c in codes if c))
    if not codes:
        return {}
    return {p["canonical_code"]: p for p in stores.get_store("content").get_problems_by_codes(codes)}


def _current_slugs(kind: str, ids: list[str], stored: list[str]) -> list[str]:
    """The slugs of the tags as they are named today (they can be renamed after a question was written); the stored slugs when the
    catalogue cannot answer."""
    if not ids:
        return sorted(set(stored))
    try:
        index = _content_index(kind)["id"]
        return sorted({index[i].slug for i in ids if i in index}) or sorted(set(stored))
    except Exception:  # noqa: BLE001 - a missing catalogue must not fail a read that has the stored slugs
        LOG.warning("catalogue %s unavailable; using the stored slugs", kind)
        return sorted(set(stored))


def _snapshot(quiz_id: Any, name: str, doc: Any) -> dict:
    """The JSON snapshot of a paper, solution or response under ``exam/papers/<quiz_id>/`` of the data bucket (the object_store
    behaviour of today): ``{object_key, sha256}``. Written BEFORE the transaction that references it."""
    body = json.dumps(doc, default=str, sort_keys=True).encode()
    key = f"exam/papers/{quiz_id}/{name}.json"
    ddb.client("s3").put_object(Bucket=ddb.data_bucket(), Key=key, Body=body, ContentType="application/json")
    return {"object_key": key, "sha256": hashlib.sha256(body).hexdigest()}


# ------------------------------------------------------------------------------------------------ dynamodb

class PapersDynamoDB:
    """DynamoDB backend over mb-exam."""

    # -- reads of one paper ---------------------------------------------------------------------------------------------

    def _pp_paper(self, quiz_id: Any, student_id: Any) -> ep.ExamPaperItem:
        """A1: the paper of this learner (strongly consistent); a foreign or unknown id is 404."""
        item = typed.get(ep.ExamPaperItem, ddb.student_pk(student_id), ep.paper_sk(quiz_id))
        if item is None:
            raise _missing()
        return item

    def _pp_collect(self, student_id: Any, models: list[type], *, sk_begins: str | None = None,
                    sk_between: tuple[str, str] | None = None, forward: bool = True, max_items: int | None = None) -> list[Any]:
        out: list[Any] = []
        token = None
        while True:
            page = typed.query(CTX, ddb.student_pk(student_id), models=models, sk_begins=sk_begins, sk_between=sk_between,
                               forward=forward, limit=PAGE if max_items is None else min(PAGE, max_items), next_token=token)
            out += page.items
            token = page.next_token
            if not token or (max_items is not None and len(out) >= max_items):
                return out[:max_items] if max_items is not None else out

    def _pp_open(self, paper: ep.ExamPaperItem, verb: str) -> None:
        if paper.status not in ql.OPEN_STATUSES:
            raise QuizError("EXAM_NOT_EDITABLE", f"paper is {paper.status} and cannot be {verb}", status_code=409)

    def get_paper_header(self, quiz_id: UUID, student_id: UUID) -> dict:
        """A1: the paper header with the owner check (the columns of ``quiz.paper``)."""
        paper = self._pp_paper(quiz_id, student_id)
        return {k: getattr(paper, k, None) for k in HEADER_FIELDS}

    # -- A2 -------------------------------------------------------------------------------------------------------------

    def _pp_learner_range(self, quiz_id: Any, student_id: Any) -> tuple[list, dict, dict]:
        """The learner range ``QUIZ#<qid>#P#`` .. ``#P#\\uffff``: questions, the learner's responses and drafts. It ends before ``#S#``,
        so an answer key is unreachable from here by construction (and the model list rejects any other type)."""
        lo, hi = _paper_range(quiz_id, "P")
        items = self._pp_collect(student_id, [ep.ExamQuestionItem, ep.ExamResponseItem, ep.ExamDraft], sk_between=(lo, hi))
        questions = sorted((i for i in items if isinstance(i, ep.ExamQuestionItem)), key=lambda q: q.ordinal)
        responses = {str(i.question_id): i for i in items if isinstance(i, ep.ExamResponseItem)}
        drafts = {str(i.question_id): i for i in items if isinstance(i, ep.ExamDraft)}
        return questions, responses, drafts

    def get_quiz(self, quiz_id: UUID, student_id: UUID) -> dict:
        """The learner view: the allow-list of every question plus the learner's own response and draft. Never a key or a solution."""
        paper = self._pp_paper(quiz_id, student_id)
        questions, responses, drafts = self._pp_learner_range(quiz_id, student_id)
        rows = []
        for q in questions:
            qid = str(q.question_id)
            resp, draft = responses.get(qid), drafts.get(qid)
            rows.append(ql.learner_question(
                {"question_id": qid, "ordinal": q.ordinal, "question_type": q.question_type, "prompt_text": _val(q, "prompt_text"),
                 "prompt_latex": _val(q, "prompt_latex"), "options": _val(q, "options"), "points": q.points,
                 "diagram_object_key": q.diagram_object_key},
                student_response=_val(resp, "raw_response") if resp else None,
                draft_response=_val(draft, "raw_response") if draft else None, answered=resp is not None))
        return ql.quiz_view({
            "quiz_id": str(paper.quiz_id), "style": paper.style, "title": paper.title, "status": paper.status,
            "instructions": paper.instructions, "exam_mode": paper.exam_mode, "time_limit_seconds": paper.time_limit_seconds,
            "started_at": paper.started_at, "resume_question_ordinal": paper.resume_question_ordinal}, rows)

    # -- A3 -------------------------------------------------------------------------------------------------------------

    def list_my_quizzes(self, student_id: UUID, *, limit: int = 20) -> list[dict]:
        """Latest papers first with question and correct counts. Read from GSI1, whose projection already holds every field of the
        answer (and no answer key), so no second read; eventually consistent."""
        out: list[dict] = []
        token = None
        while len(out) < limit:
            page = ddb.query_page(CTX, f"STUDENT#{student_id}#PAPERS", index="GSI1", forward=False, limit=min(limit - len(out), PAGE),
                                  next_token=token)
            out += [{"quiz_id": i["quiz_id"], "style": i["style"], "title": i["title"], "status": i["status"],
                     "created_at": _time(i["created_at"]), "question_count": i.get("question_count", 0),
                     "correct_count": i.get("correct_count", 0)} for i in page["items"]]
            token = page["next_token"]
            if not token:
                break
        return out[:limit]

    # -- start / create -------------------------------------------------------------------------------------------------

    def _pp_create(self, student_id: Any, quiz_id: UUID, *, style: str, title: str, instructions: str, count: int, types: list[str],
                   skills: list[str], concepts: list[str], band: str | None, generated_by: str, agent_framework: str, exam_mode: bool,
                   time_limit: int | None) -> None:
        """PAPER + PAPER_OWNER in one transaction, with a ConditionCheck on the learner's profile in ``mb-learner`` (replaces the FK)."""
        now = ddb.now_iso()
        uow = ExamUnitOfWork(student_id)
        uow.put_new(ep.ExamPaperItem(
            PK=uow.pk, SK=ep.paper_sk(quiz_id), student_id=UUID(str(student_id)), quiz_id=quiz_id, style=style, title=title,
            instructions=instructions, requested_question_count=count, requested_question_types=types, target_skill_slugs=skills,
            target_concept_slugs=concepts, difficulty_band=band, generated_by=generated_by, agent_framework=agent_framework,
            exam_mode=exam_mode, answer_disclosure="AFTER_SUBMIT" if exam_mode else "IMMEDIATE", time_limit_seconds=time_limit,
            status="GENERATING", question_count=0, answered_count=0, correct_count=0, diagnosis_version=0, created_at=now, version=1,
            **ep.paper_keys(student_id, quiz_id, now, "GENERATING")))
        uow.put_new(ExamPaperOwner(PK=ep.owner_pk(quiz_id), SK="OWNER", quiz_id=quiz_id, student_id=UUID(str(student_id)), created_at=now))
        uow.add(ddb.Check(LEARNER_CTX, uow.pk, "PROFILE",
                          ddb.Cond("attribute_exists(PK) AND #pst = :active", {"#pst": "status"}, {":active": "ACTIVE"}),
                          conflict=_missing("no active student account"), label="profile"))
        uow.commit()

    def start_paper(self, student_id: UUID, *, style: str, title: str, instructions: str = "", requested_question_count: int,
                    requested_question_types: list[str], target_skill_slugs: list[str] | None = None,
                    target_concept_slugs: list[str] | None = None, difficulty_band: str | None = None, generated_by: str,
                    exam_mode: bool = True, time_limit_seconds: int | None = None) -> UUID:
        """The GENERATING shell of an exam paper, with the CHECKs of ``quiz.paper`` as store rules (style, count, types, band, limit)."""
        band = ql.validate_paper_request(style=style, requested_question_count=requested_question_count,
                                         requested_question_types=requested_question_types, difficulty_band=difficulty_band,
                                         time_limit_seconds=time_limit_seconds)
        quiz_id = uuid4()
        self._pp_create(student_id, quiz_id, style=style, title=title, instructions=instructions, count=requested_question_count,
                        types=requested_question_types, skills=target_skill_slugs or [], concepts=target_concept_slugs or [], band=band,
                        generated_by=generated_by, agent_framework="STRANDS_BEDROCK", exam_mode=exam_mode, time_limit=time_limit_seconds)
        return quiz_id

    def import_paper(self, student_id: UUID, *, style: str, title: str, instructions: str = "", requested_question_count: int,
                     requested_question_types: list[str], target_skill_slugs: list[str] | None = None,
                     target_concept_slugs: list[str] | None = None, difficulty_band: str | None = None, generated_by: str,
                     exam_mode: bool = True, time_limit_seconds: int | None = None, questions: list[dict]) -> dict:
        """start_paper + finalize_paper in one call; everything is validated before the first write (no stray GENERATING shell)."""
        ql.validate_paper_request(style=style, requested_question_count=requested_question_count,
                                  requested_question_types=requested_question_types, difficulty_band=difficulty_band,
                                  time_limit_seconds=time_limit_seconds)
        if not questions:
            raise QuizError("NO_QUESTIONS", "at least one question is required")
        quiz_id = self.start_paper(
            student_id, style=style, title=title, instructions=instructions, requested_question_count=requested_question_count,
            requested_question_types=requested_question_types, target_skill_slugs=target_skill_slugs,
            target_concept_slugs=target_concept_slugs, difficulty_band=difficulty_band, generated_by=generated_by,
            exam_mode=exam_mode, time_limit_seconds=time_limit_seconds)
        return self.finalize_paper(quiz_id, student_id, questions=questions)

    # -- paper state transitions ---------------------------------------------------------------------------------------

    def _pp_paper_op(self, student_id: Any, quiz_id: Any, *, status: str | None = None, set_: dict | None = None,
                     set_once: dict | None = None, increment: dict[str, int] | None = None, expected: dict | None = None,
                     cond: ddb.Cond | None = None, conflict: Exception | None = None, label: str = "") -> ddb.TxOp:
        """``UPDATE`` of the PAPER: ``SET <set_>, <set_once if absent>, <counters + n>, version + 1, updated_at``, the status change
        keeping GSI2 in step, guarded by the item existing, ``expected`` equalities (the version read) and ``cond``."""
        changes = dict(set_ or {})
        if status is not None:
            changes["status"], changes["GSI2PK"] = status, f"PAPER_STATUS#{status}"
        names: dict[str, str] = {"#upd": "updated_at", "#ver": "version"}
        values: dict[str, Any] = {":now": ddb.now_iso(), ":one": 1, ":zero": 0}
        sets: list[str] = []
        for i, (attr, val) in enumerate(typed.validate_changes(ep.ExamPaperItem, changes).items()):
            names[f"#c{i}"], values[f":c{i}"] = attr, val
            sets.append(f"#c{i} = :c{i}")
        for i, (attr, val) in enumerate(typed.validate_changes(ep.ExamPaperItem, set_once or {}).items()):
            names[f"#o{i}"], values[f":o{i}"] = attr, val
            sets.append(f"#o{i} = if_not_exists(#o{i}, :o{i})")
        for i, (attr, by) in enumerate((increment or {}).items()):
            names[f"#i{i}"], values[f":i{i}"] = attr, int(by)
            sets.append(f"#i{i} = if_not_exists(#i{i}, :zero) + :i{i}")
        sets += ["#ver = if_not_exists(#ver, :zero) + :one", "#upd = :now"]
        guards = ["attribute_exists(PK)"]
        for i, (attr, val) in enumerate((expected or {}).items()):
            names[f"#e{i}"], values[f":e{i}"] = attr, val
            guards.append(f"#e{i} = :e{i}")
        if cond:
            guards.append(f"({cond.expr})")
            names.update(cond.names)
            values.update(cond.values)
        return ddb.Update(CTX, ddb.student_pk(student_id), ep.paper_sk(quiz_id), "SET " + ", ".join(sets), names=names, values=values,
                          cond=ddb.Cond(" AND ".join(guards)), conflict=conflict, label=label or "PAPER")

    def _pp_fail(self, student_id: Any, quiz_id: Any, message: str) -> None:
        """GENERATING -> FAILED; a paper that is not GENERATING any more is left as it is (parity of ``fail_paper``)."""
        uow = ExamUnitOfWork(student_id)
        uow.add(self._pp_paper_op(student_id, quiz_id, status="FAILED", set_={"error_message": message[:500]},
                                  cond=_status_in("GENERATING"), conflict=_PaperMoved(), label="PAPER fail"))
        try:
            uow.commit()
        except _PaperMoved:
            pass

    def fail_paper(self, quiz_id: UUID, student_id: UUID, error_message: str) -> dict:
        """Acts only from GENERATING (a failed condition returns the paper unchanged); returns the learner view."""
        paper = typed.get(ep.ExamPaperItem, ddb.student_pk(student_id), ep.paper_sk(quiz_id))
        if paper is None:
            raise _missing("paper not found")
        if paper.status == "GENERATING":
            self._pp_fail(student_id, quiz_id, error_message)
        return self.get_quiz(quiz_id, student_id)

    # -- finalize -------------------------------------------------------------------------------------------------------

    @staticmethod
    def _pp_tag_fields(q: dict, refs: dict[str, dict[str, dict]]) -> dict:
        """``<kind>_ids`` / ``<kind>_slugs`` of a question from the resolved content references (unknown slugs are dropped)."""
        out: dict[str, list] = {}
        for kind in ("concept", "technique", "skill"):
            found = [(s, refs[kind][s]) for s in sorted(set(q.get(f"{kind}_slugs") or [])) if s in refs[kind]]
            if found:
                out[f"{kind}_ids"] = [UUID(r["id"]) for _, r in found]
                out[f"{kind}_slugs"] = [s for s, _ in found]
        return out

    @staticmethod
    def _pp_sources(sources: list[dict], problem_ids: dict[str, str]) -> list[dict]:
        """The ranked inspiration sources of a question: at most 5 given, unresolved codes skipped, problem ids de-duplicated, rank =
        position (so ranks are unique by construction and rank 1 is ``inspired_by_problem_id``)."""
        out: list[dict] = []
        for source in (sources or [])[:5]:
            pid = problem_ids.get(source["canonical_code"])
            if pid and all(s["problem_id"] != pid for s in out):
                out.append({"rank": len(out) + 1, "problem_id": pid, "canonical_code": source["canonical_code"],
                            "note": source.get("note", "")})
        return out

    def _pp_question_items(self, uow: ExamUnitOfWork, quiz_id: UUID, ordinal: int, q: dict, *, refs: dict, problem_ids: dict,
                           pool_question_id: str | None, now: str) -> None:
        question_id = uuid4()
        sources = self._pp_sources(q.get("inspiration_sources") or [], problem_ids)
        steps = q.get("solution_steps") or []
        diagram = q.get("diagram") or {}
        uow.put_new(ep.ExamQuestionItem(
            PK=uow.pk, SK=ep.question_sk(quiz_id, question_id), question_id=question_id, quiz_id=quiz_id,
            student_id=UUID(uow.student_id), ordinal=ordinal, question_type=q["question_type"], prompt_text=q["prompt_text"],
            prompt_latex=q.get("prompt_latex"), options=q.get("options") or None, points=1,
            inspired_by_problem_id=UUID(sources[0]["problem_id"]) if sources else None,
            diagram_object_key=diagram.get("object_key"), diagram_sha256=diagram.get("sha256"),
            pool_question_id=UUID(str(pool_question_id)) if pool_question_id else None,
            difficulty_band=ql.normalize_band(q.get("difficulty_band")), complexity_signals=ql.complexity_signals(q), created_at=now,
            **self._pp_tag_fields(q, refs)))
        uow.put_new(ep.ExamQuestionSecretItem(
            PK=uow.pk, SK=ep.secret_sk(quiz_id, question_id), question_id=question_id, quiz_id=quiz_id, student_id=UUID(uow.student_id),
            correct_answer=q["correct_answer"], option_explanations=q.get("option_explanations") or {},
            revision_log=q.get("revision_log") or [], inspiration_sources=sources, solution_text=q["solution_text"],
            key_insight=q.get("key_insight", ""), solution_steps=steps, step_count=len(steps), solution_created_at=now))

    def _pp_pool_links(self, student_id: Any, quiz_id: UUID, paper: ep.ExamPaperItem, questions: list[dict], *,
                       generated_by: str | None, pool_topic: str | None, pool_concept_slugs: list[str]) -> list[str | None]:
        """Per question the pool id it links to, or None: the entry it was served from (checked to exist) or the entry written back for
        it, resolved by the pool area (``link_or_insert_pool_questions``, one call for the whole finalize, else
        ``link_or_insert_pool_question`` per question) in its own transactions BEFORE the paper's. Best effort: the pool is a cache, so a
        failure there links nothing and never fails the paper."""
        docs = [{**q, "style": paper.style, "paper_difficulty_band": paper.difficulty_band, "generated_by": generated_by or paper.generated_by,
                 "pool_topic": pool_topic, "pool_concept_slugs": list(pool_concept_slugs or [])} for q in questions]
        batch = getattr(self, "link_or_insert_pool_questions", None)
        single = getattr(self, "link_or_insert_pool_question", None)
        try:
            if callable(batch):
                ids = list(batch(student_id, quiz_id, docs))
            elif callable(single):
                ids = [single(student_id, quiz_id, d) if d.get("pool_question_id") or d.get("add_to_pool") else None for d in docs]
            else:
                ids = [d.get("pool_question_id") for d in docs]
        except Exception:
            LOG.exception("pool linking failed for quiz %s", quiz_id)
            ids = [None] * len(docs)
        return [str(i) if i else None for i in ids]

    def finalize_paper(self, quiz_id: UUID, student_id: UUID, *, questions: list[dict], generated_by: str | None = None,
                       pool_topic: str | None = None, pool_concept_slugs: list[str] | None = None) -> dict:
        """GENERATING -> READY with every question in ONE transaction: PAPER + (QUESTION + QUESTION_SECRET) per question + the pool's
        serve ops, at most 1 + 40 + 40 items for 20 questions. Ordinals 1..n come from construction, guarded by the status
        condition, so a second finalize fails 404. Any other failure marks the paper FAILED (never stuck GENERATING)."""
        if not questions:
            raise QuizError("NO_QUESTIONS", "at least one question is required")
        if len(questions) > ql.MAX_QUESTIONS:
            raise QuizError("INVALID_QUESTION_COUNT", f"at most {ql.MAX_QUESTIONS} questions fit one paper")
        for q in questions:
            if q["question_type"] not in ql.QUESTION_TYPES:
                raise QuizError("INVALID_QUESTION_TYPE", f"question_type must be one of {ql.QUESTION_TYPES}")
        paper = typed.get(ep.ExamPaperItem, ddb.student_pk(student_id), ep.paper_sk(quiz_id))
        if paper is None or paper.status != "GENERATING":
            raise _missing("no GENERATING quiz with that id for this student — call start_paper first")
        try:
            refs = {kind: _resolve_slugs(kind, sorted({s for q in questions for s in q.get(f"{kind}_slugs") or []}))
                    for kind in ("concept", "technique", "skill")}
            problem_ids = _problem_ids([s["canonical_code"] for q in questions for s in (q.get("inspiration_sources") or [])[:5]])
            pool_ids = self._pp_pool_links(student_id, quiz_id, paper, questions, generated_by=generated_by, pool_topic=pool_topic,
                                           pool_concept_slugs=pool_concept_slugs or [])
            now = ddb.now_iso()
            uow = ExamUnitOfWork(student_id)
            uow.add(self._pp_paper_op(
                student_id, quiz_id, status="READY",
                set_={"question_count": len(questions), **({"generated_by": generated_by} if generated_by else {})},
                cond=_status_in("GENERATING"),
                conflict=_missing("no GENERATING quiz with that id for this student — call start_paper first"), label="PAPER finalize"))
            for ordinal, q in enumerate(questions, start=1):
                self._pp_question_items(uow, quiz_id, ordinal, q, refs=refs, problem_ids=problem_ids, pool_question_id=pool_ids[ordinal - 1],
                                        now=now)
            serve = getattr(self, "build_pool_serve_ops", None)
            linked = list(dict.fromkeys(p for p in pool_ids if p))
            if linked and callable(serve):
                for op in serve(student_id, linked, quiz_id=quiz_id):
                    if uow.fits(1):
                        uow.add(op)
                    else:
                        LOG.warning("pool serve op dropped: transaction budget exhausted for quiz %s", quiz_id)
            uow.commit()
        except QuizError:
            raise
        except Exception as exc:
            LOG.exception("paper finalization failed for quiz %s", quiz_id)
            self._pp_fail(student_id, quiz_id, str(exc))
            raise QuizError("GENERATION_FAILED", "paper finalization failed", status_code=502) from exc
        return self.get_quiz(quiz_id, student_id)

    # -- practice generation --------------------------------------------------------------------------------------------

    def generate_quiz(self, student_id: UUID, *, style: str, question_count: int, question_types: list[str],
                      target_skill_slugs: list[str] | None = None, target_concept_slugs: list[str] | None = None,
                      difficulty_band: str | None = None) -> dict:
        """The practice flow: validate, resolve targets (explicit slugs, else the weakest areas), a GENERATING paper, the LLM loop,
        then ``_pp_persist_practice`` (or FAILED with 502)."""
        ql.validate_practice_request(style, question_count, question_types)
        band = ql.normalize_band(difficulty_band)
        concept_rows = _resolve_slugs("concept", target_concept_slugs or [])
        skill_rows = _resolve_slugs("skill", target_skill_slugs or [])
        targets: list[dict] = ([{"kind": "concept", "slug": s, **concept_rows[s]} for s in concept_rows]
                               + [{"kind": "skill", "slug": s, **skill_rows[s]} for s in skill_rows])
        if not targets:
            targets = ql._targets_from_state(student_id, max_targets=max(1, question_count))
            for t in targets:           # the weakest-area targets carry no id yet: QUZ-F02/F03 want their tags written
                row = _resolve_slugs(t["kind"], [t["slug"]]).get(t["slug"]) if t["kind"] in ("concept", "technique", "skill") else None
                if row:
                    t["id"] = row["id"]
        if not targets:
            targets = [{"kind": "topic", "slug": "general", "name": "general competition mathematics"}]
        quiz_id = uuid4()
        self._pp_create(student_id, quiz_id, style=style, title=f"{style.replace('_', ' ').title()} Practice Set", instructions="",
                        count=question_count, types=question_types, skills=target_skill_slugs or [],
                        concepts=target_concept_slugs or [], band=band, generated_by=ql.MODEL_NAME, agent_framework="OPENAI_DIRECT",
                        exam_mode=False, time_limit=None)
        try:
            drafted = ql.draft_practice_questions(
                ql._client(), style=style, question_types=question_types, question_count=question_count, targets=targets,
                resolve_problem_id=lambda code: _problem_ids([code]).get(code) if code else None)
        except Exception as exc:
            LOG.exception("Quiz generation failed")
            self._pp_fail(student_id, quiz_id, str(exc))
            raise QuizError("GENERATION_FAILED", "quiz generation failed", status_code=502) from exc
        self._pp_persist_practice(student_id, quiz_id, drafted)
        return self.get_quiz(quiz_id, student_id)

    def _pp_persist_practice(self, student_id: Any, quiz_id: UUID, drafted: list[dict]) -> None:
        """QUESTION + QUESTION_SECRET per drafted question and PAPER -> READY, at most 1 + 2 * 20 items. The paper and solution snapshots
        go to S3 first."""
        paper_snapshot = _snapshot(quiz_id, "paper", {"quiz_id": str(quiz_id), "questions": drafted})
        now = ddb.now_iso()
        uow = ExamUnitOfWork(student_id)
        uow.add(self._pp_paper_op(student_id, quiz_id, status="READY",
                                  set_={"question_count": len(drafted), "object_key": paper_snapshot["object_key"],
                                        "object_sha256": paper_snapshot["sha256"]},
                                  cond=_status_in("GENERATING"), conflict=_missing(), label="PAPER persist"))
        for q in drafted:
            question_id = uuid4()
            g = q["generated"]
            options, correct = ql.practice_answer_key(q)
            target = q["target"]
            tag = ({f"{target['kind']}_ids": [UUID(target["id"])], f"{target['kind']}_slugs": [target["slug"]]}
                   if target["kind"] in ("concept", "technique", "skill") and target.get("id") else {})
            diagram = q["diagram"] or {}
            solution = _snapshot(quiz_id, f"solution-{question_id}", {"solution_text": g["solution_text"], "key_insight": g["key_insight"]})
            uow.put_new(ep.ExamQuestionItem(
                PK=uow.pk, SK=ep.question_sk(quiz_id, question_id), question_id=question_id, quiz_id=quiz_id,
                student_id=UUID(uow.student_id), ordinal=q["ordinal"], question_type=q["question_type"], prompt_text=g["prompt_text"],
                prompt_latex=g.get("prompt_latex"), options=options, points=1,
                inspired_by_problem_id=UUID(q["inspired_by_problem_id"]) if q["inspired_by_problem_id"] else None,
                diagram_object_key=diagram.get("object_key"), diagram_sha256=diagram.get("sha256"), created_at=now, **tag))
            uow.put_new(ep.ExamQuestionSecretItem(
                PK=uow.pk, SK=ep.secret_sk(quiz_id, question_id), question_id=question_id, quiz_id=quiz_id,
                student_id=UUID(uow.student_id), correct_answer=correct, solution_text=g["solution_text"], key_insight=g["key_insight"],
                solution_object_key=solution["object_key"], solution_object_sha256=solution["sha256"], solution_created_at=now))
        uow.commit()

    # -- progress -------------------------------------------------------------------------------------------------------

    def save_exam_progress(self, quiz_id: UUID, student_id: UUID, *, current_question_ordinal: int, question_id: UUID | None = None,
                           raw_response: dict | None = None) -> dict:
        """PAPER ``resume_question_ordinal`` / ``started_at`` (once) / IN_PROGRESS, guarded by READY|IN_PROGRESS, plus an optional
        DRAFT put (TTL 90 days) with a ConditionCheck that the question has no response yet (409 ALREADY_ANSWERED)."""
        paper = self._pp_paper(quiz_id, student_id)
        self._pp_open(paper, "changed")
        questions = self._pp_collect(student_id, [ep.ExamQuestionItem], sk_begins=f"{ep.paper_sk(quiz_id)}#P#Q#")
        question = next((q for q in questions if q.ordinal == current_question_ordinal), None)
        if question is None:
            raise _missing("no question with that ordinal in this paper")
        if question_id is not None and str(question.question_id) != str(question_id):
            raise QuizError("INVALID_DRAFT", "question_id does not match current_question_ordinal")
        uow = ExamUnitOfWork(student_id)
        if raw_response is not None:
            ql.validate_exam_draft({"question_type": question.question_type, "options": _val(question, "options")}, raw_response)
            uow.add(ddb.Check(CTX, uow.pk, ep.response_sk(quiz_id, question.question_id), ddb.NOT_EXISTS,
                              conflict=QuizError("ALREADY_ANSWERED", "this question already has a response", status_code=409),
                              label="no response yet"))
            uow.put(ep.ExamDraft(PK=uow.pk, SK=ep.draft_sk(quiz_id, question.question_id), quiz_id=quiz_id, question_id=question.question_id,
                                 student_id=UUID(uow.student_id), raw_response=raw_response, updated_at=ddb.now_iso(),
                                 ttl=ddb.epoch_after(ep.DRAFT_TTL_DAYS)))
        uow.add(self._pp_paper_op(
            student_id, quiz_id, status="IN_PROGRESS", set_={"resume_question_ordinal": current_question_ordinal},
            set_once={"started_at": ddb.now_iso()}, cond=_status_in(*ql.OPEN_STATUSES),
            conflict=QuizError("EXAM_NOT_EDITABLE", "paper changed state and cannot be changed", status_code=409), label="PAPER progress"))
        uow.commit()
        return {"saved": True, "current_question_ordinal": current_question_ordinal}

    # -- respond --------------------------------------------------------------------------------------------------------

    def submit_response(self, quiz_id: UUID, question_id: UUID, student_id: UUID, *, raw_response: dict,
                        time_spent_seconds: int | None = None) -> dict:
        """Read paper, question and key; grade ONCE (exact match or LLM); then one transaction: RESPONSE + RESPONSE_OWNER + a
        QUIZ_EVIDENCE per concept/technique + DRAFT deleted + PAPER counters/status guarded by its version and READY|IN_PROGRESS.
        A lost version race re-reads and retries (at most 3 attempts) without grading again."""
        paper = self._pp_paper(quiz_id, student_id)
        pk = ddb.student_pk(student_id)
        if paper.status not in ql.OPEN_STATUSES:
            if ddb.get_item(CTX, pk, ep.response_sk(quiz_id, question_id)) is not None:     # a retry of an answer the paper already holds
                raise QuizError("ALREADY_ANSWERED", "this question already has a response", status_code=409)
            self._pp_open(paper, "answered")
        by_type = {raw["type"]: raw for raw in ddb.batch_get(CTX, [(pk, ep.question_sk(quiz_id, question_id)),
                                                                   (pk, ep.secret_sk(quiz_id, question_id))])}
        if "QUESTION" not in by_type or "QUESTION_SECRET" not in by_type:
            raise _missing("no such question in this quiz")
        question = ep.ExamQuestionItem.from_item(by_type["QUESTION"])
        secret = ep.ExamQuestionSecretItem.from_item(by_type["QUESTION_SECRET"])
        if ddb.get_item(CTX, pk, ep.response_sk(quiz_id, question_id)) is not None:
            raise QuizError("ALREADY_ANSWERED", "this question already has a response", status_code=409)
        is_correct, method, confidence, feedback = ql.grade_answer(
            {"question_type": question.question_type, "prompt_text": _val(question, "prompt_text"),
             "correct_answer": _val(secret, "correct_answer")}, raw_response)
        response_id, submitted_at = uuid4(), ddb.now_iso()
        snapshot = _snapshot(quiz_id, f"response-{response_id}", {"raw_response": raw_response, "is_correct": is_correct, "feedback": feedback})
        band = question.difficulty_band or paper.difficulty_band
        tags = [("C", t) for t in question.concept_ids or []] + [("T", t) for t in question.technique_ids or []]

        def attempt() -> int:
            cur = self._pp_paper(quiz_id, student_id)
            self._pp_open(cur, "answered")
            answered = cur.answered_count + 1
            graded = answered >= cur.question_count and cur.answer_disclosure == "IMMEDIATE"
            uow = ExamUnitOfWork(student_id)
            uow.put_new(ep.ExamResponseItem(
                PK=pk, SK=ep.response_sk(quiz_id, question_id), response_id=response_id, question_id=question_id, quiz_id=quiz_id,
                student_id=UUID(uow.student_id), ordinal=question.ordinal, response_type=question.question_type, raw_response=raw_response,
                is_correct=is_correct, grading_method=method, grading_confidence=confidence, grading_feedback=feedback,
                time_spent_seconds=time_spent_seconds, submitted_at=submitted_at, object_key=snapshot["object_key"],
                object_sha256=snapshot["sha256"], regrades=[], version=1),
                conflict=QuizError("ALREADY_ANSWERED", "this question already has a response", status_code=409))
            uow.put_new(ExamResponseOwner(PK=ep.response_owner_pk(response_id), SK="OWNER", response_id=response_id, question_id=question_id,
                                          quiz_id=quiz_id, student_id=UUID(uow.student_id)))
            for kind, tag_id in tags:
                uow.put_new(ep.ExamQuizEvidenceItem(
                    PK=pk, SK=ep.evidence_sk(kind, tag_id, submitted_at, response_id), student_id=UUID(uow.student_id),
                    response_id=response_id, quiz_id=quiz_id, question_id=question_id, is_correct=is_correct, attempted_at=submitted_at,
                    difficulty_band=band, **({"concept_id": tag_id} if kind == "C" else {"technique_id": tag_id})))
            uow.delete(ep.ExamDraft, pk, ep.draft_sk(quiz_id, question_id))
            uow.add(self._pp_paper_op(
                student_id, quiz_id, status="GRADED" if graded else "IN_PROGRESS",
                set_={"graded_at": submitted_at} if graded else None,
                set_once={"started_at": submitted_at, **({"submitted_at": submitted_at} if graded else {})},
                increment={"answered_count": 1, "correct_count": 1 if is_correct else 0}, expected={"version": cur.version},
                cond=_status_in(*ql.OPEN_STATUSES), conflict=_PaperMoved(), label="PAPER respond"))
            uow.commit()
            return answered

        try:
            answered_count = with_retries(attempt, attempts=RACE_ATTEMPTS, on=(_PaperMoved,))
        except _PaperMoved:
            raise QuizError("CONFLICT", "the paper changed while answering; try again", status_code=409) from None
        self._pp_absorb(student_id, [t for k, t in tags if k == "C"], [t for k, t in tags if k == "T"])
        solution = {"solution_text": _val(secret, "solution_text"), "key_insight": _val(secret, "key_insight")}
        return ql.respond_view(
            {"is_correct": is_correct, "grading_method": method, "confidence": confidence, "feedback": feedback,
             "solution": solution if any(v is not None for v in solution.values()) else None},
            answer_disclosure=paper.answer_disclosure, question_id=question_id, answered_count=answered_count)

    @staticmethod
    def _pp_absorb(student_id: Any, concept_ids: list[UUID], technique_ids: list[UUID]) -> None:
        """Recompute the mastery of the answered question's tags (what ``_absorb_mastery_feedback`` always did), after the commit and
        never failing the response: the ``exam-mastery-fanout`` consumer is the safety net and the recompute is idempotent."""
        if not settings.quiz_mastery_inline or not (concept_ids or technique_ids):
            return
        try:
            for cid in concept_ids:
                mastery.recompute_concept_mastery(UUID(str(student_id)), cid)
            for tid in technique_ids:
                mastery.recompute_technique_mastery(UUID(str(student_id)), tid)
        except Exception:
            LOG.exception("inline mastery recompute failed for student %s", student_id)

    # -- events ---------------------------------------------------------------------------------------------------------

    def log_response_event(self, quiz_id: UUID, question_id: UUID, student_id: UUID, *, event_type: str, option_key: str | None = None,
                           client_timestamp_ms: int | None = None) -> dict:
        """Append one interaction event (never updated or deleted). A SKIP also deletes the question's draft, in the same transaction."""
        client_ts = ql.validate_event(event_type, option_key, client_timestamp_ms)
        self._pp_paper(quiz_id, student_id)
        pk = ddb.student_pk(student_id)
        question = typed.get(ep.ExamQuestionItem, pk, ep.question_sk(quiz_id, question_id))
        if question is None:
            raise _missing("no such question in this quiz")
        event_id, created = uuid4(), ddb.now_iso()
        uow = ExamUnitOfWork(student_id)
        uow.put_new(ep.ExamResponseEventItem(
            PK=pk, SK=ep.event_sk(quiz_id, created, event_id), event_id=event_id, quiz_id=quiz_id, question_id=question_id,
            student_id=UUID(uow.student_id), ordinal=question.ordinal, event_type=event_type, option_key=option_key,
            client_timestamp_ms=client_ts, created_at=created))
        if event_type == "SKIP":
            uow.delete(ep.ExamDraft, pk, ep.draft_sk(quiz_id, question_id))
        uow.commit()
        return {"event_id": str(event_id), "event_type": event_type, "option_key": option_key}

    def get_response_events(self, quiz_id: UUID, student_id: UUID) -> list[dict]:
        """A9: the interaction timeline, oldest first (the sort key is the server time then the event id)."""
        self._pp_paper(quiz_id, student_id)
        events = self._pp_collect(student_id, [ep.ExamResponseEventItem], sk_begins=f"{ep.paper_sk(quiz_id)}#T#EVT#")
        return [{"question_id": str(e.question_id), "ordinal": e.ordinal, "event_type": e.event_type, "option_key": e.option_key,
                 "client_timestamp_ms": e.client_timestamp_ms, "created_at": e.created_at} for e in events]

    def post_generation_event(self, quiz_id: UUID, *, ordinal: int, phase: str, status: str, question_ordinal: int | None = None,
                              detail: str = "") -> None:
        """Append one progress event. The caller has no student id: the owner comes from PAPER_OWNER (404 when the quiz is unknown).
        A duplicate ordinal is a no-op; an event after the paper left GENERATING/READY/FAILED is 409; a bad phase or status is 422."""
        ql.validate_generation_event(phase, status, ordinal)
        owner = typed.get(ExamPaperOwner, ep.owner_pk(quiz_id), "OWNER")
        if owner is None:
            raise _missing("no such quiz")
        uow = ExamUnitOfWork(owner.student_id)
        uow.put_new(ep.ExamGenerationEventItem(
            PK=uow.pk, SK=ep.generation_sk(quiz_id, ordinal), event_id=uuid4(), quiz_id=quiz_id, student_id=owner.student_id,
            ordinal=ordinal, phase=phase, status=status, question_ordinal=question_ordinal, detail=detail, created_at=ddb.now_iso(),
            ttl=ddb.epoch_after(ep.GENERATION_EVENT_TTL_DAYS)), conflict=_DuplicateOrdinal())
        uow.add(ddb.Check(CTX, uow.pk, ep.paper_sk(quiz_id), _status_in("GENERATING", "READY", "FAILED"),
                          conflict=QuizError("EXAM_NOT_EDITABLE", "paper no longer accepts generation events", status_code=409),
                          label="paper status"))
        try:
            uow.commit()
        except _DuplicateOrdinal:
            return

    def list_generation_events(self, quiz_id: UUID, student_id: UUID, *, since_ordinal: int = 0) -> list[dict]:
        """A8: events with ``ordinal > since_ordinal``, in order."""
        self._pp_paper(quiz_id, student_id)
        base = f"{ep.paper_sk(quiz_id)}#T#GEN#"
        lo = max(int(since_ordinal), 0) + 1
        if lo > 999_999:
            return []
        events = self._pp_collect(student_id, [ep.ExamGenerationEventItem], sk_between=(f"{base}{lo:06d}", f"{base}999999"))
        return [{"ordinal": e.ordinal, "phase": e.phase, "status": e.status, "question_ordinal": e.question_ordinal,
                 "detail": _val(e, "detail") or "", "created_at": e.created_at} for e in events]

    # -- submit, review, diagnosis --------------------------------------------------------------------------------------

    def submit_exam(self, quiz_id: UUID, student_id: UUID) -> dict:
        """READY|IN_PROGRESS -> GRADED in one transaction that also deletes the paper's drafts (GENERATING is not submittable)."""
        paper = self._pp_paper(quiz_id, student_id)
        if paper.status in ("SUBMITTED", "GRADED"):
            raise QuizError("ALREADY_SUBMITTED", f"paper is already {paper.status}", status_code=409)
        if paper.status == "GENERATING":
            raise QuizError("EXAM_NOT_EDITABLE", "paper is still GENERATING and cannot be submitted", status_code=409)
        self._pp_open(paper, "submitted")
        drafts = self._pp_collect(student_id, [ep.ExamDraft], sk_begins=f"{ep.paper_sk(quiz_id)}#P#DRAFT#")
        uow = ExamUnitOfWork(student_id)
        now = ddb.now_iso()
        uow.add(self._pp_paper_op(
            student_id, quiz_id, status="GRADED", set_={"graded_at": now}, set_once={"submitted_at": now},
            cond=_status_in(*ql.OPEN_STATUSES),
            conflict=QuizError("ALREADY_SUBMITTED", "paper is no longer open", status_code=409), label="PAPER submit"))
        for draft in drafts:
            uow.delete(ep.ExamDraft, draft.PK, draft.SK)
        uow.commit()
        return self.get_review(quiz_id, student_id)

    def _pp_rows(self, quiz_id: Any, student_id: Any) -> list[dict]:
        """A7: questions with their keys and the learner's responses (one query over ``#P#`` .. ``#S#``), by ordinal."""
        lo, hi = _paper_range(quiz_id, "S")
        items = self._pp_collect(student_id, [ep.ExamQuestionItem, ep.ExamResponseItem, ep.ExamDraft, ep.ExamQuestionSecretItem],
                                 sk_between=(lo, hi))
        responses = {str(i.question_id): i for i in items if isinstance(i, ep.ExamResponseItem)}
        secrets = {str(i.question_id): i for i in items if isinstance(i, ep.ExamQuestionSecretItem)}
        return [{"question": q, "response": responses.get(str(q.question_id)), "secret": secrets.get(str(q.question_id))}
                for q in sorted((i for i in items if isinstance(i, ep.ExamQuestionItem)), key=lambda x: x.ordinal)]

    def get_review(self, quiz_id: UUID, student_id: UUID) -> dict:
        """A7: the full review, a PURE READ (409 EXAM_IN_PROGRESS until the exam is submitted; practice papers are always open).
        Sources are enriched (competition, year, URL) through the content store."""
        paper = self._pp_paper(quiz_id, student_id)
        if not ql.review_open(answer_disclosure=paper.answer_disclosure, status=paper.status):
            raise QuizError("EXAM_IN_PROGRESS", "this exam paper must be submitted before it can be reviewed", status_code=409)
        rows = self._pp_rows(quiz_id, student_id)
        sources = {str(r["question"].question_id): _val(r["secret"], "inspiration_sources") or [] for r in rows if r["secret"]}
        enrich = _source_rows([s["canonical_code"] for lst in sources.values() for s in lst])
        by_question = {qid: [{"canonical_code": s["canonical_code"], "competition": (enrich.get(s["canonical_code"]) or {}).get("competition"),
                              "year": (enrich.get(s["canonical_code"]) or {}).get("year"),
                              "source_url": (enrich.get(s["canonical_code"]) or {}).get("source_url"), "note": s.get("note", "")}
                             for s in sorted(lst, key=lambda s: s["rank"])] for qid, lst in sources.items()}
        flat = []
        for r in rows:
            q, resp, secret = r["question"], r["response"], r["secret"]
            flat.append({
                "question_id": str(q.question_id), "ordinal": q.ordinal, "question_type": q.question_type,
                "prompt_text": _val(q, "prompt_text"), "points": q.points, "options": _val(q, "options"),
                "correct_answer": _val(secret, "correct_answer") if secret else None,
                "option_explanations": (_val(secret, "option_explanations") if secret else None) or {},
                "complexity_signals": _val(q, "complexity_signals"), "difficulty_band": q.difficulty_band,
                "solution_text": _val(secret, "solution_text") if secret else None,
                "key_insight": _val(secret, "key_insight") if secret else None,
                "solution_steps": _val(secret, "solution_steps") if secret else None,
                "raw_response": _val(resp, "raw_response") if resp else None, "is_correct": resp.is_correct if resp else None,
                "grading_feedback": _val(resp, "grading_feedback") if resp else None})
        return ql.review_view({"quiz_id": str(paper.quiz_id), "style": paper.style, "title": paper.title}, flat, by_question)

    def write_diagnosis(self, quiz_id: UUID, student_id: UUID, *, time_management_verdict: str, pacing_notes: list[dict],
                        reasoning_guidance: list[dict], improvement_areas: list[dict], generated_by: str) -> dict:
        """A new DIAGNOSIS version (history is kept) and the PAPER's ``diagnosis_version`` advance in one transaction, conditional on the
        version that was read; needs a GRADED paper (409 NOT_GRADED)."""
        def attempt() -> None:
            paper = self._pp_paper(quiz_id, student_id)
            if paper.status != "GRADED":
                raise QuizError("NOT_GRADED", "the paper must be fully graded before a diagnosis can be written", status_code=409)
            nxt = paper.diagnosis_version + 1
            uow = ExamUnitOfWork(student_id)
            uow.add(self._pp_paper_op(student_id, quiz_id, increment={"diagnosis_version": 1},
                                      expected={"diagnosis_version": paper.diagnosis_version}, cond=_status_in("GRADED"),
                                      conflict=_PaperMoved(), label="PAPER diagnosis"))
            uow.put_new(ep.ExamDiagnosisItem(
                PK=uow.pk, SK=ep.diagnosis_sk(quiz_id, nxt), quiz_id=quiz_id, student_id=UUID(uow.student_id),
                time_management_verdict=time_management_verdict, pacing_notes=pacing_notes, reasoning_guidance=reasoning_guidance,
                improvement_areas=improvement_areas, generated_by=generated_by, created_at=ddb.now_iso(), version=nxt))
            uow.commit()

        try:
            with_retries(attempt, attempts=RACE_ATTEMPTS, on=(_PaperMoved,))
        except _PaperMoved:
            raise QuizError("CONFLICT", "the diagnosis changed while writing; try again", status_code=409) from None
        return self.get_diagnosis(quiz_id, student_id)

    def get_diagnosis(self, quiz_id: UUID, student_id: UUID) -> dict:
        """A11: the latest diagnosis (404 when none yet)."""
        self._pp_paper(quiz_id, student_id)
        latest = self._pp_collect(student_id, [ep.ExamDiagnosisItem], sk_begins=f"{ep.paper_sk(quiz_id)}#X#DIAG#", forward=False,
                                  max_items=1)
        if not latest:
            raise _missing("no diagnosis yet for this paper")
        d = latest[0]
        return {"quiz_id": str(d.quiz_id), "time_management_verdict": d.time_management_verdict,
                "pacing_notes": _val(d, "pacing_notes") or [], "reasoning_guidance": _val(d, "reasoning_guidance") or [],
                "improvement_areas": _val(d, "improvement_areas") or [], "generated_by": d.generated_by, "created_at": d.created_at}

    def get_paper_for_diagnosis(self, quiz_id: UUID, student_id: UUID) -> dict:
        """A10: per-question correctness, timing, difficulty and tags, plus the learner's mastery of every tagged concept/technique
        (through the learner store); slugs are the tags' current names."""
        paper = self._pp_paper(quiz_id, student_id)
        out = []
        for r in self._pp_rows(quiz_id, student_id):
            q, resp, secret = r["question"], r["response"], r["secret"]
            out.append({
                "question_id": str(q.question_id), "ordinal": q.ordinal, "question_type": q.question_type,
                "prompt_text": _val(q, "prompt_text"), "difficulty_band": q.difficulty_band,
                "is_correct": resp.is_correct if resp else None, "time_spent_seconds": resp.time_spent_seconds if resp else None,
                "student_response": _val(resp, "raw_response") if resp else None,
                "solution_text": _val(secret, "solution_text") if secret else None,
                "key_insight": _val(secret, "key_insight") if secret else None,
                "concept_slugs": _current_slugs("concept", [str(i) for i in q.concept_ids or []], q.concept_slugs or []),
                "technique_slugs": _current_slugs("technique", [str(i) for i in q.technique_ids or []], q.technique_slugs or []),
                "skill_slugs": _current_slugs("skill", [str(i) for i in q.skill_ids or []], q.skill_slugs or [])})
        concepts = {s for q in out for s in q["concept_slugs"]}
        techniques = {s for q in out for s in q["technique_slugs"]}
        summary = (stores.get_store("learner").get_mastery_summary(student_id) if (concepts or techniques)
                   else {"concepts": [], "techniques": []})
        return {
            "quiz_id": str(paper.quiz_id), "style": paper.style, "time_limit_seconds": paper.time_limit_seconds,
            "started_at": paper.started_at, "submitted_at": paper.submitted_at, "questions": out,
            "concept_mastery_pre_exam": {r["slug"]: float(r["mastery_score"]) for r in summary["concepts"] if r["slug"] in concepts},
            "technique_mastery_pre_exam": {r["slug"]: float(r["mastery_score"]) for r in summary["techniques"] if r["slug"] in techniques}}

    # -- A18 ------------------------------------------------------------------------------------------------------------

    def get_quiz_evidence(self, student_id: UUID, kind: str, tag_id: UUID) -> list[dict]:
        """A18: the graded quiz responses to questions tagged with one concept (``kind`` C) or technique (T), oldest first, in the
        shape of a learner attempt row (``hint_count`` 0: quizzes have no hint ladder). Strongly consistent."""
        if kind not in ("C", "T"):
            raise ValidationFailed(f"kind must be C or T, not {kind!r}")
        items = self._pp_collect(student_id, [ep.ExamQuizEvidenceItem], sk_begins=f"QEVID#{kind}#{tag_id}#")
        return [{"is_correct": e.is_correct, "attempted_at": e.attempted_at, "hint_count": 0, "difficulty_band": e.difficulty_band}
                for e in items]

    # -- the generator's difficulty signal -------------------------------------------------------------------------------

    def get_difficulty_distribution(self, *, concept_slug: str | None = None, technique_slug: str | None = None) -> dict:
        """Corpus problems per ``difficulty_band`` for a concept or technique (non-rejected tags only), from the content read model:
        the tag's PTAG partition (GSI1) names the problems, their PROBLEM items hold the band."""
        from mathbank_rest.models.ddb.content import ContentPtag

        kind, slug = ("concept", concept_slug) if concept_slug else ("technique", technique_slug)
        entry = _resolve_slugs(kind, [slug] if slug else []).get(slug)
        if entry is None:
            return {"distribution": {}}
        codes: set[str] = set()
        token = None
        while True:
            page = typed.query(ContentPtag, f"{kind.upper()}#{entry['id']}", index="GSI1", limit=PAGE, next_token=token, consistent=False)
            codes |= {t.problem_code for t in page.items if t.review_status != "REJECTED"}
            token = page.next_token
            if not token:
                break
        counts: dict[str, int] = {}
        for problem in typed.batch_get(ContentProblem, [(f"PROBLEM#{c}", "META") for c in sorted(codes)], consistent=False):
            if problem.difficulty_band:
                counts[problem.difficulty_band] = counts.get(problem.difficulty_band, 0) + 1
        return {"distribution": counts}
