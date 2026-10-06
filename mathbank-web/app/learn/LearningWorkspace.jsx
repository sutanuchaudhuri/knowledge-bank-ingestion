"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import MathText from "../_components/MathText.jsx";
import ProblemDiagrams from "../_components/ProblemDiagrams.jsx";
import { Callout, EmptyState, Icon, IconButton, PageHeader, Pill } from "../_components/ui.jsx";
import { DIAGNOSES, hintRequestState } from "../../lib/learningFlow.mjs";
import { hasStepSolution } from "../../lib/solveFlow.mjs";

async function tutorRequest(path, options = {}) {
  const response = await fetch(`/api/tutor/${path}`, options);
  const body = await response.json();
  if (!response.ok) {
    throw new Error(typeof body.error === "string" ? body.error : JSON.stringify(body.error || `Request failed: ${response.status}`));
  }
  return body;
}

function Provenance({ item }) {
  return (
    <span className="small text-secondary">
      {item.approval_method === "automatic" ? "Automatically approved (not human-reviewed)" : item.review_status || "Review status unavailable"} · source: {item.source || "Not provided"}
      {item.confidence !== undefined && item.confidence !== null && ` · confidence: ${item.confidence}`}
    </span>
  );
}

export default function LearningWorkspace() {
  const params = useSearchParams();
  const queryCode = params.get("problem") || "";
  const [codeInput, setCodeInput] = useState(queryCode);
  const [code, setCode] = useState(queryCode);
  const [reloadKey, setReloadKey] = useState(0);
  const [context, setContext] = useState(null);
  const [practice, setPractice] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [practiceError, setPracticeError] = useState(null);
  const [diagnosis, setDiagnosis] = useState("concept");
  const [attempt, setAttempt] = useState("");
  const [previousAttempt, setPreviousAttempt] = useState("");
  const [coaching, setCoaching] = useState(null);
  const [hintLevel, setHintLevel] = useState(0);
  const [busy, setBusy] = useState(false);
  const coachController = useRef(null);
  const attemptRef = useRef(null);

  useEffect(() => {
    setCode(queryCode);
    setCodeInput(queryCode);
  }, [queryCode]);

  useEffect(() => {
    coachController.current?.abort();
    coachController.current = null;
    const controller = new AbortController();
    setContext(null);
    setPractice(null);
    setCoaching(null);
    setAttempt("");
    setPreviousAttempt("");
    setDiagnosis("concept");
    setHintLevel(0);
    setBusy(false);
    setError(null);
    setPracticeError(null);
    setLoading(Boolean(code));
    if (!code) return () => controller.abort();
    tutorRequest(`learning-context/${encodeURIComponent(code)}`, { signal: controller.signal })
      .then((data) => {
        if (controller.signal.aborted) return;
        setContext(data);
        tutorRequest(`practice/${encodeURIComponent(code)}?limit=5`, { signal: controller.signal })
          .then((result) => { if (!controller.signal.aborted) setPractice(result); })
          .catch((err) => { if (!controller.signal.aborted) setPracticeError(err.message); });
      })
      .catch((err) => { if (!controller.signal.aborted) setError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => { controller.abort(); coachController.current?.abort(); };
  }, [code, reloadKey]);

  const options = context?.diagnostic_options || DIAGNOSES;
  const question = options.find((item) => item.id === diagnosis)?.question;
  const requestState = hintRequestState(attempt, previousAttempt, hintLevel);

  async function requestHint() {
    if (!context || busy || coachController.current || !requestState.allowed) return;
    const controller = new AbortController();
    coachController.current = controller;
    const submittedAttempt = attempt.trim();
    setBusy(true);
    setError(null);
    try {
      const data = await tutorRequest("coach", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ problem_code: code, diagnosis, student_attempt: submittedAttempt, hint_level: requestState.nextLevel }),
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      setCoaching(data);
      setHintLevel(data.hint_level);
      setPreviousAttempt(submittedAttempt);
    } catch (err) {
      if (!controller.signal.aborted) setError(err.message);
    } finally {
      if (coachController.current === controller) {
        coachController.current = null;
        if (!controller.signal.aborted) setBusy(false);
      }
    }
  }

  function changeDiagnosis(value) {
    coachController.current?.abort();
    coachController.current = null;
    setBusy(false);
    setDiagnosis(value);
    setCoaching(null);
    setHintLevel(0);
    setPreviousAttempt("");
    setError(null);
  }

  return (
    <div>
      <PageHeader icon="compass" title="Guided math practice"
        subtitle="Say where you are stuck, try a small step, and unlock one hint at a time."
        pills={<Pill tone="neutral" icon="incognito" title="Your draft and hint progress are temporary. Hint requests send your attempt to the coaching service and its model provider; nothing is saved as a learner attempt or mastery record.">Temporary workspace</Pill>} />
      <form className="mb-search mb-4" onSubmit={(event) => { event.preventDefault(); setCode(codeInput.trim()); setReloadKey((value) => value + 1); }}>
        <label htmlFor="learning-code" className="visually-hidden">Problem code</label>
        <Icon name="search" className="mb-search-icon" />
        <input id="learning-code" className="form-control" value={codeInput}
          onChange={(event) => setCodeInput(event.target.value)} placeholder="Problem code, e.g. AIME_2023_I_Q11" required maxLength={200} />
        <button className="btn btn-primary" disabled={loading || busy}>Load problem</button>
        <IconButton icon="grid-3x3-gap" label="Find a problem" variant="outline-secondary" href="/db/problems" />
      </form>
      {loading && <p role="status" className="text-secondary"><span className="spinner-border spinner-border-sm me-2" />Loading answer-free learning context…</p>}
      {error && <Callout tone="danger" role="alert" className="mb-3">{error}</Callout>}
      {!context && !loading && !error && <div className="card"><EmptyState icon="journal-text">Load a problem to begin. Teaching metadata is enriched automatically, so the first load can take a little longer.</EmptyState></div>}
      {context && (
        <div className="row g-4">
          <div className="col-12 col-xl-8">
            <section className="card border-0 shadow-sm mb-4">
              <div className="card-body">
                <div className="d-flex flex-wrap justify-content-between gap-2 mb-2">
                  <h2 className="h5">{context.problem.canonical_code}</h2>
                  {hasStepSolution(context.problem.canonical_code) && (
                    <Link className="btn btn-sm btn-primary ms-auto" href={`/learn/solve/${encodeURIComponent(context.problem.canonical_code)}`}>
                      Solve step by step
                    </Link>
                  )}
                  <span className={`badge ${context.metadata_status === "reviewed" ? "text-bg-success" : "text-bg-warning"}`}>
                    {context.metadata_status === "automatic" ? "Automatically enriched" : context.metadata_status === "reviewed" ? "Human-reviewed teaching metadata" : "Not yet enriched"}
                  </span>
                </div>
                <p className="small text-secondary">{context.problem.competition} · {context.problem.year} · {context.problem.difficulty_band || "Difficulty not recorded"}</p>
                <MathText>{context.problem.statement_text}</MathText>
                <ProblemDiagrams code={context.problem.canonical_code} images={context.problem.diagrams} />
                <p className="small text-secondary mt-3 mb-0">No official answer or full solution is loaded in this workspace.</p>
              </div>
            </section>
            <section className="card border-0 shadow-sm mb-4">
              <div className="card-body">
                <h2 className="h5">1. Where are you stuck?</h2>
                <fieldset disabled={busy} className="mb-3">
                  <legend className="small text-secondary">Your self-assessment, not a mastery score</legend>
                  <div className="d-flex flex-wrap gap-2">
                    {options.map((option) => (
                      <button type="button" key={option.id} aria-pressed={diagnosis === option.id}
                        className={`mb-tab${diagnosis === option.id ? " active" : ""}`}
                        onClick={() => changeDiagnosis(option.id)}>{option.label}</button>
                    ))}
                  </div>
                </fieldset>
                <p className="fw-semibold">{question}</p>
                <label className="form-label" htmlFor="student-attempt">Your current attempt or sticking point</label>
                <textarea ref={attemptRef} id="student-attempt" className="form-control mb-2" rows={4} maxLength={4000}
                  value={attempt} disabled={busy} onChange={(event) => setAttempt(event.target.value)}
                  placeholder="Describe what you tried, even if it did not work." />
                <p className="small text-secondary">{requestState.reason || `Ready for hint level ${requestState.nextLevel} of 3.`}</p>
                <button className="btn btn-primary" type="button" disabled={!requestState.allowed || busy} onClick={requestHint}>
                  {busy ? "Preparing a small next step..." : hintLevel === 0 ? "Request first hint" : "Request next hint"}
                </button>
              </div>
            </section>
            {coaching && (
              <section className="card border-0 shadow-sm">
                <div className="card-body">
                  <div className="d-flex gap-2 align-items-center mb-3">
                    <h2 className="h5 mb-0">2. Try one small step</h2>
                    <span className="badge text-bg-secondary">Hint {coaching.hint_level}/3</span>
                  </div>
                  <p className="small text-secondary"><Icon name="robot" className="me-1" />Generated coaching, not an expert-reviewed hint ladder. <Provenance item={coaching.provenance || {}} /></p>
                  <Callout tone="insight" title="Micro-lesson" className="mb-3"><MathText>{coaching.micro_lesson}</MathText></Callout>
                  <Callout tone="hint" title="Your next hint" className="mb-3"><MathText>{coaching.hint}</MathText></Callout>
                  <Callout tone="neutral" icon="arrow-return-left" title="Back to the original problem">
                    <MathText>{coaching.return_prompt}</MathText>
                    <button type="button" className="btn btn-sm btn-outline-primary mt-2" onClick={() => attemptRef.current?.focus()}><Icon name="pencil" className="me-1" />Update my attempt</button>
                  </Callout>
                  {(coaching.warnings || []).map((warning, index) => <p key={index} className="small text-secondary mt-2 mb-0">{warning}</p>)}
                </div>
              </section>
            )}
          </div>
          <aside className="col-12 col-xl-4">
            <section className="card border-0 shadow-sm mb-4">
              <div className="card-body">
                <h2 className="h5">Learning context</h2>
                {(context.warnings || []).map((warning, index) => <div key={index} className="alert alert-warning small">{warning}</div>)}
                <h3 className="h6">Approved skills</h3>
                {context.skills.length ? context.skills.map((skill) => (
                  <div key={`${skill.slug}-${skill.relation_type || ""}-${skill.role}`} className="border rounded-3 p-3 mb-2">
                    <strong>{skill.name}</strong>
                    <p className="small mb-1">{skill.objective}</p>
                    <p className="small mb-1">{skill.relation_type && `${skill.relation_type} · `}{skill.role} · required level: {skill.required_level ?? "Unknown"} · importance: {skill.importance ?? "Unknown"}</p>
                    <Provenance item={skill} />
                  </div>
                )) : <p className="small text-secondary">No approved skill mappings. Concepts are not assumed to be measurable skills.</p>}
                <h3 className="h6 mt-3">Approved prerequisites</h3>
                {context.prerequisites.length ? context.prerequisites.map((skill) => (
                  <div key={skill.slug} className="small mb-2"><strong>{skill.name}</strong><br /><Provenance item={skill} /></div>
                )) : <p className="small text-secondary">No supported prerequisite path recorded.</p>}
                <h3 className="h6 mt-3">Approved concept tags</h3>
                {context.concepts.map(item => <div key={`${item.slug}-${item.role}-${item.source}`} className="small mb-2">{item.name}<br /><Provenance item={item} /></div>)}
                {!context.concepts.length && <p className="small text-secondary">No applicable concept tags recorded.</p>}
                <h3 className="h6 mt-3">Approved technique tags</h3>
                {context.techniques.map(item => <div key={`${item.slug}-${item.role}-${item.source}`} className="small mb-2">{item.name}<br /><Provenance item={item} /></div>)}
                {!context.techniques.length && <p className="small text-secondary">No applicable technique tags recorded.</p>}
                <p className="small text-secondary">Approved includes automatic and human decisions. Topics and methods are not proof of learner mastery.</p>
                <h3 className="h6 mt-3">Difficulty dimensions</h3>
                <dl className="small mb-0">
                  {["conceptual_depth", "technical_load", "algebraic_load", "insight_required", "number_of_steps", "prerequisite_depth", "estimated_contest_level"].map((key) => (
                    <div className="d-flex justify-content-between gap-2" key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{context.difficulty?.[key] ?? "Not recorded"}</dd></div>
                  ))}
                </dl>
                <Provenance item={context.difficulty || {}} />
              </div>
            </section>
            <section className="card border-0 shadow-sm">
              <div className="card-body">
                <h2 className="h5">Lower-level same-skill practice</h2>
                {practiceError && <p role="alert" className="text-danger small">{practiceError}</p>}
                {!practice && !practiceError && <p role="status" className="small">Checking reviewed practice coverage...</p>}
                {(practice?.results || []).map((problem) => (
                  <Link className="d-block mb-2" key={problem.canonical_code} href={`/learn?problem=${encodeURIComponent(problem.canonical_code)}`}>
                    {problem.canonical_code} · {problem.competition} {problem.year}
                  </Link>
                ))}
                {practice && !(practice.results || []).length && <p className="small text-secondary">No reviewed lower-level same-skill practice is available.</p>}
                {(practice?.warnings || []).map((warning, index) => <p key={index} className="small text-secondary">{warning}</p>)}
                <Link href="/graph/requires-skill" className="btn btn-sm btn-outline-primary mt-2">Inspect the teaching graph</Link>
              </div>
            </section>
          </aside>
        </div>
      )}
    </div>
  );
}
