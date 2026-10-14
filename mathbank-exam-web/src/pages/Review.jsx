import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { PageHeader, Pill, Callout, Button } from "../components/ui.jsx";
import { MathText } from "../components/MathText.jsx";
import { api } from "../api.js";

export default function Review() {
  const { quizId } = useParams();
  const [review, setReview] = useState(null);
  const [diagnosis, setDiagnosis] = useState(null);
  const [diagnosisLoading, setDiagnosisLoading] = useState(true);
  const [error, setError] = useState(null);
  // Guards against a duplicate diagnosis-generation call (a real, billed OpenAI
  // request) if this effect is ever invoked twice in quick succession, e.g.
  // React 18 StrictMode's dev-only double-invoke, or a fast remount.
  const diagnosisRequested = useRef(false);

  useEffect(() => {
    api.review(quizId).then(setReview).catch((err) => setError(err.message));
  }, [quizId]);

  useEffect(() => {
    if (diagnosisRequested.current) return;
    diagnosisRequested.current = true;
    // The diagnosis is synthesized once, on demand — try to fetch an existing one
    // first, and only generate (a real, billed OpenAI call) if none exists yet.
    (async () => {
      try {
        const existing = await api.getDiagnosis(quizId);
        setDiagnosis(existing);
      } catch {
        try {
          const generated = await api.diagnose(quizId);
          setDiagnosis(generated);
        } catch (err) {
          setError((e) => e || err.message);
        }
      } finally {
        setDiagnosisLoading(false);
      }
    })();
  }, [quizId]);

  if (error) return <div className="mb-shell"><Callout tone="danger" icon="exclamation-triangle">{error}</Callout></div>;
  if (!review) return <div className="mb-shell">Loading…</div>;

  const scorePct = Math.round((review.score / Math.max(1, review.total)) * 100);

  return (
    <div className="mb-shell">
      <PageHeader
        icon="journal-check"
        title={`${review.title} — Review`}
        subtitle={`Score: ${review.score} of ${review.total} (${scorePct}%)`}
        actions={
          <Button tone="ghost" icon="printer" onClick={() => window.print()}>
            Export / Print
          </Button>
        }
      />

      {diagnosisLoading && (
        <Callout tone="primary" icon="hourglass-split">Synthesizing your performance diagnosis…</Callout>
      )}
      {diagnosis && (
        <div className="mb-card" style={{ marginBottom: "1.5rem" }}>
          <h2 style={{ marginTop: 0, fontSize: "1.05rem" }}>
            <i className="bi bi-graph-up-arrow" aria-hidden="true" /> Performance diagnosis
          </h2>
          <Callout tone="info" icon="stopwatch">{diagnosis.time_management_verdict}</Callout>
          {diagnosis.pacing_notes?.length > 0 && (
            <>
              <h3 style={{ fontSize: "0.9rem" }}>Pacing notes</h3>
              <ul>
                {diagnosis.pacing_notes.map((n, i) => (
                  <li key={i}>Q{n.question_ordinal}: {n.note} {n.time_spent_seconds != null && `(${n.time_spent_seconds}s)`}</li>
                ))}
              </ul>
            </>
          )}
          {diagnosis.reasoning_guidance?.length > 0 && (
            <>
              <h3 style={{ fontSize: "0.9rem" }}>How to think about the ones you missed</h3>
              {diagnosis.reasoning_guidance.map((n, i) => (
                <Callout key={i} tone="warning" icon="lightbulb">Q{n.question_ordinal}: {n.guidance}</Callout>
              ))}
            </>
          )}
          {diagnosis.improvement_areas?.length > 0 && (
            <>
              <h3 style={{ fontSize: "0.9rem" }}>Areas to improve</h3>
              {diagnosis.improvement_areas.map((a, i) => (
                <div key={i} style={{ marginBottom: "0.5rem" }}>
                  <Pill tone={a.current_mastery_tier === "critical" ? "danger" : a.current_mastery_tier === "developing" ? "warning" : "neutral"}>
                    {a.concept_or_technique} — {a.current_mastery_tier}
                  </Pill>
                  <p style={{ fontSize: "0.85rem", margin: "0.25rem 0 0", color: "var(--mb-muted)" }}>{a.evidence}</p>
                </div>
              ))}
            </>
          )}
        </div>
      )}

      <h2 style={{ fontSize: "1.05rem" }}>
        <i className="bi bi-list-check" aria-hidden="true" /> All questions and solutions
      </h2>
      {review.questions.map((q) => (
        <div className="mb-card" key={q.question_id} style={{ marginBottom: "1.25rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div className="mb-question-prompt" style={{ fontWeight: 500, marginTop: 0 }}>
              Q{q.ordinal}. <MathText text={q.prompt_text} />
            </div>
            <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap", justifyContent: "flex-end" }}>
              {q.student_response != null ? (
                <Pill tone={q.is_correct ? "success" : "danger"} icon={q.is_correct ? "check2" : "x-lg"}>
                  {q.is_correct ? "Correct" : "Incorrect"}
                </Pill>
              ) : (
                <Pill tone="neutral" icon="dash-circle">Not answered</Pill>
              )}
              {q.difficulty_band && (
                <Pill tone="neutral" icon="bar-chart-steps">
                  {q.difficulty_band}
                  {q.complexity_signals?.step_count ? ` · ${q.complexity_signals.step_count} steps` : ""}
                </Pill>
              )}
            </div>
          </div>

          {q.question_type === "MCQ" && q.options && (
            <div>
              {q.options.map((opt) => {
                const isCorrect = q.correct_answer?.correct_key === opt.key;
                const isSelected = q.student_response?.selected_key === opt.key;
                let cls = "mb-option";
                if (isCorrect) cls += " mb-option-correct";
                else if (isSelected) cls += " mb-option-incorrect";
                return (
                  <div className={cls} key={opt.key}>
                    <div style={{ flex: 1 }}>
                      <strong>{opt.key}.</strong> <MathText text={opt.text} />
                      {isSelected && <Pill tone="info" style={{ marginLeft: "0.5rem" }}>Your answer</Pill>}
                      {isCorrect && <Pill tone="success" style={{ marginLeft: "0.5rem" }}>Correct answer</Pill>}
                      {q.option_explanations?.[opt.key] && (
                        <div style={{ fontSize: "0.85rem", margin: "0.35rem 0 0", color: "var(--mb-muted)" }}>
                          <MathText text={q.option_explanations[opt.key]} />
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {q.question_type !== "MCQ" && q.student_response?.response_text && (
            <Callout tone="info" icon="chat-left-text">
              Your response: <MathText text={q.student_response.response_text} />
            </Callout>
          )}
          {q.feedback && <Callout tone={q.is_correct ? "success" : "warning"} icon="chat-square-text">{q.feedback}</Callout>}

          <h4 style={{ fontSize: "0.85rem", marginBottom: "0.25rem" }}>Full solution</h4>
          <div style={{ fontSize: "0.9rem" }}><MathText text={q.solution_text} /></div>
          {q.key_insight && (
            <Callout tone="primary" icon="stars">{q.key_insight}</Callout>
          )}
          {q.inspiration_sources?.length > 0 && (
            <Callout tone="info" icon="bookmark-star">
              <strong>Inspired by</strong> (newly composed, never copied):
              <ul style={{ margin: "0.35rem 0 0", paddingLeft: "1.1rem" }}>
                {q.inspiration_sources.map((s, i) => (
                  <li key={i} style={{ fontSize: "0.85rem" }}>
                    {s.source_url ? (
                      <a href={s.source_url} target="_blank" rel="noreferrer">{s.canonical_code}</a>
                    ) : (
                      s.canonical_code
                    )}
                    {" "}({s.competition} {s.year}) — {s.note}
                  </li>
                ))}
              </ul>
            </Callout>
          )}
        </div>
      ))}
    </div>
  );
}
