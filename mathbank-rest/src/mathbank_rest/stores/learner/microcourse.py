"""Learner store, micro-course area (requirement 71 WP5; requirement 70 C1 access patterns A26-A32, write paths T21-T26).

``MicroCoursePostgres`` delegates to the SQL functions of ``micro_course_service`` / ``interaction_runtime`` / ``micro_course_assist``
at call time (behaviour unchanged, monkeypatched tests keep working); every method takes the SQL connection first. ``MicroCourseDynamoDB``
is the ``mb-learner`` implementation on ``LearnerUnitOfWork`` and the typed models of ``models/manual/learner_microcourse.py``; the
connection is ignored (callers pass ``None``). Published content (the pinned release's reader payload, answer keys, interaction
instances) comes from ``stores.get_store("content")`` and is read BEFORE the transaction: a release snapshot is immutable.

Operations (a method is a read exactly when its name starts with a ``stores.READ_PREFIXES`` entry):

* reads   ``get_enrollment_runtime`` (A27), ``list_enrollments`` (A28), ``list_item_interactions`` (A31), ``list_misconceptions`` /
          ``get_misconception_state`` (A32); for the admin plane ``get_enrollment_owner`` (A30), ``list_course_activity`` (A29)
* writes  ``start_enrollment`` (T21), ``advance_enrollment`` (T22), ``submit_learning_item_response`` / ``submit_activity_response``
          (T23), ``record_interaction_event`` (T24), ``abandon_enrollment`` (T25), ``reset_enrollment`` (T26, admin), ``assist_item``

Every mutation that takes an ``Idempotency-Key`` runs through ``run_idempotent``: the receipt is written in the SAME transaction as the
effect, a repeat replays the stored response with ``replayed: true`` (LRN-F18). PostgreSQL ignores the key (it has no receipt store).

Concurrency: ``ENROLL.version`` is the client-visible ``state_version``; it changes only on advance, abandon and reset, with the client's
value checked in code first (409) and then enforced by the transaction condition. A learner's response never changes it: it updates
``last_responses`` guarded by ``response_seq`` and retried (server-derived condition) on a concurrent writer.

Differences from PostgreSQL that callers can observe (all listed in the WP5 report):

* ``Idempotency-Key`` is honoured (DynamoDB only); a replay carries ``replayed: true``;
* the open-enrollment rule is a sentinel in the learner's partition, so two concurrent enrolls resolve to ONE enrollment (LRN-S05);
* ``record_interaction_event`` evaluates deterministically and applies misconception evidence only when ``MISCONCEPTION_EVIDENCE=on``
  and the content store can supply the approved evidence rule (``find_misconception_evidence_rule``); without it the event is only recorded;
* the item-help "help" request writes no audit row (the ``mb-audit`` writer is WP9); a give-up is recorded as the response it is;
* item-help grounding of the course targets carries no target description (the release snapshot has none).
"""
from __future__ import annotations

import datetime as dt
import json
import logging
from typing import Any

from pydantic import TypeAdapter

from mathbank_rest import interaction_runtime as ixrt
from mathbank_rest import micro_course_assist as assist
from mathbank_rest import micro_course_service as courses
from mathbank_rest import stores
from mathbank_rest.config import settings
from mathbank_rest.models.base import UtcDateTime
from mathbank_rest.models.ddb.learner import LearnerProfile
from mathbank_rest.models.manual import learner_microcourse as mc
from mathbank_rest.stores import ddb, typed
from mathbank_rest.stores.errors import ConditionFailed, UniqueViolation
from mathbank_rest.stores.learner.uow import CTX, LearnerUnitOfWork, run_idempotent, with_retries

LOG = logging.getLogger(__name__)

ENROLLMENT_STATUSES = ("IN_PROGRESS", "COMPLETED", "ABANDONED")
RECENT_ACTIVITY = 25
MAX_PAGES = 50                        # 50 pages x 200 items bound every list; a learner or release is far smaller
_TS = TypeAdapter(UtcDateTime)
_IN_PROGRESS = ddb.Cond("#st = :in", {"#st": "status"}, {":in": "IN_PROGRESS"})
_STALE_LESSON = "micro-course lesson changed; refresh before continuing"
_NOT_FOUND = "micro-course enrollment not found"
_NOT_OPEN = "micro-course enrollment is not in progress"


# ------------------------------------------------------------------------------------------------ PostgreSQL

