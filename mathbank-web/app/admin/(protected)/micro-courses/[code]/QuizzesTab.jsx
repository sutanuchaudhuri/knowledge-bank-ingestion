"use client";

import { useState } from "react";
import { Callout, EmptyState, Icon, Pill, SectionTitle } from "../../../../_components/ui.jsx";
import { request } from "./shared.js";

const activitiesEndpoint = "/api/rest/admin/activities";
const ACTIVITY_TYPES = ["MCQ", "MULTISELECT", "NUMERIC", "SHORT_RESPONSE", "SUBPROBLEM",
  "STEP_ORDERING", "ERROR_DIAGNOSIS", "CONFIDENCE_CHECK", "LIVE_POLL"];
const PURPOSES = ["ENTRY_CHECK", "COMPREHENSION", "RECOGNITION", "MISCONCEPTION_DIAGNOSTIC",
  "EXECUTION", "EXIT_CHECK", "TRANSFER"];

function emptyForm() {
  return {
    activity_type: "MCQ", prompt: "", optionsText: "3\n4\n5", correct_index: 1, correct_value: "",
    estimated_seconds: 60, purpose: "ENTRY_CHECK",
  };
}

/** Add-question form + per-state quiz list, backed by the quiz/activity admin API
 * (requirements/46_MICRO_COURSE_QUIZ_AUTHORING_API_GAPS.md). Creating a question calls
 * POST /v1/admin/activities (Tier A, always INSTRUCTOR_CREATED+STATIC) then attaches it to
 * the chosen state via POST .../states/{state_id}/activities (Tier B, the already-validated
 * attach_activity service function). "Draft with AI" remains out of scope here — see doc 43
 * §7.1 for the open answer-exposure issue any AI-assisted drafting would need to account for. */
