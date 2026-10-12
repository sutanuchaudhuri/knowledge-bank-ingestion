"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { MathComposer } from "mathbank-widgets";
import MathText from "../_components/MathText.jsx";
import ProblemDiagrams from "../_components/ProblemDiagrams.jsx";
import ProblemSource from "../_components/ProblemSource.jsx";
import ConstructionPreview from "../_components/ConstructionPreview.jsx";
import WrittenWorkUpload from "../_components/WrittenWorkUpload.jsx";
import { ProblemPreviewCard } from "../_components/ProblemPreview.jsx";
import { Callout, EmptyState, Icon, IconButton, PageHeader, Pill, SectionTitle } from "../_components/ui.jsx";
import { hintRequestState } from "../../lib/learningFlow.mjs";
import { hasStepSolution } from "../../lib/solveFlow.mjs";
import { corpusJson, hasQuestionText, tutorProblemHref } from "../../lib/corpusProblems.mjs";
import { prepareProblemPresentation } from "../../lib/problemPresentation.mjs";
import { resolveProblemReference } from "../../lib/problemReference.mjs";

async function tutorRequest(path, options = {}) {
  const { timeoutMs, ...fetchOptions } = options;
  const signal = timeoutMs ? AbortSignal.any([options.signal, AbortSignal.timeout(timeoutMs)].filter(Boolean)) : options.signal;
  let response;
  try {
    response = await fetch(`/api/tutor/${path}`, { ...fetchOptions, signal });
  } catch (error) {
    if (error.name === "TimeoutError") throw new Error("Teaching data timed out. You can keep writing and retry.");
    throw error;
  }
  const body = await response.json();
  if (!response.ok) throw new Error(typeof body.error === "string" ? body.error : `Teaching service unavailable (${response.status}).`);
  return body;
}

const DEFAULT_JOURNEY = [
  { id: "understand", title: "Understand", icon: "search" },
  { id: "plan", title: "Plan", icon: "signpost-split" },
  { id: "work", title: "Work", icon: "pencil" },
  { id: "check", title: "Check", icon: "check2-circle" },
  { id: "reflect", title: "Reflect", icon: "lightbulb" },
];

function EasierPractice({ code }) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    tutorRequest(`practice/${encodeURIComponent(code)}?limit=5`, { signal: controller.signal })
      .then((result) => { if (!controller.signal.aborted) setData(result); })
      .catch((err) => { if (!controller.signal.aborted) setError(err.message); });
    return () => controller.abort();
  }, [code, open]);
  return <details className="card p-3 mt-4" onToggle={(event) => setOpen(event.currentTarget.open)}>
    <summary className="mb-section-title mb-0"><Icon name="bullseye" />Lower-level same-skill practice</summary>
    {open && <div className="pt-3">
      {error && <Callout tone="warning" role="alert">{error}</Callout>}
      {!data && !error && <p role="status">Checking reviewed practice coverage…</p>}
      {data && !(data.results || []).length && <p className="small text-secondary">No reviewed lower-level same-skill practice is available.</p>}
      {(data?.results || []).map((item) => <Link key={item.canonical_code} className="d-block mb-2 text-break" href={`/learn?problem=${encodeURIComponent(item.canonical_code)}`}>
        {item.canonical_code} · {item.competition} {item.year}
      </Link>)}
      {(data?.warnings || []).map((warning, index) => <Callout key={index} tone="warning" className="mt-2">{warning}</Callout>)}
    </div>}
  </details>;
}

