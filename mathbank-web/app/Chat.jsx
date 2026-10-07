"use client";

import { useEffect, useRef, useState } from "react";
import { createSession, newSessionId, streamMessage } from "./agentClient.js";
import { MathComposer, SpeakButton } from "mathbank-widgets";
import Link from "next/link";
import MathText from "./_components/MathText.jsx";
import TutorAnswer from "./_components/TutorAnswer.jsx";
import { Avatar, Callout, EmptyState, Icon, Pill, SectionTitle } from "./_components/ui.jsx";
import { MAX_MEDIA_BYTES } from "../lib/privateRuntimeProxy.mjs";

const ATTEMPT_MEDIA_ROOT = "/api/rest/attempt-media/submissions";
const PRINTED_WORK_TYPES = ["image/jpeg", "image/png", "application/pdf"];
const formatDuration = (seconds) => {
  const total = Math.max(0, Math.floor(seconds || 0));
  return total < 60 ? `${total}s` : `${Math.floor(total / 60)}m ${total % 60}s`;
};

const SUGGESTIONS = [
  ["bullseye", "Explain the power of a point"],
  ["search", "Recent combinatorics questions"],
  ["triangle", "A hard geometry problem to try"],
];

const ACTIVITY_LOOK = {
  complete: { tone: "success", icon: "check-lg" },
  error: { tone: "danger", icon: "x-lg" },
  stopped: { tone: "warning", icon: "pause-fill" },
  running: { tone: "primary", icon: "gear" },
};

