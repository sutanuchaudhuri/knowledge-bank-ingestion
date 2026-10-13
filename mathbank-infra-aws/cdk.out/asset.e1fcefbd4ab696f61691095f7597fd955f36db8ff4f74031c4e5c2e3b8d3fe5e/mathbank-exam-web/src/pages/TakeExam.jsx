import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PageHeader, Pill, Callout, Button } from "../components/ui.jsx";
import { MathText } from "../components/MathText.jsx";
import { api } from "../api.js";

function formatClock(totalSeconds) {
  if (totalSeconds == null) return null;
  const s = Math.max(0, Math.floor(totalSeconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const pad = (n) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(sec)}` : `${m}:${pad(sec)}`;
}

export default function TakeExam() {
  const { quizId } = useParams();
  const navigate = useNavigate();
  const [paper, setPaper] = useState(null);
  const [error, setError] = useState(null);
  const [openIndex, setOpenIndex] = useState(0);
  // Per-question UI state: draft selection/text not yet submitted to grading.
  const [drafts, setDrafts] = useState({});
  // Questions whose final answer (or skip) has already been recorded — locked from further edits.
  const [confirmed, setConfirmed] = useState({});
  const [viewedAt, setViewedAt] = useState({});
  const [remaining, setRemaining] = useState(null);
  const [showSubmitWarning, setShowSubmitWarning] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const autoSubmitted = useRef(false);
  // Synchronous mirrors of per-question confirm state, since `doSubmit`'s sweep must
  // never rely on React's (batched, async) `confirmed` state to decide whether a
  // question still needs submitting — racing the two would double-POST the same
  // question and hit quiz.response's UNIQUE(question_id) constraint as a raw 500.
  const confirmedRef = useRef({});
  const pendingConfirm = useRef({});

  useEffect(() => {
    api.getPaper(quizId).then((p) => {
      if (p.status === "SUBMITTED" || p.status === "GRADED") {
        navigate(`/exam/${quizId}/review`, { replace: true });
        return;
      }
      setPaper(p);
    }).catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [quizId]);

  useEffect(() => {
    if (!paper || paper.time_limit_seconds == null) return;
    const startedAt = paper.started_at ? new Date(paper.started_at).getTime() : Date.now();
    const elapsed = (Date.now() - startedAt) / 1000;
    setRemaining(Math.max(0, paper.time_limit_seconds - elapsed));
  }, [paper]);

  useEffect(() => {
    if (remaining == null) return;
    const timer = setInterval(() => {
      setRemaining((r) => (r == null ? null : Math.max(0, r - 1)));
    }, 1000);
    return () => clearInterval(timer);
  }, [remaining == null]);

  useEffect(() => {
    if (remaining === 0 && !autoSubmitted.current && paper) {
      autoSubmitted.current = true;
      doSubmit(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [remaining]);

  const questions = paper?.questions || [];
  const answeredCount = Object.keys(confirmed).length;

  function markViewed(questionId) {
    if (!viewedAt[questionId]) {
      setViewedAt((v) => ({ ...v, [questionId]: Date.now() }));
      api.logEvent(quizId, questionId, { event_type: "VIEW" }).catch(() => {});
    }
  }

  function openQuestion(index) {
    setOpenIndex(index);
    const q = questions[index];
    if (q) markViewed(q.question_id);
  }

  function selectOption(question, optionKey) {
    if (confirmed[question.question_id]) return;
    const prev = drafts[question.question_id]?.selected_key;
    if (prev && prev !== optionKey) {
      api.logEvent(quizId, question.question_id, { event_type: "DESELECT_OPTION", option_key: prev }).catch(() => {});
    }
    api.logEvent(quizId, question.question_id, { event_type: "SELECT_OPTION", option_key: optionKey }).catch(() => {});
    setDrafts((d) => ({ ...d, [question.question_id]: { selected_key: optionKey } }));
  }

  function updateText(question, value) {
    if (confirmed[question.question_id]) return;
    setDrafts((d) => ({ ...d, [question.question_id]: { response_text: value } }));
    api.logEvent(quizId, question.question_id, { event_type: "TEXT_CHANGE" }).catch(() => {});
  }

  async function confirmAndAdvance(index) {
    const question = questions[index];
    if (pendingConfirm.current[question.question_id]) return pendingConfirm.current[question.question_id];
    const run = (async () => {
      const draft = drafts[question.question_id];
      const timeSpent = viewedAt[question.question_id]
        ? Math.round((Date.now() - viewedAt[question.question_id]) / 1000)
        : null;
      try {
        if (draft && (draft.selected_key || draft.response_text)) {
          await api.respond(quizId, question.question_id, { ...draft, time_spent_seconds: timeSpent });
        } else {
          await api.logEvent(quizId, question.question_id, { event_type: "SKIP" });
        }
        confirmedRef.current[question.question_id] = true;
        setConfirmed((c) => ({ ...c, [question.question_id]: true }));
        if (index + 1 < questions.length) {
          openQuestion(index + 1);
        }
      } catch (err) {
        setError(err.message);
      }
    })();
    pendingConfirm.current[question.question_id] = run;
    try {
      await run;
    } finally {
      delete pendingConfirm.current[question.question_id];
    }
  }

  async function doSubmit(auto = false) {
    setSubmitting(true);
    try {
      // Confirm any still-open, not-yet-confirmed question with whatever draft it has.
      // Await any confirm already in flight for a question before deciding whether it
      // still needs submitting here — using the synchronous confirmedRef, not the
      // (possibly stale, batched) React `confirmed` state.
      for (let i = 0; i < questions.length; i++) {
        const q = questions[i];
        if (pendingConfirm.current[q.question_id]) {
          await pendingConfirm.current[q.question_id];
        }
        if (!confirmedRef.current[q.question_id]) {
          const draft = drafts[q.question_id];
          const timeSpent = viewedAt[q.question_id]
            ? Math.round((Date.now() - viewedAt[q.question_id]) / 1000)
            : null;
          if (draft && (draft.selected_key || draft.response_text)) {
            await api.respond(quizId, q.question_id, { ...draft, time_spent_seconds: timeSpent });
          } else {
            await api.logEvent(quizId, q.question_id, { event_type: "SKIP" });
          }
          confirmedRef.current[q.question_id] = true;
        }
      }
      await api.submitExam(quizId);
      navigate(`/exam/${quizId}/review`);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
      setShowSubmitWarning(false);
    }
  }

  const unanswered = questions.length - answeredCount;
  const clock = useMemo(() => formatClock(remaining), [remaining]);

  if (error) return <div className="mb-shell"><Callout tone="danger" icon="exclamation-triangle">{error}</Callout></div>;
  if (!paper) return <div className="mb-shell">Loading…</div>;

  return (
    <div className="mb-shell" style={{ paddingBottom: "5rem" }}>
      <PageHeader
        icon="journal-check"
        title={paper.title}
        subtitle={paper.instructions || "Answer each question, then move to the next — once you move on, your answer is locked in."}
        actions={
          clock && (
            <span className={`mb-timer ${remaining < 60 ? "mb-timer-low" : ""}`}>
              <i className="bi bi-stopwatch" aria-hidden="true" /> {clock}
            </span>
          )
        }
      />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
        <Pill tone="primary" icon="list-check">{answeredCount} of {questions.length} attempted</Pill>
        <div className="mb-progress-bar" style={{ flex: 1, margin: "0 1rem" }}>
          <div style={{ width: `${(answeredCount / Math.max(1, questions.length)) * 100}%` }} />
        </div>
      </div>

      {questions.map((q, index) => {
        const isOpen = openIndex === index;
        const isConfirmed = Boolean(confirmed[q.question_id]);
        const draft = drafts[q.question_id] || {};
        return (
          <div className="mb-accordion-item" key={q.question_id}>
            <button className="mb-accordion-header" onClick={() => openQuestion(index)}>
              <span>
                Question {q.ordinal}
                {isConfirmed && <Pill tone="success" icon="check2" style={{ marginLeft: "0.5rem" }}>Answered</Pill>}
              </span>
              <i className={`bi bi-chevron-${isOpen ? "up" : "down"}`} aria-hidden="true" />
            </button>
            {isOpen && (
              <div className="mb-accordion-body">
                <p style={{ fontWeight: 500 }}>
                  <MathText text={q.prompt_text} />
                </p>
                {q.question_type === "MCQ" && q.options && (
                  <div>
                    {q.options.map((opt) => (
                      <div
                        key={opt.key}
                        className={`mb-option ${draft.selected_key === opt.key ? "mb-option-selected" : ""}`}
                        onClick={() => selectOption(q, opt.key)}
                        role="radio"
                        aria-checked={draft.selected_key === opt.key}
                        tabIndex={0}
                      >
                        <strong>{opt.key}.</strong> <MathText text={opt.text} />
                      </div>
                    ))}
                  </div>
                )}
                {q.question_type !== "MCQ" && (
                  <textarea
                    className="mb-textarea"
                    rows={5}
                    disabled={isConfirmed}
                    value={draft.response_text || ""}
                    onChange={(e) => updateText(q, e.target.value)}
                    placeholder="Write your full response…"
                  />
                )}
                {!isConfirmed && (
                  <div style={{ marginTop: "1rem" }}>
                    <Button tone="primary" icon="arrow-right" onClick={() => confirmAndAdvance(index)}>
                      {index + 1 < questions.length ? "Confirm & next" : "Confirm"}
                    </Button>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}

      <div className="mb-sticky-footer mb-no-print">
        <span style={{ fontSize: "0.85rem", color: "var(--mb-muted)" }}>
          {unanswered > 0 ? `${unanswered} question${unanswered === 1 ? "" : "s"} not yet answered` : "All questions answered"}
        </span>
        <Button tone="primary" icon="send" onClick={() => setShowSubmitWarning(true)}>
          Submit exam
        </Button>
      </div>

      {showSubmitWarning && (
        <div className="mb-modal-backdrop">
          <div className="mb-modal">
            <h3 style={{ marginTop: 0 }}>Submit this exam?</h3>
            <p>
              {unanswered > 0
                ? `You have ${unanswered} unanswered question${unanswered === 1 ? "" : "s"}. Once submitted, you cannot change any answers.`
                : "Once submitted, you cannot change any answers."}
            </p>
            <div style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
              <Button tone="ghost" onClick={() => setShowSubmitWarning(false)} disabled={submitting}>
                Keep working
              </Button>
              <Button tone="danger" icon="send" onClick={() => doSubmit(false)} disabled={submitting}>
                {submitting ? "Submitting…" : "Submit now"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
