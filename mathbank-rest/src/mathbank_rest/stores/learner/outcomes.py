"""Learner store, outcomes area (requirement 71 WP5; requirement 70 C1 access patterns A6-A9, A41, A42, write path T7).

Outcomes (``OUTCOME``), the per-tag evidence they fan out to (``MEVID``), the running scores (``MASTERY``), the practice cursor
(``PROBLEM``), daily activity (``DAILY``) and the cohort aggregate (``COHORT``).

``OutcomesPostgres`` delegates to ``db/learner.py`` at call time (behaviour unchanged). ``OutcomesDynamoDB`` writes an outcome and
everything derived from it in ONE transaction (T7):

    OUTCOME (append-only)  +  PROBLEM counters  +  for each tag of the problem: MEVID (graded work only) and the recomputed MASTERY

The score is computed in process with the unchanged ``mastery.compute_mastery_score`` from the strongly consistent evidence of the tag
(A7) plus the new row; the MASTERY write is conditional on the version that was read, so two concurrent completions on one concept
retry and converge (``with_retries``). When the items do not fit in 100, the OUTCOME is flagged ``mastery_pending`` and MASTERY/MEVID
follow in transactions of their own (the ``mastery-repair`` consumer of requirement 70 section 5 guarantees convergence).

Composition for other areas (T12 step completion, T14 early submit, admin import, attempt-media approval): call
``OutcomesDynamoDB().stage_outcome(uow, ...)`` on the operation's own ``LearnerUnitOfWork``, commit, then
``finish_deferred_mastery(student_id, staged)``. ``record_outcome`` is exactly that plus idempotency and retries.

Known differences from PostgreSQL (the migration's tag de-duplication included, see the WP5 report):

* a tag attached twice to one problem counts once (PostgreSQL counted both rows);
* ``source`` outside the six allowed values is stored as ``import`` with the original in ``legacy_source`` (LRN-S02);
* ``list_attempts`` hides outcomes of problems that are no longer ACTIVE in the content read model (the SQL used an inner join);
* concept and technique names come from the content read model; practice progress counts come from the PTAG partitions (cached 5 min);
* ``get_cohort_weak_concepts`` reports ``total_attempts`` only when the cohort consumer maintains ``sum_attempts`` (else ``None``).
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, ClassVar
from uuid import UUID, uuid4

from mathbank_rest import mastery, stores
from mathbank_rest.config import settings
from mathbank_rest.models.ddb.content import (
    ContentConcept,
    ContentProblem,
    ContentPtag,
    ContentTechnique,
)
from mathbank_rest.models.ddb.learner import LearnerProblem
from mathbank_rest.models.manual.learner_outcomes import (
    DAILY_COUNTERS,
    MASTERY_FORMULA_VERSION,
    OUTCOME_SOURCES,
    CohortItem,
    DailyItem,
    MasteryItem,
    MevidItem,
    OutcomeItem,
)
from mathbank_rest.stores import ddb, typed
from mathbank_rest.stores.errors import NotFound, StoreError, ValidationFailed
from mathbank_rest.stores.learner.uow import CTX, LearnerUnitOfWork, run_idempotent, with_retries

LOG = logging.getLogger(__name__)

PAGE = 200
FOLLOWUP_TAGS = 49                      # one MEVID + one MASTERY per tag, within the 100-item transaction limit
THEME_CACHE_SECONDS = 300


def _db():
    from mathbank_rest.db import learner

    return learner


# ------------------------------------------------------------------------------------------------ postgres

class OutcomesPostgres:
    """Postgres backend: calls today's functions at call time (monkeypatched tests keep working)."""

    def get_problem_id_by_code(self, code: str) -> UUID | None:
        return _db().get_problem_id_by_code(code)

    def record_outcome(self, *, student_id: UUID, problem_id: UUID, is_correct: bool, submitted_answer: str | None = None,
                       time_spent_seconds: int | None = None, hint_count: int = 0, source: str = "web",
                       idempotency_key: str | None = None) -> dict:
        """Insert the attempt, then recompute the mastery of every tag of the problem (what ``POST /learner/attempts`` always did).
        ``idempotency_key`` is accepted for interface parity; only the DynamoDB store can make the two steps atomic and replayable."""
        attempt = _db().insert_attempt(student_id=student_id, problem_id=problem_id, is_correct=is_correct,
                                       submitted_answer=submitted_answer, time_spent_seconds=time_spent_seconds,
                                       hint_count=hint_count, source=source)
        return {"attempt": attempt, "updated_mastery": mastery.recompute_mastery_for_problem(student_id, problem_id)}

    def list_attempts(self, student_id: UUID, *, limit: int = 50, offset: int = 0) -> list[dict]:
        return _db().list_attempts(student_id, limit=limit, offset=offset)

    def get_concepts_and_techniques_for_problem(self, problem_id: UUID) -> dict:
        return _db().get_concepts_and_techniques_for_problem(problem_id)

    def get_attempts_for_concept(self, student_id: UUID, concept_id: UUID) -> list[dict]:
        return _db().get_attempts_for_concept(student_id, concept_id)

    def get_attempts_for_technique(self, student_id: UUID, technique_id: UUID) -> list[dict]:
        return _db().get_attempts_for_technique(student_id, technique_id)

    def upsert_concept_mastery(self, *, student_id: UUID, concept_id: UUID, mastery_score: float, attempts_count: int,
                               correct_count: int, last_attempt_at: datetime) -> None:
        _db().upsert_concept_mastery(student_id=student_id, concept_id=concept_id, mastery_score=mastery_score,
                                     attempts_count=attempts_count, correct_count=correct_count, last_attempt_at=last_attempt_at)

    def upsert_technique_mastery(self, *, student_id: UUID, technique_id: UUID, mastery_score: float, attempts_count: int,
                                 correct_count: int, last_attempt_at: datetime) -> None:
        _db().upsert_technique_mastery(student_id=student_id, technique_id=technique_id, mastery_score=mastery_score,
                                       attempts_count=attempts_count, correct_count=correct_count, last_attempt_at=last_attempt_at)

    def recompute_concept_mastery(self, student_id: UUID, concept_id: UUID) -> float:
        attempts = self.get_attempts_for_concept(student_id, concept_id)
        score = mastery.compute_mastery_score(attempts)
        self.upsert_concept_mastery(
            student_id=student_id, concept_id=concept_id, mastery_score=score, attempts_count=len(attempts),
            correct_count=sum(1 for a in attempts if a["is_correct"]),
            last_attempt_at=attempts[-1]["attempted_at"] if attempts else datetime.now(UTC))
        return score

    def recompute_technique_mastery(self, student_id: UUID, technique_id: UUID) -> float:
        attempts = self.get_attempts_for_technique(student_id, technique_id)
        score = mastery.compute_mastery_score(attempts)
        self.upsert_technique_mastery(
            student_id=student_id, technique_id=technique_id, mastery_score=score, attempts_count=len(attempts),
            correct_count=sum(1 for a in attempts if a["is_correct"]),
            last_attempt_at=attempts[-1]["attempted_at"] if attempts else datetime.now(UTC))
        return score

    def get_mastery_summary(self, student_id: UUID) -> dict:
        return _db().get_mastery_summary(student_id)

    def get_practice_progress(self, student_id: UUID) -> dict:
        return _db().get_practice_progress(student_id)

    def get_cohort_weak_concepts(self, *, min_students: int = 1, limit: int = 20) -> list[dict]:
        return _db().get_cohort_weak_concepts(min_students=min_students, limit=limit)

    def list_daily_activity(self, student_id: UUID, date_from: date, date_to: date) -> list[dict]:
        return _db().list_daily_activity(student_id, date_from, date_to)