export default function Chat() {
  const sessionRef = useRef(null);
  const streamRef = useRef(null);
  const bottomRef = useRef(null);
  const [ready, setReady] = useState(false);
  const [saved, setSaved] = useState(null);
  const [messages, setMessages] = useState([
    { role: "assistant", text: "Hi! Ask me about any competition math topic, or pick a starter below." },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [activity, setActivity] = useState([]);
  const [error, setError] = useState(null);
  const [studentName, setStudentName] = useState("");
  const [lessonProgress, setLessonProgress] = useState(null);
  const [checkpointAnswer, setCheckpointAnswer] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [uploadResumeUrl, setUploadResumeUrl] = useState("");
  const [problemSelection, setProblemSelection] = useState(null);
  const uploadRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    if (!sessionRef.current) {
      const id = newSessionId();
      sessionRef.current = { id, request: createSession(id) };
    }
    sessionRef.current.request
      .then((session) => { if (!cancelled) { setReady(true); setSaved(session); } })
      .catch((err) => { if (!cancelled) setError(`Could not reach the agent: ${err.message}`); });
    return () => { cancelled = true; streamRef.current?.abort(); };
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/rest/learner/me", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((me) => { if (!cancelled && me?.first_name) setStudentName(`${me.first_name} ${me.last_name || ""}`.trim()); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: sending ? "instant" : "smooth", block: "nearest" });
  }, [messages, sending]);

  async function handleSend(event, requestedText) {
    event?.preventDefault();
    const text = (requestedText ?? input).trim();
    if (!text || !ready || streamRef.current) return;
    const controller = new AbortController();
    streamRef.current = controller;
    const answerIndex = messages.length + 1;
    setMessages((m) => [...m, { role: "user", text }, { role: "assistant", text: "" }]);
    setInput("");
    setError(null);
    setActivity([]);
    setSending(true);
    try {
      await streamMessage(sessionRef.current.id, text, (update) => {
        if (update.type === "answer") {
          setMessages((items) => items.map((item, index) => index === answerIndex ? { ...item, text: update.text } : item));
        } else if (update.type === "activity") {
          setActivity((items) => [...items, update]);
        } else if (update.type === "progress") {
          setLessonProgress(update.progress);
          setCheckpointAnswer("");
        } else if (update.type === "done") {
          setActivity((items) => [...items, { label: "Response complete", status: "complete" }]);
        }
      }, controller.signal);
    } catch (err) {
      if (err.name === "AbortError") {
        setActivity((items) => [...items, { label: "Response stopped", status: "stopped" }]);
      } else {
        setError(err.message);
        setActivity((items) => [...items, { label: "Response failed", status: "error" }]);
      }
    } finally {
      streamRef.current = null;
      setSending(false);
    }
  }

  const latestTutorReply = [...messages].reverse().find((message) => message.role === "assistant")?.text || "";
  const problemCodes = [...new Set([...latestTutorReply.matchAll(/(?:\*\*)?Canonical Code(?:\*\*:|:\*\*|:)\s*`?([A-Z][A-Z0-9_]{2,})/gi)].map((match) => match[1]))];
  const activeProblemCode = problemCodes.length === 1
    ? problemCodes[0]
    : problemSelection?.reply === latestTutorReply && problemCodes.includes(problemSelection.code) ? problemSelection.code : "";

  async function uploadWrittenWork(file) {
    if (!file) return;
    setUploadError("");
    setUploadResumeUrl("");
    if (!activeProblemCode) {
      setUploadError("Load or identify a canonical problem in this conversation before uploading work. The tutor will only review work for the active problem.");
      return;
    }
    if (!PRINTED_WORK_TYPES.includes(file.type)) {
      setUploadError("Choose a JPEG, PNG, or PDF of your written solution.");
      return;
    }
    if (file.size > MAX_MEDIA_BYTES) {
      setUploadError("Choose a file under 20 MB.");
      return;
    }
    let submissionId = "";
    try {
      const createdResponse = await fetch(ATTEMPT_MEDIA_ROOT, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ problem_ref: activeProblemCode }), cache: "no-store",
      });
      const created = await createdResponse.json();
      if (!createdResponse.ok) {
        const detail = created?.detail?.code || created?.detail;
        throw new Error(typeof detail === "string" ? detail : "Could not create a private work submission.");
      }
      submissionId = created.submission_id;
      const uploadResponse = await fetch(
        `${ATTEMPT_MEDIA_ROOT}/${encodeURIComponent(created.submission_id)}/assets?filename=${encodeURIComponent(file.name)}&expected_version=${created.transcription_version || 1}`,
        { method: "POST", headers: { "Content-Type": file.type }, body: file, cache: "no-store" },
      );
      const uploaded = await uploadResponse.json().catch(() => null);
      if (!uploadResponse.ok) {
        const detail = uploaded?.detail?.code || uploaded?.detail;
        throw new Error(typeof detail === "string" ? detail : "The private upload failed.");
      }
      window.location.assign(`/learn/attempt-media?problem_ref=${encodeURIComponent(activeProblemCode)}&submission_id=${encodeURIComponent(submissionId)}`);
    } catch (err) {
      setUploadError(err.message || "The upload failed. Please retry.");
      if (submissionId) {
        setUploadResumeUrl(`/learn/attempt-media?problem_ref=${encodeURIComponent(activeProblemCode)}&submission_id=${encodeURIComponent(submissionId)}`);
      }
    }
  }

  const greeting = messages.length === 1;
  const status = sending ? { tone: "info", icon: "broadcast", text: "Streaming" }
    : ready ? { tone: "success", icon: "circle-fill", text: "Agent connected" }
      : { tone: "neutral", icon: "hourglass-split", text: "Connecting" };

  return (
    <div className="row g-4">
      <div className="col-12 col-xl-9">
        <section className="card mb-chat" aria-label="Tutor conversation">
          <div className="d-flex justify-content-end gap-2 px-3 pt-2">
            <Link className="btn btn-ghost btn-sm" href="/learn/attempt-media"><Icon name="file-earmark-richtext" />Upload my written attempt</Link>
            <Link className="btn btn-ghost btn-sm" href="/artifacts"><Icon name="collection" />Artifact library</Link>
          </div>
          <div className="mb-chat-scroll" aria-live="polite" aria-busy={sending}>
            {messages.map((message, index) => {
              const mine = message.role === "user";
              const streaming = sending && index === messages.length - 1;
              return (
                <div key={index} className={`mb-msg ${mine ? "mb-msg-user" : "mb-msg-assistant"}`}>
                  {mine ? <Avatar name={studentName || "You"} size={32} /> : <Avatar name="MathBank Tutor" icon="stars" size={32} />}
                  <div className="min-w-0">
                    <div className={`mb-msg-meta ${mine ? "justify-content-end" : ""}`}>
                      <span className="fw-semibold">{mine ? "You" : "MathBank Tutor"}</span>
                      {!mine && message.text && !streaming && <SpeakButton text={message.text} label="Listen to this answer" />}
                    </div>
                    <div className="mb-bubble">
                      {mine ? (
                        /\$|\\\(|\\\[/.test(message.text) ? <MathText>{message.text}</MathText>
                          : <div style={{ whiteSpace: "pre-wrap" }}>{message.text}</div>
                      ) : message.text ? (
                        <TutorAnswer>{message.text}</TutorAnswer>
                      ) : sending ? (
                        <span className="mb-typing" role="status" aria-label="Working on your question"><span /><span /><span /></span>
                      ) : (
                        <span className="text-secondary small">No answer received.</span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
            {greeting && (
              <div className="mb-suggestions ps-5" aria-label="Suggested questions">
                {SUGGESTIONS.map(([icon, text]) => (
                  <button key={text} type="button" className="mb-tab" onClick={() => setInput(text)} disabled={!ready}>
                    <Icon name={icon} />{text}
                  </button>
                ))}
              </div>
            )}
            <div ref={bottomRef} />
          </div>
          <div className="mb-chat-foot">
            {error && <Callout tone="danger" role="alert" className="mb-2">{error}</Callout>}
            {uploadError && <Callout tone="danger" role="alert" className="mb-2">
              {uploadError}{uploadResumeUrl && <> <Link href={uploadResumeUrl}>Resume this private upload</Link></>}
            </Callout>}
            <form onSubmit={handleSend}>
              <label htmlFor="chat-input" className="visually-hidden">Your question</label>
              <MathComposer id="chat-input" ariaLabel="Your question" testId="chat-composer" rows={1}
                value={input} onChange={setInput} onSubmit={() => handleSend()} showSubmit={false}
                renderMath={(t) => <MathText>{t}</MathText>}
                placeholder={ready ? "Ask anything about competition math…" : "Connecting to the agent…"}
                disabled={!ready || sending}>
                <input ref={uploadRef} type="file" className="visually-hidden" accept=".jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf"
                  aria-label="Choose a photo or PDF of written work" onChange={(event) => {
                    const file = event.currentTarget.files?.[0];
                    event.currentTarget.value = "";
                    void uploadWrittenWork(file);
                  }} />
                <button type="button" className="mbw-ghost" title={activeProblemCode ? `Upload work for ${activeProblemCode}` : problemCodes.length > 1 ? "Choose the problem for your work" : "Load a canonical problem before uploading work"}
                  aria-label="Upload written work for the current problem" disabled={!ready || sending || !activeProblemCode}
                  onClick={() => uploadRef.current?.click()}><Icon name="paperclip" /></button>
                {sending ? (
                  <button type="button" className="mbw-send is-danger" onClick={() => streamRef.current?.abort()}><Icon name="stop-fill" />Stop</button>
                ) : (
                  <button className="mbw-send" disabled={!ready || !input.trim()}><Icon name="send-fill" />Send</button>
                )}
              </MathComposer>
            </form>
            {problemCodes.length > 1 && (
              <div className="d-flex align-items-center gap-2 mt-2">
                <label htmlFor="work-problem" className="small text-secondary">Work for</label>
                <select id="work-problem" className="form-select form-select-sm w-auto"
                  aria-label="Problem for uploaded work" value={activeProblemCode}
                  onChange={(event) => setProblemSelection({ reply: latestTutorReply, code: event.target.value })}>
                  <option value="">Choose a problem</option>
                  {problemCodes.map((code) => <option key={code} value={code}>{code}</option>)}
                </select>
              </div>
            )}
            <div className="d-flex flex-wrap align-items-center gap-2 mt-2 small text-secondary">
              <Pill tone={status.tone} icon={status.icon}>{status.text}</Pill>
              {saved && (
                <span data-testid="chat-saved-state">
                  {saved.linked
                    ? <><Icon name="cloud-check" className="me-1" />Auto-saved to <Link href="/learn/conversations">your conversations</Link></>
                    : <><Icon name="incognito" className="me-1" />Anonymous · <Link href="/login">sign in</Link> to keep history</>}
                </span>
              )}
            </div>
          </div>
        </section>
      </div>
      <aside className="col-12 col-xl-3">
        <section className="card p-3 mb-sticky" aria-label="Agent activity">
          <SectionTitle icon="activity">Agent activity</SectionTitle>
          <div className="small text-secondary mb-2">Tool evidence and progress · not private reasoning</div>
          {activity.length ? (
            <ol className="mb-activity" aria-live="polite">
              {activity.map((item, index) => {
                const look = ACTIVITY_LOOK[item.status] || ACTIVITY_LOOK.running;
                return (
                  <li key={index}>
                    <span className={`mb-activity-dot mb-tone-${look.tone}`}><Icon name={look.icon} /></span>
                    <span className="min-w-0 text-break pt-1">{item.label}</span>
                  </li>
                );
              })}
            </ol>
          ) : (
            <EmptyState icon="cpu">Tool calls appear here while the tutor works.</EmptyState>
          )}
          {lessonProgress && (
            <section className="mt-4 pt-3 border-top" aria-label="Lesson progress">
              <div className="d-flex align-items-center justify-content-between gap-2 mb-2">
                <SectionTitle icon="graph-up-arrow">Path to mastery</SectionTitle>
                <Pill tone="neutral">{lessonProgress.completed} done · {lessonProgress.skipped} skipped</Pill>
              </div>
              <div className="progress mb-3" role="progressbar"
                aria-label="Lesson stages completed"
                aria-valuenow={lessonProgress.completed}
                aria-valuemin={0}
                aria-valuemax={lessonProgress.stages.length}>
                <div className="progress-bar" style={{ width: `${lessonProgress.stages.length ? (lessonProgress.completed / lessonProgress.stages.length) * 100 : 0}%` }} />
              </div>
              <ol className="list-unstyled d-grid gap-2 mb-3">
                {lessonProgress.stages.map((stage) => (
                  <li key={stage.index}>
                    <button type="button" className={`btn btn-sm w-100 text-start d-flex align-items-center gap-2 ${stage.is_current ? "btn-primary" : "btn-outline-secondary"}`}
                      aria-label={`Jump to stage: ${stage.title}`}
                      aria-current={stage.is_current ? "step" : undefined}
                      disabled={sending || !ready || stage.is_current}
                      onClick={() => handleSend(null, `jump to step ${stage.index + 1}`)}>
                      <Icon name={stage.icon} />
                      <span className="flex-grow-1">{stage.acronym} · {stage.short_title}</span>
                      <span className="small">{stage.status} · {formatDuration(stage.seconds)}</span>
                    </button>
                  </li>
                ))}
              </ol>
              {lessonProgress.checkpoint && (
                <div className="mb-3" aria-label="Current checkpoint">
                  <p className="small fw-semibold mb-2">{lessonProgress.checkpoint.question}</p>
                  {lessonProgress.checkpoint.input_type === "single-choice" ? (
                    <fieldset className="d-grid gap-1 border-0 p-0 m-0">
                      <legend className="visually-hidden">Choose one answer</legend>
                      {lessonProgress.checkpoint.choices.map((choice, index) => {
                        const letter = String.fromCharCode(65 + index);
                        return (
                          <label className="form-check border rounded px-2 py-2" key={letter}>
                            <input className="form-check-input me-2" type="radio" name="lesson-checkpoint"
                              value={letter} checked={checkpointAnswer === letter}
                              onChange={() => setCheckpointAnswer(letter)} disabled={sending} />
                            <span className="small"><strong>{letter}.</strong> <MathText>{choice}</MathText></span>
                          </label>
                        );
                      })}
                    </fieldset>
                  ) : (
                    <input className="form-control form-control-sm" aria-label="Checkpoint answer"
                      type={lessonProgress.checkpoint.input_type === "numeric" ? "number" : "text"}
                      inputMode={lessonProgress.checkpoint.input_type === "numeric" ? "decimal" : undefined}
                      value={checkpointAnswer} onChange={(event) => setCheckpointAnswer(event.target.value)} disabled={sending} />
                  )}
                  <div className="d-flex flex-wrap gap-2 mt-2">
                    <button type="button" className="btn btn-primary btn-sm" disabled={!checkpointAnswer || sending}
                      onClick={() => handleSend(null, checkpointAnswer)}>Check answer</button>
                    {lessonProgress.checkpoint.hint_available && (
                      <button type="button" className="btn btn-ghost btn-sm" disabled={sending}
                        onClick={() => handleSend(null, "show hint")}><Icon name="lightbulb" />Hint</button>
                    )}
                  </div>
                </div>
              )}
              {lessonProgress.feedback && lessonProgress.feedback_tone && (
                <Callout tone={lessonProgress.feedback_tone} className="mb-3"><MathText>{lessonProgress.feedback}</MathText></Callout>
              )}
              <div className="d-flex flex-wrap gap-2">
                <button type="button" className="btn btn-ghost btn-sm" disabled={sending || !ready || lessonProgress.current_unit >= lessonProgress.stages.length - 1}
                  onClick={() => handleSend(null, "skip step")}><Icon name="skip-forward-fill" />Skip step</button>
                <button type="button" className="btn btn-ghost btn-sm" disabled={sending || !ready}
                  onClick={() => handleSend(null, "jump to problem")}><Icon name="file-earmark-text" />Jump to problem</button>
                {lessonProgress.current_unit === lessonProgress.stages.length - 1 && (
                  <button type="button" className="btn btn-ghost btn-sm" disabled={sending || !ready}
                    onClick={() => handleSend(null, "give me a problem")}>Get a problem</button>
                )}
              </div>
              <p className="small text-secondary mt-2 mb-0">Time is recorded when you move stages. Skipping or jumping does not count as completion or mastery.</p>
            </section>
          )}
        </section>
      </aside>
    </div>
  );
}
