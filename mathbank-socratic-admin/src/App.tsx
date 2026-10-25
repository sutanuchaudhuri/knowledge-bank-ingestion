import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { api, ApiError, checkPreview, checkWorkflow, pathId, pollJob } from "./api";
import type { Edge, Job, Preview, PreviewAnswer, Program, Session, Strategy, Validation, Workflow, WorkflowSummary } from "./contracts";
import { actorName, isDirty } from "./contracts";
import { Coauthor } from "./Coauthor";
import { Designer } from "./Designer";
import { Resources } from "./Resources";
import { Rules } from "./Rules";
import { Icon, MathText, PageHeader, Pager, Pill } from "./ui";

const views = [
  { key: "designer", label: "Designer + Simulator", icon: "bezier2", subtitle: "Author draft journeys and inspect server-owned synthetic transitions." },
  { key: "rules", label: "Rules by topic", icon: "diagram-3", subtitle: "Review plain-language explanations beside their authoritative typed rules." },
  { key: "resources", label: "Resource Library", icon: "database", subtitle: "Link canonical sources and released step-authoring references." },
] as const;
type View = typeof views[number]["key"];
type Proposal = { job: Job; workflowId: string; baseHash: string };
const viewFromHash = (): View => {
  const key = window.location.hash.slice(1);
  return views.some(view => view.key === key) ? key as View : "designer";
};

