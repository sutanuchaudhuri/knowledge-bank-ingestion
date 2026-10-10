"use client";

import { useEffect, useState } from "react";
import { Callout, EmptyState, Pill, SectionTitle } from "../../../../_components/ui.jsx";
import { endpoint, request } from "./shared.js";

function Field({ label, id, ...props }) {
  return (
    <div className="mb-3">
      <label className="form-label" htmlFor={id}>{label}</label>
      <input id={id} className="form-control" {...props} />
    </div>
  );
}

const SAFE_AGENT_POLICY = {
  may_rephrase: true,
  may_explain_current_content: true,
  may_create_quiz: false,
  may_search_web: false,
  may_recommend_media: false,
  may_generate_diagram: false,
  may_add_course_state: false,
};

const STATE_TYPES = ["ORIENTATION", "EXPLANATION", "SLIDE", "VIDEO", "READING", "VISUAL", "EXAMPLE",
  "CHECKPOINT", "QUIZ", "DIAGNOSTIC", "REMEDIATION", "PRACTICE", "SUMMARY", "TRANSFER"];

export default function ContentTab({ release, refresh }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [moduleForm, setModuleForm] = useState({ module_key: "", title: "", objective: "" });
  const [stateForm, setStateForm] = useState({ state_key: "", state_type: "ORIENTATION", title: "", module_id: "", objective: "", student_instruction: "" });
  const [transitionForm, setTransitionForm] = useState({ from_state_id: "", to_state_id: "", transition_type: "NEXT" });

  const [bindingType, setBindingType] = useState("CONCEPT");
  const [bindingQuery, setBindingQuery] = useState("");
  const [bindingTargets, setBindingTargets] = useState([]);
  const [bindingTarget, setBindingTarget] = useState(null);
  const [bindingStateId, setBindingStateId] = useState("");
  const [bindingRole, setBindingRole] = useState("TEACHES");

  const [approvedInteractions, setApprovedInteractions] = useState([]);
  const [interactionStateId, setInteractionStateId] = useState("");
  const [interactionInstanceId, setInteractionInstanceId] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    const query = new URLSearchParams({ target_type: bindingType, q: bindingQuery, limit: "20" });
    request(`${endpoint}/targets?${query}`, { signal: controller.signal })
      .then(setBindingTargets)
      .catch(err => { if (err.name !== "AbortError") setError(err.message); });
    return () => controller.abort();
  }, [bindingType, bindingQuery]);

  useEffect(() => {
    const controller = new AbortController();
    request(`${endpoint}/interactions?limit=250`, { signal: controller.signal })
      .then(setApprovedInteractions)
      .catch(err => { if (err.name !== "AbortError") setError(err.message); });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!release?.states?.length) return;
    const stateIds = new Set(release.states.map(state => state.state_id));
    if (!stateIds.has(interactionStateId)) setInteractionStateId(release.states[0].state_id);
  }, [release, interactionStateId]);

  async function perform(url, payload, success, after) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await request(url, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      setNotice(success(result));
      refresh();
      after?.(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (!release) return <EmptyState icon="file-earmark-text">Create a draft release first (see the Versions tab).</EmptyState>;

  const editable = release.status === "DRAFT";
  const bindingRoles = {
    CONCEPT: ["TEACHES", "REQUIRES", "REVIEWS", "MENTIONS"],
    TECHNIQUE: ["TEACHES", "REQUIRES", "RECOGNIZES", "APPLIES", "REVIEWS"],
    SKILL: ["TEACHES", "REQUIRES", "ASSESSES", "REVIEWS"],
    MISCONCEPTION: ["WATCH_FOR", "ADDRESSES", "DIAGNOSES"],
  }[bindingType];

  async function createModule(event) {
    event.preventDefault();
    await perform(`${endpoint}/releases/${release.release_id}/modules`, {
      ...moduleForm, ordinal: release.modules.length, required: true,
    }, () => "Module added.", () => setModuleForm({ module_key: "", title: "", objective: "" }));
  }

  async function createState(event) {
    event.preventDefault();
    await perform(`${endpoint}/releases/${release.release_id}/states`, {
      ...stateForm, module_id: stateForm.module_id || null, ordinal: release.states.length,
      required: true, skippable: false, agent_policy: SAFE_AGENT_POLICY,
    }, () => "State added.", () => setStateForm({
      state_key: "", state_type: "ORIENTATION", title: "", module_id: "", objective: "", student_instruction: "",
    }));
  }

  async function bindState(event) {
    event.preventDefault();
    if (!bindingStateId || !bindingTarget) return;
    await perform(`${endpoint}/states/${bindingStateId}/bindings`,
      { target_type: bindingType, target_id: bindingTarget.id, role: bindingRole },
      () => "Canonical mapping added.", () => setBindingTarget(null));
  }

  async function bindInteraction(event) {
    event.preventDefault();
    const state = release.states.find(item => item.state_id === interactionStateId);
    if (!state || !interactionInstanceId) return;
    await perform(`${endpoint}/states/${interactionStateId}/interactions`, {
      interaction_instance_id: interactionInstanceId, ordinal: state.interactions?.length || 0, required: true,
    }, () => "Approved interaction attached to the draft state.", () => setInteractionInstanceId(""));
  }

  async function createTransition(event) {
    event.preventDefault();
    await perform(`${endpoint}/releases/${release.release_id}/transitions`, transitionForm, () => "Transition added.");
  }

  return (
    <div>
      {error && <Callout tone="danger" role="alert" className="mb-3">{error}</Callout>}
      {notice && <Callout tone="success" role="status" className="mb-3">{notice}</Callout>}
      {!editable && (
        <Callout tone="info" className="mb-3">
          This release is {release.status}; start a new draft version to edit its content.
        </Callout>
      )}

      <div className="card border-0 shadow-sm p-3 mb-4">
        <SectionTitle icon="list-check">Outline — v{release.version}</SectionTitle>
        {!release.states.length ? <EmptyState icon="inbox">Add authored states to build the course outline.</EmptyState> : (
          <ol className="list-group list-group-numbered list-group-flush">
            {release.states.map(state => (
              <li key={state.state_id} className="list-group-item d-flex justify-content-between align-items-start gap-3">
                <div className="ms-2 me-auto">
                  <strong>{state.title}</strong>
                  <div className="small text-secondary">{state.state_key}{state.objective ? ` · ${state.objective}` : ""}</div>
                  <div className="d-flex flex-wrap gap-1 mt-2">
                    {Object.entries(state.bindings || {}).flatMap(([kind, bindings]) =>
                      bindings.map(binding => <Pill key={`${kind}-${binding.target_id}-${binding.role}`} tone="neutral">{kind} · {binding.role}</Pill>))}
                    {(state.interactions || []).map(interaction => (
                      <Pill key={interaction.interaction_instance_id} tone="info">{interaction.template_key} · {interaction.title}</Pill>
                    ))}
                    {(state.assets || []).map(asset => (
                      <Pill key={asset.asset_id} tone={asset.validation_status === "VALID" ? "success" : "warning"}>
                        {asset.title || asset.asset_kind} · {asset.mime_type}
                      </Pill>
                    ))}
                  </div>
                </div>
                <Pill tone={state.required ? "primary" : "neutral"}>{state.state_type}</Pill>
              </li>
            ))}
          </ol>
        )}
      </div>

      {editable && (
        <div className="row g-3 mb-4">
          <div className="col-lg-6">
            <form className="card border-0 shadow-sm p-3 h-100" onSubmit={createModule}>
              <SectionTitle icon="folder-plus">Add module</SectionTitle>
              <Field id="module-key" label="Module key" value={moduleForm.module_key}
                onChange={event => setModuleForm({ ...moduleForm, module_key: event.target.value.toUpperCase() })} required />
              <Field id="module-title" label="Title" value={moduleForm.title}
                onChange={event => setModuleForm({ ...moduleForm, title: event.target.value })} required />
              <Field id="module-objective" label="Objective" value={moduleForm.objective}
                onChange={event => setModuleForm({ ...moduleForm, objective: event.target.value })} />
              <button className="btn btn-outline-primary mt-auto" type="submit" disabled={busy}>Add module</button>
            </form>
          </div>
          <div className="col-lg-6">
            <form className="card border-0 shadow-sm p-3 h-100" onSubmit={createState}>
              <SectionTitle icon="plus-square">Add state</SectionTitle>
              <div className="row g-2">
                <div className="col-sm-6"><Field id="state-key" label="State key" value={stateForm.state_key}
                  onChange={event => setStateForm({ ...stateForm, state_key: event.target.value.toUpperCase() })} required /></div>
                <div className="col-sm-6">
                  <label className="form-label" htmlFor="state-type">Type</label>
                  <select id="state-type" className="form-select mb-3" value={stateForm.state_type}
                    onChange={event => setStateForm({ ...stateForm, state_type: event.target.value })}>
                    {STATE_TYPES.map(type => <option key={type}>{type}</option>)}
                  </select>
                </div>
              </div>
              <Field id="state-title" label="Title" value={stateForm.title}
                onChange={event => setStateForm({ ...stateForm, title: event.target.value })} required />
              <label className="form-label" htmlFor="state-module">Module</label>
              <select id="state-module" className="form-select mb-3" value={stateForm.module_id}
                onChange={event => setStateForm({ ...stateForm, module_id: event.target.value })}>
                <option value="">No module</option>
                {release.modules.map(module => <option key={module.module_id} value={module.module_id}>{module.title}</option>)}
              </select>
              <Field id="state-objective" label="Objective" value={stateForm.objective}
                onChange={event => setStateForm({ ...stateForm, objective: event.target.value })} />
              <div className="mb-3">
                <label className="form-label" htmlFor="state-instruction">Student instruction</label>
                <textarea id="state-instruction" className="form-control" rows={3} value={stateForm.student_instruction}
                  onChange={event => setStateForm({ ...stateForm, student_instruction: event.target.value })} />
              </div>
              <button className="btn btn-outline-primary mt-auto" type="submit" disabled={busy}>Add state</button>
            </form>
          </div>
        </div>
      )}

      {editable && release.states.length > 0 && (
        <div className="card border-0 shadow-sm p-3 mb-4">
          <SectionTitle icon="diagram-3">Map a state to a concept/technique/skill/misconception</SectionTitle>
          <form className="row g-3 align-items-end" onSubmit={bindState}>
            <div className="col-md-3">
              <label className="form-label" htmlFor="binding-state">State</label>
              <select id="binding-state" className="form-select" value={bindingStateId}
                onChange={event => setBindingStateId(event.target.value)} required>
                <option value="">Choose state</option>
                {release.states.map(state => <option key={state.state_id} value={state.state_id}>{state.state_key}</option>)}
              </select>
            </div>
            <div className="col-md-2">
              <label className="form-label" htmlFor="binding-type">Maps to</label>
              <select id="binding-type" className="form-select" value={bindingType}
                onChange={event => {
                  const nextType = event.target.value;
                  setBindingType(nextType);
                  setBindingTarget(null);
                  setBindingRole(nextType === "MISCONCEPTION" ? "WATCH_FOR" : "TEACHES");
                }}>
                {["CONCEPT", "TECHNIQUE", "SKILL", "MISCONCEPTION"].map(kind => <option key={kind}>{kind}</option>)}
              </select>
            </div>
            <div className="col-md-3">
              <label className="form-label" htmlFor="binding-search">Find canonical node</label>
              <input id="binding-search" className="form-control" value={bindingQuery}
                onChange={event => setBindingQuery(event.target.value)} placeholder="Search name or code" />
              <select className="form-select mt-2" aria-label="Canonical node result" value={bindingTarget?.id || ""}
                onChange={event => setBindingTarget(bindingTargets.find(item => item.id === event.target.value) || null)} required>
                <option value="">Choose a result</option>
                {bindingTargets.map(item => <option key={item.id} value={item.id}>{item.name} · {item.slug}</option>)}
              </select>
            </div>
            <div className="col-md-2">
              <label className="form-label" htmlFor="binding-role">Role</label>
              <select id="binding-role" className="form-select" value={bindingRole}
                onChange={event => setBindingRole(event.target.value)}>
                {bindingRoles.map(role => <option key={role}>{role}</option>)}
              </select>
            </div>
            <div className="col-md-2"><button className="btn btn-outline-primary w-100" type="submit" disabled={busy}>Map node</button></div>
          </form>
        </div>
      )}

      {editable && release.states.length > 0 && (
        <div className="card border-0 shadow-sm p-3 mb-4">
          <SectionTitle icon="puzzle">Attach an approved interaction</SectionTitle>
          {!approvedInteractions.length ? (
            <EmptyState icon="puzzle">No approved interactions with published templates are available (see the Widgets tab).</EmptyState>
          ) : (
            <form className="row g-3 align-items-end" onSubmit={bindInteraction}>
              <div className="col-md-5">
                <label className="form-label" htmlFor="interaction-state">Lesson state</label>
                <select id="interaction-state" className="form-select" value={interactionStateId}
                  onChange={event => setInteractionStateId(event.target.value)} required>
                  {release.states.map(state => <option key={state.state_id} value={state.state_id}>{state.state_key} · {state.title}</option>)}
                </select>
              </div>
              <div className="col-md-5">
                <label className="form-label" htmlFor="interaction-instance">Approved interaction</label>
                <select id="interaction-instance" className="form-select" value={interactionInstanceId}
                  onChange={event => setInteractionInstanceId(event.target.value)} required>
                  <option value="">Choose an interaction</option>
                  {approvedInteractions.map(item => (
                    <option key={item.interaction_instance_id} value={item.interaction_instance_id}>{item.title} · {item.template_key}</option>
                  ))}
                </select>
              </div>
              <div className="col-md-2">
                <button className="btn btn-outline-primary w-100" type="submit" disabled={busy || !interactionInstanceId}>Attach</button>
              </div>
            </form>
          )}
        </div>
      )}

      {editable && release.states.length > 1 && (
        <div className="card border-0 shadow-sm p-3 mb-4">
          <SectionTitle icon="signpost-split">Define a transition</SectionTitle>
          <form className="row g-3 align-items-end" onSubmit={createTransition}>
            <div className="col-md-4">
              <label className="form-label" htmlFor="transition-from">From</label>
              <select id="transition-from" className="form-select" value={transitionForm.from_state_id}
                onChange={event => setTransitionForm({ ...transitionForm, from_state_id: event.target.value })} required>
                <option value="">Choose state</option>
                {release.states.map(state => <option key={state.state_id} value={state.state_id}>{state.state_key} · {state.title}</option>)}
              </select>
            </div>
            <div className="col-md-4">
              <label className="form-label" htmlFor="transition-to">To</label>
              <select id="transition-to" className="form-select" value={transitionForm.to_state_id}
                onChange={event => setTransitionForm({ ...transitionForm, to_state_id: event.target.value })} required>
                <option value="">Choose state</option>
                {release.states.map(state => <option key={state.state_id} value={state.state_id}>{state.state_key} · {state.title}</option>)}
              </select>
            </div>
            <div className="col-md-3">
              <label className="form-label" htmlFor="transition-type">Type</label>
              <select id="transition-type" className="form-select" value={transitionForm.transition_type}
                onChange={event => setTransitionForm({ ...transitionForm, transition_type: event.target.value })}>
                {["NEXT", "USER_CONTINUE", "USER_BACK", "RETRY"].map(type => <option key={type}>{type}</option>)}
              </select>
            </div>
            <div className="col-md-1"><button className="btn btn-outline-primary w-100" type="submit" disabled={busy}>Add</button></div>
          </form>
        </div>
      )}
    </div>
  );
}
