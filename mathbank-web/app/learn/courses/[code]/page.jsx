"use client";

import { Suspense, useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import MathText from "../../../_components/MathText.jsx";
import { Callout, EmptyState, Icon, PageHeader, Pill } from "../../../_components/ui.jsx";
import InteractionTemplateRenderer from "./InteractionTemplateRenderer.jsx";

const STATE_TYPE_LABELS = {
  ORIENTATION: "Start here",
  EXPLANATION: "Learn",
  SLIDE: "Visual explanation",
  VIDEO: "Watch",
  READING: "Read",
  VISUAL: "Explore",
  EXAMPLE: "Worked example",
  CHECKPOINT: "Checkpoint",
  QUIZ: "Quiz",
  DIAGNOSTIC: "Quick check",
  REMEDIATION: "Review",
  PRACTICE: "Practice",
  SUMMARY: "Key ideas",
  TRANSFER: "Apply it",
};

/** Returns a privacy-friendly youtube-nocookie embed URL for common watch/share/embed
 * link shapes, or null when the URL is not a recognizable YouTube link. */
function youTubeEmbedUrl(url) {
  if (!url) return null;
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return null;
  }
  const host = parsed.hostname.replace(/^www\./, "");
  let videoId = null;
  if (host === "youtu.be") {
    videoId = parsed.pathname.slice(1);
  } else if (host === "youtube.com" || host === "m.youtube.com" || host === "youtube-nocookie.com") {
    if (parsed.pathname === "/watch") videoId = parsed.searchParams.get("v");
    else if (parsed.pathname.startsWith("/embed/")) videoId = parsed.pathname.split("/")[2];
  }
  if (!videoId) return null;
  // Carry a chapter/timestamp start time (e.g. "?t=7248s") into the embed's start= param.
  const rawStart = parsed.searchParams.get("t") || parsed.searchParams.get("start");
  const startSeconds = rawStart ? parseInt(rawStart.replace(/s$/, ""), 10) : null;
  const query = Number.isFinite(startSeconds) && startSeconds > 0 ? `?start=${startSeconds}` : "";
  return `https://www.youtube-nocookie.com/embed/${videoId}${query}`;
}

const ACTIVITY_PURPOSE_LABELS = {
  ENTRY_CHECK: "Quick check",
  COMPREHENSION: "Checkpoint question",
  RECOGNITION: "Recognition check",
  MISCONCEPTION_DIAGNOSTIC: "Common mistake check",
  EXECUTION: "Practice question",
  EXIT_CHECK: "Exit check",
  TRANSFER: "Transfer question",
};

/** Interactive preview quiz question (MCQ/NUMERIC). Grades locally against the
 * already-visible correctness_policy; when `onRespond` is given (student is enrolled),
 * the attempt is also recorded server-side via POST .../activity-responses. The
 * correct answer is never pre-highlighted — only after the student answers. */
function QuizActivity({ activity, onRespond }) {
  const policy = activity.correctness_policy || {};
  const options = Array.isArray(activity.options) ? activity.options : [];
  const isNumeric = activity.activity_type === "NUMERIC";
  const [selectedIndex, setSelectedIndex] = useState(null);
  const [numericValue, setNumericValue] = useState("");
  const [pending, setPending] = useState(false);
  const [result, setResult] = useState(
    typeof activity.answered_correctly === "boolean"
      ? { is_correct: activity.answered_correctly, explanation: policy.explanation, previousAttempt: true }
      : null,
  );

  async function choose(index) {
    if (result || pending) return;
    setSelectedIndex(index);
    setPending(true);
    const response = onRespond ? await onRespond({ activityId: activity.activity_id, choiceIndex: index }) : null;
    setPending(false);
    setResult(response || { is_correct: index === policy.correct_index, explanation: policy.explanation });
  }

  async function submitNumeric() {
    if (result || pending || numericValue === "") return;
    setPending(true);
    const value = Number(numericValue);
    const response = onRespond ? await onRespond({ activityId: activity.activity_id, value }) : null;
    setPending(false);
    setResult(response || {
      is_correct: policy.correct_value !== undefined && Math.abs(value - Number(policy.correct_value)) < 1e-9,
      explanation: policy.explanation,
    });
  }

  return (
    <Callout tone={result ? (result.is_correct ? "success" : "warning") : "hint"} title={ACTIVITY_PURPOSE_LABELS[activity.purpose] || "Quiz question"}>
      <MathText>{activity.prompt}</MathText>
      {isNumeric ? (
        <div className="d-flex flex-wrap gap-2 align-items-center mt-2">
          <label className="visually-hidden" htmlFor={`activity-${activity.activity_id}`}>Your numeric answer</label>
          <input id={`activity-${activity.activity_id}`} type="number" className="form-control form-control-sm mb-num"
            style={{ maxWidth: "8rem" }} value={numericValue} disabled={!!result}
            onChange={event => setNumericValue(event.target.value)} />
          <button type="button" className="btn btn-sm btn-primary" disabled={!!result || pending || numericValue === ""}
            onClick={submitNumeric}>
            Check answer
          </button>
        </div>
      ) : options.length > 0 && (
        <div className="d-flex flex-column gap-2 mt-2" role="group" aria-label="Answer options">
          {options.map((option, index) => {
            let variant = "btn-outline-secondary";
            if (result) {
              if (index === policy.correct_index) variant = "btn-outline-success";
              else if (index === selectedIndex) variant = "btn-outline-danger";
            }
            return (
              <button key={index} type="button" className={`btn btn-sm text-start ${variant}`}
                disabled={!!result || pending} onClick={() => choose(index)}>
                <MathText>{option}</MathText>
              </button>
            );
          })}
        </div>
      )}
      {result && (
        <div className="mt-2 small d-flex align-items-start gap-2">
          <Icon name={result.is_correct ? "check-circle-fill" : "x-circle-fill"} />
          <div>
            {result.previousAttempt && <p className="mb-1 fst-italic">You already answered this one.</p>}
            {result.explanation && <MathText>{result.explanation}</MathText>}
          </div>
        </div>
      )}
    </Callout>
  );
}

