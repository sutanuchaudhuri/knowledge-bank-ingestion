"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import MathText from "../../../_components/MathText.jsx";
import { Callout, Icon, IconButton, PageHeader, Pill } from "../../../_components/ui.jsx";
import { MathComposer, SpeakButton } from "mathbank-widgets";
import ProblemDiagrams from "../../../_components/ProblemDiagrams.jsx";

const renderMath = (t) => <MathText>{t}</MathText>;
import {
  ACTION_BADGES, DECISION_NOTES, HINT_LADDER, canDiagnose, currentRecoveryItem, feedbackTone, gapStatusLabel,
  hintSummary, humanize, inRecovery, isConflict, likelihoodTone, masterySummary, nextHintLevel, probeHref, probeLabel,
  progressPercent, recoveryOutcome, recoveryPayload, recoveryStageProgress, stepLabel, timelineStatus,
} from "../../../../lib/solveFlow.mjs";

const enc = encodeURIComponent;

async function solveRequest(path, { method = "GET", body } = {}) {
  const init = { method, cache: "no-store" };
  if (method === "POST") {
    init.headers = { "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID() };
    init.body = JSON.stringify(body || {});
  }
  const res = await fetch(`/api/rest/solve/${path}`, init);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(typeof data.error === "string" ? data.error : data.error?.message || JSON.stringify(data.error));
    Object.assign(err, { status: res.status, body: data });
    throw err;
  }
  return data;
}

function Timeline({ timeline }) {
  return (
    <ol className="list-unstyled mb-0 solve-timeline">
      {timeline.map((entry) => {
        const status = timelineStatus(entry);
        return (
          <li key={entry.solution_step_id} className={`d-flex align-items-center gap-2 py-1${entry.is_current ? " fw-semibold" : ""}`}>
            <span className={`badge rounded-pill text-bg-${status.tone} solve-timeline-icon`} aria-hidden="true">{status.icon}</span>
            <span className={entry.state === "LOCKED" ? "text-secondary" : ""}>{stepLabel(entry)}</span>
            {entry.step_type && <span className="small text-secondary d-none d-xl-inline">· {humanize(entry.step_type)}</span>}
            <span className="visually-hidden">{status.label}</span>
            {entry.help_level_used > 0 && <span className="ms-auto badge text-bg-light border" title="hints used">💡 {entry.help_level_used}</span>}
          </li>
        );
      })}
    </ol>
  );
}

