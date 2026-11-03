"""ExamUnitOfWork: the learner unit of work (atomic <= 100 items, ownership, typed updates, append-only rules) on ``mb-exam``.

Exam data of a learner lives under ``STUDENT#<sid>`` with SK prefix ``QUIZ#<qid>`` (requirement 70 C2 section 3), so the ownership rule
is the same. Append-only here: RESPONSE_EVENT, GENERATION_EVENT, DIAGNOSIS (a new version is a new item). RESPONSE and QUIZ_EVIDENCE
are rewritten by an admin regrade, so they are NOT append-only.
"""
from __future__ import annotations

from mathbank_rest.stores.learner.uow import LearnerUnitOfWork, run_idempotent, with_retries

__all__ = ["APPEND_ONLY", "CTX", "ExamUnitOfWork", "run_idempotent", "with_retries"]

CTX = "exam"
APPEND_ONLY = frozenset({"RESPONSE_EVENT", "GENERATION_EVENT", "DIAGNOSIS"})


class ExamUnitOfWork(LearnerUnitOfWork):
    CTX = CTX
    APPEND_ONLY = APPEND_ONLY