function StepContent({ state, courseCode, onRecordActivity, onRecordInteractionEvent }) {
  return (
    <article className="card border-0 shadow-sm p-3 p-lg-4" aria-live="polite">
      <div className="d-flex flex-wrap justify-content-between gap-2 align-items-start">
        <div>
          <h3 className="h5 mb-1">{state.title}</h3>
        </div>
        <Pill tone={state.required ? "primary" : "neutral"}>{STATE_TYPE_LABELS[state.state_type] || "Lesson"}</Pill>
      </div>
      {state.objective && <Callout tone="insight" title="Focus" className="mt-3"><MathText>{state.objective}</MathText></Callout>}
      {state.student_instruction && (
        <div className="mt-3 mb-course-reading">
          <MathText>{state.student_instruction}</MathText>
        </div>
      )}
      {state.assets?.map((asset, index) => {
        const href = asset.private_object
          ? `/api/rest/micro-courses/${encodeURIComponent(courseCode)}/assets/${encodeURIComponent(asset.asset_id)}/content`
          : asset.video_url || asset.source_url;
        if (!href) return null;
        if (asset.private_object && asset.mime_type?.startsWith("image/")) {
          return <img key={`${asset.asset_id || asset.asset_kind}-${index}`} className="img-fluid rounded-3 my-3"
            src={href} alt={asset.title || "Course illustration"} />;
        }
        if (asset.private_object && asset.mime_type?.startsWith("video/")) {
          return <video key={`${asset.asset_id}-${index}`} className="w-100 rounded-3 my-3" controls preload="metadata">
            <source src={href} type={asset.mime_type} />
            Your browser does not support embedded video.
          </video>;
        }
        if (asset.private_object && asset.mime_type?.startsWith("audio/")) {
          return <audio key={`${asset.asset_id}-${index}`} className="w-100 my-3" controls preload="metadata">
            <source src={href} type={asset.mime_type} />
            Your browser does not support embedded audio.
          </audio>;
        }
        const embedUrl = !asset.private_object ? youTubeEmbedUrl(href) : null;
        if (embedUrl) {
          return (
            <div key={`${asset.asset_id || asset.asset_kind}-${index}`} className="my-3">
              <div className="ratio ratio-16x9 rounded-3 overflow-hidden">
                <iframe
                  src={embedUrl}
                  title={asset.title || "Approved course video"}
                  loading="lazy"
                  allow="accelerometer; encrypted-media; picture-in-picture"
                  allowFullScreen
                />
              </div>
              {asset.title && <p className="small text-secondary mt-2 mb-0">{asset.title}</p>}
            </div>
          );
        }
        return (
          <Callout key={`${asset.asset_kind}-${index}`} tone="hint" title={asset.title || asset.asset_kind || "Course resource"}>
            <a href={href} target="_blank" rel="noreferrer">{asset.private_object ? "Open approved resource" : "Open approved external resource"}</a>
            {asset.duration_ms ? <Pill className="ms-2" tone="neutral">{Math.ceil(asset.duration_ms / 60000)} min</Pill> : null}
          </Callout>
        );
      })}
      {state.interactions?.map(interaction => (
        <InteractionTemplateRenderer key={interaction.interaction_instance_id} interaction={interaction}
          onRecordInteractionEvent={onRecordInteractionEvent} />
      ))}
      {state.transcript_segments?.length > 0 && (
        <details className="mt-3">
          <summary className="fw-semibold">Approved transcript · {state.transcript_segments.length} segments</summary>
          <ol className="list-unstyled mt-3 mb-0">
            {state.transcript_segments.map(segment => (
              <li className="border-start ps-3 mb-3" key={segment.segment_id}>
                <Pill tone="neutral">{Math.floor(segment.start_ms / 60000)}:{String(Math.floor(segment.start_ms / 1000) % 60).padStart(2, "0")}</Pill>
                {segment.speaker && <span className="small text-secondary ms-2">{segment.speaker}</span>}
                <div className="mt-1"><MathText>{segment.transcript_text}</MathText></div>
              </li>
            ))}
          </ol>
        </details>
      )}
      {state.learning_items?.map(item => (
        <Callout key={item.learning_item_id} tone="hint" title={item.purpose.replaceAll("_", " ")}>
          <MathText>{item.question_text}</MathText>
          {Array.isArray(item.choices) && item.choices.length > 0 && (
            <ul className="mb-0 mt-2">
              {item.choices.map((choice, index) => (
                <li key={index}><MathText>{typeof choice === "string" ? choice : JSON.stringify(choice)}</MathText></li>
              ))}
            </ul>
          )}
        </Callout>
      ))}
      {state.activities?.map(activity => (
        <QuizActivity key={activity.activity_id} activity={activity}
          onRespond={onRecordActivity ? payload => onRecordActivity(payload) : null} />
      ))}
      {state.qa_contexts?.map((context, index) => (
        <Callout key={`${context.context_type}-${index}`} tone="insight" title={context.context_type.replaceAll("_", " ")}>
          {context.question_pattern && <strong className="d-block mb-1">{context.question_pattern}</strong>}
          <MathText>{context.approved_content}</MathText>
        </Callout>
      ))}
    </article>
  );
}