function CompletedSteps({ timeline }) {
  const done = timeline.filter((t) => t.reference_text);
  if (!done.length) return null;
  return (
    <div className="card shadow-sm border-0 mb-3">
      <div className="card-header bg-white fw-semibold">Established so far</div>
      <ul className="list-group list-group-flush">
        {done.map((t) => (
          <li key={t.solution_step_id} className="list-group-item">
            <div className="d-flex justify-content-between small text-secondary mb-1">
              <span>{stepLabel(t)}</span><span>{timelineStatus(t).label}</span>
            </div>
            <MathText>{t.reference_text}</MathText>
            {t.your_response && (
              <details className="small mt-1"><summary className="text-secondary">Your response</summary><MathText>{t.your_response}</MathText></details>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Practice({ stepId }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [open, setOpen] = useState(false);

  useEffect(() => { setData(null); setOpen(false); setError(null); }, [stepId]);

  async function load() {
    setOpen(true);
    if (data) return;
    try { setData(await solveRequest(`practice/${enc(stepId)}?limit=5`)); }
    catch (err) { setError(err.message); }
  }

  return (
    <div className="card shadow-sm border-0">
      <div className="card-header bg-white d-flex align-items-center">
        <span className="fw-semibold">Practise this skill</span>
        {!open && <button type="button" className="btn btn-sm btn-outline-secondary ms-auto" onClick={load}>Find similar steps</button>}
      </div>
      {open && (
        <div className="card-body small">
          {error && <div className="text-danger">{error}</div>}
          {!data && !error && <div role="status">Searching similar steps…</div>}
          {data && !data.results.length && <div className="text-secondary">No similar steps found.</div>}
          {data?.results?.map((r) => (
            <Link key={r.solution_step_id} className="d-flex justify-content-between text-decoration-none py-1 border-bottom"
              href={`/learn/solve/${enc(r.problem_code)}`}>
              <span>{r.problem_code}</span><span className="text-secondary">{humanize(r.step_type)}</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function Diagnosis({ step, busy, onDiagnose, onDetour }) {
  const d = step.diagnosis;
  const action = d ? ACTION_BADGES[d.recommended_action] : null;
  const suggestDetour = d?.recommended_action === "RECOVERY_DETOUR";
  return (
    <div className="card shadow-sm border-0 mb-3">
      <div className="card-header bg-white d-flex align-items-center gap-2">
        <span className="fw-semibold">What&apos;s tripping you up?</span>
        {d?.ranked_by === "AI" && <span className="badge text-bg-light border" title="Order refined by the AI tutor">AI-ranked</span>}
        {action && <span className={`badge text-bg-${action.tone} ms-auto`}>{action.label}</span>}
      </div>
      <div className="card-body small">
        {!d && (
          <p className="text-secondary mb-2">
            {canDiagnose(step)
              ? "Stuck? The tutor can look at your attempts and hints so far and suggest which skill to strengthen."
              : "Have a go at this step first — then the tutor can work out what might be missing."}
          </p>
        )}
        {d && (
          <>
            <p className="mb-2">{d.recommended_action_label}</p>
            <ol className="list-unstyled mb-2">
              {d.hypotheses.map((h) => (
                <li key={h.rank} className="d-flex align-items-start gap-2 py-1 border-bottom">
                  <span className={`badge text-bg-${likelihoodTone(h.likelihood)}`}>{h.likelihood}</span>
                  <span className="flex-grow-1">
                    <span className="fw-semibold">{h.target_label || "Unlabelled skill"}</span>
                    <span className="d-block text-secondary">{h.focus_label}</span>
                  </span>
                  {h.status !== "UNRESOLVED" && <span className="badge text-bg-light border">{gapStatusLabel(h.status)}</span>}
                </li>
              ))}
            </ol>
            {d.probes?.length > 0 && (
              <>
                <div className="fw-semibold mb-1">Quick checks for “{d.probe_target_label || d.hypotheses[0]?.target_label}”</div>
                {d.probes.map((p) => {
                  const href = probeHref(p);
                  const key = p.solution_step_id || p.learning_item_id;
                  const label = probeLabel(p);
                  return href ? (
                    <Link key={key} className="d-flex justify-content-between text-decoration-none py-1" href={href}>
                      <span>{label.title}</span><span className="text-secondary">{label.detail}</span>
                    </Link>
                  ) : (
                    <div key={key} className="d-flex justify-content-between py-1">
                      <span>{label.title}</span><span className="text-secondary">{label.detail}</span>
                    </div>
                  );
                })}
                {d.probes.some((p) => p.kind === "LEARNING_ITEM") && (
                  <div className="text-secondary mt-1">These questions are part of the detour below.</div>
                )}
              </>
            )}
          </>
        )}
        <div className="d-flex flex-wrap gap-2 mt-2">
          <button type="button" className="btn btn-sm btn-outline-primary" onClick={onDiagnose}
            disabled={!canDiagnose(step) || Boolean(busy)}>
            {busy === "diagnose" ? "Diagnosing…" : d ? "Re-check with my latest work" : "Diagnose where I'm stuck"}
          </button>
          <button type="button" className={`btn btn-sm ${suggestDetour ? "btn-danger" : "btn-outline-secondary"}`}
            onClick={() => onDetour(d)} disabled={Boolean(busy)}
            title="Practise the skill behind this step, then come straight back here">
            {busy === "detour" ? "Preparing…" : suggestDetour ? "Start a short detour" : "Strengthen this skill"}
          </button>
        </div>
      </div>
    </div>
  );
}

function StageTrack({ plan }) {
  return (
    <div className="d-flex flex-wrap gap-1 mb-3" aria-label="Detour stages">
      {recoveryStageProgress(plan).map((s) => {
        const cls = { done: "text-bg-success", current: "text-bg-primary", failed: "text-bg-warning", todo: "text-bg-light border text-secondary" }[s.state];
        return (
          <span key={s.stage} className={`badge rounded-pill ${cls}`}>
            {s.state === "done" ? "✓ " : s.state === "current" ? "● " : ""}{s.label}{s.count > 1 ? ` ×${s.count}` : ""}
          </span>
        );
      })}
    </div>
  );
}

function SourceProblem({ code, statement, part }) {
  if (!statement) return null;
  return (
    <details className="small mb-2">
      <summary className="text-secondary">Source problem {code}{part && part !== "MAIN" ? ` · part ${part}` : ""}</summary>
      <div className="border rounded p-2 mt-1 bg-light"><MathText>{statement}</MathText></div>
    </details>
  );
}

function RecoveryItem({ item, busy, onAnswer }) {
  const [choice, setChoice] = useState(null);
  const [text, setText] = useState("");
  const c = item.content || {};
  const payload = recoveryPayload(item, { choiceIndex: choice, text });
  const submit = (e) => { e.preventDefault(); if (payload) onAnswer(item, payload); };

  if (item.item_kind === "THEORY") {
    return (
      <form onSubmit={submit}>
        <h3 className="h6">{c.title}</h3>
        {c.skill_description && <p className="small text-secondary">{c.skill_description}</p>}
        <SourceProblem code={c.example_problem_code} statement={c.example_problem_statement} />
        <div className="border-start border-4 border-info ps-3 py-1 mb-3"><MathText>{c.example_step_text}</MathText></div>
        <button type="submit" className="btn btn-primary btn-sm" disabled={Boolean(busy)}>
          {busy === "recovery" ? "Saving…" : "Got it — continue"}
        </button>
      </form>
    );
  }
  return (
    <form onSubmit={submit}>
      <div className="d-flex align-items-center gap-2 mb-2">
        <h3 className="h6 mb-0">{item.type_label || c.title}</h3>
        {item.is_transfer && <span className="badge text-bg-info">New context</span>}
        {item.tries > 0 && <span className="small text-secondary ms-auto">Try {item.tries + 1} of 2</span>}
      </div>
      <SourceProblem code={c.source_problem_code} statement={c.source_problem_statement} part={c.source_part_label} />
      <div className="mb-3"><MathText>{c.question_text}</MathText></div>
      {c.form === "MCQ" ? (
        <div className="list-group mb-3" role="radiogroup">
          {(c.choices || []).map((choiceText, i) => (
            <label key={i} className={`list-group-item list-group-item-action d-flex gap-2 align-items-start${choice === i ? " active" : ""}`}>
              <input className="form-check-input mt-1" type="radio" name={`choice-${item.recovery_plan_item_id}`}
                checked={choice === i} onChange={() => setChoice(i)} />
              <span><MathText>{choiceText}</MathText></span>
            </label>
          ))}
        </div>
      ) : (
        <>
          <MathComposer value={text} onChange={setText} rows={4} ariaLabel="Your answer" testId="recovery-composer"
            placeholder="Write your step in words or LaTeX" renderMath={renderMath} />
        </>
      )}
      <button type="submit" className="btn btn-primary btn-sm mt-3" disabled={!payload || Boolean(busy)}>
        {busy === "recovery" ? <><span className="spinner-border spinner-border-sm me-1" />Checking…</> : "Check answer"}
      </button>
    </form>
  );
}

function FinishedItems({ plan }) {
  const done = (plan.items || []).filter((i) => i.item_kind === "LEARNING_ITEM" && ["PASSED", "FAILED"].includes(i.status));
  if (!done.length) return null;
  return (
    <details className="mt-3 small">
      <summary className="text-secondary">Questions answered so far ({done.length})</summary>
      <ul className="list-group list-group-flush mt-2">
        {done.map((i) => (
          <li key={i.recovery_plan_item_id} className="list-group-item px-0">
            <div className="d-flex gap-2 align-items-center mb-1">
              <span className={`badge text-bg-${i.status === "PASSED" ? "success" : "warning"}`}>{i.status === "PASSED" ? "✓" : "✗"}</span>
              <span className="fw-semibold">{i.type_label || i.stage_label}</span>
              <span className="text-secondary ms-auto">{i.independent_success ? "first try" : `${i.tries} tries`}</span>
            </div>
            {i.content?.question_text && <MathText>{i.content.question_text}</MathText>}
            {i.content?.answer && <div className="mt-1"><span className="text-secondary">Answer: </span><MathText>{i.content.answer}</MathText></div>}
          </li>
        ))}
      </ul>
    </details>
  );
}

function RecoveryPanel({ plan, busy, lastResult, onAnswer, onReturn, onAbort }) {
  const item = currentRecoveryItem(plan);
  const outcome = recoveryOutcome(plan);
  const origin = plan.origin || {};
  return (
    <div className="card shadow-sm border-0 border-start border-4 border-primary">
      <div className="card-header bg-white">
        <div className="small text-secondary text-uppercase fw-semibold">Detour · strengthening a skill</div>
        <div className="d-flex flex-wrap align-items-center gap-2">
          <h2 className="h5 mb-0">{plan.target_label || "This skill"}</h2>
          {plan.parent_target_label && <span className="badge text-bg-warning">building block for {plan.parent_target_label}</span>}
          <span className="small text-secondary ms-auto">
            Returns to {origin.problem_code} · {stepLabel({ part_label: origin.part_label, step_index_in_part: origin.step_index_in_part })}
          </span>
        </div>
      </div>
      <div className="card-body">
        <StageTrack plan={plan} />
        <p className="small text-secondary mb-3">{masterySummary(plan.mastery)}</p>
        {lastResult && (
          <div className={`alert alert-${lastResult.result?.result === "SUCCESS" ? "success" : "warning"} py-2`} role="status">
            <span className="fw-semibold me-1">{lastResult.result?.result === "SUCCESS" ? "Correct." : "Not yet."}</span>
            {lastResult.result?.feedback && lastResult.result.feedback !== "Correct." ? `${lastResult.result.feedback} ` : ""}
            {DECISION_NOTES[lastResult.decision] || ""}
          </div>
        )}
        {outcome ? (
          <div className={`alert alert-${outcome.tone}`}>
            <div className="fw-semibold">{outcome.title}</div>{outcome.text}
            <div className="mt-2">
              <button type="button" className="btn btn-primary btn-sm" onClick={onReturn} disabled={Boolean(busy)}>
                {busy === "return" ? "Returning…" : "Return to the original problem"}
              </button>
            </div>
          </div>
        ) : item && plan.status === "ACTIVE" ? (
          <RecoveryItem key={`${item.recovery_plan_item_id}:${item.tries}`} item={item} busy={busy} onAnswer={onAnswer} />
        ) : (
          <div className="text-secondary small">Loading the next question…</div>
        )}
        <FinishedItems plan={plan} />
        {!outcome && (
          <button type="button" className="btn btn-link btn-sm text-secondary px-0 mt-3" onClick={onAbort} disabled={Boolean(busy)}>
            Leave the detour and go back now
          </button>
        )}
      </div>
    </div>
  );
}

export default function SolveWorkspace({ code }) {
  const [attemptId, setAttemptId] = useState(null);
  const [runtime, setRuntime] = useState(null);
  const [hints, setHints] = useState([]);
  const [response, setResponse] = useState("");
  const [feedback, setFeedback] = useState(null);
  const [notice, setNotice] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);
  const [plan, setPlan] = useState(null);
  const [lastResult, setLastResult] = useState(null);
  const currentId = runtime?.current_step?.solution_step_id;
  const lastStep = useRef(null);
  const detourId = inRecovery(runtime) ? runtime.recovery.recovery_plan_id : null;
  const runtimeVersion = runtime?.attempt?.state_version;

  const refresh = useCallback(async (id = attemptId) => {
    const data = await solveRequest(`attempts/${enc(id)}`);
    setRuntime(data);
    return data;
  }, [attemptId]);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    solveRequest(`start/${enc(code)}`, { method: "POST" })
      .then((started) => {
        if (cancelled) return;
        setAttemptId(started.solve_attempt_id);
        setRuntime(started.runtime);
        const r = started.runtime;
        const hasProgress = r.timeline.some((t) => t.state !== "LOCKED" && !t.is_current)
          || (r.current_step && (r.current_step.attempt_count > 0 || r.current_step.help_level_used > 0));
        if (started.resumed && hasProgress) setNotice("Welcome back — your session was restored where you left off.");
      })
      .catch((err) => !cancelled && setError(err.status === 409
        ? "This problem does not have a step-by-step solution yet. Try the guided practice view instead."
        : err.message));
    return () => { cancelled = true; };
  }, [code]);

  // Restore the hint ladder and the last evaluation for the current step after refresh/advance.
  useEffect(() => {
    if (!attemptId || !currentId || lastStep.current === currentId) return;
    lastStep.current = currentId;
    setResponse("");
    setFeedback(runtime.current_step.last_evaluation || null);
    setHints([]);
    if (runtime.current_step.help_level_used > 0) {
      solveRequest(`attempts/${enc(attemptId)}/hints/${enc(currentId)}`).then((d) => setHints(d.hints)).catch(() => {});
    }
  }, [attemptId, currentId, runtime]);

  // Phase 10: a running detour is part of the persisted runtime, so a reload restores it exactly.
  useEffect(() => {
    if (!detourId) { setPlan(null); setLastResult(null); return; }
    let cancelled = false;
    solveRequest(`recovery-plans/${enc(detourId)}`).then((p) => !cancelled && setPlan(p)).catch(() => {});
    return () => { cancelled = true; };
  }, [detourId, runtimeVersion]);

  async function mutate(kind, fn) {
    setBusy(kind);
    setError(null);
    setNotice(null);
    try {
      await fn();
    } catch (err) {
      if (isConflict(err.status, err.body)) {
        await refresh();
        setNotice("This session changed in another tab — the latest state has been loaded.");
      } else {
        setError(err.message);
      }
    } finally {
      setBusy(null);
    }
  }

  const submit = (e) => {
    e.preventDefault();
    if (!response.trim()) return;
    mutate("submit", async () => {
      const result = await solveRequest(`attempts/${enc(attemptId)}/responses/${enc(currentId)}`, {
        method: "POST", body: { response_text: response, state_version: runtime.attempt.state_version } });
      if (result.evaluation_status === "UNAVAILABLE") {
        setNotice("Your response was saved, but the tutor could not check it right now. Please try submitting again.");
      } else if (result.evaluation_status === "PENDING") {
        setNotice("Your response was saved; checking is still pending.");
      }
      const fresh = await refresh();
      if (result.evaluation && fresh.current_step?.solution_step_id === currentId) setFeedback(result.evaluation);
      else if (result.evaluation) setNotice(`✓ ${result.evaluation.feedback || "Correct."} On to the next step.`);
    });
  };

  const askHint = () => mutate("hint", async () => {
    const result = await solveRequest(`attempts/${enc(attemptId)}/hint/${enc(currentId)}`, {
      method: "POST", body: { state_version: runtime.attempt.state_version } });
    setHints((prev) => [...prev.filter((h) => h.help_level !== result.help_level), result]);
    await refresh();
  });

  const diagnose = () => mutate("diagnose", async () => {
    const result = await solveRequest(`attempts/${enc(attemptId)}/diagnose/${enc(currentId)}`, { method: "POST" });
    if (result.reused) setNotice("Nothing new since the last check — here is the same diagnosis.");
    await refresh();
  });

  const startDetour = (d) => mutate("detour", async () => {
    const body = { state_version: runtime.attempt.state_version,
      ...(d ? { trigger: "DIAGNOSIS", gap_diagnosis_id: d.gap_diagnosis_id } : { trigger: "STUDENT_REQUEST" }) };
    const result = await solveRequest(`attempts/${enc(attemptId)}/recovery-plans`, { method: "POST", body });
    setPlan(result.recovery_plan);
    setLastResult(null);
    if (result.resumed) setNotice("You already have a detour in progress — picking up where you left off.");
    await refresh();
  });

  const answerRecovery = (item, payload) => mutate("recovery", async () => {
    const result = await solveRequest(`recovery-plans/${enc(plan.recovery_plan_id)}/items/${enc(item.recovery_plan_item_id)}`, {
      method: "POST", body: { ...payload, state_version: runtime.attempt.state_version } });
    setPlan(result.recovery_plan);
    setLastResult(item.item_kind === "THEORY" ? null : result);
    await refresh();
  });

  const leaveDetour = (abort) => mutate(abort ? "abort" : "return", async () => {
    await solveRequest(`recovery-plans/${enc(plan.recovery_plan_id)}/${abort ? "abort" : "resume"}`, {
      method: "POST", body: { state_version: runtime.attempt.state_version } });
    setPlan(null);
    setLastResult(null);
    lastStep.current = null;  // re-load hints and the last evaluation for the origin step
    await refresh();
    setNotice(abort ? "Back to your step — the detour was saved and you can start another any time."
      : "Back to the step where you were stuck. Try it again with what you just practised.");
  });

  if (error && !runtime) {
    return (
      <div className="alert alert-warning">
        <div className="fw-semibold mb-1">Could not open {code}</div>{error}
        <div className="mt-2"><Link href={`/learn?problem=${enc(code)}`}>Open guided practice</Link></div>
      </div>
    );
  }
  if (!runtime) return <div className="d-flex align-items-center gap-2" role="status"><span className="spinner-border spinner-border-sm" /> Opening your session…</div>;

  const { attempt, current_step: step, timeline, progress } = runtime;
  const pct = progressPercent(progress);
  const completed = attempt.status !== "IN_PROGRESS" || !step;
  const nextHint = step ? nextHintLevel(step.help_level_used) : null;
  const tone = feedbackTone(feedback);
  const detouring = Boolean(detourId);

  return (
    <div className="solve-workspace">
      <PageHeader icon="signpost-split" title={attempt.problem_code} subtitle="Step-by-step solving"
        pills={<>
          <Pill tone={completed ? "success" : "primary"} icon={completed ? "check-circle" : "play-circle"}>{humanize(attempt.status)}</Pill>
          <Pill tone="neutral" icon="list-check">{progress.completed_steps}/{progress.total_steps} steps</Pill>
          {detouring && <Pill tone="warning" icon="arrow-return-right">Detour</Pill>}
        </>}
        actions={<><IconButton icon="file-earmark-richtext" label="Upload my written attempt" href={`/learn/attempt-media?problem_ref=${enc(code)}`} />
          <IconButton icon="compass" label="Guided view" variant="outline-secondary" href={`/learn?problem=${enc(code)}`} /></>} />
      <div className="mb-bar-track mb-3" role="progressbar" aria-label="Solution progress" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
        <div className="mb-bar-fill" style={{ width: `${pct}%` }} />
      </div>

      {notice && <Callout tone="neutral" role="status" className="mb-3">{notice}</Callout>}
      {error && <Callout tone="danger" role="alert" className="mb-3">{error}</Callout>}

      <div className="row g-3">
        <div className="col-lg-7">
          <div className="card mb-3">
            <div className="card-header fw-semibold"><Icon name="file-earmark-text" className="me-2 text-primary" />Problem</div>
            <div className="card-body">
              <MathText>{attempt.statement_text}</MathText>
              <ProblemDiagrams code={attempt.problem_code || code}
                imageAlt={(image) => `Diagram ${image.ordinal} for ${attempt.problem_code || code}`} />
            </div>
          </div>

          <CompletedSteps timeline={timeline} />

          {completed ? (
            <div className="card shadow-sm border-0 border-start border-success border-4">
              <div className="card-body">
                <h2 className="h5"><Icon name="trophy" className="me-2 text-success" />Problem complete</h2>
                <p className="mb-2">
                  {timeline.filter((t) => t.state === "SUCCESS_INDEPENDENT").length} steps solved independently,{" "}
                  {timeline.filter((t) => t.state === "SUCCESS_WITH_HELP").length} with help. Your mastery has been updated.
                </p>
                <Link className="btn btn-primary btn-sm" href="/profile">See my progress</Link>
              </div>
            </div>
          ) : detouring ? (
            plan ? (
              <RecoveryPanel plan={plan} busy={busy} lastResult={lastResult} onAnswer={answerRecovery}
                onReturn={() => leaveDetour(false)} onAbort={() => leaveDetour(true)} />
            ) : <div className="d-flex align-items-center gap-2" role="status"><span className="spinner-border spinner-border-sm" /> Loading your detour…</div>
          ) : (
            <form className="card shadow-sm border-0" onSubmit={submit}>
              <div className="card-header bg-white d-flex flex-wrap align-items-center gap-2">
                <span className="fw-semibold">{stepLabel(step)}</span>
                {step.step_type && <span className="badge text-bg-light border">{humanize(step.step_type)}</span>}
                {step.is_checkpoint && <span className="badge text-bg-warning">Checkpoint</span>}
                {step.attempt_count > 0 && <span className="small text-secondary ms-auto">Attempt {step.attempt_count + 1}</span>}
              </div>
              <div className="card-body">
                <p className="mb-1"><span className="fw-semibold">Goal:</span> {step.goal}</p>
                {step.skill_name && <p className="small text-secondary mb-3">Skill: {step.skill_name}</p>}
                {feedback && (
                  <Callout tone={tone} role="status" className="mb-3"
                    title={feedback.result === "SUCCESS" ? "Correct" : humanize(feedback.verdict || "not yet")}>
                    {feedback.feedback}
                  </Callout>
                )}
                <label htmlFor="step-response" className="form-label small fw-semibold">Your reasoning for this step</label>
                <MathComposer id="step-response" ariaLabel="Your reasoning for this step" testId="step-composer" rows={4}
                  value={response} onChange={setResponse} renderMath={renderMath}
                  placeholder="Write this step in words or LaTeX, e.g. Since PQ || AD, …" />
                <div className="d-flex gap-2 mt-3">
                  <button type="submit" className="btn btn-primary" disabled={!response.trim() || Boolean(busy)}>
                    {busy === "submit" ? <><span className="spinner-border spinner-border-sm me-1" />Checking…</> : "Check my step"}
                  </button>
                </div>
              </div>
            </form>
          )}
        </div>

        <div className="col-lg-5">
          {!completed && !detouring && (
            <div className="card shadow-sm border-0 mb-3">
              <div className="card-header fw-semibold"><Icon name="lightbulb" className="me-2 text-warning" />Hints</div>
              <div className="card-body">
                <p className="small text-secondary">{hintSummary(step.help_level_used)}</p>
                <div className="d-flex gap-1 mb-3" aria-label="Hint ladder">
                  {HINT_LADDER.map((h) => (
                    <span key={h.level} title={h.detail}
                      className={`flex-fill text-center small rounded py-1 ${h.level <= step.help_level_used ? "bg-warning-subtle fw-semibold" : "bg-light text-secondary"}`}>
                      {h.label}
                    </span>
                  ))}
                </div>
                {hints.slice().sort((a, b) => a.help_level - b.help_level).map((h) => (
                  <div key={h.help_level} className={`border-start border-3 ps-2 mb-2 ${h.help_level === 5 ? "border-danger" : "border-warning"}`}>
                    <div className="small text-secondary">{HINT_LADDER[h.help_level - 1]?.label}</div>
                    {h.hint_text ? (
                      <div className="d-flex gap-2 align-items-start"><div className="flex-grow-1"><MathText>{h.hint_text}</MathText></div>
                        <SpeakButton text={h.hint_text} className="py-0" label="Listen to this hint" /></div>
                    ) : <span className="small text-secondary">Hint text is unavailable right now.</span>}
                  </div>
                ))}
                {nextHint && (
                  <button type="button" className={`btn btn-sm ${nextHint.level === 5 ? "btn-outline-danger" : "btn-outline-warning"}`}
                    onClick={askHint} disabled={Boolean(busy)}>
                    {busy === "hint" ? "Thinking…" : nextHint.level === 5 ? "Reveal this step" : `Get a hint: ${nextHint.label.toLowerCase()}`}
                  </button>
                )}
              </div>
            </div>
          )}
          {!completed && !detouring && <Diagnosis step={step} busy={busy} onDiagnose={diagnose} onDetour={startDetour} />}
          <div className="card shadow-sm border-0 mb-3">
            <div className="card-header bg-white fw-semibold">Solution path</div>
            <div className="card-body"><Timeline timeline={timeline} /></div>
          </div>
          {step && !detouring && <Practice stepId={step.solution_step_id} />}
        </div>
      </div>
    </div>
  );
}
