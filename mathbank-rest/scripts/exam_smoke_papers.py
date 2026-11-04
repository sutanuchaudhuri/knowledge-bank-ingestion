"""Read-only smoke check of the papers area of the DynamoDB exam store against a real environment (requirement 71 WP6).

    MB_AWS_PROFILE=aws-sutanu-admin DDB_ENV=dev .venv/bin/python scripts/exam_smoke_papers.py [--papers 30]

Only DynamoDB/S3 reads (GetItem, Query, BatchGetItem, GetObject); the script fails when it observes any other API operation and only
reaches store methods that read (``get_*`` / ``list_*``). PostgreSQL is never touched. Papers are sampled through the six
``PAPER_STATUS#<status>`` partitions of GSI2, never by a scan. Nothing is written, so the migrated data stays as it was.

Checks per sampled paper: every item under ``QUIZ#<qid>`` parses into its refined model (migrated shapes must validate); the PAPER_OWNER
pointer resolves to the learner; the counters equal what the partition holds (``question_count``, ``answered_count``, ``correct_count``,
``diagnosis_version``); ``get_quiz`` has the documented shape and carries no answer key, solution or explanation (no key attribute, no
solution text in the body), a foreign learner gets 404, and the paper shows up in ``list_my_quizzes``; the review is refused (409) for an
exam that is not submitted and, once open, scores exactly the correct responses; the event timeline and the generation events come back
in order and complete; the latest diagnosis is the highest version; quiz evidence per tag equals the QUIZ_EVIDENCE items of the
partition. Globally: the GSI2 status of every sampled PAPER equals its ``status``. Checks that need data the environment does not hold
are SKIP, not FAIL. Exit code 1 on a failed check.
"""
from __future__ import annotations

import argparse
import sys
import time
import uuid
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mathbank_rest import stores
from mathbank_rest.config import settings
from mathbank_rest.models import base
from mathbank_rest.models.manual import exam_papers as ep
from mathbank_rest.quiz_logic import SECRET_FIELDS, QuizError
from mathbank_rest.stores import ddb, typed
from mathbank_rest.stores.content import DynamoDBContentStore
from mathbank_rest.stores.exam.papers import PapersDynamoDB
from mathbank_rest.stores.learner import DynamoDBLearnerStore

FAILURES: list[str] = []
OPERATIONS: set[str] = set()
READS = {"get_item", "query", "batch_get_item", "get_object", "get_caller_identity", "head_object"}
STATUSES = ("GENERATING", "READY", "IN_PROGRESS", "SUBMITTED", "GRADED", "FAILED")
QUIZ_KEYS = {"quiz_id", "style", "title", "status", "instructions", "exam_mode", "time_limit_seconds", "started_at", "resume_question_ordinal",
             "questions"}
MODELS = [ep.ExamPaperItem, ep.ExamQuestionItem, ep.ExamQuestionSecretItem, ep.ExamResponseItem, ep.ExamDraft, ep.ExamResponseEventItem,
          ep.ExamGenerationEventItem, ep.ExamDiagnosisItem]


class Spy:
    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        attr = getattr(self._inner, name)
        if callable(attr) and not name.startswith("_"):
            OPERATIONS.add(name)
        return attr


class ReadOnly:
    """The only store surface the script uses: read methods of the papers area (a write would be a bug here)."""

    def __init__(self, store):
        self._store = store

    def __getattr__(self, name):
        if not name.startswith(stores.READ_PREFIXES):
            raise AssertionError(f"{name} is not a read")
        return getattr(self._store, name)


def check(ok: bool, label: str, detail: str = "") -> None:
    print(f"{'ok  ' if ok else 'FAIL'} {label}{(' - ' + detail) if detail else ''}")
    if not ok:
        FAILURES.append(label)


def skip(label: str, why: str) -> None:
    print(f"SKIP {label} - {why}")


def keys_of(value) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in keys_of(v)}
    if isinstance(value, list):
        return {k for v in value for k in keys_of(v)}
    return set()