/** Step navigator: a vertical rail on wide screens, a horizontal scrollable row on
 * narrow screens (pure CSS responsive switch, see .mb-course-stepper in globals.css). */
function CourseStepper({ steps, activeOrdinal, reachableOrdinal, onSelect }) {
  return (
    <nav className="mb-course-stepper" aria-label="Lesson steps">
      {steps.map(step => {
        const isCurrent = step.ordinal === activeOrdinal;
        const isDone = step.ordinal < reachableOrdinal;
        const isLocked = step.ordinal > reachableOrdinal;
        return (
          <button key={step.state_id} type="button"
            className={`mb-course-step${isCurrent ? " is-current" : ""}${isDone ? " is-done" : ""}`}
            disabled={isLocked} aria-current={isCurrent ? "step" : undefined}
            onClick={() => onSelect(step.ordinal)}>
            <span className="mb-course-step-dot" aria-hidden="true">
              {isDone ? <Icon name="check-lg" /> : step.ordinal + 1}
            </span>
            <span className="mb-course-step-label">
              <span className="d-block">{step.title}</span>
              <span className="small text-secondary">{STATE_TYPE_LABELS[step.state_type] || "Lesson"}</span>
            </span>
          </button>
        );
      })}
    </nav>
  );
}

/** Start/resume/continue controls. Anonymous visitors get a free local preview
 * (no persistence); logged-in students get a real, server-persisted enrollment. */
function EnrollmentPanel({ studentStatus, enrollment, enrolling, actionError, onStart, isAdminPreview }) {
  if (studentStatus === "loading") return null;
  if (isAdminPreview) {
    return (
      <Callout tone="warning" title="Admin preview — not visible to students" className="mb-3">
        <p className="mb-0">
          You are browsing the real student reader for a release that is not (or not yet)
          published. Progress is not saved while previewing.
        </p>
      </Callout>
    );
  }
  if (studentStatus === "anonymous") {
    return (
      <Callout tone="hint" title="Preview mode" className="mb-3">
        <p className="mb-0">
          You can browse every step below, but progress will not be saved.{" "}
          <a href="/login">Log in as a student</a> to track your progress and record quiz attempts.
        </p>
      </Callout>
    );
  }
  if (!enrollment) {
    return (
      <div className="d-flex flex-wrap align-items-center gap-3 mb-3">
        <button type="button" className="btn btn-primary" onClick={onStart} disabled={enrolling}>
          <Icon name="play-fill" /> {enrolling ? "Starting…" : "Start lesson"}
        </button>
        {actionError && <span className="text-danger small">{actionError}</span>}
      </div>
    );
  }
  if (enrollment.enrollment_status === "COMPLETED") {
    return (
      <Callout tone="success" title="Lesson completed" className="mb-3">
        <p className="mb-0">Nice work — you completed every step. Use the list to review any step again.</p>
      </Callout>
    );
  }
  return (
    <div className="d-flex flex-wrap align-items-center gap-2 mb-3">
      <Pill tone="primary" icon="signpost-split">Step {enrollment.step_number} of {enrollment.step_count}</Pill>
      {actionError && <span className="text-danger small">{actionError}</span>}
    </div>
  );
}