class MicroCoursePostgres:
    """Postgres backend: calls today's functions at call time (monkeypatched tests keep working)."""

    backend = "postgres"

    def start_enrollment(self, conn, canonical_code: str, student_id: str, idempotency_key: str | None = None) -> dict:
        return courses.start_enrollment(conn, canonical_code, str(student_id))

    def get_enrollment_runtime(self, conn, enrollment_id: str, student_id: str) -> dict:
        return courses.get_enrollment_runtime(conn, str(enrollment_id), str(student_id))

    def advance_enrollment(self, conn, enrollment_id: str, student_id: str, expected_state_version: int, action: str,
                           idempotency_key: str | None = None) -> dict:
        return courses.advance_enrollment(conn, str(enrollment_id), str(student_id), expected_state_version, action)

    def submit_learning_item_response(self, conn, enrollment_id: str, student_id: str, learning_item_id: str,
                                      choice_index: int | None, *, gave_up: bool = False,
                                      idempotency_key: str | None = None) -> dict:
        return courses.submit_learning_item_response(
            conn, str(enrollment_id), str(student_id), learning_item_id, choice_index, gave_up=gave_up)

    def submit_activity_response(self, conn, enrollment_id: str, student_id: str, activity_id: str, *,
                                 choice_index: int | None = None, value: float | None = None, gave_up: bool = False,
                                 idempotency_key: str | None = None) -> dict:
        return courses.submit_activity_response(
            conn, str(enrollment_id), str(student_id), str(activity_id), choice_index=choice_index, value=value, gave_up=gave_up)

    def record_interaction_event(self, conn, enrollment_id: str, student_id: str, interaction_instance_id: str, *,
                                 event_type: str, semantic_action: str, control_key: str | None = None,
                                 object_id: str | None = None, before_state: dict | None = None,
                                 action_payload: dict | None = None, after_state: dict | None = None,
                                 idempotency_key: str | None = None) -> dict:
        event_id = courses.record_interaction_event(
            conn, str(enrollment_id), str(student_id), str(interaction_instance_id), event_type=event_type,
            semantic_action=semantic_action, control_key=control_key, object_id=object_id, before_state=before_state,
            action_payload=action_payload, after_state=after_state)
        return {"interaction_event_id": event_id}

    def assist_item(self, conn, enrollment_id: str, student_id: str, item_kind: str, item_id: str, intent: str,
                    student_message: str | None, idempotency_key: str | None = None) -> dict:
        return assist.get_item_assist(
            conn, str(enrollment_id), str(student_id), item_kind, item_id, intent, student_message)

    def list_enrollments(self, conn, student_id: str, status: str | None = None, limit: int = 100) -> dict:
        return courses.list_enrollments(conn, str(student_id), status, limit)

    def abandon_enrollment(self, conn, enrollment_id: str, student_id: str, idempotency_key: str | None = None) -> dict:
        return courses.abandon_enrollment(conn, str(enrollment_id), str(student_id))

    def list_item_interactions(self, conn, enrollment_id: str, student_id: str, interaction_instance_id: str) -> list[dict]:
        return assist.recent_interactions(conn, str(enrollment_id), str(interaction_instance_id))

    def list_misconceptions(self, conn, student_id: str) -> dict:
        items = ixrt.list_misconception_state(conn, str(student_id))
        return {"items": items, "total": len(items)}

    def get_misconception_state(self, conn, student_id: str, misconception_id: str) -> dict | None:
        return next((i for i in ixrt.list_misconception_state(conn, str(student_id))
                     if i["misconception_id"] == str(misconception_id)), None)

    # admin plane
    def get_enrollment_owner(self, conn, enrollment_id: str) -> str | None:
        return courses.get_enrollment_owner(conn, str(enrollment_id))

    def list_course_activity(self, conn, canonical_code: str) -> dict:
        return courses.get_course_activity(conn, canonical_code)

    def reset_enrollment(self, conn, enrollment_id: str, to_state_id: str, actor: str) -> dict:
        return courses.reset_enrollment(conn, str(enrollment_id), str(to_state_id), actor)


# ------------------------------------------------------------------------------------------------ DynamoDB

def _content() -> Any:
    return stores.get_store("content")


def _json_default(value: Any) -> Any:
    if isinstance(value, dt.datetime):
        return ddb.encode(value)
    return str(value)


def _idempotent(sid: str, key: str | None, operation: str, body: dict, build, *, retry: bool = True) -> dict:
    """``run_idempotent`` whose receipt keeps the response exactly as built: DynamoDB drops null attributes of a stored map, so the
    response travels as a JSON string and is parsed back on a first run and on a replay alike (same keys, nulls kept). A replay
    carries ``replayed: true``."""
    def run() -> tuple[dict, bool]:
        return run_idempotent(sid, key=key, operation=operation, body=body,
                              build=lambda uow: {"json": json.dumps(build(uow), default=_json_default)})

    packed, replayed = with_retries(run) if retry else run()
    response = json.loads(packed["json"])
    return {**response, "replayed": True} if replayed else response


def _when(timestamp: str) -> dt.datetime:
    return _TS.validate_python(timestamp)


def _status_filter(status: str | None) -> None:
    if status is not None and status not in ENROLLMENT_STATUSES:
        raise ValueError("status must be IN_PROGRESS, COMPLETED or ABANDONED")


