"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import MathText from "../../../../_components/MathText.jsx";
import { Callout, Icon, PageHeader, Pill, StatCard } from "../../../../_components/ui.jsx";

async function load(url) {
  const response = await fetch(url, { cache: "no-store" });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(body.error?.message || body.error || `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return body;
}

export default function QuizReviewPage() {
  const params = useParams();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const [review, setReview] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    load(`/api/rest/quiz/${id}/review`).then(setReview).catch(setError);
  }, [id]);

  if (error?.status === 401) {
    return <Callout tone="neutral" icon="lock">Please <Link href="/login">sign in</Link> to review this quiz.</Callout>;
  }
  if (error) return <Callout tone="danger" role="alert">{error.message}</Callout>;
  if (!review) return <p className="text-secondary"><span className="spinner-border spinner-border-sm me-2" />Loading…</p>;

  const pct = review.total ? Math.round((review.score / review.total) * 100) : 0;

  return (
    <>
      <PageHeader icon="journal-check" title={`${review.title} — Review`}
        subtitle={`${review.style.replaceAll("_", " ")} practice set`}
        pills={<Pill tone={pct >= 70 ? "success" : pct >= 40 ? "warning" : "danger"}>{review.score}/{review.total} correct</Pill>}
        actions={<Link href="/learn/quizzes" className="btn btn-outline-secondary btn-sm"><Icon name="arrow-left" className="me-1" />Back to quizzes</Link>} />

      <div className="row g-3 mb-4">
        <div className="col-md-4">
          <StatCard icon="check-circle" label="Score" value={`${review.score}/${review.total}`} tone="success" />
        </div>
        <div className="col-md-4">
          <StatCard icon="percent" label="Accuracy" value={`${pct}%`} tone="primary" />
        </div>
        <div className="col-md-4">
          <StatCard icon="list-check" label="Answered" value={`${review.answered_count}/${review.total}`} tone="info" />
        </div>
      </div>

      {review.questions.map((q) => (
        <section key={q.question_id} className="card mb-3">
          <div className="card-body">
            <div className="d-flex justify-content-between align-items-start mb-2">
              <h3 className="h6 mb-0">Question {q.ordinal}</h3>
              <div className="d-flex gap-2">
                <Pill tone="neutral">{q.question_type.replaceAll("_", " ").toLowerCase()}</Pill>
                {q.is_correct !== null && (
                  <Pill tone={q.is_correct ? "success" : "danger"} icon={q.is_correct ? "check-circle" : "x-circle"}>
                    {q.is_correct ? "Correct" : "Incorrect"}
                  </Pill>
                )}
              </div>
            </div>
            <div className="mb-2"><MathText>{q.prompt_text}</MathText></div>
            {q.student_response && (
              <div className="small text-secondary mb-2">
                <strong>Your answer:</strong>{" "}
                {q.student_response.selected_key || q.student_response.response_text || "—"}
              </div>
            )}
            {q.feedback && (
              <Callout tone={q.is_correct ? "success" : "warning"} icon="chat-square-text" className="mb-2">
                {q.feedback}
              </Callout>
            )}
            {q.solution_text && (
              <Callout tone="insight" icon="journal-check">
                <div className="fw-semibold small text-uppercase mb-1">Solution</div>
                <MathText>{q.solution_text}</MathText>
                {q.key_insight && (
                  <div className="small mt-2 pt-2 border-top"><Icon name="lightbulb" className="me-1" />{q.key_insight}</div>
                )}
              </Callout>
            )}
          </div>
        </section>
      ))}
    </>
  );
}