function PublishedCourseWorkspaceInner() {
  const params = useParams();
  const searchParams = useSearchParams();
  const code = Array.isArray(params.code) ? params.code[0] : params.code;
  const isAdminPreview = searchParams.get("preview") === "1";
  const previewReleaseId = searchParams.get("release_id") || "";
  const [course, setCourse] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [studentStatus, setStudentStatus] = useState("loading"); // loading | anonymous | active
  const [enrollment, setEnrollment] = useState(null);
  const [enrolling, setEnrolling] = useState(false);
  const [actionError, setActionError] = useState("");
  const [localIndex, setLocalIndex] = useState(0); // used only for anonymous preview + reviewing past steps

  useEffect(() => {
    if (!code) return undefined;
    const controller = new AbortController();
    const url = isAdminPreview
      ? `/api/rest/admin/micro-courses/${encodeURIComponent(code)}/preview${previewReleaseId ? `?release_id=${encodeURIComponent(previewReleaseId)}` : ""}`
      : `/api/rest/micro-courses/${encodeURIComponent(code)}`;
    fetch(url, {
      cache: "no-store",
      signal: controller.signal,
    }).then(async response => {
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || `Course could not be loaded (${response.status})`);
      return body;
    }).then(setCourse)
      .catch(err => { if (err.name !== "AbortError") setError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [code, isAdminPreview, previewReleaseId]);

  useEffect(() => {
    if (isAdminPreview) { setStudentStatus("anonymous"); return undefined; }
    const controller = new AbortController();
    fetch("/api/rest/learner/me", { cache: "no-store", signal: controller.signal })
      .then(response => setStudentStatus(response.ok ? "active" : "anonymous"))
      .catch(err => { if (err.name !== "AbortError") setStudentStatus("anonymous"); });
    return () => controller.abort();
  }, [isAdminPreview]);

  async function startOrResumeEnrollment() {
    setEnrolling(true);
    setActionError("");
    try {
      const response = await fetch(`/api/rest/micro-courses/${encodeURIComponent(code)}/enroll`, { method: "POST" });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "Could not start this lesson.");
      setEnrollment(body);
      setLocalIndex(body.current_state.ordinal);
    } catch (err) {
      setActionError(err.message);
    } finally {
      setEnrolling(false);
    }
  }

  async function advanceEnrollment(action) {
    if (!enrollment) return;
    setActionError("");
    try {
      const response = await fetch(`/api/rest/micro-courses/enrollments/${enrollment.enrollment_id}/advance`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_state_version: enrollment.state_version, action }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "Could not update your progress.");
      setEnrollment(body);
      setLocalIndex(body.current_state.ordinal);
    } catch (err) {
      setActionError(err.message);
    }
  }

  async function recordActivity({ activityId, choiceIndex, value }) {
    if (!enrollment) return null;
    try {
      const response = await fetch(`/api/rest/micro-courses/enrollments/${enrollment.enrollment_id}/activity-responses`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ activity_id: activityId, choice_index: choiceIndex ?? null, value: value ?? null }),
      });
      const body = await response.json();
      if (!response.ok) return null;
      return body;
    } catch {
      return null;
    }
  }

  // Silent/implicit telemetry (slider settles, control edits) — best-effort, never surfaced
  // to the student and never blocking; failures here must not disrupt the lesson experience.
  async function recordInteractionEvent({ interactionInstanceId, eventType, semanticAction, controlKey, actionPayload }) {
    if (!enrollment) return;
    try {
      await fetch(`/api/rest/micro-courses/enrollments/${enrollment.enrollment_id}/interaction-events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          interaction_instance_id: interactionInstanceId,
          event_type: eventType,
          semantic_action: semanticAction,
          control_key: controlKey ?? null,
          action_payload: actionPayload || {},
        }),
      });
    } catch {
      // Best-effort telemetry: silently drop on failure.
    }
  }

  if (loading) {
    return <>
      <PageHeader icon="diagram-3" title="Loading course" subtitle="Opening the published lesson." />
      <p role="status" className="text-secondary">Loading course content…</p>
    </>;
  }
  if (error || !course) {
    return <>
      <PageHeader icon="diagram-3" title="Course unavailable" subtitle="This published lesson could not be opened." />
      <Callout tone="danger" role="alert">{error || "Published course not found."}</Callout>
    </>;
  }

  const steps = [...course.states].sort((a, b) => a.ordinal - b.ordinal);
  const enrolled = enrollment && enrollment.enrollment_status === "IN_PROGRESS";
  // Reachable = how far the stepper unlocks. Enrolled students only unlock up through
  // their server-pinned current step; anonymous/completed visitors can browse freely.
  const reachableOrdinal = enrolled
    ? enrollment.current_state.ordinal
    : steps.length ? steps[steps.length - 1].ordinal : 0;
  const isViewingCurrent = enrolled && localIndex === enrollment.current_state.ordinal;
  const activeState = isViewingCurrent
    ? enrollment.current_state
    : steps.find(step => step.ordinal === localIndex) || steps[0];
  const releaseStatus = course.release_status; // only present on admin-preview reads
  const versionPill = releaseStatus && releaseStatus !== "PUBLISHED"
    ? <Pill key="version" tone="warning">{releaseStatus.charAt(0) + releaseStatus.slice(1).toLowerCase()} v{course.version}</Pill>
    : <Pill key="version" tone="success">Published v{course.version}</Pill>;

  return (
    <>
      <PageHeader
        icon="diagram-3"
        title={course.title}
        subtitle={course.description || "A focused, instructor-reviewed MathBank lesson."}
        pills={[
          versionPill,
          ...course.primary_targets.map(target => (
            <Pill key={`${target.target_type}-${target.slug}`} tone="primary">{target.name}</Pill>
          )),
        ]}
      />
      {course.learning_objectives?.length > 0 && (
        <Callout tone="insight" title="What you will learn">
          <ul className="mb-0">
            {course.learning_objectives.map((objective, index) => <li key={index}><MathText>{typeof objective === "string" ? objective : objective.text || JSON.stringify(objective)}</MathText></li>)}
          </ul>
        </Callout>
      )}
      <div className="d-flex flex-wrap gap-2 mb-3">
        <Pill tone="neutral" icon="clock">{course.estimated_minutes ? `${course.estimated_minutes} min` : "Self-paced"}</Pill>
        <Pill tone="neutral" icon="list-check">{course.states.length} learning steps</Pill>
      </div>
      <EnrollmentPanel studentStatus={studentStatus} enrollment={enrollment} enrolling={enrolling}
        actionError={actionError} onStart={startOrResumeEnrollment} isAdminPreview={isAdminPreview} />
      {steps.length === 0 && <EmptyState icon="inbox">This release has no lesson states yet.</EmptyState>}
      {steps.length > 0 && (
        <div className="mb-course-workspace">
          <CourseStepper steps={steps} activeOrdinal={localIndex} reachableOrdinal={reachableOrdinal}
            onSelect={setLocalIndex} />
          <div className="mb-course-content">
            <StepContent state={activeState} courseCode={code}
              onRecordActivity={isViewingCurrent ? recordActivity : null}
              onRecordInteractionEvent={isViewingCurrent ? recordInteractionEvent : null} />
            {isViewingCurrent && enrolled && (
              <div className="d-flex justify-content-between gap-2 mt-3">
                <button type="button" className="btn btn-outline-secondary" disabled={!enrollment.can_go_back}
                  onClick={() => advanceEnrollment("BACK")}>
                  <Icon name="arrow-left" /> Back
                </button>
                <button type="button" className="btn btn-primary" disabled={!enrollment.can_continue && !enrollment.can_finish}
                  onClick={() => advanceEnrollment("CONTINUE")}>
                  {enrollment.can_finish ? "Finish lesson" : "Continue"} <Icon name="arrow-right" />
                </button>
              </div>
            )}
            {!isViewingCurrent && enrolled && (
              <div className="mt-3">
                <button type="button" className="btn btn-outline-primary btn-sm"
                  onClick={() => setLocalIndex(enrollment.current_state.ordinal)}>
                  <Icon name="arrow-return-left" /> Back to where you left off
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}

export default function PublishedCourseWorkspace() {
  return (
    <Suspense fallback={<p role="status" className="text-secondary">Loading…</p>}>
      <PublishedCourseWorkspaceInner />
    </Suspense>
  );
}
