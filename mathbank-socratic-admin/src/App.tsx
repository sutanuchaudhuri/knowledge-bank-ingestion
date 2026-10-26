import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { api, ApiError, checkPreview, checkWorkflow, pathId, pollJob } from "./api";
import type { Capability, Edge, Job, Outcome, Preview, PreviewAnswer, Program, Role, Session, Strategy, Validation, Workflow, WorkflowSummary } from "./contracts";
import { actorName, can, isDirty, roleLabels } from "./contracts";
import { Coauthor } from "./Coauthor";
import { Designer } from "./Designer";
import type { Representation } from "./Designer";
import { Library } from "./Library";
import { NewRulePanel, NewStepPanel, NewWorkflowPanel, RulePanel, SettingsPanel, StepPanel } from "./Panels";
import { RulesView } from "./RulesView";
import { Sidebar } from "./Sidebar";
import { Simulator } from "./Simulator";
import { AccountPanel, UserPanel, Users } from "./Users";
import { Drawer, Empty, Hero, Icon, IconButton, MathText, Pill } from "./ui";

const views = [
  { key: "designer", label: "Workflow designer", icon: "bezier2", needs: "author" },
  { key: "rules", label: "Rules by topic", icon: "signpost-split", needs: "author" },
  { key: "library", label: "Templates & sources", icon: "grid", needs: "author" },
  { key: "student", label: "Student simulator", icon: "person-video3", needs: "preview" },
  { key: "users", label: "Users & access", icon: "people", needs: "manage_users" },
] as const satisfies readonly { key: string; label: string; icon: string; needs: Capability }[];
type View = typeof views[number]["key"];
const allowedViews = (session: Session | null) => views.filter(item => can(session, item.needs));
type Panel =
  | { kind: "step"; key: string } | { kind: "rule"; index: number } | { kind: "new-rule"; from?: string }
  | { kind: "new-step" } | { kind: "new-workflow"; strategy?: Strategy | null } | { kind: "settings" } | { kind: "ai" }
  | { kind: "user"; username: string } | { kind: "account" };
