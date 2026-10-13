"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Callout, EmptyState, Icon, PageHeader, Pill } from "../../_components/ui.jsx";

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

const STYLES = [
  { value: "AIME", label: "AIME-style" },
  { value: "HMMT", label: "HMMT-style" },
  { value: "PROOF_BASED", label: "Proof-based" },
  { value: "TOPIC_BASED", label: "Topic-based" },
  { value: "SKILL_BASED", label: "Skill-based" },
  { value: "MIXED", label: "Mixed" },
];
const TYPES = [
  { value: "MCQ", label: "Multiple choice" },
  { value: "FREE_TEXT", label: "Free text" },
  { value: "PROOF", label: "Proof" },
];
const STATUS_TONE = {
  GENERATING: "warning", READY: "info", IN_PROGRESS: "primary",
  SUBMITTED: "primary", GRADED: "success", FAILED: "danger",
};

export default function QuizzesPage() {
  const router = useRouter();
  const [quizzes, setQuizzes] = useState(null);
  const [error, setError] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [style, setStyle] = useState("AIME");
  const [questionCount, setQuestionCount] = useState(3);
  const [questionTypes, setQuestionTypes] = useState(["MCQ", "FREE_TEXT"]);
  const [topic, setTopic] = useState("");

  const refresh = () => load("/api/rest/quiz/mine").then(setQuizzes).catch(setError);
  useEffect(() => { refresh(); }, []);

  function toggleType(value) {
    setQuestionTypes((prev) => (prev.includes(value) ? prev.filter((t) => t !== value) : [...prev, value]));
  }

  async function generate() {
    setGenerating(true);
    setError(null);
    try {
      const body = {
        style, question_count: questionCount,
        question_types: questionTypes.length ? questionTypes : ["MCQ"],
        target_concept_slugs: topic.trim() ? [topic.trim()] : [],
      };
      const quiz = await load("/api/rest/quiz/generate", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      router.push(`/learn/quizzes/${quiz.quiz_id}`);
    } catch (err) {
      setError(err);
    } finally {
      setGenerating(false);
    }
  }

  if (error?.status === 401) {
    return <Callout tone="neutral" icon="lock">Please <Link href="/login">sign in</Link> to generate and take practice quizzes.</Callout>;
  }

  return (
    <>
      <PageHeader icon="patch-question" title="Practice quizzes"
        subtitle="Generate a personalized AIME/HMMT/proof/topic/skill-based question paper, inspired by real corpus problems." />
      {error && <Callout tone="danger" role="alert" className="mb-3">{error.message}</Callout>}

      <section className="card mb-4">
        <div className="card-body">
          <h2 className="h6 mb-3"><Icon name="magic" className="me-1" />Generate a new quiz</h2>
          <div className="row g-3 align-items-end">
            <div className="col-md-3">
              <label className="form-label small">Style</label>
              <select className="form-select" value={style} onChange={(e) => setStyle(e.target.value)}>
                {STYLES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>
            <div className="col-md-2">
              <label className="form-label small">Questions</label>
              <input type="number" min={1} max={10} className="form-control" value={questionCount}
                onChange={(e) => setQuestionCount(Math.max(1, Math.min(10, Number(e.target.value) || 1)))} />
            </div>
            <div className="col-md-4">
              <label className="form-label small">Question types</label>
              <div className="d-flex gap-2 flex-wrap">
                {TYPES.map((t) => (
                  <button key={t.value} type="button"
                    className={`btn btn-sm ${questionTypes.includes(t.value) ? "btn-primary" : "btn-outline-secondary"}`}
                    onClick={() => toggleType(t.value)}>{t.label}</button>
                ))}
              </div>
            </div>
            <div className="col-md-3">
              <label className="form-label small">Topic/skill (optional)</label>
              <input type="text" className="form-control" placeholder="e.g. power-of-a-point"
                value={topic} onChange={(e) => setTopic(e.target.value)} />
            </div>
          </div>
          <Callout tone="hint" className="mt-3" icon="lightbulb">
            Leave topic/skill blank to automatically target your own weakest areas.
          </Callout>
          <button type="button" className="btn btn-primary mt-2" disabled={generating} onClick={generate}>
            {generating
              ? <><span className="spinner-border spinner-border-sm me-2" />Generating…</>
              : <><Icon name="stars" className="me-1" />Generate quiz</>}
          </button>
        </div>
      </section>

      <h2 className="h6 mb-3">My quizzes</h2>
      {quizzes === null && <p className="text-secondary"><span className="spinner-border spinner-border-sm me-2" />Loading…</p>}
      {quizzes?.length === 0 && <EmptyState icon="patch-question">No quizzes generated yet.</EmptyState>}
      <div className="list-group" data-testid="quiz-list">
        {quizzes?.map((q) => (
          <Link key={q.quiz_id} href={q.status === "GRADED" ? `/learn/quizzes/${q.quiz_id}/review` : `/learn/quizzes/${q.quiz_id}`}
            className="list-group-item list-group-item-action d-flex justify-content-between align-items-center">
            <div>
              <div className="fw-semibold">{q.title}</div>
              <div className="small text-secondary">{q.question_count} question{q.question_count === 1 ? "" : "s"}
                {q.status === "GRADED" && <> · {q.correct_count}/{q.question_count} correct</>}</div>
            </div>
            <Pill tone={STATUS_TONE[q.status] || "neutral"}>{q.status.replaceAll("_", " ").toLowerCase()}</Pill>
          </Link>
        ))}
      </div>
    </>
  );
}