# ------------------------------------------------------------------------------------------------ dynamodb helpers

def _content():
    return stores.get_store("content")


def _normalise_source(source: str) -> tuple[str, str | None]:
    """A source outside the enum is stored as ``import`` and the original text kept (the migration did the same)."""
    return (source, None) if source in OUTCOME_SOURCES else ("import", str(source)[:200])


def _evidence_row(e: MevidItem) -> dict:
    return {"is_correct": e.is_correct, "attempted_at": e.attempted_at, "hint_count": e.hint_count,
            "difficulty_band": e.difficulty_band}


def _read_evidence(student_id: UUID | str, kind: str, tag_id: UUID | str) -> list[MevidItem]:
    """A7: every graded evidence row of one tag, oldest first, strongly consistent."""
    pk, token, out = ddb.student_pk(student_id), None, []
    while True:
        page = typed.query(MevidItem, pk, sk_begins=f"MEVID#{kind}#{tag_id}#", limit=PAGE, next_token=token)
        out += page.items
        token = page.next_token
        if not token:
            return out


def _summarise(rows: list[dict]) -> tuple[float, int, int, datetime]:
    """(score, attempts_count, correct_count, last_attempt_at) exactly as ``recompute_*_mastery`` derived them."""
    rows = sorted(rows, key=lambda r: r["attempted_at"])
    return (mastery.compute_mastery_score(rows), len(rows), sum(1 for r in rows if r["is_correct"]),
            rows[-1]["attempted_at"] if rows else datetime.now(UTC))


