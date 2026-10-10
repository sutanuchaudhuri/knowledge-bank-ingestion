"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Callout, Icon, PageHeader, Pill } from "../../../../_components/ui.jsx";

const endpoint = "/api/rest/admin/micro-courses";

async function request(url, options) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || body.detail || `Request failed (${response.status})`);
  return body;
}

const STEPS = ["Identity", "Target", "Starting point"];

export default function NewCourseWizard() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const [canonicalCode, setCanonicalCode] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [createdBy, setCreatedBy] = useState("");

  const [targetType, setTargetType] = useState("TECHNIQUE");
  const [targetQuery, setTargetQuery] = useState("");
  const [targets, setTargets] = useState([]);
  const [target, setTarget] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    const query = new URLSearchParams({ target_type: targetType, q: targetQuery, limit: "20" });
    request(`${endpoint}/targets?${query}`, { signal: controller.signal })
      .then(setTargets)
      .catch(err => { if (err.name !== "AbortError") setError(err.message); });
    return () => controller.abort();
  }, [targetType, targetQuery]);

  const canAdvanceFromIdentity = canonicalCode.trim() && title.trim() && createdBy.trim();

  async function createBlankCourse() {
    if (!target) return;
    setBusy(true);
    setError("");
    try {
      await request(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          canonical_code: canonicalCode.trim(),
          title: title.trim(),
          description: description.trim() || null,
          created_by: createdBy.trim(),
          metadata: {},
          targets: [{ target_type: targetType, target_id: target.id, role: "PRIMARY" }],
        }),
      });
      router.push(`/admin/micro-courses/${encodeURIComponent(canonicalCode.trim())}`);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader icon="plus-circle" title="New micro-course" subtitle="Identity, then a canonical target, then a starting point." />
      {error && <Callout tone="danger" role="alert">{error}</Callout>}

      <nav className="mb-course-stepper mb-4" aria-label="Creation steps" style={{ flexDirection: "row", position: "static" }}>
        {STEPS.map((label, index) => (
          <button key={label} type="button" className={`mb-course-step${index === step ? " is-current" : ""}${index < step ? " is-done" : ""}`}
            disabled={index > step} onClick={() => setStep(index)} style={{ width: "auto", flex: "none" }}>
            <span className="mb-course-step-dot" aria-hidden="true">{index < step ? <Icon name="check-lg" /> : index + 1}</span>
            <span className="mb-course-step-label"><span className="d-block">{label}</span></span>
          </button>
        ))}
      </nav>

      <div className="card border-0 shadow-sm p-3 p-lg-4" style={{ maxWidth: 640 }}>
        {step === 0 && (
          <>
            <div className="mb-3">
              <label className="form-label" htmlFor="new-code">Canonical code</label>
              <input id="new-code" className="form-control" value={canonicalCode}
                onChange={event => setCanonicalCode(event.target.value.toUpperCase())}
                placeholder="MC-GEO-POWER-POINT" maxLength={120} />
            </div>
            <div className="mb-3">
              <label className="form-label" htmlFor="new-title">Title</label>
              <input id="new-title" className="form-control" value={title}
                onChange={event => setTitle(event.target.value)} maxLength={300} />
            </div>
            <div className="mb-3">
              <label className="form-label" htmlFor="new-description">Description</label>
              <textarea id="new-description" className="form-control" rows={2} value={description}
                onChange={event => setDescription(event.target.value)} />
            </div>
            <div className="mb-3">
              <label className="form-label" htmlFor="new-author">Author</label>
              <input id="new-author" className="form-control" value={createdBy}
                onChange={event => setCreatedBy(event.target.value)} />
            </div>
            <button type="button" className="btn btn-primary" disabled={!canAdvanceFromIdentity} onClick={() => setStep(1)}>
              Next: Target <Icon name="arrow-right" />
            </button>
          </>
        )}
        {step === 1 && (
          <>
            <div className="mb-3">
              <label className="form-label" htmlFor="new-target-type">Primary target type</label>
              <select id="new-target-type" className="form-select" value={targetType}
                onChange={event => { setTargetType(event.target.value); setTarget(null); }}>
                <option value="CONCEPT">Concept</option>
                <option value="TECHNIQUE">Technique</option>
                <option value="SKILL">Skill</option>
              </select>
            </div>
            <div className="mb-3">
              <label className="form-label" htmlFor="new-target-search">Find an existing target</label>
              <input id="new-target-search" className="form-control" value={targetQuery}
                onChange={event => setTargetQuery(event.target.value)} placeholder="Search by name or slug" />
            </div>
            <div className="mb-3">
              <label className="form-label" htmlFor="new-target-result">Canonical match</label>
              <select id="new-target-result" className="form-select" value={target?.id || ""}
                onChange={event => setTarget(targets.find(item => item.id === event.target.value) || null)}>
                <option value="">Choose a result</option>
                {targets.map(item => <option key={item.id} value={item.id}>{item.name} · {item.slug}</option>)}
              </select>
            </div>
            {target && <div className="mb-3"><Pill tone="primary">{target.name} · {target.slug}</Pill></div>}
            <div className="d-flex gap-2">
              <button type="button" className="btn btn-outline-secondary" onClick={() => setStep(0)}><Icon name="arrow-left" /> Back</button>
              <button type="button" className="btn btn-primary" disabled={!target} onClick={() => setStep(2)}>
                Next: Starting point <Icon name="arrow-right" />
              </button>
            </div>
          </>
        )}
        {step === 2 && (
          <>
            <p className="mb-3">Start from a blank draft and build the lesson in the Content tab, or clone an existing course's structure.</p>
            <Callout tone="hint" className="mb-3">
              Cloning an existing course's structure is not yet available — start blank for now;
              you can always author states/interactions/quizzes in the Content tab afterward.
            </Callout>
            <div className="d-flex gap-2">
              <button type="button" className="btn btn-outline-secondary" onClick={() => setStep(1)}><Icon name="arrow-left" /> Back</button>
              <button type="button" className="btn btn-primary" disabled={busy} onClick={createBlankCourse}>
                <Icon name="plus-lg" /> {busy ? "Creating…" : "Create blank course"}
              </button>
            </div>
          </>
        )}
      </div>
    </>
  );
}
