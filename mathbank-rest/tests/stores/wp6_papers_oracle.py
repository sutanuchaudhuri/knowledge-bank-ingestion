"""The PostgreSQL side of the WP6 parity tests: ``quiz_runtime``'s SQL layer as an in-memory oracle.

``PostgresExamStore`` calls ``quiz_runtime.<function>`` at call time, so replacing those functions with the methods below makes
the REAL Postgres store (and the real routers) run without a database. Every method reproduces what the SQL function of the same name
returns and raises today (shapes, error codes, status machine incl. ``QUIZ_STRICT_EXAM_POLICY`` on), so the parity cases compare the
DynamoDB store with today's contract rather than with itself.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from uuid import UUID

from mathbank_rest import quiz_logic as ql
from mathbank_rest import quiz_runtime
from mathbank_rest.quiz_logic import QuizError

FUNCTIONS = ("start_paper", "import_paper", "generate_quiz", "finalize_paper", "fail_paper", "get_quiz", "list_my_quizzes",
             "save_exam_progress", "submit_response", "log_response_event", "get_response_events", "post_generation_event",
             "list_generation_events", "submit_exam", "get_review", "write_diagnosis", "get_diagnosis", "get_paper_for_diagnosis")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class QuizSqlOracle:
    def __init__(self, new_id: Callable[[], UUID], grade_text: Callable[[], tuple[bool, float, str]]) -> None:
        self.new_id, self.grade_text = new_id, grade_text
        self.papers: dict[str, dict] = {}
        self.questions: dict[str, list[dict]] = {}
        self.responses: dict[str, dict] = {}                 # by question_id
        self.drafts: dict[tuple[str, str], dict] = {}
        self.events: dict[str, list[dict]] = {}
        self.gen: dict[str, dict[int, dict]] = {}
        self.diagnoses: dict[str, dict] = {}
        self.mastery = {"concepts": {"counting": 0.5, "other": 0.9}, "techniques": {}}

    def install(self, monkeypatch) -> None:
        for name in FUNCTIONS:
            monkeypatch.setattr(quiz_runtime, name, getattr(self, name))

    # -- helpers ----------------------------------------------------------------------------------------------------------

    def _paper(self, quiz_id, student_id) -> dict:
        paper = self.papers.get(str(quiz_id))
        if paper is None or paper["student_id"] != str(student_id):
            raise QuizError("NOT_FOUND", "no quiz with that id for this student", status_code=404)
        return paper

    def _new_paper(self, student_id, **kw) -> dict:
        quiz_id = str(self.new_id())
        paper = {"quiz_id": quiz_id, "student_id": str(student_id), "status": "GENERATING", "started_at": None, "submitted_at": None,
                 "resume_question_ordinal": None, "instructions": "", "time_limit_seconds": None, "exam_mode": False, **kw}
        self.papers[quiz_id] = paper
        self.questions[quiz_id], self.events[quiz_id], self.gen[quiz_id] = [], [], {}
        return paper

    # -- creation ---------------------------------------------------------------------------------------------------------

    def start_paper(self, student_id, *, style, title, instructions="", requested_question_count, requested_question_types,
                    target_skill_slugs=None, target_concept_slugs=None, difficulty_band=None, generated_by, exam_mode=True,
                    time_limit_seconds=None) -> UUID:
        if style not in ql.STYLES:
            raise QuizError("INVALID_STYLE", f"style must be one of {ql.STYLES}")
        if not 1 <= requested_question_count <= 20:
            raise QuizError("INVALID_QUESTION_COUNT", "requested_question_count must be between 1 and 20")
        return UUID(self._new_paper(student_id, style=style, title=title, instructions=instructions, exam_mode=exam_mode,
                                    time_limit_seconds=time_limit_seconds)["quiz_id"])

    def finalize_paper(self, quiz_id, student_id, *, questions, generated_by=None, pool_topic=None, pool_concept_slugs=None) -> dict:
        if not questions:
            raise QuizError("NO_QUESTIONS", "at least one question is required")
        paper = self.papers.get(str(quiz_id))
        if not paper or paper["student_id"] != str(student_id) or paper["status"] != "GENERATING":
            raise QuizError("NOT_FOUND", "no GENERATING quiz with that id for this student — call start_paper first", status_code=404)
        for q in questions:
            if q["question_type"] not in ql.QUESTION_TYPES:
                raise QuizError("INVALID_QUESTION_TYPE", f"question_type must be one of {ql.QUESTION_TYPES}")
        for ordinal, q in enumerate(questions, start=1):
            self.questions[str(quiz_id)].append({**q, "question_id": str(self.new_id()), "ordinal": ordinal,
                                                 "complexity_signals": ql.complexity_signals(q)})
        paper["status"] = "READY"
        return self.get_quiz(quiz_id, student_id)

    def import_paper(self, student_id, *, style, title, requested_question_count, requested_question_types, generated_by,
                     questions, **kw) -> dict:
        if style not in ql.STYLES:
            raise QuizError("INVALID_STYLE", f"style must be one of {ql.STYLES}")
        if not questions:
            raise QuizError("NO_QUESTIONS", "at least one question is required")
        quiz_id = self.start_paper(student_id, style=style, title=title, requested_question_count=requested_question_count,
                                   requested_question_types=requested_question_types, generated_by=generated_by, **kw)
        return self.finalize_paper(quiz_id, student_id, questions=questions)

    def generate_quiz(self, student_id, *, style, question_count, question_types, target_skill_slugs=None, target_concept_slugs=None,
                      difficulty_band=None) -> dict:
        ql.validate_practice_request(style, question_count, question_types)
        paper = self._new_paper(student_id, style=style, title=f"{style.replace('_', ' ').title()} Practice Set", exam_mode=False)
        for i in range(question_count):
            qtype = question_types[i % len(question_types)]
            self.questions[paper["quiz_id"]].append({
                "question_id": str(self.new_id()), "ordinal": i + 1, "question_type": qtype, "prompt_text": f"Practice {i + 1}",
                "prompt_latex": None, "options": [{"key": "A", "text": "1"}, {"key": "B", "text": "2"}] if qtype == "MCQ" else None,
                "correct_answer": {"correct_key": "B"} if qtype == "MCQ" else {"expected_answer": "2", "grading_rubric": None},
                "solution_text": "because", "key_insight": "insight", "option_explanations": {}, "complexity_signals": None,
                "solution_steps": [], "difficulty_band": None})
        paper["status"] = "READY"
        return self.get_quiz(paper["quiz_id"], student_id)

    def fail_paper(self, quiz_id, student_id, error_message) -> dict:
        paper = self.papers.get(str(quiz_id))
        if not paper or paper["student_id"] != str(student_id):
            raise QuizError("NOT_FOUND", "paper not found", status_code=404)
        if paper["status"] == "GENERATING":
            paper["status"], paper["error_message"] = "FAILED", error_message[:500]
        return self.get_quiz(quiz_id, student_id)

    # -- reads of a paper -------------------------------------------------------------------------------------------------

    def get_quiz(self, quiz_id, student_id) -> dict:
        paper = self._paper(quiz_id, student_id)
        qid = paper["quiz_id"]
        return {
            "quiz_id": qid, "style": paper["style"], "title": paper["title"], "status": paper["status"],
            "instructions": paper["instructions"], "exam_mode": paper["exam_mode"], "time_limit_seconds": paper["time_limit_seconds"],
            "started_at": paper["started_at"], "resume_question_ordinal": paper["resume_question_ordinal"],
            "questions": [{
                "question_id": q["question_id"], "ordinal": q["ordinal"], "question_type": q["question_type"],
                "prompt_text": q["prompt_text"], "prompt_latex": q.get("prompt_latex"), "options": q.get("options") or None,
                "points": 1.0, "has_diagram": False,
                "student_response": (self.responses.get(q["question_id"]) or {}).get("raw_response"),
                "draft_response": (self.drafts.get((qid, q["question_id"])) or {}).get("raw_response"),
                "answered": q["question_id"] in self.responses} for q in self.questions[qid]]}

    def list_my_quizzes(self, student_id, *, limit=20) -> list[dict]:
        rows = [p for p in self.papers.values() if p["student_id"] == str(student_id)]
        return [{"quiz_id": p["quiz_id"], "style": p["style"], "title": p["title"], "status": p["status"], "created_at": _now(),
                 "question_count": len(self.questions[p["quiz_id"]]),
                 "correct_count": sum(1 for q in self.questions[p["quiz_id"]] if (self.responses.get(q["question_id"]) or {}).get("is_correct"))}
                for p in reversed(rows)][:limit]

    # -- progress and answers ---------------------------------------------------------------------------------------------

    def save_exam_progress(self, quiz_id, student_id, *, current_question_ordinal, question_id=None, raw_response=None) -> dict:
        paper = self._paper(quiz_id, student_id)
        if paper["status"] not in ("READY", "IN_PROGRESS"):
            raise QuizError("EXAM_NOT_EDITABLE", f"paper is {paper['status']} and cannot be changed", status_code=409)
        question = next((q for q in self.questions[paper["quiz_id"]] if q["ordinal"] == current_question_ordinal), None)
        if question is None:
            raise QuizError("NOT_FOUND", "no question with that ordinal in this paper", status_code=404)
        if question_id is not None and str(question["question_id"]) != str(question_id):
            raise QuizError("INVALID_DRAFT", "question_id does not match current_question_ordinal")
        if raw_response is not None:
            ql.validate_exam_draft(question, raw_response)
            self.drafts[(paper["quiz_id"], question["question_id"])] = {"raw_response": raw_response}
        paper["resume_question_ordinal"] = current_question_ordinal
        paper["started_at"] = paper["started_at"] or _now()
        paper["status"] = "IN_PROGRESS"
        return {"saved": True, "current_question_ordinal": current_question_ordinal}

    def submit_response(self, quiz_id, question_id, student_id, *, raw_response, time_spent_seconds=None) -> dict:
        paper = self._paper(quiz_id, student_id)
        if paper["status"] not in ("READY", "IN_PROGRESS"):
            if str(question_id) in self.responses:
                raise QuizError("ALREADY_ANSWERED", "this question already has a response", status_code=409)
            raise QuizError("EXAM_NOT_EDITABLE", f"paper is {paper['status']} and cannot be answered", status_code=409)
        question = next((q for q in self.questions[paper["quiz_id"]] if q["question_id"] == str(question_id)), None)
        if question is None:
            raise QuizError("NOT_FOUND", "no such question in this quiz", status_code=404)
        if str(question_id) in self.responses:
            raise QuizError("ALREADY_ANSWERED", "this question already has a response", status_code=409)
        is_correct, method, confidence, feedback = ql.grade_answer(question, raw_response, grade_free_text=lambda *a: self._text(a))
        self.new_id()                                                         # the DynamoDB response carries an id too
        self.responses[str(question_id)] = {"raw_response": raw_response, "is_correct": is_correct, "feedback": feedback,
                                            "time_spent_seconds": time_spent_seconds, "grading_method": method}
        self.drafts.pop((paper["quiz_id"], str(question_id)), None)
        paper["status"], paper["started_at"] = "IN_PROGRESS", paper["started_at"] or _now()
        result = {"is_correct": is_correct, "grading_method": method, "confidence": confidence, "feedback": feedback,
                  "solution": {"solution_text": question["solution_text"], "key_insight": question.get("key_insight", "")}}
        answered = sum(1 for q in self.questions[paper["quiz_id"]] if q["question_id"] in self.responses)
        return ql.respond_view(result, answer_disclosure="AFTER_SUBMIT" if paper["exam_mode"] else "IMMEDIATE", question_id=question_id,
                               answered_count=answered)

    def _text(self, _args) -> dict:
        ok, confidence, feedback = self.grade_text()
        return {"is_correct": ok, "confidence": confidence, "feedback": feedback}

    # -- events ------------------------------------------------------------------------------------------------------------

    def log_response_event(self, quiz_id, question_id, student_id, *, event_type, option_key=None, client_timestamp_ms=None) -> dict:
        if event_type not in ql.EVENT_TYPES:
            raise QuizError("INVALID_EVENT_TYPE", f"event_type must be one of {ql.EVENT_TYPES}")
        paper = self._paper(quiz_id, student_id)
        question = next((q for q in self.questions[paper["quiz_id"]] if q["question_id"] == str(question_id)), None)
        if question is None:
            raise QuizError("NOT_FOUND", "no such question in this quiz", status_code=404)
        self.events[paper["quiz_id"]].append({"question_id": question["question_id"], "ordinal": question["ordinal"], "event_type": event_type,
                                              "option_key": option_key, "client_timestamp_ms": client_timestamp_ms, "created_at": _now()})
        if event_type == "SKIP":
            self.drafts.pop((paper["quiz_id"], str(question_id)), None)
        return {"event_id": str(self.new_id()), "event_type": event_type, "option_key": option_key}

    def get_response_events(self, quiz_id, student_id) -> list[dict]:
        return list(self.events[self._paper(quiz_id, student_id)["quiz_id"]])

    def post_generation_event(self, quiz_id, *, ordinal, phase, status, question_ordinal=None, detail="") -> None:
        self.new_id()                                                         # the DynamoDB event carries an id too: keep the ids in step
        self.gen[str(quiz_id)].setdefault(ordinal, {"ordinal": ordinal, "phase": phase, "status": status, "question_ordinal": question_ordinal,
                                                    "detail": detail, "created_at": _now()})

    def list_generation_events(self, quiz_id, student_id, *, since_ordinal=0) -> list[dict]:
        events = self.gen[self._paper(quiz_id, student_id)["quiz_id"]]
        return [events[o] for o in sorted(events) if o > since_ordinal]

    # -- submit, review, diagnosis ----------------------------------------------------------------------------------------

    def submit_exam(self, quiz_id, student_id) -> dict:
        paper = self._paper(quiz_id, student_id)
        if paper["status"] not in ("GENERATING", "READY", "IN_PROGRESS"):
            raise QuizError("ALREADY_SUBMITTED", f"paper is already {paper['status']}", status_code=409)
        if paper["status"] == "GENERATING":
            raise QuizError("EXAM_NOT_EDITABLE", "paper is still GENERATING and cannot be submitted", status_code=409)
        paper["status"], paper["submitted_at"] = "SUBMITTED", paper["submitted_at"] or _now()
        for key in [k for k in self.drafts if k[0] == paper["quiz_id"]]:
            del self.drafts[key]
        return self.get_review(quiz_id, student_id)

    def get_review(self, quiz_id, student_id) -> dict:
        paper = self._paper(quiz_id, student_id)
        if paper["exam_mode"] and paper["status"] not in ("SUBMITTED", "GRADED"):
            raise QuizError("EXAM_IN_PROGRESS", "this exam paper must be submitted before it can be reviewed", status_code=409)
        rows = []
        for q in self.questions[paper["quiz_id"]]:
            r = self.responses.get(q["question_id"])
            rows.append({**q, "points": 1.0, "raw_response": r["raw_response"] if r else None, "is_correct": r["is_correct"] if r else None,
                         "grading_feedback": r["feedback"] if r else None, "option_explanations": q.get("option_explanations") or {},
                         "complexity_signals": q.get("complexity_signals"), "difficulty_band": q.get("difficulty_band"),
                         "options": q.get("options") or None})
        if paper["status"] == "SUBMITTED" or (any(r["raw_response"] is not None for r in rows) and all(r["raw_response"] is not None for r in rows)):
            paper["status"], paper["submitted_at"] = "GRADED", paper["submitted_at"] or _now()
        return ql.review_view(paper, rows, self._sources())

    def _sources(self) -> dict[str, list[dict]]:
        """The SQL joined ``question_source`` to the corpus: only codes that exist, ranked, with competition / year / URL."""
        from wp6_papers_support import CODES

        out: dict[str, list[dict]] = {}
        for questions in self.questions.values():
            for q in questions:
                seen: list[str] = []
                for s in (q.get("inspiration_sources") or [])[:5]:
                    if s["canonical_code"] in CODES and s["canonical_code"] not in seen:
                        seen.append(s["canonical_code"])
                        comp, year, _ = CODES[s["canonical_code"]]
                        out.setdefault(q["question_id"], []).append({
                            "canonical_code": s["canonical_code"], "competition": comp, "year": year,
                            "source_url": f"https://example.org/{s['canonical_code']}", "note": s.get("note", "")})
        return out

    def write_diagnosis(self, quiz_id, student_id, *, time_management_verdict, pacing_notes, reasoning_guidance, improvement_areas,
                        generated_by) -> dict:
        paper = self._paper(quiz_id, student_id)
        if paper["status"] != "GRADED":
            raise QuizError("NOT_GRADED", "the paper must be fully graded before a diagnosis can be written", status_code=409)
        self.diagnoses[paper["quiz_id"]] = {
            "quiz_id": paper["quiz_id"], "time_management_verdict": time_management_verdict, "pacing_notes": pacing_notes,
            "reasoning_guidance": reasoning_guidance, "improvement_areas": improvement_areas, "generated_by": generated_by,
            "created_at": _now()}
        return self.get_diagnosis(quiz_id, student_id)

    def get_diagnosis(self, quiz_id, student_id) -> dict:
        paper = self._paper(quiz_id, student_id)
        if paper["quiz_id"] not in self.diagnoses:
            raise QuizError("NOT_FOUND", "no diagnosis yet for this paper", status_code=404)
        return dict(self.diagnoses[paper["quiz_id"]])

    def get_paper_for_diagnosis(self, quiz_id, student_id) -> dict:
        from wp6_papers_support import CONCEPTS, TECHNIQUES

        paper = self._paper(quiz_id, student_id)
        out = []
        for q in self.questions[paper["quiz_id"]]:
            r = self.responses.get(q["question_id"])
            out.append({"question_id": q["question_id"], "ordinal": q["ordinal"], "question_type": q["question_type"],
                        "prompt_text": q["prompt_text"], "difficulty_band": q.get("difficulty_band"),
                        "is_correct": r["is_correct"] if r else None, "time_spent_seconds": r["time_spent_seconds"] if r else None,
                        "student_response": r["raw_response"] if r else None, "solution_text": q["solution_text"],
                        "key_insight": q.get("key_insight"),
                        "concept_slugs": sorted(set(q.get("concept_slugs") or []) & set(CONCEPTS)),
                        "technique_slugs": sorted(set(q.get("technique_slugs") or []) & set(TECHNIQUES))})
        concepts = {s for q in out for s in q["concept_slugs"]}
        techniques = {s for q in out for s in q["technique_slugs"]}
        return {"quiz_id": paper["quiz_id"], "style": paper["style"], "time_limit_seconds": paper["time_limit_seconds"],
                "started_at": paper["started_at"], "submitted_at": paper["submitted_at"], "questions": out,
                "concept_mastery_pre_exam": {s: v for s, v in self.mastery["concepts"].items() if s in concepts},
                "technique_mastery_pre_exam": {s: v for s, v in self.mastery["techniques"].items() if s in techniques}}

