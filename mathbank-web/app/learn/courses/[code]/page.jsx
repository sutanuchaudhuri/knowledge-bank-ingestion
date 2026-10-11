"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
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

// Sub-rail labels for the per-item decomposition (requirements/47 §2.2, MCN2-3).
const SUB_ITEM_LABELS = {
  asset: "Watch/read",
  interaction: "Explore",
  learning_item: "Quick check",
  activity: "Quiz question",
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

const LEARNING_ITEM_PURPOSE_LABELS = {
  ENTRY_CHECK: "Pre-check",
  EXIT_CHECK: "Exit check",
  COMPREHENSION: "Checkpoint question",
  RECOGNITION: "Recognition check",
  MISCONCEPTION_DIAGNOSTIC: "Common mistake check",
  EXECUTION: "Practice question",
  TRANSFER: "Transfer question",
};

/** Normalizes the two differently-shaped gradable item records (`activity.definition`'s
 * `prompt`/`options`/`correctness_policy` vs. `learning_item`'s `question_text`/`choices`/
 * `correct_answer`) into one field set `GradableItem` renders from — the "small adapter,
 * not a second parallel component" requirements/47 §2.4/MCN2-5 calls for. */
function gradableItemFields(kind, raw) {
  if (kind === "learning_item") {
    const choices = Array.isArray(raw.choices) ? raw.choices.map(choice => (typeof choice === "string" ? choice : JSON.stringify(choice))) : [];
    return {
      id: raw.learning_item_id,
      prompt: raw.question_text,
      options: choices,
      isNumeric: false,
      correctIndex: Array.isArray(raw.choices) ? raw.choices.findIndex(choice => choice === raw.correct_answer) : -1,
      correctValue: null,
      explanation: raw.answer_or_solution_seed,
      title: LEARNING_ITEM_PURPOSE_LABELS[raw.purpose] || (raw.purpose || "Pre-check").replaceAll("_", " "),
      previouslyAnswered: typeof raw.answered_correctly === "boolean" ? raw.answered_correctly : null,
    };
  }
  const policy = raw.correctness_policy || {};
  return {
    id: raw.activity_id,
    prompt: raw.prompt,
    options: Array.isArray(raw.options) ? raw.options : [],
    isNumeric: raw.activity_type === "NUMERIC",
    correctIndex: policy.correct_index,
    correctValue: policy.correct_value,
    explanation: policy.explanation,
    title: ACTIVITY_PURPOSE_LABELS[raw.purpose] || "Quiz question",
    previouslyAnswered: typeof raw.answered_correctly === "boolean" ? raw.answered_correctly : null,
  };
}

/** Scoped "Help me?" / "Give up" micro-chat for exactly one lesson item
 * (requirements/47 §3, MCN2-6/MCN2-7). Opens inline next to the item it belongs to —
 * never a floating global widget. `onGiveUp` (when provided) receives the raw assist
 * response so the caller can resolve the item (reveal answer / skip) the same way a
 * normal submission would. */
function ItemHelpPanel({ itemKind, itemId, onAsk, canGiveUp, onGiveUp, disabled }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [studentMessage, setStudentMessage] = useState("");
  const [pending, setPending] = useState(false);

  async function ask(intent) {
    if (pending) return;
    setPending(true);
    const response = await onAsk({ itemKind, itemId, intent, studentMessage: studentMessage.trim() || null });
    setPending(false);
    setStudentMessage("");
    if (!response) {
      setMessages(current => [...current, { from: "system", text: "Help isn't available right now — please try again." }]);
      return;
    }
    if (intent === "give_up") {
      setMessages(current => [...current, {
        from: "assistant",
        text: response.action === "revealed"
          ? (response.explanation || "Here is the answer for this one.")
          : "No problem — this one is optional, so it's skipped.",
      }]);
      onGiveUp?.(response);
    } else {
      setMessages(current => [...current, { from: "assistant", text: response.message }]);
    }
  }

  if (disabled) return null;
  return (
    <div className="mt-2">
      <button type="button" className="btn btn-sm btn-link ps-0 text-decoration-none" onClick={() => setOpen(value => !value)}>
        <Icon name="life-preserver" /> Help me?
      </button>
      {open && (
        <div className="border rounded-3 p-3 mb-course-help-panel">
          {messages.map((message, index) => (
            <div key={index} className={`small mb-2 ${message.from === "system" ? "text-danger" : ""}`}><MathText>{message.text}</MathText></div>
          ))}
          <div className="d-flex flex-wrap gap-2 align-items-center">
            <label className="visually-hidden" htmlFor={`help-${itemKind}-${itemId}`}>Ask about this step (optional)</label>
            <input id={`help-${itemKind}-${itemId}`} className="form-control form-control-sm" style={{ maxWidth: "18rem" }}
              placeholder="Ask about this step (optional)" value={studentMessage} disabled={pending}
              onChange={event => setStudentMessage(event.target.value)} />
            <button type="button" className="btn btn-sm btn-outline-primary" disabled={pending} onClick={() => ask("help")}>
              {pending ? "Thinking…" : "Get a hint"}
            </button>
            {canGiveUp && (
              <button type="button" className="btn btn-sm btn-outline-secondary" disabled={pending} onClick={() => ask("give_up")}>
                Give up
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/** Interactive preview quiz question, shared by `activity` and `learning_item` kinds
 * (requirements/47 §2.4, MCN2-5 — a `learning_item` now renders with the exact same
 * answerable UI as `activity` instead of a static list). Grades locally against the
 * already-visible correctness fields; when `onRespond` is given (student is enrolled),
 * the attempt is also recorded server-side. The correct answer is never pre-highlighted
 * until the student answers or gives up. */
function GradableItem({ kind, raw, onRespond, onAsk, onItemResolved }) {
  const fields = gradableItemFields(kind, raw);
  const [selectedIndex, setSelectedIndex] = useState(null);
  const [numericValue, setNumericValue] = useState("");
  const [pending, setPending] = useState(false);
  const [result, setResult] = useState(
    fields.previouslyAnswered !== null
      ? { is_correct: fields.previouslyAnswered, explanation: fields.explanation, previousAttempt: true }
      : null,
  );

  function resolve(outcome) {
    setResult(outcome);
    onItemResolved?.();
  }

  async function choose(index) {
    if (result || pending) return;
    setSelectedIndex(index);
    setPending(true);
    const response = onRespond ? await onRespond({ itemId: fields.id, choiceIndex: index }) : null;
    setPending(false);
    resolve(response || { is_correct: index === fields.correctIndex, explanation: fields.explanation });
  }

  async function submitNumeric() {
    if (result || pending || numericValue === "") return;
    setPending(true);
    const value = Number(numericValue);
    const response = onRespond ? await onRespond({ itemId: fields.id, value }) : null;
    setPending(false);
    resolve(response || {
      is_correct: fields.correctValue !== undefined && Math.abs(value - Number(fields.correctValue)) < 1e-9,
      explanation: fields.explanation,
    });
  }

  function handleGiveUp(assistResponse) {
    resolve({
      is_correct: false,
      gave_up: true,
      explanation: assistResponse.explanation ?? fields.explanation,
    });
  }

  return (
    <Callout tone={result ? (result.is_correct ? "success" : "warning") : "hint"} title={fields.title}>
      <MathText>{fields.prompt}</MathText>
      {fields.isNumeric ? (
        <div className="d-flex flex-wrap gap-2 align-items-center mt-2">
          <label className="visually-hidden" htmlFor={`item-${kind}-${fields.id}`}>Your numeric answer</label>
          <input id={`item-${kind}-${fields.id}`} type="number" className="form-control form-control-sm mb-num"
            style={{ maxWidth: "8rem" }} value={numericValue} disabled={!!result}
            onChange={event => setNumericValue(event.target.value)} />
          <button type="button" className="btn btn-sm btn-primary" disabled={!!result || pending || numericValue === ""}
            onClick={submitNumeric}>
            Check answer
          </button>
        </div>
      ) : fields.options.length > 0 && (
        <div className="d-flex flex-column gap-2 mt-2" role="group" aria-label="Answer options">
          {fields.options.map((option, index) => {
            let variant = "btn-outline-secondary";
            if (result) {
              if (index === fields.correctIndex) variant = "btn-outline-success";
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
            {result.gave_up && <p className="mb-1 fst-italic">You asked to see the answer.</p>}
            {result.explanation && <MathText>{result.explanation}</MathText>}
          </div>
        </div>
      )}
      {onAsk && (
        <ItemHelpPanel itemKind={kind} itemId={fields.id} onAsk={onAsk} disabled={!!result}
          canGiveUp={!!onRespond} onGiveUp={handleGiveUp} />
      )}
    </Callout>
  );
}

/** Renders one asset's media (image/video/audio/private-object, approved external link,
 * or YouTube embed) — factored out of `StepContent` so the single-active-item sequenced
 * renderer (requirements/47 §2, MCN2-1) can show exactly one asset at a time without a
 * second parallel implementation. */
function AssetMedia({ asset, courseCode }) {
  const href = asset.private_object
    ? `/api/rest/micro-courses/${encodeURIComponent(courseCode)}/assets/${encodeURIComponent(asset.asset_id)}/content`
    : asset.video_url || asset.source_url;
  if (!href) return null;
  if (asset.private_object && asset.mime_type?.startsWith("image/")) {
    return <img className="img-fluid rounded-3 my-3" src={href} alt={asset.title || "Course illustration"} />;
  }
  if (asset.private_object && asset.mime_type?.startsWith("video/")) {
    return <video className="w-100 rounded-3 my-3" controls preload="metadata">
      <source src={href} type={asset.mime_type} />
      Your browser does not support embedded video.
    </video>;
  }
  if (asset.private_object && asset.mime_type?.startsWith("audio/")) {
    return <audio className="w-100 my-3" controls preload="metadata">
      <source src={href} type={asset.mime_type} />
      Your browser does not support embedded audio.
    </audio>;
  }
  const embedUrl = !asset.private_object ? youTubeEmbedUrl(href) : null;
  if (embedUrl) {
    return (
      <div className="my-3">
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
    <Callout tone="hint" title={asset.title || asset.asset_kind || "Course resource"}>
      <a href={href} target="_blank" rel="noreferrer">{asset.private_object ? "Open approved resource" : "Open approved external resource"}</a>
      {asset.duration_ms ? <Pill className="ms-2" tone="neutral">{Math.ceil(asset.duration_ms / 60000)} min</Pill> : null}
    </Callout>
  );
}

function StepContent({ state, courseCode, onRecordActivity, onRecordLearningItem, onRecordInteractionEvent, onItemHelp }) {
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
      {state.assets?.map((asset, index) => <AssetMedia key={`${asset.asset_id || asset.asset_kind}-${index}`} asset={asset} courseCode={courseCode} />)}
      {state.interactions?.map(interaction => (
        <InteractionTemplateRenderer key={interaction.interaction_instance_id} interaction={interaction}
          courseCode={courseCode} onRecordInteractionEvent={onRecordInteractionEvent} />
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
        <GradableItem key={item.learning_item_id} kind="learning_item" raw={item}
          onRespond={onRecordLearningItem ? payload => onRecordLearningItem(payload) : null}
          onAsk={onItemHelp ? payload => onItemHelp(payload) : null} />
      ))}
      {state.activities?.map(activity => (
        <GradableItem key={activity.activity_id} kind="activity" raw={activity}
          onRespond={onRecordActivity ? payload => onRecordActivity(payload) : null}
          onAsk={onItemHelp ? payload => onItemHelp(payload) : null} />
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

const ITEM_ID_FIELD = { asset: "asset_id", interaction: "interaction_instance_id", learning_item: "learning_item_id", activity: "activity_id" };

/** Looks up one item's full content record from a state's per-kind buckets by
 * (item_kind, item_id) — the ordering-only `items` array (requirements/47 §2.1) carries
 * just enough to sequence and gate; the actual content still lives in the existing
 * per-kind arrays, unchanged, for backward compatibility. */
function stateItemContentByKey(state) {
  const lookup = {};
  const buckets = { asset: state.assets, interaction: state.interactions, learning_item: state.learning_items, activity: state.activities };
  for (const [kind, list] of Object.entries(buckets)) {
    for (const entry of list || []) lookup[`${kind}:${entry[ITEM_ID_FIELD[kind]]}`] = entry;
  }
  return lookup;
}

function initiallyResolvedKeys(state) {
  const resolved = new Set();
  for (const kind of ["learning_item", "activity"]) {
    for (const entry of state[kind === "learning_item" ? "learning_items" : "activities"] || []) {
      if (typeof entry.answered_correctly === "boolean") resolved.add(`${kind}:${entry[ITEM_ID_FIELD[kind]]}`);
    }
  }
  return resolved;
}

/** Single-active-item renderer for a state authored with cross-kind `sequence_position`
 * (requirements/47 §2.1-2.4, MCN2-1/MCN2-3/MCN2-4). Shows exactly one item at a time in
 * authored order — required gradable items block "Next item" until answered or given up;
 * required assets/interactions block until marked viewed/progressed; optional items can
 * always be skipped. Mount with `key={state.state_id}` from the caller so switching states
 * cleanly resets local progress instead of carrying it across states. */
function SequencedStepContent({
  state, courseCode, itemIndex, onSelectItem, onRecordActivity, onRecordLearningItem,
  onRecordInteractionEvent, onItemHelp,
}) {
  const items = state.items || [];
  const contentByKey = useMemo(() => stateItemContentByKey(state), [state]);
  const [resolvedKeys, setResolvedKeys] = useState(() => initiallyResolvedKeys(state));
  const current = items[itemIndex];
  const currentKey = current ? `${current.item_kind}:${current.item_id}` : null;
  const isResolved = currentKey ? resolvedKeys.has(currentKey) : false;

  function markResolved(key) {
    setResolvedKeys(existing => new Set(existing).add(key));
  }

  if (!current) {
    return (
      <article className="card border-0 shadow-sm p-3 p-lg-4">
        <h3 className="h5 mb-1">{state.title}</h3>
        <EmptyState icon="inbox">This step has no content yet.</EmptyState>
      </article>
    );
  }
  const content = contentByKey[currentKey];
  let body;
  if (!content) {
    body = <EmptyState icon="inbox">This item is not available.</EmptyState>;
  } else if (current.item_kind === "asset") {
    body = (
      <>
        <AssetMedia key={currentKey} asset={content} courseCode={courseCode} />
        {!isResolved && (
          <button type="button" className="btn btn-sm btn-outline-primary mt-2" onClick={() => markResolved(currentKey)}>
            <Icon name="check2" /> {current.required ? "Mark as watched" : "Continue"}
          </button>
        )}
      </>
    );
  } else if (current.item_kind === "interaction") {
    body = (
      <>
        <InteractionTemplateRenderer key={currentKey} interaction={content} courseCode={courseCode}
          onRecordInteractionEvent={payload => { onRecordInteractionEvent?.(payload); markResolved(currentKey); }} />
        {!isResolved && !current.required && (
          <button type="button" className="btn btn-sm btn-outline-primary mt-2" onClick={() => markResolved(currentKey)}>
            <Icon name="check2" /> Continue
          </button>
        )}
      </>
    );
  } else {
    body = (
      <GradableItem key={currentKey} kind={current.item_kind} raw={content}
        onRespond={current.item_kind === "activity"
          ? (onRecordActivity ? payload => onRecordActivity(payload) : null)
          : (onRecordLearningItem ? payload => onRecordLearningItem(payload) : null)}
        onAsk={onItemHelp ? payload => onItemHelp(payload) : null}
        onItemResolved={() => markResolved(currentKey)} />
    );
  }

  const canAdvance = isResolved || !current.required;
  return (
    <article className="card border-0 shadow-sm p-3 p-lg-4" aria-live="polite">
      <div className="d-flex flex-wrap justify-content-between gap-2 align-items-start">
        <h3 className="h5 mb-1">{state.title}</h3>
        <Pill tone="neutral">Item {itemIndex + 1} of {items.length}</Pill>
      </div>
      <div className="mt-3">{body}</div>
      <div className="mb-course-item-nav mt-3">
        <button type="button" className="btn btn-outline-secondary btn-sm" disabled={itemIndex === 0}
          onClick={() => onSelectItem(Math.max(0, itemIndex - 1))}>
          <Icon name="arrow-left" /> Previous item
        </button>
        {itemIndex < items.length - 1 ? (
          <button type="button" className="btn btn-sm btn-primary" disabled={!canAdvance}
            onClick={() => onSelectItem(Math.min(itemIndex + 1, items.length - 1))}>
            {canAdvance ? "Next item" : "Answer to continue"} <Icon name="arrow-right" />
          </button>
        ) : (
          <Pill tone={canAdvance ? "success" : "warning"}>
            {canAdvance ? "Last item in this step" : "Answer to finish this step"}
          </Pill>
        )}
      </div>
    </article>
  );
}

/** Step navigator: a vertical rail on wide screens, a horizontal scrollable row on
 * narrow screens (pure CSS responsive switch, see .mb-course-stepper in globals.css).
 * When the current state has been authored with cross-kind item sequencing
 * (requirements/47 §2.2, MCN2-3), it expands into a sub-rail of that state's own items. */
function CourseStepper({ steps, activeOrdinal, reachableOrdinal, onSelect, activeItems, activeItemIndex, onSelectItem }) {
  return (
    <nav className="mb-course-stepper" aria-label="Lesson steps">
      {steps.map(step => {
        const isCurrent = step.ordinal === activeOrdinal;
        const isDone = step.ordinal < reachableOrdinal;
        const isLocked = step.ordinal > reachableOrdinal;
        return (
          <div key={step.state_id}>
            <button type="button"
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
            {isCurrent && activeItems?.length > 1 && (
              <div className="mb-course-substeps" aria-label={`${step.title} items`}>
                {activeItems.map((item, index) => {
                  const itemDone = index < activeItemIndex;
                  const itemCurrent = index === activeItemIndex;
                  const itemLocked = index > activeItemIndex;
                  return (
                    <button key={`${item.item_kind}-${item.item_id}`} type="button"
                      className={`mb-course-substep${itemCurrent ? " is-current" : ""}${itemDone ? " is-done" : ""}`}
                      disabled={itemLocked} title={itemLocked ? `Unlocks after item ${index}` : undefined}
                      onClick={() => onSelectItem(index)}>
                      <span className="mb-course-substep-dot" aria-hidden="true">
                        {itemDone ? <Icon name="check-lg" /> : itemLocked ? <Icon name="lock-fill" /> : index + 1}
                      </span>
                      <span>{SUB_ITEM_LABELS[item.item_kind] || item.item_kind}{item.purpose ? ` · ${item.purpose.replaceAll("_", " ")}` : ""}</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
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
  // Which single item is active within the current state's sequenced items
  // (requirements/47 §2, MCN2-1/MCN2-4) — meaningless for a non-sequenced state.
  const [itemIndex, setItemIndex] = useState(0);

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

  async function recordActivity({ itemId, choiceIndex, value }) {
    if (!enrollment) return null;
    try {
      const response = await fetch(`/api/rest/micro-courses/enrollments/${enrollment.enrollment_id}/activity-responses`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ activity_id: itemId, choice_index: choiceIndex ?? null, value: value ?? null }),
      });
      const body = await response.json();
      if (!response.ok) return null;
      return body;
    } catch {
      return null;
    }
  }

  async function recordLearningItem({ itemId, choiceIndex }) {
    if (!enrollment) return null;
    try {
      const response = await fetch(`/api/rest/micro-courses/enrollments/${enrollment.enrollment_id}/responses`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ learning_item_id: itemId, choice_index: choiceIndex ?? null }),
      });
      const body = await response.json();
      if (!response.ok) return null;
      return body;
    } catch {
      return null;
    }
  }

  // Scoped "Help me?" / "Give up" micro-chat for the current single item
  // (requirements/47 §3, MCN2-6/MCN2-7) — grounded server-side, current state only.
  async function itemHelp({ itemKind, itemId, intent, studentMessage }) {
    if (!enrollment) return null;
    try {
      const response = await fetch(`/api/rest/micro-courses/enrollments/${enrollment.enrollment_id}/item-help`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ item_kind: itemKind, item_id: itemId, intent, student_message: studentMessage }),
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

  const steps = course ? [...course.states].sort((a, b) => a.ordinal - b.ordinal) : [];
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
  // Reset the within-state item position whenever the visible state changes
  // (requirements/47 §2, MCN2-1) — a fresh state always starts at its first item.
  useEffect(() => { setItemIndex(0); }, [activeState?.state_id]);

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

  const releaseStatus = course.release_status; // only present on admin-preview reads
  const versionPill = releaseStatus && releaseStatus !== "PUBLISHED"
    ? <Pill key="version" tone="warning">{releaseStatus.charAt(0) + releaseStatus.slice(1).toLowerCase()} v{course.version}</Pill>
    : <Pill key="version" tone="success">Published v{course.version}</Pill>;
  // Backward compatible by construction (requirements/47 §2.1, MCN2-2): `items` always
  // exists, but only states an admin has actually authored with cross-kind
  // `sequence_position` switch the reader into single-active-item mode; everything else
  // keeps the pre-existing grouped-by-kind rendering untouched.
  const isSequenced = (activeState?.items || []).some(item => item.sequence_position !== null && item.sequence_position !== undefined);

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
            onSelect={setLocalIndex}
            activeItems={isViewingCurrent && isSequenced ? activeState.items : null}
            activeItemIndex={itemIndex} onSelectItem={setItemIndex} />
          <div className="mb-course-content">
            {isViewingCurrent && isSequenced ? (
              <SequencedStepContent key={activeState.state_id} state={activeState} courseCode={code}
                itemIndex={itemIndex} onSelectItem={setItemIndex}
                onRecordActivity={recordActivity} onRecordLearningItem={recordLearningItem}
                onRecordInteractionEvent={recordInteractionEvent} onItemHelp={enrolled ? itemHelp : null} />
            ) : (
              <StepContent state={activeState} courseCode={code}
                onRecordActivity={isViewingCurrent ? recordActivity : null}
                onRecordLearningItem={isViewingCurrent ? recordLearningItem : null}
                onRecordInteractionEvent={isViewingCurrent ? recordInteractionEvent : null}
                onItemHelp={isViewingCurrent && enrolled ? itemHelp : null} />
            )}
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