export default function LearningWorkspace() {
  const params = useSearchParams();
  const queryCode = params.get("problem") || "";
  const [codeInput, setCodeInput] = useState(queryCode);
  const [code, setCode] = useState("");
  const [lookupBusy, setLookupBusy] = useState(false);
  const [lookupError, setLookupError] = useState("");
  const [matches, setMatches] = useState([]);
  const [lookupResult, setLookupResult] = useState(null);
  const lookupRef = useRef(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [context, setContext] = useState(null);
  const [problem, setProblem] = useState(null);
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(false);
  const [contextLoading, setContextLoading] = useState(false);
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [workspaceError, setWorkspaceError] = useState("");
  const [stage, setStage] = useState(0);
  const [stageStates, setStageStates] = useState({});
  const [steps, setSteps] = useState([{ text: "", feedback: null }]);
  const [selected, setSelected] = useState(0);
  const [busy, setBusy] = useState(false);
  const [microFeedback, setMicroFeedback] = useState(null);
  const [choice, setChoice] = useState("");
  const [showVisual, setShowVisual] = useState(false);
  const controllerRef = useRef(null);
  const workRef = useRef(null);
  const current = steps[selected];
  const journey = session?.journey || DEFAULT_JOURNEY;
  const prompt = session?.active_prompt;
  const requestState = hintRequestState(current.text, current.previousAttempt || "", current.hintsUsed || 0);
  const presentation = useMemo(() => problem ? prepareProblemPresentation(problem.statement_text, code) : null, [problem, code]);

  function chooseProblem(candidate) {
    setCodeInput(candidate.canonical_code); setCode(candidate.canonical_code);
    setMatches([]); setLookupResult(null); setLookupError(""); setReloadKey((value) => value + 1);
  }
  async function lookupProblem(input) {
    lookupRef.current?.abort();
    const controller = new AbortController();
    lookupRef.current = controller;
    setLookupBusy(true); setLookupError(""); setMatches([]); setLookupResult(null);
    try {
      const result = await resolveProblemReference(input, {
        signal: AbortSignal.any([controller.signal, AbortSignal.timeout(12000)]), fetchPage: corpusJson,
      });
      if (controller.signal.aborted) return;
      if (result.kind !== "search" && result.candidates.length === 1) chooseProblem(result.candidates[0]);
      else { setMatches(result.candidates); setLookupResult(result); }
    } catch (err) {
      if (!controller.signal.aborted) setLookupError(err.name === "TimeoutError" ? "Problem lookup timed out. Please retry." : err.message);
    } finally {
      if (lookupRef.current === controller) { lookupRef.current = null; setLookupBusy(false); }
    }
  }
  useEffect(() => {
    setCodeInput(queryCode);
    if (queryCode) void lookupProblem(queryCode);
    else { setCode(""); setMatches([]); setLookupResult(null); setLookupError(""); }
    return () => lookupRef.current?.abort();
  }, [queryCode]);
  useEffect(() => {
    setSteps([{ text: "", feedback: null }]); setSelected(0); setStage(0); setStageStates({});
    setMicroFeedback(null); setChoice(""); setShowVisual(false);
    setProblem(null); setSession(null);
  }, [code]);
  useEffect(() => {
    controllerRef.current?.abort(); controllerRef.current = null;
    const controller = new AbortController();
    setContext(null); setError(""); setLoadError(""); setWorkspaceError("");
    setBusy(false);
    setLoading(Boolean(code));
    setContextLoading(Boolean(code));
    if (!code) return () => controller.abort();
    tutorRequest(`workspace/${encodeURIComponent(code)}`, { signal: controller.signal, timeoutMs: 12000 })
      .then((data) => {
        if (!controller.signal.aborted) {
          setProblem(data.problem);
          setSession((currentSession) => currentSession || data.pedagogy_session || null);
        }
      }).catch(async (err) => {
        if (controller.signal.aborted) return;
        setWorkspaceError(`Problem orientation could not be loaded: ${err.message}`);
        try {
          const data = await corpusJson(`/api/rest/problems/${encodeURIComponent(code)}`, {
            signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]),
          });
          if (!controller.signal.aborted) setProblem((existing) => existing || ({
            canonical_code: data.canonical_code, statement_text: data.statement_text,
            competition: data.competition, year: data.year, diagrams: data.diagrams,
          }));
        } catch (fallbackError) {
          if (!controller.signal.aborted) setError(`The canonical question could not be loaded either: ${fallbackError.message}`);
        }
      }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    tutorRequest(`learning-context/${encodeURIComponent(code)}`, { signal: controller.signal, timeoutMs: 15000 })
      .then((data) => {
        if (!controller.signal.aborted) {
          setContext(data);
          setProblem((existing) => existing || data.problem);
          setSession((currentSession) => currentSession || data.pedagogy_session || null);
        }
      }).catch((err) => { if (!controller.signal.aborted) setLoadError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setContextLoading(false); });
    return () => { controller.abort(); controllerRef.current?.abort(); };
  }, [code, reloadKey]);

  async function microCheck(response) {
    if (busy || controllerRef.current || prompt?.action !== "ASK_MICRO_CHECK") return;
    const controller = new AbortController(); controllerRef.current = controller;
    setBusy(true); setError("");
    try {
      const result = await tutorRequest("micro-check", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ problem_code: code, index: prompt.index, response }), signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      setMicroFeedback(result);
      setSession(result.session);
      if (result.correct) setChoice("");
      if (result.session.active_prompt.action === "REQUEST_STUDENT_STEP") setStage(1);
    } catch (err) { if (!controller.signal.aborted) setError(err.message); }
    finally {
      if (controllerRef.current === controller) { controllerRef.current = null; setBusy(false); }
    }
  }

  async function requestHint() {
    if (!context || busy || controllerRef.current || !requestState.allowed) return;
    const controller = new AbortController(); controllerRef.current = controller;
    const text = current.text.trim();
    const index = selected;
    setBusy(true); setError("");
    try {
      const result = await tutorRequest("coach", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          problem_code: code, diagnosis: stage === 0 ? "concept" : stage === 1 ? "strategy" : stage === 3 ? "calculation" : "connection",
          student_attempt: text,
          hint_level: requestState.nextLevel,
        }), signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      setSteps((items) => items.map((step, i) => i === index ? {
        ...step, hintsUsed: result.hint_level, previousAttempt: text, feedback: { ...result, submittedText: text },
      } : step));
    } catch (err) { if (!controller.signal.aborted) setError(err.message); }
    finally {
      if (controllerRef.current === controller) { controllerRef.current = null; setBusy(false); }
    }
  }

  function focusWork() { workRef.current?.querySelector("textarea")?.focus(); }
  function changeStep(text) {
    setSteps((items) => items.map((step, index) => index === selected ? { ...step, text } : step));
  }
  function addStep() {
    if (!current.text.trim() || busy || steps.length >= 20) return;
    setSteps((items) => [...items, { text: "", feedback: null }]); setSelected(steps.length);
  }
  const feedback = current.feedback;
  return <div className="mb-learning-workspace">
    <PageHeader icon="signpost-split" title="Guided math practice"
      subtitle="One small step at a time." />
    <details className="mb-workspace-options mb-2" open={!code || Boolean(lookupError) || Boolean(lookupResult) || undefined}>
      <summary><Icon name="search" />{code ? "Change problem" : "Find a problem"}</summary>
    <form className="mb-search mt-2" onSubmit={(event) => { event.preventDefault(); void lookupProblem(codeInput); }}>
      <label htmlFor="learning-code" className="visually-hidden">Search for a problem</label><Icon name="search" className="mb-search-icon" />
      <input id="learning-code" className="form-control" value={codeInput} onChange={(event) => setCodeInput(event.target.value)} required maxLength={2000} placeholder="Describe a problem, paste question text, or enter a contest or code…" />
      <button className="btn btn-primary" disabled={loading || busy || lookupBusy}>{lookupBusy ? "Searching…" : "Search"}</button>
      <IconButton icon="grid-3x3-gap" label="Find a problem" variant="outline-secondary" href="/db/problems" />
    </form>
    </details>
    {lookupError && <Callout tone="warning" role="alert" className="mb-2">{lookupError}</Callout>}
    {lookupResult && <section className="card p-3 mb-3" aria-label="Choose a matching problem">
      <p className="small mb-2">{lookupResult.kind === "search" ? "Choose a question to practise. Search relevance is not a verified topic annotation." : "More than one paper matches. Choose the version you mean."}</p>
      {lookupResult.kind === "search" ? <div className="d-grid gap-2">
        {matches.map((candidate) => <ProblemPreviewCard key={candidate.canonical_code} item={candidate} onChoose={chooseProblem} revealSolutions={false} />)}
        {!matches.length && <EmptyState icon="search">No matching problems. Try a different description or choose from the corpus.</EmptyState>}
      </div> : <div className="d-flex flex-wrap gap-2">{matches.map((candidate) => <button key={candidate.canonical_code}
        className="btn btn-outline-primary btn-sm" onClick={() => chooseProblem(candidate)}>
        {candidate.competition} {candidate.year} · {candidate.paper_code} · Problem {candidate.problem_number}
      </button>)}</div>}
      {lookupResult.warnings.length > 0 && <details className="small text-secondary mt-2"><summary>Search details</summary>{lookupResult.warnings.map((warning, index) => <p key={index} className="mb-1">{warning}</p>)}</details>}
    </section>}
    {loading && !problem && <p role="status">Loading the canonical question…</p>}
    {contextLoading && <p role="status" className="small text-secondary mb-2"><Icon name="hourglass-split" />Hints loading…</p>}
    {loadError && <Callout tone="warning" role="alert" className="mb-2">
      Teaching context could not be loaded. {problem && "Your question and work are available; hints are disabled."}
      <button className="btn btn-sm btn-outline-secondary ms-2" disabled={loading || busy} onClick={() => setReloadKey((value) => value + 1)}>Retry learning data</button>
    </Callout>}
    {error && <Callout tone="danger" role="alert" className="mb-3">{error}</Callout>}
    {loadError && !problem && <details className="mb-workspace-options mb-2"><summary>Loading details</summary>{loadError}</details>}
    {!code && !lookupResult && !lookupBusy && <EmptyState icon="journal-text">Search for a topic or question to open your workspace.</EmptyState>}
    {problem && <>
      <section className="card p-2 mb-3" aria-label="Your solving journey">
        <div className="d-flex flex-wrap align-items-center gap-1">
          {journey.map((item, index) => <button key={item.id} className={`mb-tab${stage === index ? " active" : ""}`}
            aria-current={stage === index ? "step" : undefined} disabled={busy} title="Self-directed progress, not a mastery score"
            onClick={() => { setStage(index); setChoice(""); }}>
            <Icon name={item.icon} />{item.title}{stageStates[index] && <span className="small"> · {stageStates[index]}</span>}
          </button>)}
          <button className="btn btn-ghost btn-sm" disabled={busy || stage === journey.length - 1}
            onClick={() => { setStageStates((value) => ({ ...value, [stage]: "skipped" })); setStage(stage + 1); }}>Skip stage</button>
          <button className="btn btn-ghost btn-sm" disabled={busy}
            onClick={() => setStageStates((value) => ({ ...value, [stage]: "self-reported done" }))}>Mark stage done</button>
        </div>
      </section>
      <div className="row g-3">
        <div className="col-12 col-xl-7">
          <section className="card p-3 mb-3" aria-label="Current problem">
            <div className="d-flex flex-wrap align-items-center gap-2 mb-2"><h2 className="h6 mb-0 text-break">{problem.canonical_code}</h2>
              {problem.year && <Pill icon="calendar3">{problem.year}</Pill>}
            </div>
            {hasQuestionText(problem) ? <div className="mb-tutor-problem"><MathText>{presentation.markdown}</MathText></div>
              : <Callout tone="warning">Question text is incomplete. Consult the source before working.</Callout>}
            <ProblemDiagrams code={code} images={problem.diagrams} showSource={false} />
            <details className="mb-corpus-related mt-3"><summary className="mb-section-title mb-0"><Icon name="book" />Source details</summary>
              <div className="pt-3"><p className="small text-secondary">{problem.competition}</p><ProblemSource code={code} /></div>
            </details>
            <div className="d-flex gap-2 flex-wrap mt-3">
              <Link className="btn btn-outline-secondary btn-sm" href={tutorProblemHref(code)}><Icon name="chat-dots" />Discuss with tutor</Link>
              {hasStepSolution(code) && <Link className="btn btn-outline-secondary btn-sm" href={`/learn/solve/${encodeURIComponent(code)}`}><Icon name="list-check" />Solve step by step</Link>}
            </div>
          </section>
          <section className="card p-3" aria-label="My work">
            <SectionTitle icon="pencil">My work</SectionTitle>
            <div className="d-flex flex-wrap gap-2 mb-2">{steps.map((step, index) => <button key={index}
              className={`mb-tab${index === selected ? " active" : ""}`} disabled={busy} onClick={() => setSelected(index)}>
              Step {index + 1}{step.feedback && <Icon name="chat-dots" />}
            </button>)}</div>
            <div ref={workRef}>
              <MathComposer id="student-attempt" ariaLabel="Your current attempt or sticking point" testId="guided-work-composer"
                value={current.text} onChange={changeStep} onSubmit={requestHint} rows={3} disabled={busy}
                showSubmit={false} renderMath={(text) => <MathText>{text}</MathText>} placeholder="Write a relation or explain your idea…" />
            </div>
            <div className="d-flex flex-wrap gap-2 my-2">
              <button className="btn btn-outline-primary btn-sm" disabled={busy || !current.text.trim() || steps.length >= 20} onClick={addStep}><Icon name="plus-lg" />Add another step</button>
            </div>
            <WrittenWorkUpload key={code} code={code} />
            {feedback && <section className="mt-3" aria-label={`Tutor feedback for step ${selected + 1}`}>
              <Pill tone="warning" icon="robot">Generated coaching · not verified correctness</Pill>
              {feedback.submittedText !== current.text.trim() && <Callout tone="warning" className="mt-2">This feedback applies to your earlier draft. Request new guidance after your edit.</Callout>}
              <Callout tone="insight" title="A useful idea" className="mt-3"><MathText>{feedback.micro_lesson}</MathText></Callout>
              <Callout tone="hint" title="Small nudge" className="mt-3"><MathText>{feedback.hint}</MathText></Callout>
              <Callout tone="neutral" title="Try next" className="mt-3"><MathText>{feedback.return_prompt}</MathText></Callout>
              {!!feedback.warnings?.length && <details className="small mt-2"><summary>Feedback details</summary>{feedback.warnings.map((warning, index) => <p key={index} className="mb-1">{warning}</p>)}</details>}
            </section>}
          </section>
        </div>
        <aside className="col-12 col-xl-5">
          <section className="card p-3" aria-label="Tutor guidance">
            <SectionTitle icon="stars">Tutor</SectionTitle>
            <details className="mb-workspace-options mb-2"><summary>Choose how to work</summary>
            <div className="d-flex flex-wrap gap-2 mt-2">
              <button className="mb-tab" onClick={() => setStage(0)} disabled={busy}><Icon name="search" />Help me see the structure</button>
              <button className="mb-tab" onClick={focusWork} disabled={busy}><Icon name="pencil" />I have a starting idea</button>
              <button className="mb-tab" onClick={() => { setStage(2); focusWork(); }} disabled={busy}>Let me try it myself</button>
            </div>
            </details>
            {stage === 0 && prompt?.action === "ASK_MICRO_CHECK" && <section aria-label="Orientation checkpoint">
              <MathText>{prompt.prompt}</MathText>
              <fieldset disabled={busy}><legend className="visually-hidden">Choose an orientation answer</legend>
                {prompt.choices.map((value) => <label className="form-check border rounded p-2 mb-2" key={value}>
                  <input type="radio" className="form-check-input ms-0 me-2" name="orientation" checked={choice === value} onChange={() => setChoice(value)} />
                  <MathText>{value}</MathText>
                </label>)}
              </fieldset>
              <button className="btn btn-primary btn-sm" disabled={busy || !choice} onClick={() => microCheck(choice)}>Check answer</button>
              <button className="btn btn-ghost btn-sm ms-2" disabled={busy} onClick={() => microCheck("hint")}>Give me a tiny nudge</button>
            </section>}
            {microFeedback && <Callout tone={microFeedback.hint ? "hint" : microFeedback.correct ? "success" : "warning"} className="mt-3">
              <MathText>{microFeedback.hint || microFeedback.explanation}</MathText>
            </Callout>}
            {(stage !== 0 || prompt?.action !== "ASK_MICRO_CHECK") && <Callout tone="neutral" className="mb-3">
              {prompt?.action === "REQUEST_STUDENT_STEP" ? <MathText>{prompt.prompt}</MathText> : "Choose what is given, what you need to show, and one relation you can justify. Add your idea to My work."}
            </Callout>}
            {code === "PRASOLOV_PGV1_CH06_P031" && <>
              <button className="btn btn-outline-secondary btn-sm my-3" aria-expanded={showVisual} onClick={() => setShowVisual(!showVisual)}>
                <Icon name="image" />{showVisual ? "Hide construction" : "Show the construction visually"}
              </button>
              {showVisual && <ConstructionPreview key={session?.visual_intent?.current_step || "unavailable"} intent={session?.visual_intent} code={code} />}
            </>}
            <div className="border-top pt-2 mt-2">
              <p className="small text-secondary mb-2">{requestState.reason || `Ready for hint ${requestState.nextLevel} of 3 on this step.`}</p>
              <button className="btn btn-outline-primary btn-sm" disabled={!context || !requestState.allowed || busy} onClick={requestHint} title="AI coaching, not certified mathematical correctness">
                <Icon name="lightbulb" />{busy ? "Preparing guidance…" : "Give me a small hint"}
              </button>
            </div>
          </section>
          <details className="mb-workspace-options mt-2">
            <summary><Icon name="info-circle" />Workspace details</summary>
            <p className="small mt-2 mb-1">Temporary workspace: drafts and journey choices are not saved after leaving this page and do not write mastery evidence. AI coaching is not certified mathematical correctness.</p>
            {workspaceError && <p className="small text-warning-emphasis mb-1">{workspaceError}</p>}
            {loadError && <p className="small text-warning-emphasis mb-1">{loadError}</p>}
            {[...(context?.warnings || []), ...(presentation?.warnings || [])].map((warning, index) => <p key={index} className="small text-secondary mb-1">{warning}</p>)}
          </details>
          {context && <EasierPractice key={code} code={code} />}
        </aside>
      </div>
    </>}
  </div>;
}