export function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [conflict, setConflict] = useState(false);
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const lifecycle = useRef(new AbortController());
  const [view, setView] = useState<View>(viewFromHash);
  const [menuOpen, setMenuOpen] = useState(false);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowSummary[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogFailed, setCatalogFailed] = useState(false);
  const [catalogRetry, setCatalogRetry] = useState(0);
  const [workflowPage, setWorkflowPage] = useState(0);
  const [workflowsHaveMore, setWorkflowsHaveMore] = useState(false);
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [program, setProgram] = useState<Program | null>(null);
  const [selected, setSelected] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const previewBaseHash = useRef<string | null>(null);
  const [validation, setValidation] = useState<Validation | null>(null);
  const [instruction, setInstruction] = useState("");
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [pollRetry, setPollRetry] = useState(0);
  const [polling, setPolling] = useState(false);
  const [title, setTitle] = useState("");
  const [domain, setDomain] = useState("");
  const [pendingOpen, setPendingOpen] = useState<string | null>(null);
  const dirty = isDirty(workflow, program);
  const activeView = views.find(item => item.key === view)!;

  const onError = useCallback((cause: unknown) => {
    if (cause instanceof DOMException && cause.name === "AbortError") return;
    setError(cause instanceof Error ? cause.message : "Unexpected failure. No changes have been assumed.");
    if (cause instanceof ApiError && cause.status === 409) setConflict(true);
    if (cause instanceof ApiError && cause.status === 401) {
      api.setSession(null); setSession(null);
      setWorkflow(null); setProgram(null); setPreview(null); setProposal(null);
      setWorkflows([]); setStrategies([]);
    }
  }, []);

  useEffect(() => {
    lifecycle.current = new AbortController();
    const controller = lifecycle.current;
    api.request<Session>("/session", { signal: controller.signal }).then(value => {
      if (!value.csrf_token || !value.actor) throw new Error("Invalid administrator session response.");
      api.setSession(value); setSession(value);
    }).catch(cause => {
      if (!(cause instanceof ApiError && cause.status === 401) && !controller.signal.aborted) onError(cause);
    }).finally(() => { if (!controller.signal.aborted) setChecking(false); });
    const navigation = () => { setView(viewFromHash()); setMenuOpen(false); };
    window.addEventListener("hashchange", navigation);
    return () => { controller.abort(); window.removeEventListener("hashchange", navigation); };
  }, [onError]);

  useEffect(() => {
    if (!session) return;
    const controller = new AbortController();
    setCatalogLoading(true); setCatalogFailed(false);
    Promise.all([
      api.request<{ strategies: Strategy[] }>("/strategies", { signal: controller.signal }),
      api.request<{ workflows: WorkflowSummary[]; has_more: boolean }>(
        `/workflows?limit=25&offset=${workflowPage * 25}`, { signal: controller.signal }),
    ]).then(([registry, drafts]) => {
      setStrategies(registry.strategies); setWorkflows(drafts.workflows);
      setWorkflowsHaveMore(drafts.has_more);
    }).catch(cause => { if (!controller.signal.aborted) { setCatalogFailed(true); onError(cause); } })
      .finally(() => { if (!controller.signal.aborted) setCatalogLoading(false); });
    return () => controller.abort();
  }, [session, catalogRetry, workflowPage, onError]);

  useEffect(() => {
    const id = proposal?.job.job_id;
    if (!id || !["QUEUED", "RUNNING"].includes(proposal.job.status)) return;
    const controller = new AbortController();
    setPolling(true);
    pollJob(api, id, controller.signal, job => {
      setProposal(current => current?.job.job_id === id ? { ...current, job } : current);
    }).catch(cause => { if (!controller.signal.aborted) onError(cause); })
      .finally(() => { if (!controller.signal.aborted) setPolling(false); });
    return () => { controller.abort(); setPolling(false); };
    // Status updates must not restart or extend the bounded polling window.
  }, [proposal?.job.job_id, pollRetry, onError]);

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  function navigate(next: View) { window.location.hash = next; setView(next); setMenuOpen(false); }
  async function run(action: () => Promise<void>) {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError(""); setNotice("");
    try { await action(); } catch (cause) { if (!lifecycle.current.signal.aborted) onError(cause); }
    finally { lock.current = false; if (!lifecycle.current.signal.aborted) setBusy(false); }
  }
  const request = <T,>(path: string, method = "GET", body?: unknown) =>
    api.request<T>(path, { method, body, signal: lifecycle.current.signal });

  function remember(detail: Workflow) {
    checkWorkflow(detail); setWorkflow(detail); setProgram(structuredClone(detail.program));
    setWorkflows(current => {
      const { program: _, prototype_only: __, ...summary } = detail;
      return current.some(item => item.workflow_id === detail.workflow_id)
        ? current.map(item => item.workflow_id === detail.workflow_id ? summary : item) : [summary, ...current];
    });
    setValidation(null); setConflict(false);
  }
  async function open(id: string) {
    const detail = checkWorkflow(await request<Workflow>(`/workflows/${pathId(id)}`));
    remember(detail); setSelected(detail.program.entry); setPreview(null); setProposal(null); setPendingOpen(null);
  }
  async function save(): Promise<Workflow> {
    if (!workflow || !program) throw new Error("Open a workflow first.");
    if (!isDirty(workflow, program)) return workflow;
    const detail = checkWorkflow(await request<Workflow>(`/workflows/${pathId(workflow.workflow_id)}`, "PUT", {
      expected_hash: workflow.content_hash, program,
    }));
    remember(detail); setNotice("Draft saved on the server.");
    return detail;
  }
  function edit(next: Program) { setProgram(next); setValidation(null); setNotice(""); }

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    await run(async () => {
      const value = await request<Session>("/session", "POST", { username: data.get("username"), password: data.get("password") });
      if (!value.csrf_token || !value.actor) throw new Error("Invalid administrator session response.");
      api.setSession(value); setSession(value); form.reset(); setConflict(false);
    });
  }

  function previewAction(action: "respond" | "assist" | "reveal", answer?: PreviewAnswer) {
    void run(async () => {
      if (!preview || !workflow) throw new Error("Start a synthetic preview first.");
      if (dirty || previewBaseHash.current !== workflow.content_hash) throw new Error("The draft changed. Save and restart the preview before continuing.");
      setPreview(checkPreview(await request<Preview>(`/previews/${pathId(preview.preview_id)}/${action}`, "POST", {
        expected_version: preview.state_version, idempotency_key: crypto.randomUUID(),
        ...(action === "respond" ? {
          current_node_key: preview.current_node.key, activity_id: preview.activity?.activity_id,
          activity_revision: preview.activity?.revision, response: answer,
        } : {}),
      })));
    });
  }
  const coauthor = workflow && program ? <Coauthor key={`proposal-${proposal?.job.job_id || workflow.workflow_id}`} program={workflow.program}
    instruction={instruction} setInstruction={setInstruction} job={proposal?.job} baseHash={proposal?.baseHash}
    stale={!!proposal && (dirty || workflow.content_hash !== proposal.baseHash || workflow.workflow_id !== proposal.workflowId)}
    disabled={busy || conflict} polling={polling}
    onRequest={() => void run(async () => {
      const saved = await save();
      const started = await request<{ job_id: string; status: Job["status"]; execution_arn: string }>(`/workflows/${pathId(saved.workflow_id)}/proposals`, "POST", { expected_hash: saved.content_hash, instruction: instruction.trim() });
      if (!["QUEUED", "RUNNING", "SUCCEEDED", "FAILED"].includes(started.status)) throw new Error("Unsupported proposal job status.");
      const job: Job = ["SUCCEEDED", "FAILED"].includes(started.status)
        ? await request<Job>(`/jobs/${pathId(started.job_id)}`) : { job_id: started.job_id, status: started.status, error: null, result: null };
      setProposal({ workflowId: saved.workflow_id, baseHash: saved.content_hash, job });
    })}
    onAccept={(candidate?: Edge) => void run(async () => {
      if (!proposal) return;
      const accepted = checkWorkflow(await request<Workflow>(`/workflows/${pathId(workflow.workflow_id)}/proposals/${pathId(proposal.job.job_id)}/accept`, "POST", {
        expected_hash: proposal.baseHash, ...(candidate ? { candidate } : {}),
      }));
      remember(accepted); setPreview(null); setProposal(null); setNotice("Proposed edge accepted into the server draft. Not published.");
    })}
    onReject={() => setProposal(null)} onResume={() => { setError(""); setPollRetry(value => value + 1); }} /> : null;

  let content: ReactNode;
  if (checking) content = <p role="status">Checking administrator session…</p>;
  else if (!session) content = <section className="sc-card sc-login">
    <h2>Administrator sign in</h2><p className="sc-muted">An HTTP-only cookie secures this session. No browser API keys.</p>
    <form className="sc-stack" onSubmit={login}>
      <label>Username<input name="username" autoComplete="username" required disabled={busy} /></label>
      <label>Password<input name="password" type="password" autoComplete="current-password" required disabled={busy} /></label>
      <button className="sc-primary" disabled={busy}>Sign in</button>
    </form>
  </section>;
  else content = <>
    {view === "designer" && <>
      <details className="sc-card" open={!workflow}>
        <summary>Workflow drafts · {workflow?.title || "Choose or create a journey"}</summary>
        <div className="sc-stack">
        <div className="sc-toolbar sc-between"><h2>Server drafts</h2><button disabled={busy || catalogLoading} onClick={() => setCatalogRetry(value => value + 1)}>Refresh catalog</button></div>
        {catalogLoading ? <p role="status">Loading strategies and workflows…</p> : catalogFailed ? <p>Catalog unavailable. Retry before creating or choosing strategies.</p> : <>
          {workflows.length === 0 ? <p>No server drafts on this page.</p> : <div className="sc-draft-list">{workflows.slice(0, 25).map(item =>
            <button key={item.workflow_id} disabled={busy} aria-pressed={workflow?.workflow_id === item.workflow_id} onClick={() => {
              if (dirty) setPendingOpen(item.workflow_id); else void run(() => open(item.workflow_id));
            }}><MathText text={item.title} /><span className="sc-muted">{item.domain} · revision {item.revision}</span></button>)}</div>}
          <Pager page={workflowPage} hasMore={workflowsHaveMore} onChange={setWorkflowPage} disabled={busy || catalogLoading} />
          <form className="sc-config" onSubmit={event => {
            event.preventDefault();
            void run(async () => {
              if (dirty) throw new Error("Save or explicitly discard the current draft before creating another.");
              const detail = checkWorkflow(await request<Workflow>("/workflows", "POST", { title: title.trim(), domain }));
              remember(detail); setSelected(detail.program.entry); setPreview(null); setProposal(null); setTitle("");
            });
          }}>
            <label>New workflow title<input required maxLength={200} value={title} disabled={busy} onChange={event => setTitle(event.target.value)} /></label>
            <label>Domain<select required value={domain} disabled={busy} onChange={event => setDomain(event.target.value)}>
              <option value="">Choose domain…</option>{[...new Set(strategies.map(item => item.domain))].sort().map(value => <option key={value}>{value}</option>)}
            </select></label>
            <button className="sc-primary" disabled={busy || dirty || !title.trim() || !domain}>Create server draft</button>
          </form>
        </>}
        {pendingOpen && <div className="sc-callout" role="alert">Unsaved draft changes will be discarded.
          <div className="sc-toolbar"><button className="sc-danger" disabled={busy} onClick={() => void run(() => open(pendingOpen))}>Discard changes & open</button><button onClick={() => setPendingOpen(null)}>Keep editing</button></div>
        </div>}
        </div>
      </details>
    </>}
    {workflow && program && <section className="sc-card sc-toolbar sc-between sc-workflow-status" aria-label="Current draft">
      <div><strong><MathText text={workflow.title} /></strong><div className="sc-toolbar"><Pill>{workflow.domain}</Pill><Pill>Revision {workflow.revision}</Pill><Pill tone={dirty ? "warning" : "success"}>{dirty ? "Unsaved changes" : "Server saved"}</Pill></div></div>
      <div className="sc-toolbar">
        <button className="sc-primary" disabled={busy || conflict || !dirty} onClick={() => void run(async () => { await save(); })}>Save draft</button>
        <button disabled={busy || conflict} onClick={() => void run(async () => {
          const saved = await save();
          setValidation(await request<Validation>(`/workflows/${pathId(saved.workflow_id)}/validate`, "POST", { expected_hash: saved.content_hash }));
        })}>Save & validate</button>
      </div>
      <details className="sc-full"><summary>Draft identity</summary><code>{workflow.workflow_id}<br />{workflow.content_hash}</code></details>
    </section>}
    {validation && <section className="sc-callout" aria-label="Structural validation">
      <h2>{validation.valid ? "Structural validation passed" : "Structural validation requires changes"}</h2>
      <p>Not mathematical attestation, pedagogical review or publication approval.</p>
      <ul>{validation.findings.map((finding, index) => <li key={index}><MathText text={finding} /></li>)}</ul>
    </section>}
    {view === "designer" && workflow && program && <Designer key={workflow.workflow_id} program={program} strategies={strategies} selected={selected} setSelected={setSelected}
      preview={preview} disabled={busy || conflict} edit={edit} onSources={() => navigate("resources")}
      onPropose={() => { setInstruction(`After ${program.nodes.find(node => node.key === selected)?.label || selected}, continue to the next approved discovery.`); navigate("rules"); }}
      onRespond={answer => previewAction("respond", answer)} onAssist={() => previewAction("assist")} onReveal={() => previewAction("reveal")}
      onSimulate={() => void run(async () => {
        const saved = await save();
        setPreview(checkPreview(await request<Preview>(`/workflows/${pathId(saved.workflow_id)}/simulate`, "POST", { expected_hash: saved.content_hash })));
        previewBaseHash.current = saved.content_hash;
      })}
      onTransition={outcome => void run(async () => {
        if (!preview) return;
        if (dirty || previewBaseHash.current !== workflow.content_hash) throw new Error("The draft changed. Save and restart the preview before simulating outcomes.");
        setPreview(checkPreview(await request<Preview>(`/previews/${pathId(preview.preview_id)}/transition`, "POST", {
          expected_version: preview.state_version, idempotency_key: crypto.randomUUID(), outcome,
        })));
      })}
      onRefreshPreview={() => void run(async () => {
        if (preview) setPreview(checkPreview(await request<Preview>(`/previews/${pathId(preview.preview_id)}`)));
      })} />}
    {view === "designer" && coauthor}
    {view === "rules" && <Rules key={workflow?.workflow_id || "none"} program={program} strategies={strategies} domain={workflow?.domain || ""} edit={edit} disabled={busy || conflict}
      coauthor={coauthor} onInspect={key => { setSelected(key); navigate("designer"); }} />}
    {view === "resources" && <Resources disabled={busy || conflict} canAttach={!!workflow} program={program} onError={onError}
      onPreview={key => void run(async () => {
        const saved = await save();
        const next = checkPreview(await request<Preview>(`/workflows/${pathId(saved.workflow_id)}/simulate`, "POST", {
          expected_hash: saved.content_hash, start_node_key: key,
        }));
        setPreview(next); previewBaseHash.current = saved.content_hash; setSelected(key); navigate("designer");
      })} onAttach={source => {
      if (program) { edit({ ...program, source }); setNotice("Source references attached to the unsaved draft. Save to persist."); navigate("designer"); }
    }} />}
  </>;

  return <div className={`sc-shell${menuOpen ? " sc-menu-open" : ""}`}>
    <a className="sc-skip" href="#main-content">Skip to content</a>
    <aside className="sc-sidebar" id="studio-navigation">
      <a className="sc-brand" href="#designer"><Icon name="infinity" /> MathBank</a>
      <p className="sc-muted">Socratic Studio</p>
      <nav aria-label="Studio navigation">{views.map(item => <a key={item.key} href={`#${item.key}`} aria-current={view === item.key ? "page" : undefined} onClick={() => navigate(item.key)}>
        <Icon name={item.icon} />{item.label}
      </a>)}</nav>
      <div className="sc-sidebar-footer"><Pill tone="warning">Prototype only</Pill><p>Production publishing unavailable.</p></div>
    </aside>
    <div className="sc-main">
      <header className="sc-topbar">
        <button className="sc-menu-toggle" aria-label="Toggle navigation" title="Toggle navigation" aria-controls="studio-navigation" aria-expanded={menuOpen} onClick={() => setMenuOpen(value => !value)}><Icon name="list" /></button>
        <nav aria-label="Breadcrumb"><a href="#designer" onClick={() => navigate("designer")}>Studio</a><span aria-hidden="true"> / </span><span aria-current="page">{activeView.label}</span></nav>
        {session && <div className="sc-toolbar sc-user"><span className="sc-avatar" aria-hidden="true">{actorName(session.actor).slice(0, 2).toUpperCase()}</span>
          <span>{actorName(session.actor)}</span><button disabled={busy} onClick={() => {
            if (dirty) { setError("Save or discard the draft before signing out."); return; }
            void run(async () => {
              await request<void>("/session", "DELETE");
              api.setSession(null); setSession(null); setWorkflow(null); setProgram(null); setPreview(null); setProposal(null); setWorkflows([]); setStrategies([]);
            });
          }}>Sign out</button></div>}
      </header>
      <main id="main-content" className="sc-content sc-stack">
        <PageHeader title={activeView.label} subtitle={activeView.subtitle} icon={activeView.icon} />
        {session?.auth_mode === "local" && <div className="sc-callout" role="status">
          <Pill tone="warning">Local testing</Pill> Loopback-only staff session. No AWS identity or production approval.
        </div>}
        {error && <div className="sc-error" role="alert"><MathText text={error} /></div>}
        {conflict && workflow && <div className="sc-callout">
          Reload explicitly to resolve the conflict. Reloading the draft discards unsaved edits and any proposal.
          <div className="sc-toolbar"><button disabled={busy} onClick={() => void run(async () => { await open(workflow.workflow_id); setNotice("Current server draft loaded."); })}>Discard edits & reload server draft</button>
            {preview && <button disabled={busy} onClick={() => void run(async () => {
              setPreview(checkPreview(await request<Preview>(`/previews/${pathId(preview.preview_id)}`))); setConflict(false);
            })}>Reload current preview version</button>}</div>
        </div>}
        {notice && <p className="sc-callout" role="status">{notice}</p>}
        {busy && <p role="status">Saving / contacting server…</p>}
        {content}
        {session && dirty && <button className="sc-danger" disabled={busy} onClick={() => {
          if (workflow) { setProgram(structuredClone(workflow.program)); setValidation(null); setNotice("Unsaved edits discarded; showing the last loaded server draft."); }
        }}>Discard unsaved edits</button>}
      </main>
    </div>
  </div>;
}