export default function QuizzesTab({ release, refresh }) {
  const [openStateId, setOpenStateId] = useState(null);
  const [form, setForm] = useState(emptyForm());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  if (!release) return <EmptyState icon="patch-question">Create a draft release first (see the Versions tab).</EmptyState>;

  const quizStates = release.states.filter(state => (state.activities || []).length > 0
    || ["QUIZ", "CHECKPOINT", "DIAGNOSTIC"].includes(state.state_type));

  async function addQuestion(stateId) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const options = form.optionsText.split("\n").map(line => line.trim()).filter(Boolean);
      const isNumeric = form.activity_type === "NUMERIC";
      const correctness_policy = isNumeric
        ? { correct_value: Number(form.correct_value) }
        : { correct_index: Number(form.correct_index) };
      const created = await request(activitiesEndpoint, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          activity_type: form.activity_type, prompt: form.prompt,
          options: isNumeric ? [] : options.map(text => ({ text })),
          correctness_policy, estimated_seconds: Number(form.estimated_seconds) || 60,
          created_by: "admin-ui",
        }),
      });
      const ordinal = (release.states.find(s => s.state_id === stateId)?.activities || []).length;
      await request(`/api/rest/admin/micro-courses/states/${stateId}/activities`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ activity_id: created.activity_id, ordinal, purpose: form.purpose, required: true }),
      });
      setNotice(`Added "${form.prompt.slice(0, 40)}${form.prompt.length > 40 ? "…" : ""}" to this state.`);
      setForm(emptyForm());
      setOpenStateId(null);
      refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function deactivate(activityId) {
    setBusy(true);
    setError("");
    try {
      await request(`${activitiesEndpoint}/${activityId}/deactivate`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ actor: "admin-ui" }),
      });
      setNotice("Question deactivated.");
      refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function detach(stateId, activityId) {
    setBusy(true);
    setError("");
    try {
      await request(`/api/rest/admin/micro-courses/states/${stateId}/activities/${activityId}`, { method: "DELETE" });
      setNotice("Question detached from this state.");
      refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <Callout tone="hint" className="mb-3">
        <Icon name="robot" /> <strong>"Draft with AI" is not yet available.</strong> Questions are
        authored here directly; AI-assisted drafting and the per-question answer-exposure notice
        depend on requirements/43 §7.1 being resolved first.
      </Callout>
      {error && <Callout tone="danger" className="mb-3">{error}</Callout>}
      {notice && <Callout tone="success" className="mb-3">{notice}</Callout>}

      {!quizStates.length ? (
        <EmptyState icon="patch-question">No quiz states in this release yet.</EmptyState>
      ) : (
        quizStates.map(state => (
          <div key={state.state_id} className="card border-0 shadow-sm p-3 mb-3">
            <div className="d-flex justify-content-between align-items-start">
              <SectionTitle icon="patch-question">{state.title} <Pill tone="neutral" className="ms-2">{state.state_type}</Pill></SectionTitle>
              <button type="button" className="btn btn-sm btn-outline-primary"
                onClick={() => setOpenStateId(openStateId === state.state_id ? null : state.state_id)}>
                <Icon name="plus-lg" /> Add question
              </button>
            </div>

            {!state.activities?.length ? (
              <p className="text-secondary small mb-0">No questions attached to this state.</p>
            ) : (
              <ul className="list-group list-group-flush">
                {state.activities.map(activity => (
                  <li key={activity.activity_id} className="list-group-item">
                    <div className="d-flex justify-content-between gap-2 align-items-start">
                      <strong>{activity.prompt}</strong>
                      <div className="d-flex gap-2 align-items-center">
                        <Pill tone="info">{activity.activity_type}</Pill>
                        {activity.purpose && <Pill tone="neutral">{activity.purpose}</Pill>}
                        <button type="button" className="btn btn-sm btn-outline-secondary" disabled={busy}
                          title="Detach from this state" aria-label="Detach from this state"
                          onClick={() => detach(state.state_id, activity.activity_id)}>
                          <Icon name="x-lg" />
                        </button>
                        <button type="button" className="btn btn-sm btn-outline-danger" disabled={busy}
                          title="Deactivate this question" aria-label="Deactivate this question"
                          onClick={() => deactivate(activity.activity_id)}>
                          <Icon name="slash-circle" />
                        </button>
                      </div>
                    </div>
                    {Array.isArray(activity.options) && activity.options.length > 0 && (
                      <ul className="small text-secondary mt-1 mb-0">
                        {activity.options.map((option, index) => (
                          <li key={index}>{typeof option === "string" ? option : option.text}</li>
                        ))}
                      </ul>
                    )}
                  </li>
                ))}
              </ul>
            )}

            {openStateId === state.state_id && (
              <div className="mt-3 p-3 border rounded-3">
                <div className="row g-2">
                  <div className="col-md-4">
                    <label className="form-label small" htmlFor={`type-${state.state_id}`}>Type</label>
                    <select id={`type-${state.state_id}`} className="form-select form-select-sm"
                      value={form.activity_type} onChange={e => setForm({ ...form, activity_type: e.target.value })}>
                      {ACTIVITY_TYPES.map(type => <option key={type} value={type}>{type}</option>)}
                    </select>
                  </div>
                  <div className="col-md-4">
                    <label className="form-label small" htmlFor={`purpose-${state.state_id}`}>Purpose</label>
                    <select id={`purpose-${state.state_id}`} className="form-select form-select-sm"
                      value={form.purpose} onChange={e => setForm({ ...form, purpose: e.target.value })}>
                      {PURPOSES.map(p => <option key={p} value={p}>{p}</option>)}
                    </select>
                  </div>
                  <div className="col-md-4">
                    <label className="form-label small" htmlFor={`seconds-${state.state_id}`}>Estimated seconds</label>
                    <input id={`seconds-${state.state_id}`} type="number" className="form-control form-control-sm"
                      value={form.estimated_seconds} onChange={e => setForm({ ...form, estimated_seconds: e.target.value })} />
                  </div>
                  <div className="col-12">
                    <label className="form-label small" htmlFor={`prompt-${state.state_id}`}>Prompt</label>
                    <textarea id={`prompt-${state.state_id}`} className="form-control form-control-sm" rows={2}
                      value={form.prompt} onChange={e => setForm({ ...form, prompt: e.target.value })} />
                  </div>
                  {form.activity_type === "NUMERIC" ? (
                    <div className="col-md-4">
                      <label className="form-label small" htmlFor={`value-${state.state_id}`}>Correct value</label>
                      <input id={`value-${state.state_id}`} type="number" className="form-control form-control-sm"
                        value={form.correct_value} onChange={e => setForm({ ...form, correct_value: e.target.value })} />
                    </div>
                  ) : (
                    <>
                      <div className="col-md-8">
                        <label className="form-label small" htmlFor={`options-${state.state_id}`}>Options (one per line)</label>
                        <textarea id={`options-${state.state_id}`} className="form-control form-control-sm" rows={3}
                          value={form.optionsText} onChange={e => setForm({ ...form, optionsText: e.target.value })} />
                      </div>
                      <div className="col-md-4">
                        <label className="form-label small" htmlFor={`correct-${state.state_id}`}>Correct option (0-based index)</label>
                        <input id={`correct-${state.state_id}`} type="number" className="form-control form-control-sm"
                          value={form.correct_index} onChange={e => setForm({ ...form, correct_index: e.target.value })} />
                      </div>
                    </>
                  )}
                  <div className="col-12">
                    <button type="button" className="btn btn-sm btn-primary" disabled={busy || !form.prompt.trim()}
                      onClick={() => addQuestion(state.state_id)}>
                      {busy ? "Saving…" : "Save question"}
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        ))
      )}
    </div>
  );
}