def sample_papers(limit: int) -> list[tuple[str, str, str]]:
    """(student_id, quiz_id, status) from the status partitions of GSI2: the partition a paper's status says it is in."""
    out: list[tuple[str, str, str]] = []
    per = max(1, limit // len(STATUSES))
    for status in STATUSES:
        page = ddb.query_page("exam", f"PAPER_STATUS#{status}", index="GSI2", limit=per, forward=False, consistent=False)
        out += [(str(i["student_id"]), str(i["quiz_id"]), status) for i in page["items"]]
    return out


def partition(sid: str, qid: str) -> list:
    out, token = [], None
    while True:
        page = typed.query("exam", ddb.student_pk(sid), models=MODELS, sk_begins=f"QUIZ#{qid}", limit=200, next_token=token)
        out += page.items
        token = page.next_token
        if not token:
            return out


def evidence(sid: str, kind: str) -> list:
    out, token = [], None
    while True:
        page = typed.query(ep.ExamQuizEvidenceItem, ddb.student_pk(sid), sk_begins=f"QEVID#{kind}#", limit=200, next_token=token)
        out += page.items
        token = page.next_token
        if not token:
            return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--papers", type=int, default=30, help="papers sampled over the six GSI2 status partitions")
    args = parser.parse_args()
    real = ddb.client
    ddb.client = lambda service="dynamodb": Spy(real(service))      # records every API operation used
    print(f"env={settings.ddb_env} profile={settings.aws_profile or '(default chain)'} table={ddb.table_name('exam')}")
    reads = ReadOnly(PapersDynamoDB())
    papers = sample_papers(args.papers)
    check(bool(papers), "PAPER_STATUS partitions list papers", f"{len(papers)} sampled")
    parsed = 0
    with stores.override_store("content", DynamoDBContentStore()), stores.override_store("learner", DynamoDBLearnerStore()):
        for sid, qid, status in papers:
            tag = f"{qid[:8]} {status}"
            items = partition(sid, qid)
            parsed += len(items)
            paper = next((i for i in items if isinstance(i, ep.ExamPaperItem)), None)
            check(paper is not None and paper.status == status, f"{tag} PAPER parses and its GSI2 status = status")
            if paper is None:
                continue
            owner = typed.get(base.model_for("exam", "PAPER_OWNER"), ep.owner_pk(qid), "OWNER")
            check(owner is not None and str(owner.student_id) == sid, f"{tag} owner pointer")
            questions = [i for i in items if isinstance(i, ep.ExamQuestionItem)]
            secrets = [i for i in items if isinstance(i, ep.ExamQuestionSecretItem)]
            responses = [i for i in items if isinstance(i, ep.ExamResponseItem)]
            diagnoses = sorted((i for i in items if isinstance(i, ep.ExamDiagnosisItem)), key=lambda d: d.SK)
            check(paper.question_count == len(questions) == len(secrets) or status in ("GENERATING", "FAILED"),
                  f"{tag} question_count = QUESTION = QUESTION_SECRET", f"{paper.question_count}/{len(questions)}/{len(secrets)}")
            check(paper.answered_count == len(responses), f"{tag} answered_count = RESPONSE items", f"{paper.answered_count} vs {len(responses)}")
            check(paper.correct_count == sum(1 for r in responses if r.is_correct), f"{tag} correct_count = correct RESPONSE items")
            check(paper.diagnosis_version == len(diagnoses), f"{tag} diagnosis_version = DIAGNOSIS items")
            t0 = time.perf_counter()
            view = reads.get_quiz(UUID(qid), UUID(sid))
            check(set(view) == QUIZ_KEYS and len(view["questions"]) == len(questions), f"{tag} get_quiz shape",
                  f"{(time.perf_counter() - t0) * 1000:.0f} ms")
            check(not (keys_of(view) & SECRET_FIELDS), f"{tag} get_quiz carries no answer-key attribute")
            blob = repr(view)
            leaked = [s.resolve("solution_text") for s in secrets if s.resolve("solution_text") and len(s.resolve("solution_text")) > 25
                      and s.resolve("solution_text") in blob]
            check(not leaked, f"{tag} get_quiz carries no solution text")
            try:
                reads.get_quiz(UUID(qid), uuid.uuid4())
                check(False, f"{tag} foreign learner refused")
            except QuizError as exc:
                check(exc.status_code == 404, f"{tag} foreign learner refused")
            mine = reads.list_my_quizzes(UUID(sid), limit=200)
            check(qid in {r["quiz_id"] for r in mine} or len(mine) >= 200, f"{tag} listed in my quizzes", f"{len(mine)} papers")
            try:
                review = reads.get_review(UUID(qid), UUID(sid))
                check(review["score"] == paper.correct_count or status not in ("GRADED", "SUBMITTED"), f"{tag} review score",
                      f"{review['score']}/{review['total']}")
                check(review["total"] == len(questions) and review["answered_count"] == len(responses), f"{tag} review counts")
            except QuizError as exc:
                check(exc.status_code == 409 and paper.answer_disclosure != "IMMEDIATE" and status not in ("SUBMITTED", "GRADED"),
                      f"{tag} review refused while the exam is open", exc.code)
            events = [i for i in items if isinstance(i, ep.ExamResponseEventItem)]
            timeline = reads.get_response_events(UUID(qid), UUID(sid))
            check(len(timeline) == len(events) and [e["created_at"] for e in timeline] == sorted(e["created_at"] for e in timeline),
                  f"{tag} event timeline complete and ordered", f"{len(events)} events")
            gen = sorted((i for i in items if isinstance(i, ep.ExamGenerationEventItem)), key=lambda g: g.ordinal)
            listed = reads.list_generation_events(UUID(qid), UUID(sid))
            check([e["ordinal"] for e in listed] == [g.ordinal for g in gen], f"{tag} generation events complete and ordered", f"{len(gen)} events")
            if len(gen) > 1:
                since = reads.list_generation_events(UUID(qid), UUID(sid), since_ordinal=gen[0].ordinal)
                check([e["ordinal"] for e in since] == [g.ordinal for g in gen[1:]], f"{tag} generation events since an ordinal")
            if diagnoses:
                latest = reads.get_diagnosis(UUID(qid), UUID(sid))
                check(latest["time_management_verdict"] == diagnoses[-1].time_management_verdict, f"{tag} latest diagnosis = highest version")
            else:
                skip(f"{tag} diagnosis", "none written")
            if status == "GRADED":
                data = reads.get_paper_for_diagnosis(UUID(qid), UUID(sid))
                check(len(data["questions"]) == len(questions), f"{tag} diagnosis input", f"{len(data['concept_mastery_pre_exam'])} concepts")
        by_kind: dict[str, dict] = {"C": {}, "T": {}}
        for sid in {s for s, _, _ in papers}:
            for kind, groups in by_kind.items():
                for item in evidence(sid, kind):
                    groups.setdefault((sid, str(item.concept_id or item.technique_id)), []).append(item)
        for kind, groups in by_kind.items():
            for (sid, tag_id), rows in list(groups.items())[:40]:
                got = reads.get_quiz_evidence(UUID(sid), kind, UUID(tag_id))
                check(len(got) == len(rows) and [r["attempted_at"] for r in got] == sorted(r["attempted_at"] for r in got),
                      f"{sid[:8]} evidence {kind} {tag_id[:8]} = QUIZ_EVIDENCE items", f"{len(rows)} rows")
    check(parsed > 0, "migrated exam items parse into the refined models", f"{parsed} items")
    bad = OPERATIONS - READS
    check(not bad, "only read API operations were used", ", ".join(sorted(OPERATIONS)))
    print(f"{len(FAILURES)} failed" if FAILURES else "all checks passed")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
