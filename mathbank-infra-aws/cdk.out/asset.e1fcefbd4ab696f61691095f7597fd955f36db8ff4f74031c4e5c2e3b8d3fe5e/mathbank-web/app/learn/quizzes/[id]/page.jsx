"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import MathText from "../../../_components/MathText.jsx";
import { Callout, EmptyState, Icon, PageHeader, Pill } from "../../../_components/ui.jsx";

async function load(url, options) {
  const response = await fetch(url, { cache: "no-store", ...options });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(body.error?.message || body.error || `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return body;
}

function QuestionCard({ question, onSubmit }) {
  const [selectedKey, setSelectedKey] = useState("");
  const [responseText, setResponseText] = useState("");
  const [result, setResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const answered = question.answered || Boolean(result);

  async function submit() {
    const body = question.question_type === "MCQ"
      ? { selected_key: selectedKey }
      : { response_text: responseText };
    if (question.question_type === "MCQ" && !selectedKey) return;
    if (question.question_type !== "MCQ" && !responseText.trim()) return;
    setSubmitting(true);
    try {
      const graded = await onSubmit(question.question_id, body);
      setResult(graded);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="card mb-3">
      <div className="card-body">
        <div className="d-flex justify-content-between align-items-start mb-2">
          <h3 className="h6 mb-0">Question {question.ordinal}</h3>
          <Pill tone="neutral">{question.question_type.replaceAll("_", " ").toLowerCase()}</Pill>
        </div>
        <div className="mb-3"><MathText>{question.prompt_text}</MathText></div>
        {question.has_diagram && (
          <Callout tone="hint" icon="image" className="mb-3">This question includes a generated diagram (rendered in the review page).</Callout>
        )}
        {!answered && question.question_type === "MCQ" && (
          <div className="d-flex flex-column gap-2 mb-3">
            {question.options?.map((opt) => (
              <label key={opt.key} className="form-check d-flex gap-2 align-items-start border rounded p-2">
                <input type="radio" className="form-check-input mt-1" name={`q-${question.question_id}`}
                  checked={selectedKey === opt.key} onChange={() => setSelectedKey(opt.key)} />
                <div className="d-flex gap-1 align-items-start"><strong>{opt.key}.</strong> <MathText>{opt.text}</MathText></div>
              </label>
            ))}
          </div>
        )}
        {!answered && question.question_type !== "MCQ" && (
          <textarea className="form-control mb-3" rows={question.question_type === "PROOF" ? 6 : 3}
            placeholder={question.question_type === "PROOF" ? "Write your proof…" : "Your answer…"}
            value={responseText} onChange={(e) => setResponseText(e.target.value)} />
        )}
        {!answered && (
          <button type="button" className="btn btn-primary btn-sm" disabled={submitting} onClick={submit}>
            {submitting ? <span className="spinner-border spinner-border-sm me-2" /> : null}Submit answer
          </button>
        )}
        {answered && result && (
          <Callout tone={result.is_correct ? "success" : "warning"} icon={result.is_correct ? "check-circle" : "exclamation-diamond"} className="mt-2">
            <strong>{result.is_correct ? "Correct!" : "Not quite."}</strong> {result.feedback}
            {result.solution && (
              <div className="mt-2 pt-2 border-top">
                <div className="fw-semibold small text-uppercase text-secondary mb-1">Solution</div>
                <MathText>{result.solution.solution_text}</MathText>
                {result.solution.key_insight && (
                  <div className="small text-secondary mt-1"><Icon name="lightbulb" className="me-1" />{result.solution.key_insight}</div>
                )}
              </div>
            )}
          </Callout>
        )}
        {answered && !result && (
          <Pill tone="success" icon="check-circle">Already answered — see the review page for your result.</Pill>
        )}
      </div>
    </section>
  );
}

export default function TakeQuizPage() {
  const params = useParams();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const [quiz, setQuiz] = useState(null);
  const [error, setError] = useState(null);

  const refresh = () => load(`/api/rest/quiz/${id}`).then(setQuiz).catch(setError);
  useEffect(() => { refresh(); }, [id]);

  async function handleSubmit(questionId, body) {
    const result = await load(`/api/rest/quiz/${id}/questions/${questionId}/respond`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    await refresh();
    return result;
  }

  if (error?.status === 401) {
    return <Callout tone="neutral" icon="lock">Please <Link href="/login">sign in</Link> to take this quiz.</Callout>;
  }
  if (error) return <Callout tone="danger" role="alert">{error.message}</Callout>;
  if (!quiz) return <p className="text-secondary"><span className="spinner-border spinner-border-sm me-2" />Loading…</p>;

  const answeredCount = quiz.questions.filter((q) => q.answered).length;
  const allAnswered = answeredCount === quiz.questions.length;

  return (
    <>
      <PageHeader icon="patch-question" title={quiz.title}
        subtitle={`${quiz.style.replaceAll("_", " ")} practice set · ${quiz.questions.length} question${quiz.questions.length === 1 ? "" : "s"}`}
        pills={<Pill tone="info">{answeredCount}/{quiz.questions.length} answered</Pill>}
        actions={allAnswered && (
          <Link href={`/learn/quizzes/${id}/review`} className="btn btn-primary btn-sm">
            <Icon name="journal-check" className="me-1" />Full review
          </Link>
        )} />
      {quiz.questions.length === 0 && <EmptyState icon="patch-question">No questions in this paper.</EmptyState>}
      {quiz.questions.map((q) => (
        <QuestionCard key={q.question_id} question={q} onSubmit={handleSubmit} />
      ))}
    </>
  );
}