def _mastery_item(student_id: UUID | str, kind: str, tag_id: UUID | str, summary: tuple[float, int, int, datetime],
                  version: int) -> MasteryItem:
    sid, tag = UUID(str(student_id)), UUID(str(tag_id))
    score, count, correct, last = summary
    return MasteryItem(PK=ddb.student_pk(sid), SK=f"MASTERY#{kind}#{tag}", student_id=sid, tag_id=tag, tag_kind=kind,
                       mastery_score=score, attempts_count=count, correct_count=correct, last_attempt_at=last,
                       formula_version=MASTERY_FORMULA_VERSION, updated_at=datetime.now(UTC), version=version,
                       **({"concept_id": tag} if kind == "C" else {"technique_id": tag}))


def _mastery_guard(existing: MasteryItem | None) -> ddb.Cond:
    """``attribute_not_exists(PK) OR version = :seen``: create it, or replace exactly the version that was read."""
    if existing is None:
        return ddb.NOT_EXISTS
    if existing.version is None:
        return ddb.Cond("attribute_not_exists(#ver)", {"#ver": "version"})
    return ddb.version_is(existing.version)


def _next_version(existing: MasteryItem | None) -> int:
    return 1 if existing is None else (existing.version or 0) + 1


def _load_mastery(student_id: UUID | str, kind: str, tag_id: UUID | str) -> MasteryItem | None:
    return typed.get(MasteryItem, ddb.student_pk(student_id), f"MASTERY#{kind}#{tag_id}")


def _paged(model: Any, pk: str, **kwargs: Any):
    token = None
    while True:
        page = typed.query(model, pk, limit=PAGE, next_token=token, **kwargs)
        yield from page.items
        token = page.next_token
        if not token:
            return


@dataclass
class StagedOutcome:
    """What ``stage_outcome`` added to the unit of work and what is still owed after it commits."""

    attempt: dict
    updated_mastery: dict
    deferred: list[tuple[str, UUID]] = field(default_factory=list)      # tags whose MEVID/MASTERY are not in the transaction
    evidence: dict = field(default_factory=dict)                         # the new evidence template (for the follow-up)

    def response(self) -> dict:
        return {"attempt": self.attempt, "updated_mastery": self.updated_mastery}


# ------------------------------------------------------------------------------------------------ dynamodb