def _pages(model: Any, pk: str, **kwargs: Any):
    """Every item of one key-condition query, page by page (bounded)."""
    token = None
    for _ in range(MAX_PAGES):
        page = typed.query(model, pk, limit=200, next_token=token, **kwargs)
        yield from page.items
        token = page.next_token
        if not token:
            return


class MicroCourseDynamoDB:
    """DynamoDB backend over mb-learner."""

    backend = "dynamodb"

    # ---------------------------------------------------------------------------- loading and views

    @staticmethod
    def _mc_load(student_id: str, enrollment_id: str) -> mc.LearnerEnroll:
        """The learner's own enrollment (strong read). Another student's id is simply absent from this partition: 404."""
        found = typed.get(mc.LearnerEnroll, ddb.student_pk(student_id), mc.enroll_sk(enrollment_id), consistent=True)
        if found is None:
            raise courses.MicroCourseNotFound(_NOT_FOUND)
        return found

    def _load_open(self, student_id: str, enrollment_id: str) -> mc.LearnerEnroll:
        found = self._mc_load(student_id, enrollment_id)
        if found.status != "IN_PROGRESS":
            raise courses.MicroCourseConflict(_NOT_OPEN)
        return found

    @staticmethod
    def _view(e: mc.LearnerEnroll, **over: Any) -> dict:
        return {"enrollment_id": e.enrollment_id, "enrollment_status": e.status, "started_at": e.started_at,
                "completed_at": e.completed_at, "micro_course_id": e.micro_course_id, "state_version": e.state_version,
                "current_state_id": e.current_state_id, **over}

    @staticmethod
    def _answers(e: mc.LearnerEnroll) -> dict[str, dict]:
        stored = e.resolve("last_responses", dict[str, mc.LastResponse]) or {}
        return {item_id: {"kind": r.kind, "is_correct": r.payload.is_correct} for item_id, r in stored.items()}

    def _runtime(self, e: mc.LearnerEnroll, reader: dict | None = None, **over: Any) -> dict:
        """The learner's runtime view of an enrollment; answer keys are read only to explain items already answered."""
        content = _content()
        reader = reader or content.get_pinned_micro_course_reader(None, str(e.release_id))
        return courses.assemble_runtime(
            reader, self._view(e, **over), self._answers(e),
            item_explanation=lambda item_id: (content.get_learning_item_key(None, item_id) or {}).get("answer_or_solution_seed"),
            activity_explanation=lambda activity_id: (
                (content.get_activity_key(None, activity_id) or {}).get("correctness_policy") or {}).get("explanation"))

    @staticmethod
    def _mc_event(uow: LearnerUnitOfWork, e: mc.LearnerEnroll, event_type: str, state_id: Any, payload: dict, *,
               actor: str = "STUDENT") -> tuple[str, str]:
        event_id, created = ddb.uuid7(), ddb.now_iso()
        uow.put_new(mc.LearnerMcevent(
            PK=uow.pk, SK=mc.mcevent_sk(e.enrollment_id, created, event_id), student_id=e.student_id,
            enrollment_id=e.enrollment_id, event_id=event_id, event_type=event_type, actor_type=actor, state_id=state_id,
            release_id=e.release_id, payload=payload, created_at=created, **mc.mcevent_keys(e.release_id, created, event_id)))
        return event_id, created

    # ---------------------------------------------------------------------------- A27

    def get_enrollment_runtime(self, conn, enrollment_id: str, student_id: str) -> dict:
        return self._runtime(self._mc_load(str(student_id), str(enrollment_id)))

    # ---------------------------------------------------------------------------- T21 / A26

    def start_enrollment(self, conn, canonical_code: str, student_id: str, idempotency_key: str | None = None) -> dict:
        """Create the learner's enrollment on the published release, or resume the open one (sentinel
        ``UNIQUE#open_enroll#<course>``). Two concurrent enrolls end with one enrollment: the loser resumes the winner's."""
        code, sid = courses._required_text(canonical_code, "canonical_code"), str(student_id)

        def once() -> dict:
            return _idempotent(sid, idempotency_key, "micro_course.enroll", {"canonical_code": code},
                               lambda uow: self._build_enroll(uow, code))

        try:
            return once()
        except UniqueViolation:
            return once()

    def _build_enroll(self, uow: LearnerUnitOfWork, code: str) -> dict:
        reader = _content().get_micro_course_reader(None, code)
        course_id, release_id = str(reader["micro_course_id"]), str(reader["release_id"])
        pointer = typed.get(mc.LearnerUniqueOpenEnroll, uow.pk, mc.open_enroll_sk(course_id), consistent=True)
        if pointer is not None:
            existing = typed.get(mc.LearnerEnroll, uow.pk, mc.enroll_sk(pointer.enrollment_id), consistent=True)
            if existing is not None and existing.status == "IN_PROGRESS":
                return self._runtime(existing)
        states = sorted(reader["states"], key=lambda s: (s["ordinal"], str(s["state_id"])))
        if not states:
            raise courses.MicroCourseConflict("published course has no entry state")
        entry, eid, now = states[0]["state_id"], ddb.uuid7(), ddb.now_iso()
        enroll = mc.LearnerEnroll(
            PK=uow.pk, SK=mc.enroll_sk(eid), student_id=uow.student_id, enrollment_id=eid, micro_course_id=course_id,
            canonical_code=reader["canonical_code"], release_id=release_id, status="IN_PROGRESS", current_state_id=entry,
            last_responses={}, started_at=now, updated_at=now, version=1, **mc.enroll_keys(release_id, "IN_PROGRESS", now, eid))
        uow.add(ddb.Check(CTX, uow.pk, "PROFILE", ddb.Cond("#st = :active", {"#st": "status"}, {":active": "ACTIVE"}),
                          conflict=courses.MicroCourseNotFound("active student account not found"), label="profile"))
        sentinel = mc.LearnerUniqueOpenEnroll(PK=uow.pk, SK=mc.open_enroll_sk(course_id), student_id=uow.student_id,
                                              enrollment_id=eid)
        if pointer is None:
            uow.put_new(sentinel, conflict=UniqueViolation("open_enroll", course_id))
        else:                                   # the pointer outlived its enrollment: take it over only if still the same
            uow.put(sentinel, cond=ddb.Cond("#e = :e", {"#e": "enrollment_id"}, {":e": str(pointer.enrollment_id)}))
        uow.put_new(enroll)
        uow.put_new(mc.LearnerEnrollOwner(PK=mc.enroll_owner_pk(eid), SK="OWNER", student_id=uow.student_id))
        self._mc_event(uow, enroll, "ENROLLED", entry, {"canonical_code": code})
        return self._runtime(enroll, reader)

    # ---------------------------------------------------------------------------- T22

    def advance_enrollment(self, conn, enrollment_id: str, student_id: str, expected_state_version: int, action: str,
                           idempotency_key: str | None = None) -> dict:
        normalized, sid, eid = courses.normalize_advance_action(action), str(student_id), str(enrollment_id)
        return _idempotent(
            sid, idempotency_key, "micro_course.advance",
            {"enrollment_id": eid, "expected_state_version": expected_state_version, "action": normalized},
            lambda uow: self._build_advance(uow, eid, expected_state_version, normalized), retry=False)

    def _build_advance(self, uow: LearnerUnitOfWork, eid: str, expected: int, action: str) -> dict:
        e = self._load_open(uow.student_id, eid)
        if e.state_version != expected:
            raise courses.MicroCourseConflict(_STALE_LESSON)
        reader = _content().get_pinned_micro_course_reader(None, str(e.release_id))
        transitions, state_id = reader["transitions"], str(e.current_state_id)
        transition = courses.pick_transition(transitions, state_id, action)
        if transition is None:
            if action != "CONTINUE" or any(str(t["from_state_id"]) == state_id for t in transitions):
                raise courses.MicroCourseConflict(f"no approved {action.lower()} transition from the current state")
            now = ddb.now_iso()
            changes: dict[str, Any] = {"status": "COMPLETED", "completed_at": now,
                                       "GSI1SK": f"COMPLETED#{ddb.encode(e.started_at)}#{e.enrollment_id}"}
            event_type, to_state = "COMPLETED", e.current_state_id
            after: dict[str, Any] = {"enrollment_status": "COMPLETED", "completed_at": _when(now)}
            uow.delete(mc.LearnerUniqueOpenEnroll, uow.pk, mc.open_enroll_sk(e.micro_course_id))
        else:
            event_type, to_state = "STATE_CHANGED", transition["to_state_id"]
            changes, after = {"current_state_id": to_state}, {"current_state_id": to_state}
        uow.update(mc.LearnerEnroll, e.PK, e.SK, changes, expected={"version": expected}, cond=_IN_PROGRESS,
                   conflict=courses.MicroCourseConflict(_STALE_LESSON))
        self._mc_event(uow, e, event_type, to_state, {"action": action, "from_state_id": state_id, "to_state_id": str(to_state),
                                                   "from_state_version": expected})
        return self._runtime(e, reader, state_version=expected + 1, **after)

    # ---------------------------------------------------------------------------- T23

    def submit_learning_item_response(self, conn, enrollment_id: str, student_id: str, learning_item_id: str,
                                      choice_index: int | None, *, gave_up: bool = False,
                                      idempotency_key: str | None = None) -> dict:
        """Grade a fixed multiple-choice item of the current state (the key is read here, server side, and never leaves the
        response unless the learner gave up) and record the response with its latest-response pointer, atomically."""
        def grade(e: mc.LearnerEnroll) -> dict:
            item = _content().get_grading_item(None, str(e.release_id), str(e.current_state_id), learning_item_id)
            if item is None:
                raise courses.MicroCourseNotFound("approved learning item not found in the current lesson state")
            is_correct, correct_index = courses.grade_learning_item(item, choice_index, gave_up)
            return {"kind": "QUIZ_RESPONSE", "item_id": str(item["learning_item_id"]), "state_id": e.current_state_id,
                    "gate_state": True,
                    "payload": courses.learning_item_event_payload(item, choice_index, is_correct, gave_up),
                    "response": courses.learning_item_response(item, choice_index, is_correct, gave_up, correct_index)}

        return self._respond(str(student_id), str(enrollment_id), idempotency_key, "micro_course.item_response",
                             {"learning_item_id": learning_item_id, "choice_index": choice_index, "gave_up": gave_up}, grade)

    def submit_activity_response(self, conn, enrollment_id: str, student_id: str, activity_id: str, *,
                                 choice_index: int | None = None, value: float | None = None, gave_up: bool = False,
                                 idempotency_key: str | None = None) -> dict:
        """Record and self-grade a static preview-quiz activity anywhere in the pinned release (never gates progress)."""
        def grade(e: mc.LearnerEnroll) -> dict:
            activity = _content().get_grading_activity(None, str(e.release_id), str(activity_id))
            if activity is None:
                raise courses.MicroCourseNotFound("quiz activity not found in this course release")
            is_correct, extra = courses.grade_activity(activity, choice_index, value, gave_up)
            return {"kind": "ACTIVITY_RESPONSE", "item_id": str(activity_id), "state_id": activity["state_id"],
                    "gate_state": False, "payload": courses.activity_event_payload(activity_id, is_correct, gave_up, extra),
                    "response": courses.activity_response(activity_id, is_correct, gave_up, activity["correctness_policy"])}

        return self._respond(str(student_id), str(enrollment_id), idempotency_key, "micro_course.activity_response",
                             {"activity_id": str(activity_id), "choice_index": choice_index, "value": value,
                              "gave_up": gave_up}, grade)

    def _respond(self, sid: str, eid: str, key: str | None, operation: str, body: dict, grade) -> dict:
        return _idempotent(sid, key, operation, {"enrollment_id": eid, **body}, lambda uow: self._build_response(uow, eid, grade))

    def _build_response(self, uow: LearnerUnitOfWork, eid: str, grade) -> dict:
        e = self._load_open(uow.student_id, eid)
        graded = grade(e)
        event_id, created = self._mc_event(uow, e, graded["kind"], graded["state_id"], graded["payload"])
        merged = {item_id: r.to_json() for item_id, r in (e.resolve("last_responses", dict[str, mc.LastResponse]) or {}).items()}
        merged[graded["item_id"]] = {"created_at": created, "event_id": event_id, "kind": graded["kind"],
                                     "state_id": str(graded["state_id"]), "payload": graded["payload"]}
        guard = _IN_PROGRESS
        if graded["gate_state"]:
            guard = ddb.Cond("#st = :in AND #cs = :cs", {"#st": "status", "#cs": "current_state_id"},
                             {":in": "IN_PROGRESS", ":cs": str(e.current_state_id)})
        seen = e.response_seq
        if seen is None:                        # never written by a response yet (migrated items): the counter must still be absent
            guard = ddb.Cond(f"({guard.expr}) AND attribute_not_exists(response_seq)", guard.names, guard.values)
        uow.update(mc.LearnerEnroll, e.PK, e.SK, {"last_responses": merged}, bump="response_seq",
                   expected={"response_seq": seen} if seen is not None else None, cond=guard,
                   remove=("last_responses_ref",) if e.last_responses_ref is not None else ())
        return graded["response"]

    # ---------------------------------------------------------------------------- T24 / A31 / A32

    def record_interaction_event(self, conn, enrollment_id: str, student_id: str, interaction_instance_id: str, *,
                                 event_type: str, semantic_action: str, control_key: str | None = None,
                                 object_id: str | None = None, before_state: dict | None = None,
                                 action_payload: dict | None = None, after_state: dict | None = None,
                                 idempotency_key: str | None = None) -> dict:
        """Append one raw interaction event (never updated) and, when ``MISCONCEPTION_EVIDENCE=on``, evaluate it
        deterministically and apply the matching approved misconception rule to the learner's running confidence."""
        sid, eid, instance = str(student_id), str(enrollment_id), str(interaction_instance_id)
        body = {"enrollment_id": eid, "interaction_instance_id": instance, "event_type": event_type,
                "semantic_action": semantic_action, "control_key": control_key, "object_id": object_id,
                "before_state": before_state, "action_payload": action_payload or {}, "after_state": after_state}
        return _idempotent(sid, idempotency_key, "micro_course.interaction_event", body,
                           lambda uow: self._build_interaction(uow, eid, instance, body))

    def _build_interaction(self, uow: LearnerUnitOfWork, eid: str, instance: str, body: dict) -> dict:
        e = self._load_open(uow.student_id, eid)
        found = _content().get_interaction_instance(None, instance)
        if found is None:
            raise courses.MicroCourseNotFound("interaction instance not found")
        event_type = courses._required_text(body["event_type"], "event_type").upper()
        action = courses._required_text(body["semantic_action"], "semantic_action").upper()
        evaluation = None
        if settings.misconception_evidence == "on":
            evaluation = ixrt.evaluate_submission(found.get("template_key"), event_type, body["action_payload"])
        ix_id, created = ddb.uuid7(), ddb.now_iso()
        uow.add(ddb.Check(CTX, e.PK, e.SK, _IN_PROGRESS, conflict=courses.MicroCourseConflict(_NOT_OPEN), label="enrollment"))
        uow.put_new(mc.LearnerIxevent(
            PK=uow.pk, SK=mc.ixevent_sk(e.enrollment_id, instance, created, ix_id), student_id=e.student_id,
            interaction_event_id=ix_id, enrollment_id=e.enrollment_id, course_state_id=e.current_state_id,
            interaction_instance_id=instance, event_type=event_type, semantic_action=action, control_key=body["control_key"],
            object_id=body["object_id"], before_state=body["before_state"], action_payload=body["action_payload"],
            after_state=body["after_state"], created_at=created,
            evaluation_outcome=evaluation["outcome"] if evaluation else None,
            error_signature=evaluation.get("error_signature") if evaluation else None))
        if evaluation and evaluation["outcome"] == "ERROR":
            self._apply_evidence(uow, ix_id, found, action, evaluation["error_signature"])
        return {"interaction_event_id": ix_id}

    def _apply_evidence(self, uow: LearnerUnitOfWork, ix_id: str, instance: dict, action: str, signature: str) -> None:
        """``interaction_runtime.apply_evidence`` on mb-learner: one MISCEVID row and the MISCSTATE running total, with the
        unchanged confidence maths. The approved rule comes from the content store's optional
        ``find_misconception_evidence_rule(conn, template_version_id, semantic_action, error_signature)``
        (a dict with ``misconception_id`` and ``evidence_weight``); no rule, no evidence."""
        finder = getattr(_content(), "find_misconception_evidence_rule", None)
        rule = finder(None, instance.get("interaction_template_version_id"), action, signature) if finder else None
        if rule is None:
            return
        mid, weight = str(rule["misconception_id"]), float(rule["evidence_weight"])
        state = typed.get(mc.LearnerMiscstate, uow.pk, mc.miscstate_sk(mid), consistent=True)
        before = float(state.confidence) if state else 0.0
        after = ixrt.next_confidence(before, weight)
        evidence_id, created = ddb.uuid7(), ddb.now_iso()
        uow.put_new(mc.LearnerMiscevid(
            PK=uow.pk, SK=mc.miscevid_sk(mid, created, evidence_id), student_id=uow.student_id, evidence_id=evidence_id,
            misconception_id=mid, interaction_event_id=ix_id, evidence_type="OBSERVED_ERROR", evidence_weight=weight,
            confidence_before=before, confidence_after=after, created_at=created))
        if state is None:
            uow.put_new(mc.LearnerMiscstate(
                PK=uow.pk, SK=mc.miscstate_sk(mid), student_id=uow.student_id, misconception_id=mid, confidence=after,
                confirmed=ixrt.is_confirmed(after), last_evidence_id=evidence_id, updated_at=created, version=1))
        else:
            uow.update(mc.LearnerMiscstate, state.PK, state.SK,
                       {"confidence": after, "confirmed": ixrt.is_confirmed(after), "last_evidence_id": evidence_id},
                       expected={"version": state.version})

    def list_item_interactions(self, conn, enrollment_id: str, student_id: str, interaction_instance_id: str) -> list[dict]:
        """A31: the learner's last ten events on one interaction of an enrollment, newest first."""
        page = typed.query(mc.LearnerIxevent, ddb.student_pk(student_id), forward=False, limit=assist.RECENT_INTERACTIONS,
                           sk_begins=mc.ixevent_prefix(enrollment_id, interaction_instance_id))
        return [{"event_type": ev.event_type, "semantic_action": ev.semantic_action, "control_key": ev.control_key,
                 "action_payload": ev.resolve("action_payload")} for ev in page.items]

    @staticmethod
    def _misconception_row(state: mc.LearnerMiscstate) -> dict:
        return {"misconception_id": str(state.misconception_id), "confidence": float(state.confidence),
                "confirmed": state.confirmed, "last_evidence_id": None if state.last_evidence_id is None
                else str(state.last_evidence_id), "updated_at": state.updated_at}

    def list_misconceptions(self, conn, student_id: str) -> dict:
        """A32: the learner's running confidence per misconception, strongest first."""
        rows = [self._misconception_row(s) for s in _pages(mc.LearnerMiscstate, ddb.student_pk(student_id),
                                                           sk_begins="MISCSTATE#")]
        rows.sort(key=lambda r: (-r["confidence"], r["misconception_id"]))
        return {"items": rows, "total": len(rows)}

    def get_misconception_state(self, conn, student_id: str, misconception_id: str) -> dict | None:
        state = typed.get(mc.LearnerMiscstate, ddb.student_pk(student_id), mc.miscstate_sk(misconception_id), consistent=True)
        return None if state is None else self._misconception_row(state)

    # ---------------------------------------------------------------------------- A28 / T25

    @staticmethod
    def _summary(e: mc.LearnerEnroll) -> dict:
        return courses.enrollment_summary(
            enrollment_id=e.enrollment_id, canonical_code=e.canonical_code, micro_course_id=e.micro_course_id,
            release_id=e.release_id, status=e.status, current_state_id=e.current_state_id, state_version=e.state_version,
            started_at=e.started_at, completed_at=e.completed_at)

    def list_enrollments(self, conn, student_id: str, status: str | None = None, limit: int = 100) -> dict:
        """A28: the learner's own enrollments, newest first. They share the ``ENROLL#`` prefix with their events, so the query
        reads the prefix and keeps the ENROLL items (the cost the design accepts for a rarely-called list)."""
        _status_filter(status)
        found = [item for item in _pages(
            "learner", ddb.student_pk(student_id), models=[mc.LearnerEnroll, mc.LearnerMcevent, mc.LearnerIxevent],
            sk_begins="ENROLL#") if isinstance(item, mc.LearnerEnroll)]
        found = [e for e in found if status is None or e.status == status]
        found.sort(key=lambda e: (e.started_at, str(e.enrollment_id)), reverse=True)
        return {"items": [self._summary(e) for e in found[:limit]], "total": len(found)}

    def abandon_enrollment(self, conn, enrollment_id: str, student_id: str, idempotency_key: str | None = None) -> dict:
        """Leave an in-progress enrollment for good (LRN-E12): a later enroll starts a fresh one."""
        sid, eid = str(student_id), str(enrollment_id)
        return _idempotent(sid, idempotency_key, "micro_course.abandon", {"enrollment_id": eid},
                           lambda uow: self._build_abandon(uow, eid))

    def _build_abandon(self, uow: LearnerUnitOfWork, eid: str) -> dict:
        e = self._load_open(uow.student_id, eid)
        uow.update(mc.LearnerEnroll, e.PK, e.SK, {"status": "ABANDONED", "GSI1SK": f"ABANDONED#{ddb.encode(e.started_at)}#{eid}"},
                   expected={"version": e.state_version}, cond=_IN_PROGRESS)
        uow.delete(mc.LearnerUniqueOpenEnroll, uow.pk, mc.open_enroll_sk(e.micro_course_id))
        self._mc_event(uow, e, "ABANDONED", e.current_state_id,
                    {"from_state_id": str(e.current_state_id), "from_state_version": e.state_version})
        return {**self._summary(e), "status": "ABANDONED", "state_version": e.state_version + 1}

    # ---------------------------------------------------------------------------- item-help

    def assist_item(self, conn, enrollment_id: str, student_id: str, item_kind: str, item_id: str, intent: str,
                    student_message: str | None, idempotency_key: str | None = None) -> dict:
        """Scoped "Help me?" / "Give up" for one item of the learner's CURRENT state. The grounding never carries an answer key;
        a give-up reveals it through the recorded ``gave_up`` response and nowhere else."""
        sid, eid = str(student_id), str(enrollment_id)
        e = self._load_open(sid, eid)
        reader = _content().get_pinned_micro_course_reader(None, str(e.release_id))
        state = next((s for s in reader["states"] if str(s["state_id"]) == str(e.current_state_id)), None)
        if state is None:
            raise courses.MicroCourseNotFound(_NOT_FOUND)
        grounding = assist.ground_from_state(
            state, item_kind, item_id, reveal=False, item_key=None, activity_key=None,
            recent_actions=lambda: self.list_item_interactions(None, eid, sid, item_id))
        grounding["state_context"] = assist.fallback_context_from_reader(state, reader)
        if intent == "give_up":
            outcome = None
            if item_kind == "learning_item":
                outcome = self.submit_learning_item_response(None, eid, sid, item_id, None, gave_up=True,
                                                             idempotency_key=idempotency_key)
            elif item_kind == "activity":
                outcome = self.submit_activity_response(None, eid, sid, item_id, gave_up=True, idempotency_key=idempotency_key)
            return assist.give_up_result(item_kind, outcome)
        return assist._help(item_kind, grounding, student_message)

    # ---------------------------------------------------------------------------- admin plane

    def get_enrollment_owner(self, conn, enrollment_id: str) -> str | None:
        """A30: the student an enrollment belongs to (admin routes carry no learner token), or None."""
        owner = typed.get(mc.LearnerEnrollOwner, mc.enroll_owner_pk(enrollment_id), "OWNER", consistent=True)
        return None if owner is None else str(owner.student_id)

    def reset_enrollment(self, conn, enrollment_id: str, to_state_id: str, actor: str) -> dict:
        """T26, admin: move an in-progress enrollment to another state of its pinned release; the actor is recorded on the
        RESET event (``actor_type`` ADMIN). Returns the learner's runtime view after the move."""
        owner = self.get_enrollment_owner(None, enrollment_id)
        if owner is None:
            raise courses.MicroCourseNotFound(_NOT_FOUND)

        def attempt() -> dict:
            uow = LearnerUnitOfWork(owner)
            e = self._load_open(owner, str(enrollment_id))
            reader = _content().get_pinned_micro_course_reader(None, str(e.release_id))
            if not any(str(s["state_id"]) == str(to_state_id) for s in reader["states"]):
                raise ValueError("target state does not belong to the enrollment's release")
            uow.update(mc.LearnerEnroll, e.PK, e.SK, {"current_state_id": str(to_state_id)},
                       expected={"version": e.state_version}, cond=_IN_PROGRESS)
            self._mc_event(uow, e, "RESET", to_state_id,
                        {"action": "RESET", "actor": actor, "from_state_id": str(e.current_state_id),
                         "to_state_id": str(to_state_id), "from_state_version": e.state_version}, actor="ADMIN")
            uow.commit()
            return self._runtime(e, reader, state_version=e.state_version + 1, current_state_id=to_state_id)

        return with_retries(attempt, on=(ConditionFailed,))

    def list_course_activity(self, conn, canonical_code: str) -> dict:
        """A29: live enrollment and quiz statistics of a course's published release, from the per-release index of
        enrollments and of events (GSI1 ``MC_RELEASE#<release>`` / ``MC_RELEASE#<release>#EVT``)."""
        reader = _content().get_micro_course_reader(None, courses._required_text(canonical_code, "canonical_code"))
        release_id = str(reader["release_id"])
        enrollments = list(_pages(mc.LearnerEnroll, f"MC_RELEASE#{release_id}", index="GSI1"))
        total = len(enrollments)
        completed = sum(1 for e in enrollments if e.status == "COMPLETED")
        reached: dict[str, set[str]] = {}
        attempts: dict[str, list[int]] = {}
        recent: list[mc.LearnerMcevent] = []
        for ev in _pages(mc.LearnerMcevent, f"MC_RELEASE#{release_id}#EVT", index="GSI1", forward=False):
            if len(recent) < RECENT_ACTIVITY:
                recent.append(ev)
            if ev.event_type in ("ENROLLED", "STATE_CHANGED") and ev.state_id is not None:
                reached.setdefault(str(ev.state_id), set()).add(str(ev.enrollment_id))
            elif ev.event_type == "ACTIVITY_RESPONSE":
                payload = ev.resolve("payload") or {}
                if payload.get("activity_id") is not None:
                    tally = attempts.setdefault(str(payload["activity_id"]), [0, 0])
                    tally[0] += 1
                    tally[1] += 1 if payload.get("is_correct") else 0
        states = sorted(reader["states"], key=lambda s: s["ordinal"])
        titles = {str(s["state_id"]): s["title"] for s in states}
        profiles = {str(p.student_id): p for p in typed.batch_get(
            LearnerProfile, [(ddb.student_pk(sid), "PROFILE") for sid in {str(ev.student_id) for ev in recent}])}

        def initials(student_id: str) -> str:
            p = profiles.get(student_id)
            return ((p.first_name[:1] + p.last_name[:1]).strip() if p else "") or "??"

        return {
            "canonical_code": canonical_code,
            "release_id": release_id,
            "version": reader["version"],
            "total_enrollments": total,
            "in_progress": sum(1 for e in enrollments if e.status == "IN_PROGRESS"),
            "completed": completed,
            "completion_rate": round(completed / total, 4) if total else None,
            "step_funnel": [{"state_id": str(s["state_id"]), "state_key": s["state_key"], "ordinal": s["ordinal"],
                             "title": s["title"], "reached_count": len(reached.get(str(s["state_id"]), ()))} for s in states],
            "quiz_accuracy": [
                {"activity_id": str(a["activity_id"]), "prompt": a["prompt"], "state_key": s["state_key"],
                 "attempts": attempts.get(str(a["activity_id"]), [0, 0])[0],
                 "correct": attempts.get(str(a["activity_id"]), [0, 0])[1]}
                for s in states for a in sorted(s.get("activities") or [], key=lambda a: a.get("ordinal") or 0)],
            "recent_activity": [{"event_id": str(ev.event_id), "event_type": ev.event_type, "created_at": ev.created_at,
                                 "state_title": titles.get(str(ev.state_id)), "student_initials": initials(str(ev.student_id))}
                                for ev in recent],
        }