type Proposal = { job: Job; workflowId: string; baseHash: string };
const viewFromHash = (): View => {
  const key = window.location.hash.slice(1).split("-")[0];
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
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [panel, setPanel] = useState<Panel | null>(null);
  const [representation, setRepresentation] = useState<Representation>("flow");
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
  const [pendingOpen, setPendingOpen] = useState<string | null>(null);
  const [manageableGroups, setManageableGroups] = useState<string[]>([]);
  const [usersRefresh, setUsersRefresh] = useState(0);
  const dirty = isDirty(workflow, program);
  const disabled = busy || conflict;

  const reset = useCallback(() => {
    api.setSession(null); setSession(null);
    setWorkflow(null); setProgram(null); setPreview(null); setProposal(null); setPanel(null);
    setWorkflows([]); setStrategies([]);
  }, []);
  const onError = useCallback((cause: unknown) => {
    if (cause instanceof DOMException && cause.name === "AbortError") return;
    setError(cause instanceof Error ? cause.message : "Unexpected failure. No changes have been assumed.");
    if (cause instanceof ApiError && cause.status === 409) setConflict(true);
    if (cause instanceof ApiError && cause.status === 401) reset();
  }, [reset]);

  useEffect(() => {
    lifecycle.current = new AbortController();
    const controller = lifecycle.current;
    api.request<Session>("/session", { signal: controller.signal }).then(value => {
      if (!value.csrf_token || !value.actor) throw new Error("Invalid administrator session response.");
      api.setSession(value); setSession(value);
    }).catch(cause => {
      if (!(cause instanceof ApiError && cause.status === 401) && !controller.signal.aborted) onError(cause);
    }).finally(() => { if (!controller.signal.aborted) setChecking(false); });
    const navigation = () => setView(viewFromHash());
    window.addEventListener("hashchange", navigation);
    return () => { controller.abort(); window.removeEventListener("hashchange", navigation); };
  }, [onError]);

  useEffect(() => {
    if (!session || !can(session, "preview")) return;
    const controller = new AbortController();
    setCatalogLoading(true); setCatalogFailed(false);
    Promise.all([
      can(session, "author") ? api.request<{ strategies: Strategy[] }>("/strategies", { signal: controller.signal })
        : Promise.resolve({ strategies: [] as Strategy[] }),
      api.request<{ workflows: WorkflowSummary[]; has_more: boolean }>(
        `/workflows?limit=25&offset=${workflowPage * 25}`, { signal: controller.signal }),
    ]).then(([registry, drafts]) => {
      setStrategies(registry.strategies); setWorkflows(drafts.workflows); setWorkflowsHaveMore(drafts.has_more);
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
    if (!session) return;
    const allowed = allowedViews(session);
    if (allowed.length && !allowed.some(item => item.key === view)) { window.location.hash = allowed[0].key; setView(allowed[0].key); }
  }, [session, view]);

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  useEffect(() => {
    const escape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (sidebarOpen) setSidebarOpen(false); else setPanel(null);
    };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [sidebarOpen]);

  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 4000);
    return () => clearTimeout(timer);
  }, [notice]);

  function navigate(next: View) { window.location.hash = next; setView(next); setSidebarOpen(false); }
  async function run(action: () => Promise<void>) {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError("");
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
    remember(detail); setSelected(""); setPreview(null); setProposal(null); setPendingOpen(null); setPanel(null);
    if (!can(session, "author")) navigate("student");
    else if (view === "library" || view === "student" || view === "users") navigate("designer");
  }
  async function save(): Promise<Workflow> {
    if (!workflow || !program) throw new Error("Open a workflow first.");
    if (!isDirty(workflow, program)) return workflow;
    const detail = checkWorkflow(await request<Workflow>(`/workflows/${pathId(workflow.workflow_id)}`, "PUT", {
      expected_hash: workflow.content_hash, program,
    }));
    remember(detail); setNotice("Draft saved.");
    return detail;
  }
  function edit(next: Program) { setProgram(next); setValidation(null); }
  function requestOpen(id: string) {
    setSidebarOpen(false);
    if (id === workflow?.workflow_id) return;
    if (dirty) setPendingOpen(id); else void run(() => open(id));
  }
  function exportJson() {
    if (!program || !workflow) return;
    const blob = new Blob([JSON.stringify({ title: workflow.title, domain: workflow.domain, revision: workflow.revision, program }, null, 2)], { type: "application/json" });
    if (typeof URL.createObjectURL !== "function") return;
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${workflow.title.replace(/[^a-z0-9]+/gi, "-").toLowerCase() || "workflow"}-r${workflow.revision}.json`;
    link.click(); URL.revokeObjectURL(link.href);
  }

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

  const startPreview = (startKey?: string) => void run(async () => {
    const saved = await save();
    setPreview(checkPreview(await request<Preview>(`/workflows/${pathId(saved.workflow_id)}/simulate`, "POST", {
      expected_hash: saved.content_hash, ...(startKey ? { start_node_key: startKey } : {}),
    })));
    previewBaseHash.current = saved.content_hash;
    if (startKey) setSelected(startKey);
    navigate("student");
  });
  function guardPreview(current: Preview | null): asserts current is Preview {
    if (!current || !workflow) throw new Error("Start a synthetic preview first.");
    if (dirty || previewBaseHash.current !== workflow.content_hash) throw new Error("The draft changed. Save and restart the preview before continuing.");
  }
  function previewAction(action: "respond" | "assist" | "reveal", answer?: PreviewAnswer) {
    void run(async () => {
      guardPreview(preview);
      setPreview(checkPreview(await request<Preview>(`/previews/${pathId(preview.preview_id)}/${action}`, "POST", {
        expected_version: preview.state_version, idempotency_key: crypto.randomUUID(),
        ...(action === "respond" ? {
          current_node_key: preview.current_node.key, activity_id: preview.activity?.activity_id,
          activity_revision: preview.activity?.revision, response: answer,
        } : {}),
      })));
    });
  }
  const transition = (outcome: Outcome) => void run(async () => {
    guardPreview(preview);
    setPreview(checkPreview(await request<Preview>(`/previews/${pathId(preview.preview_id)}/transition`, "POST", {
      expected_version: preview.state_version, idempotency_key: crypto.randomUUID(), outcome,
    })));
  });
  const refreshPreview = () => void run(async () => {
    if (preview) { setPreview(checkPreview(await request<Preview>(`/previews/${pathId(preview.preview_id)}`))); setConflict(false); }
  });

  const switchRole = (role: Role) => void run(async () => {
    if (dirty) throw new Error("Save or discard the draft before switching role.");
    const value = await request<Session>("/session/role", "PUT", { role });
    if (!value.csrf_token || !value.actor) throw new Error("Invalid administrator session response.");
    api.setSession(value); setSession(value);
    setWorkflow(null); setProgram(null); setPreview(null); setProposal(null); setSelected(""); setPanel(null);
    setWorkflows([]); setStrategies([]); setWorkflowPage(0);
    const first = allowedViews(value)[0];
    if (first) navigate(first.key);
    setNotice(`Switched to the ${roleLabels[role]} role.`);
  });
  const openStep = (key: string) => { setSelected(key); setPanel({ kind: "step", key }); setSidebarOpen(false); if (view !== "designer") navigate("designer"); };
  const openRule = (index: number) => setPanel({ kind: "rule", index });
  const saveButton = <button type="button" className="sc-primary" disabled={disabled || !dirty} onClick={() => void run(async () => { await save(); })}>Save changes</button>;

  let drawer: ReactNode = null;
  if (session && panel) {
    const close = () => setPanel(null);
    if (panel.kind === "account") {
      drawer = <Drawer title="Your account" onClose={close}>
        <AccountPanel session={session} disabled={disabled} onSwitch={switchRole} onError={onError} onChanged={setNotice} />
      </Drawer>;
    } else if (panel.kind === "user") {
      drawer = <Drawer title="User" onClose={close}>
        <UserPanel key={panel.username} username={panel.username} self={panel.username === actorName(session.actor)}
          groups={manageableGroups} disabled={disabled} onError={onError}
          onChanged={message => { setNotice(message); setUsersRefresh(value => value + 1); }} />
      </Drawer>;
    } else if (panel.kind === "new-workflow") {
      drawer = <Drawer title="New workflow" onClose={close} footer={<button className="sc-primary" form="new-workflow" disabled={disabled}>Create workflow</button>}>
        <NewWorkflowPanel strategies={strategies} initial={panel.strategy} onCreate={(title, domain, strategy) => void run(async () => {
          if (dirty) throw new Error("Save or discard the current draft before creating another.");
          const created = checkWorkflow(await request<Workflow>("/workflows", "POST", { title, domain }));
          remember(created); setPreview(null); setProposal(null); setSelected("");
          if (strategy && strategy !== created.program.strategy_code) setProgram({ ...structuredClone(created.program), strategy_code: strategy });
          setPanel(null); navigate("designer"); setNotice("Workflow created.");
        })} />
      </Drawer>;
    } else if (workflow && program) {
      if (panel.kind === "step") drawer = <Drawer title="Edit step" onClose={close} footer={<>
        <button type="button" className="sc-light" disabled={disabled} onClick={() => startPreview(panel.key)}>Preview as student</button>{saveButton}</>}>
        <StepPanel key={panel.key} program={program} nodeKey={panel.key} disabled={disabled} edit={edit} onRule={openRule}
          onAddRule={() => setPanel({ kind: "new-rule", from: panel.key })} onRemoved={() => { setSelected(""); setPanel(null); }} />
      </Drawer>;
      else if (panel.kind === "rule") drawer = <Drawer title="Edit rule" onClose={close} footer={<>
        {program.edges[panel.index] && <button type="button" className="sc-light" onClick={() => openStep(program.edges[panel.index].from_key)}>Open step</button>}{saveButton}</>}>
        <RulePanel key={panel.index} program={program} index={panel.index} disabled={disabled} edit={edit} onRemoved={() => setPanel(null)} />
      </Drawer>;
      else if (panel.kind === "new-rule") drawer = <Drawer title="Add branching rule" onClose={close} footer={<button className="sc-primary" form="new-rule" disabled={disabled}>Add rule</button>}>
        <NewRulePanel program={program} from={panel.from} disabled={disabled} onAdd={edge => {
          edit({ ...program, edges: [...program.edges, edge] }); setPanel({ kind: "rule", index: program.edges.length });
        }} />
      </Drawer>;
      else if (panel.kind === "new-step") drawer = <Drawer title="New step" onClose={close} footer={<button className="sc-primary" form="new-step" disabled={disabled}>Create step</button>}>
        <NewStepPanel program={program} onAdd={node => { edit({ ...program, nodes: [...program.nodes, node] }); setSelected(node.key); setPanel({ kind: "step", key: node.key }); }} />
      </Drawer>;
      else if (panel.kind === "settings") drawer = <Drawer title="Workflow settings" onClose={close} footer={saveButton}>
        <SettingsPanel workflow={workflow} program={program} strategies={strategies} validation={validation} disabled={disabled} dirty={dirty} edit={edit}
          onSources={() => { window.location.hash = "library-sources"; setView("library"); setPanel(null); }}
          onDiscard={() => { setProgram(structuredClone(workflow.program)); setValidation(null); setNotice("Unsaved edits discarded."); }}
          onValidate={() => void run(async () => {
            const saved = await save();
            setValidation(await request<Validation>(`/workflows/${pathId(saved.workflow_id)}/validate`, "POST", { expected_hash: saved.content_hash }));
          })} />
      </Drawer>;
      else if (panel.kind === "ai") drawer = <Drawer title="Ask AI" onClose={close}>
        <Coauthor key={`proposal-${proposal?.job.job_id || workflow.workflow_id}`} program={workflow.program}
          instruction={instruction} setInstruction={setInstruction} job={proposal?.job} baseHash={proposal?.baseHash}
          stale={!!proposal && (dirty || workflow.content_hash !== proposal.baseHash || workflow.workflow_id !== proposal.workflowId)}
          disabled={disabled} polling={polling}
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
            remember(accepted); setPreview(null); setProposal(null); setNotice("Proposed rule accepted into the draft. Not published.");
          })}
          onReject={() => setProposal(null)} onResume={() => { setError(""); setPollRetry(value => value + 1); }} />
      </Drawer>;
    }
  }

  if (checking) return <main className="sc-center"><p role="status">Checking your session…</p></main>;
  if (!session) return <main className="sc-center">
    <section className="sc-login" aria-label="Sign in">
      <div className="sc-logo" aria-hidden="true">M</div>
      <h1 className="sc-hero">Socratic Studio</h1>
      <p className="sc-desc">Sign in with your staff account.</p>
      {error && <div className="sc-alert" role="alert"><MathText text={error} /></div>}
      <form className="sc-form" onSubmit={login}>
        <label>Username<input name="username" autoComplete="username" required disabled={busy} /></label>
        <label>Password<input name="password" type="password" autoComplete="current-password" required disabled={busy} /></label>
        <button className="sc-primary" disabled={busy}>Sign in</button>
      </form>
    </section>
  </main>;

  const name = actorName(session.actor);
  const author = can(session, "author");
  let canvas: ReactNode;
  if (view === "users" && can(session, "manage_users")) canvas = <Users selected={panel?.kind === "user" ? panel.username : null} refresh={usersRefresh}
    onError={onError} onOpen={(username) => setPanel({ kind: "user", username })} onGroups={setManageableGroups} />;
  else if (view === "rules") canvas = <RulesView program={program} disabled={disabled} onRule={openRule} onDescribe={() => setPanel({ kind: "ai" })} />;
  else if (view === "library") canvas = <Library strategies={strategies} program={program} domain={workflow?.domain || ""} disabled={disabled} onError={onError}
    onUseStrategy={strategy => { if (program) { edit({ ...program, strategy_code: strategy.code }); setNotice(`Strategy set to ${strategy.label}. Save to keep it.`); } }}
    onStartFrom={strategy => setPanel({ kind: "new-workflow", strategy })}
    onAttach={source => { if (program) { edit({ ...program, source }); setNotice("Source linked. Save to keep it."); navigate("designer"); } }}
    onPreview={key => startPreview(key)} />;
  else if (view === "student") canvas = <Simulator key={preview?.preview_id || "none"} title={workflow?.title || ""} preview={preview} canStart={!!workflow}
    disabled={disabled} onRestart={() => startPreview()} onRefresh={refreshPreview} onTransition={transition}
    onRespond={answer => previewAction("respond", answer)} onAssist={() => previewAction("assist")} onReveal={() => previewAction("reveal")} />;
  else if (workflow && program) canvas = <Designer title={workflow.title} program={program} representation={representation} setRepresentation={setRepresentation}
    selected={selected} preview={preview} disabled={disabled} onStep={openStep} onRule={openRule} onAddStep={() => setPanel({ kind: "new-step" })} />;
  else canvas = <div className="sc-canvas-inner"><Hero kicker="Designer" title="Choose a workflow" description="Search or pick a workflow in the sidebar, or start a new one." />
    <Empty icon="bezier2" action={<button className="sc-primary" disabled={disabled} onClick={() => setPanel({ kind: "new-workflow" })}><Icon name="plus-lg" />New workflow</button>}>
      {catalogLoading ? "Loading your drafts…" : `${workflows.length} draft${workflows.length === 1 ? "" : "s"} available.`}</Empty></div>;

  return <div className={`sc-app${sidebarOpen ? " sc-sidebar-open" : ""}`}>
    <a className="sc-skip" href="#main-content">Skip to content</a>
    <nav className="sc-rail" aria-label="Studio navigation">
      <div className="sc-logo" aria-hidden="true">M</div>
      {allowedViews(session).map(item => <a key={item.key} href={`#${item.key}`} className={view === item.key ? "sc-active" : ""} aria-label={item.label} title={item.label}
        aria-current={view === item.key ? "page" : undefined} onClick={() => navigate(item.key)}><Icon name={item.icon} /></a>)}
      <div className="sc-spacer" />
      <button type="button" className="sc-avatar" title={`${name} · ${roleLabels[session.role || "admin"]} — account`}
        aria-label={`Account: ${name}, ${roleLabels[session.role || "admin"]} role`} aria-pressed={panel?.kind === "account"}
        onClick={() => setPanel(panel?.kind === "account" ? null : { kind: "account" })}>{name.slice(0, 2).toUpperCase()}</button>
      <IconButton icon="box-arrow-right" label="Sign out" disabled={busy} onClick={() => {
        if (dirty) { setError("Save or discard the draft before signing out."); return; }
        void run(async () => { await request<void>("/session", "DELETE"); reset(); });
      }} />
    </nav>
    <Sidebar query={query} setQuery={setQuery} workflows={workflows} strategies={strategies} program={program} activeId={workflow?.workflow_id}
      loading={catalogLoading} failed={catalogFailed} page={workflowPage} hasMore={workflowsHaveMore} disabled={busy}
      onPage={setWorkflowPage} onRetry={() => setCatalogRetry(value => value + 1)} onOpen={requestOpen} onStep={openStep}
      onStrategy={strategy => { setPanel({ kind: "new-workflow", strategy }); setSidebarOpen(false); }}
      onNew={() => { setPanel({ kind: "new-workflow" }); setSidebarOpen(false); }} onExport={exportJson} author={author} />
    <div className="sc-main">
      <header className="sc-top">
        <IconButton icon="layout-sidebar" label="Toggle workspace search" className="sc-sidebar-toggle" active={sidebarOpen} onClick={() => setSidebarOpen(value => !value)} />
        <nav aria-label="Breadcrumb" className="sc-crumb"><span>Socratic Studio</span><span aria-hidden="true"> / </span>
          <strong aria-current="page">{workflow ? <MathText text={workflow.title} /> : views.find(item => item.key === view)!.label}</strong></nav>
        <div className="sc-spacer" />
        <button type="button" className="sc-role" title="Active role — click to switch or manage your account"
          aria-label={`Active role: ${roleLabels[session.role || "admin"]}. Switch role or manage your account`}
          onClick={() => setPanel({ kind: "account" })}><Pill tone={session.role === "student" ? "warning" : "primary"}>
            <Icon name={session.role === "student" ? "mortarboard" : "shield-check"} />{roleLabels[session.role || "admin"]}</Pill></button>
        {session.auth_mode === "local" && <span className="sc-local" title="Loopback-only local staff session; not a cloud identity"><Pill tone="warning">
          <span className="sc-hide-narrow">Local test session</span><span className="sc-show-narrow">Local</span></Pill></span>}
        {workflow && <Pill tone={dirty ? "warning" : "success"}>{dirty ? "Unsaved changes" : `Saved · r${workflow.revision}`}</Pill>}
        {workflow && dirty && <button type="button" className="sc-light" disabled={disabled} onClick={() => void run(async () => { await save(); })}>Save</button>}
        {workflow && author && <IconButton icon="sliders" label="Workflow settings" active={panel?.kind === "settings"} onClick={() => setPanel({ kind: "settings" })} />}
        {workflow && author && view !== "student" && <button type="button" className="sc-light sc-hide-narrow" disabled={disabled} onClick={() => navigate("student")}><Icon name="person-video3" />Student view</button>}
        {workflow && author && <button type="button" className="sc-primary" disabled={disabled} onClick={() => setPanel({ kind: "ai" })}><Icon name="stars" />Ask AI</button>}
      </header>
      {(error || conflict || pendingOpen) && <div className="sc-banners">
        {error && <div className="sc-alert" role="alert"><Icon name="exclamation-circle" /><MathText text={error} />
          <IconButton icon="x" label="Dismiss message" onClick={() => setError("")} /></div>}
        {conflict && workflow && <div className="sc-alert sc-warn">The server has a newer version.
          <button type="button" className="sc-light" disabled={busy} onClick={() => void run(async () => { await open(workflow.workflow_id); setNotice("Server draft reloaded."); })}>Discard edits & reload</button>
          {preview && <button type="button" className="sc-light" disabled={busy} onClick={refreshPreview}>Reload preview</button>}</div>}
        {pendingOpen && <div className="sc-alert sc-warn">Unsaved changes will be lost.
          <button type="button" className="sc-light sc-danger-text" disabled={busy} onClick={() => void run(() => open(pendingOpen))}>Discard & open</button>
          <button type="button" className="sc-light" onClick={() => setPendingOpen(null)}>Keep editing</button></div>}
      </div>}
      <section className="sc-workspace">
        <main id="main-content" className="sc-canvas" aria-busy={busy}>{canvas}</main>
        {drawer}
      </section>
    </div>
    {sidebarOpen && <button type="button" className="sc-scrim" aria-label="Close workspace search" onClick={() => setSidebarOpen(false)} />}
    {(notice || busy) && <div className="sc-toast" role="status">{busy ? "Working…" : notice}</div>}
  </div>;
}