class OutcomesDynamoDB:
    """DynamoDB backend over mb-learner (and the content read model)."""

    # -- content lookups ---------------------------------------------------------------------------------------------

    def get_problem_id_by_code(self, code: str) -> UUID | None:
        """The one content lookup the content store has no method for: a code resolves to its id through the PROBLEM item."""
        item = typed.get(ContentProblem, f"PROBLEM#{code}", "META", consistent=False)
        return item.problem_id if item is not None and item.visibility == "ACTIVE" else None

    def get_concepts_and_techniques_for_problem(self, problem_id: UUID) -> dict:
        """Non-REJECTED tags of a problem, from the content store (WP1: REJECTED tags never feed mastery)."""
        return _content().get_problem_tags(problem_id=problem_id)

    # -- T7 ----------------------------------------------------------------------------------------------------------

    def _tag_state(self, student_id: UUID | str, kind: str, tag_id: UUID, new: dict | None) -> tuple[MasteryItem | None, tuple]:
        rows = [_evidence_row(e) for e in _read_evidence(student_id, kind, tag_id)]
        if new is not None:
            rows.append(new)
        return _load_mastery(student_id, kind, tag_id), _summarise(rows)

    @staticmethod
    def _new_row(ev: dict) -> dict | None:
        if ev["is_correct"] is None:
            return None
        return {k: ev[k] for k in ("is_correct", "attempted_at", "hint_count", "difficulty_band")}

    def _mevid(self, student_id: UUID | str, kind: str, tag_id: UUID, ev: dict) -> MevidItem:
        return MevidItem(
            PK=ddb.student_pk(student_id), student_id=UUID(str(student_id)), tag_kind=kind, tag_id=tag_id, is_correct=ev["is_correct"],
            hint_count=ev["hint_count"], difficulty_band=ev["difficulty_band"],
            difficulty_weight=mastery.difficulty_weight(ev["difficulty_band"]), attempted_at=ev["attempted_at"], src_kind="OUT",
            src_id=ev["src_id"], problem_id=ev["problem_id"],
            SK=f"MEVID#{kind}#{tag_id}#{ddb.encode(ev['attempted_at'])}#OUT#{ev['src_id']}")

    def _stage_tag(self, uow: LearnerUnitOfWork, kind: str, tag_id: UUID, ev: dict) -> float:
        new = self._new_row(ev)
        existing, summary = self._tag_state(uow.student_id, kind, tag_id, new)
        if new is not None:
            uow.put_new(self._mevid(uow.student_id, kind, tag_id, ev))
        uow.put(_mastery_item(uow.student_id, kind, tag_id, summary, _next_version(existing)), cond=_mastery_guard(existing))
        return summary[0]

    def stage_outcome(self, uow: LearnerUnitOfWork, *, problem_id: UUID, attempt_id: UUID, attempted_at: datetime,
                      is_correct: bool | None, submitted_answer: str | None, time_spent_seconds: int | None, hint_count: int,
                      source: str, difficulty_band: str | None, tags: dict, solve_attempt_id: UUID | None = None) -> StagedOutcome:
        """Add the T7 items to ``uow`` (OUTCOME, PROBLEM counters, then MEVID + MASTERY per tag while they fit in 100 items).
        ``tags`` is ``{"concept_ids": [...], "technique_ids": [...]}`` from the content store. Nothing is written until the caller
        commits; afterwards ``finish_deferred_mastery`` completes what did not fit."""
        stored_source, legacy = _normalise_source(source)
        sid = uow.student_id
        kinds = [("C", UUID(str(t))) for t in dict.fromkeys(map(str, tags.get("concept_ids", ())))]
        kinds += [("T", UUID(str(t))) for t in dict.fromkeys(map(str, tags.get("technique_ids", ())))]
        needed = 2 + (2 if is_correct is not None else 1) * len(kinds)
        pending = not uow.fits(needed)
        ev = {"is_correct": is_correct, "attempted_at": attempted_at, "hint_count": hint_count, "difficulty_band": difficulty_band,
              "src_id": attempt_id, "problem_id": problem_id}
        uow.put_new(OutcomeItem(
            PK=ddb.student_pk(sid), SK=f"OUTCOME#{ddb.encode(attempted_at)}#{attempt_id}", student_id=UUID(sid), attempt_id=attempt_id,
            attempted_at=attempted_at, hint_count=hint_count, is_correct=is_correct, source=stored_source, legacy_source=legacy,
            problem_id=problem_id, time_spent_seconds=time_spent_seconds, submitted_answer=submitted_answer,
            solve_attempt_id=solve_attempt_id, mastery_pending=True if pending else None))
        uow.add(ddb.Update(
            CTX, ddb.student_pk(sid), f"PROBLEM#{problem_id}",
            "SET #t = :type, #sid = :sid, #pid = :pid, #fa = if_not_exists(#fa, :now), #oc = if_not_exists(#oc, :zero) + :one, "
            "#ver = if_not_exists(#ver, :zero) + :one, #upd = :now",
            names={"#t": "type", "#sid": "student_id", "#pid": "problem_id", "#fa": "first_attempted_at", "#oc": "outcome_count",
                   "#ver": "version", "#upd": "updated_at"},
            values={":type": "PROBLEM", ":sid": sid, ":pid": str(problem_id), ":now": ddb.encode(attempted_at), ":zero": 0, ":one": 1},
            label="problem cursor"))
        scores: dict[str, dict[str, float]] = {"concepts": {}, "techniques": {}}
        for kind, tag in kinds:
            bucket = scores["concepts" if kind == "C" else "techniques"]
            if pending:
                bucket[str(tag)] = self._tag_state(sid, kind, tag, self._new_row(ev))[1][0]
            else:
                bucket[str(tag)] = self._stage_tag(uow, kind, tag, ev)
        return StagedOutcome(attempt={"attempt_id": str(attempt_id), "attempted_at": attempted_at.isoformat()},
                             updated_mastery=scores, deferred=kinds if pending else [], evidence=ev)

    def finish_deferred_mastery(self, student_id: UUID | str, staged: StagedOutcome) -> None:
        """Write the MEVID/MASTERY items that did not fit in the outcome's transaction, in chunks that do. A chunk that keeps losing
        its version race is left to the ``mastery-repair`` consumer (the OUTCOME carries ``mastery_pending``)."""
        for i in range(0, len(staged.deferred), FOLLOWUP_TAGS):
            chunk = staged.deferred[i:i + FOLLOWUP_TAGS]

            def attempt(chunk=chunk) -> None:
                uow = LearnerUnitOfWork(student_id)
                for kind, tag in chunk:
                    self._stage_tag(uow, kind, tag, staged.evidence)
                uow.commit()

            try:
                with_retries(attempt, attempts=5)
            except StoreError:
                LOG.exception("deferred mastery for outcome %s left to mastery-repair", staged.attempt["attempt_id"])

    def record_outcome(self, *, student_id: UUID, problem_id: UUID, is_correct: bool | None, submitted_answer: str | None = None,
                       time_spent_seconds: int | None = None, hint_count: int = 0, source: str = "web",
                       solve_attempt_id: UUID | None = None, idempotency_key: str | None = None) -> dict:
        """T7 as an operation: validate the problem against the content store, then commit the outcome and its mastery fan-out in one
        transaction (replayed when the same ``Idempotency-Key`` repeats). Returns ``{"attempt", "updated_mastery"}`` like PostgreSQL."""
        problem = _content().get_problem_by_id(problem_id)
        if problem is None:
            raise NotFound(f"problem {problem_id}")
        if hint_count < 0 or (time_spent_seconds is not None and time_spent_seconds < 0):
            raise ValidationFailed("hint_count and time_spent_seconds must not be negative")
        tags = _content().get_problem_tags(problem_id=problem_id)
        attempt_id, attempted_at = uuid4(), datetime.now(UTC)
        body = {"problem_id": str(problem_id), "is_correct": is_correct, "submitted_answer": submitted_answer,
                "time_spent_seconds": time_spent_seconds, "hint_count": hint_count, "source": source}
        staged: list[StagedOutcome] = []

        def build(uow: LearnerUnitOfWork) -> dict:
            staged.clear()
            staged.append(self.stage_outcome(
                uow, problem_id=problem_id, attempt_id=attempt_id, attempted_at=attempted_at, is_correct=is_correct,
                submitted_answer=submitted_answer, time_spent_seconds=time_spent_seconds, hint_count=hint_count, source=source,
                difficulty_band=problem.get("difficulty_band"), tags=tags, solve_attempt_id=solve_attempt_id))
            return staged[0].response()

        response, replayed = with_retries(lambda: run_idempotent(
            student_id, key=idempotency_key, operation="record_outcome", body=body, build=build))
        if staged and not replayed:
            self.finish_deferred_mastery(student_id, staged[0])
        return response

    # -- A6 ----------------------------------------------------------------------------------------------------------

    def list_attempts(self, student_id: UUID, *, limit: int = 50, offset: int = 0) -> list[dict]:
        """Own outcome history, newest first, with the problem context the UI shows (A6)."""
        content, problems, rows = _content(), {}, []
        for item in _paged(OutcomeItem, ddb.student_pk(student_id), sk_begins="OUTCOME#", forward=False):
            key = str(item.problem_id)
            if key not in problems:
                problems[key] = content.get_problem_by_id(item.problem_id)
            problem = problems[key]
            if problem is None:
                continue
            rows.append({
                "attempt_id": item.attempt_id, "is_correct": item.is_correct, "submitted_answer": item.resolve("submitted_answer"),
                "time_spent_seconds": item.time_spent_seconds, "hint_count": item.hint_count, "attempted_at": item.attempted_at,
                "source": item.legacy_source or item.source, "canonical_code": problem["canonical_code"],
                "problem_number": problem["problem_number"], "difficulty_band": problem.get("difficulty_band"),
                "competition": problem["competition"], "year": problem.get("year")})
            if len(rows) >= offset + limit:
                break
        return rows[offset:offset + limit]

    # -- A7 / mastery ------------------------------------------------------------------------------------------------

    def get_attempts_for_concept(self, student_id: UUID, concept_id: UUID) -> list[dict]:
        return [_evidence_row(e) for e in _read_evidence(student_id, "C", concept_id)]

    def get_attempts_for_technique(self, student_id: UUID, technique_id: UUID) -> list[dict]:
        return [_evidence_row(e) for e in _read_evidence(student_id, "T", technique_id)]

    def _put_mastery(self, student_id: UUID, kind: str, tag_id: UUID, summary: tuple) -> None:
        def attempt() -> None:
            existing = _load_mastery(student_id, kind, tag_id)
            uow = LearnerUnitOfWork(student_id)
            uow.put(_mastery_item(student_id, kind, tag_id, summary, _next_version(existing)), cond=_mastery_guard(existing))
            uow.commit()

        with_retries(attempt)

    def upsert_concept_mastery(self, *, student_id: UUID, concept_id: UUID, mastery_score: float, attempts_count: int,
                               correct_count: int, last_attempt_at: datetime) -> None:
        self._put_mastery(student_id, "C", concept_id, (mastery_score, attempts_count, correct_count, last_attempt_at))

    def upsert_technique_mastery(self, *, student_id: UUID, technique_id: UUID, mastery_score: float, attempts_count: int,
                                 correct_count: int, last_attempt_at: datetime) -> None:
        self._put_mastery(student_id, "T", technique_id, (mastery_score, attempts_count, correct_count, last_attempt_at))

    def _rebuild(self, student_id: UUID, kind: str, tag_id: UUID) -> float:
        """T35: recompute one score from its MEVID evidence; the write is conditional on the MASTERY version that was read."""
        def attempt() -> float:
            existing, summary = self._tag_state(student_id, kind, tag_id, None)
            uow = LearnerUnitOfWork(student_id)
            uow.put(_mastery_item(student_id, kind, tag_id, summary, _next_version(existing)), cond=_mastery_guard(existing))
            uow.commit()
            return summary[0]

        return with_retries(attempt)

    def recompute_concept_mastery(self, student_id: UUID, concept_id: UUID) -> float:
        return self._rebuild(student_id, "C", concept_id)

    def recompute_technique_mastery(self, student_id: UUID, technique_id: UUID) -> float:
        return self._rebuild(student_id, "T", technique_id)

    # -- A8 ----------------------------------------------------------------------------------------------------------

    @staticmethod
    def _names(model: Any, prefix: str, ids: set[str]) -> dict[str, Any]:
        found = typed.batch_get(model, [(f"{prefix}#{i}", "META") for i in ids], consistent=False)
        return {i.PK.split("#", 1)[1]: i for i in found}

    def get_mastery_summary(self, student_id: UUID) -> dict:
        """Own scores, weakest first, with the concept/technique name (A8). Tags missing from the content model are skipped."""
        items = list(_paged(MasteryItem, ddb.student_pk(student_id), sk_begins="MASTERY#"))
        concepts = self._names(ContentConcept, "CONCEPT", {str(i.tag_id) for i in items if i.tag_kind == "C"})
        techniques = self._names(ContentTechnique, "TECHNIQUE", {str(i.tag_id) for i in items if i.tag_kind == "T"})
        out: dict[str, list[dict]] = {"concepts": [], "techniques": []}
        for item in sorted(items, key=lambda i: i.mastery_score):
            tag = (concepts if item.tag_kind == "C" else techniques).get(str(item.tag_id))
            if tag is not None:
                out["concepts" if item.tag_kind == "C" else "techniques"].append({
                    "slug": tag.slug, "name": tag.name, "mastery_score": item.mastery_score, "attempts_count": item.attempts_count,
                    "correct_count": item.correct_count, "last_attempt_at": item.last_attempt_at})
        return out

    # -- A9 ----------------------------------------------------------------------------------------------------------

    _themes: ClassVar[dict[str, tuple[float, list]]] = {}

    @classmethod
    def _theme_problems(cls, kind: str) -> list[tuple[str, str, frozenset]]:
        """(slug, name, problem ids) of every concept or technique, from the catalogue snapshot and the PTAG partitions (cached)."""
        hit = cls._themes.get(kind)
        if hit is not None and hit[0] > time.monotonic():
            return hit[1]
        from mathbank_rest.models.docs.content import CatalogConcept, CatalogTechnique
        from mathbank_rest.stores.content.catalog import _catalogue

        doc, _ = _catalogue(kind, CatalogConcept if kind == "concept" else CatalogTechnique)

        def load(entry: Any) -> tuple[str, str, frozenset]:
            pk = f"{kind.upper()}#{getattr(entry, kind + '_id')}"
            ids = {t.problem_id for t in _paged(ContentPtag, pk, index="GSI1", consistent=False) if t.review_status != "REJECTED"}
            return entry.slug, entry.name, frozenset(ids)

        with ThreadPoolExecutor(max_workers=8) as pool:
            rows = list(pool.map(load, doc.items))
        cls._themes[kind] = (time.monotonic() + THEME_CACHE_SECONDS, rows)
        return rows

    def get_practice_progress(self, student_id: UUID) -> dict:
        """Distinct available / attempted / remaining problems per exact corpus theme; attempted = outcome_count > 0 (A9)."""
        attempted = {p.problem_id for p in _paged(LearnerProblem, ddb.student_pk(student_id), sk_begins="PROBLEM#", consistent=False)
                     if p.outcome_count > 0}
        items = []
        for kind in ("concept", "technique"):
            for slug, name, problems in self._theme_problems(kind):
                done = len(problems & attempted)
                items.append({"kind": kind, "slug": slug, "name": name, "available": len(problems), "attempted": done,
                              "remaining": len(problems) - done})
        items.sort(key=lambda r: (r["kind"], r["name"].lower(), r["slug"]))
        return {"items": items}

    # -- A41 / A42 ---------------------------------------------------------------------------------------------------

    def list_daily_activity(self, student_id: UUID, date_from: date, date_to: date) -> list[dict]:
        """Own UTC-day counters between two dates (inclusive), oldest first (A41)."""
        bounds = (f"DAILY#{date_from.isoformat()}", f"DAILY#{date_to.isoformat()}")
        return [{"activity_date": d.activity_date, **{c: getattr(d, c) for c in DAILY_COUNTERS}}
                for d in _paged(DailyItem, ddb.student_pk(student_id), sk_between=bounds)]

    def get_cohort_weak_concepts(self, *, min_students: int = 1, limit: int = 20) -> list[dict]:
        """Concept aggregates (no PII), lowest average first; a concept needs at least ``cohort_min_students`` learners (A42)."""
        floor = max(min_students, settings.cohort_min_students)
        cohort = [c for c in _paged(CohortItem, "COHORT#CONCEPT", consistent=False) if c.n_students >= floor]
        names = self._names(ContentConcept, "CONCEPT", {str(c.concept_id) for c in cohort})
        rows = [{"slug": names[str(c.concept_id)].slug, "name": names[str(c.concept_id)].name, "student_count": c.n_students,
                 "avg_mastery_score": c.sum_score / c.n_students, "total_attempts": c.sum_attempts}
                for c in cohort if str(c.concept_id) in names]
        rows.sort(key=lambda r: (r["avg_mastery_score"], r["slug"]))
        return rows[:limit]
