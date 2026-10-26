import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/App";
import { api } from "../src/api";
import { workflow, preview, assessmentPreview } from "./fixtures";
import type { Preview, Program } from "../src/contracts";

const registry = { strategies: [{ code: "COUNTING", domain: "Counting", label: "Counting strategy", status: "DRAFT", phases: ["Discover", "Transfer"] }] };
type Call = { path: string; method: string; body?: Record<string, unknown> };
let calls: Call[];
let detail = structuredClone(workflow);
let conflictOnSave = false;
let resourceQuery = "";
let currentPreview: Preview;
let failRespond = false;
let localAuth = false;
const resource = {
  canonical_code: "SOURCE_1", problem_id: "problem-1", statement_text: "Find \\(x\\).",
  solutions: [{ solution_id: "solution-1", revision: 3, verification_status: "VERIFIED" }],
  routes: [{ route_release_id: "route-1", status: "PUBLISHED", approach_name: "Reviewed construction" }],
};

beforeEach(() => {
  calls = []; detail = structuredClone(workflow); conflictOnSave = false; resourceQuery = "";
  currentPreview = structuredClone(preview); failRespond = false; localAuth = false;
  window.location.hash = "";
  api.setSession(null);
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const path = url.replace("/v1/admin/socratic", "");
    const method = init?.method || "GET";
    const body = typeof init?.body === "string" ? JSON.parse(init.body) as Record<string, unknown> : undefined;
    calls.push({ path, method, body });
    let result: unknown;
    if (path === "/session") result = { actor: "Author", csrf_token: "csrf", auth_mode: localAuth ? "local" : "cognito" };
    else if (path === "/strategies") result = registry;
    else if (path.startsWith("/workflows?")) result = { workflows: [detail], has_more: false };
    else if (path === "/workflows/workflow-1" && method === "PUT") {
      if (conflictOnSave) return new Response(JSON.stringify({ message: "stale" }), { status: 409 });
      detail = { ...detail, program: body!.program as Program, content_hash: "hash-2", revision: 2 };
      result = detail;
    } else if (path === "/workflows/workflow-1") result = detail;
    else if (path === "/workflows/workflow-1/simulate") result = currentPreview;
    else if (path === "/workflows/workflow-1/proposals") result = { job_id: "job-1", status: "QUEUED", execution_arn: "execution" };
    else if (path === "/jobs/job-1") result = {
      job_id: "job-1", status: "SUCCEEDED", error: null,
      result: { from_key: "start", to_key: "complete", outcome: "RETRY", priority: 1, explanation: "Use the transfer branch.", model_id: "test-model" },
    };
    else if (path === "/workflows/workflow-1/proposals/job-1/accept") {
      detail = { ...detail, content_hash: "hash-accepted", revision: 3 };
      result = detail;
    } else if (path.startsWith("/resources?")) { resourceQuery = path; result = { resources: [resource], has_more: true }; }
    else if (path === "/previews/preview-1/transition" || path === "/previews/preview-1/respond") {
      if (failRespond) return new Response(JSON.stringify({ message: "Evaluator unavailable; response not graded." }), { status: 503 });
      currentPreview = { ...preview, state_version: 1, current_node: workflow.program.nodes[1], feedback: "Review the bijection.",
        history: [{ node_key: "remediate", from_key: "start", to_key: "remediate", outcome: "RETRY", decision_source: "DETERMINISTIC", reason: "Synthetic retry" }] };
      result = currentPreview;
    }
    else if (path === "/previews/preview-1/assist" || path === "/previews/preview-1/reveal") {
      currentPreview = { ...currentPreview, state_version: currentPreview.state_version + 1,
        help: { level: path.endsWith("/reveal") ? 5 : 1, text: "Check whether the representation is reversible.", assisted: true } };
      result = currentPreview;
    }
    else throw new Error(`Unexpected request ${method} ${path}`);
    return new Response(JSON.stringify(result), { status: 200, headers: { "Content-Type": "application/json" } });
  }));
});

async function openDraft() {
  render(<App />);
  await userEvent.click(await screen.findByRole("button", { name: /Discovery draft/ }));
  await screen.findByRole("group", { name: "Workflow steps" });
}
async function openStep(name: RegExp) {
  await userEvent.click(within(screen.getByRole("group", { name: "Workflow steps" })).getByRole("button", { name }));
  return screen.findByRole("complementary", { name: "Edit step" });
}
async function startPreview() {
  await userEvent.click(screen.getByRole("button", { name: /Student view/ }));
  await userEvent.click(screen.getByRole("button", { name: /Save & start preview/ }));
  return screen.findByRole("region", { name: "Synthetic simulator" });
}
const promptField = () => screen.getByLabelText("Student-facing question or content");

describe("clean studio shell", () => {
  it("labels explicitly local staff sessions without implying cloud approval", async () => {
    localAuth = true;
    render(<App />);
    expect(await screen.findByText("Local test session")).toBeInTheDocument();
  });
  it("searches drafts and steps from the sidebar search module", async () => {
    await openDraft();
    const search = screen.getByRole("searchbox", { name: "Search workspace" });
    await userEvent.type(search, "smaller example");
    const sidebar = screen.getByRole("complementary", { name: "Workspace search" });
    expect(within(sidebar).getByText("Steps in this workflow")).toBeInTheDocument();
    await userEvent.click(within(sidebar).getByRole("button", { name: /Revisit/ }));
    expect(await screen.findByRole("complementary", { name: "Edit step" })).toBeInTheDocument();
    expect(promptField()).toHaveValue("Try a smaller example.");
    await userEvent.clear(search);
    await userEvent.type(search, "no such workflow");
    expect(within(sidebar).getByText("No matching workflows.")).toBeInTheDocument();
  });
  it("closes the detail drawer with Escape without discarding edits", async () => {
    await openDraft();
    await openStep(/Explore/);
    fireEvent.change(promptField(), { target: { value: "Edited" } });
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("complementary", { name: "Edit step" })).not.toBeInTheDocument());
    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
  });
  it("shows the flow as plain language or JSON without changing it", async () => {
    await openDraft();
    await userEvent.click(screen.getByRole("button", { name: /Natural language/ }));
    const story = screen.getByRole("article", { name: "Natural-language flow" });
    expect(story).toHaveTextContent("The journey starts at Explore");
    expect(story).toHaveTextContent("If the student needs another attempt, go to Revisit.");
    await userEvent.click(screen.getByRole("button", { name: "JSON" }));
    const json = screen.getByRole("region", { name: "JSON flow" });
    expect(json).toHaveTextContent('"schema_version": "socratic.prototype.v1"');
    expect(screen.queryByText("Unsaved changes")).not.toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });
});

describe("draft authoring and synthetic preview", () => {
  it("keeps keyboard step selection independent of the synthetic position", async () => {
    await openDraft();
    const simulator = await startPreview();
    expect(simulator).toHaveTextContent("Explore");
    await userEvent.click(screen.getByRole("link", { name: "Workflow designer" }));
    const steps = screen.getByRole("group", { name: "Workflow steps" });
    const first = within(steps).getAllByRole("button", { pressed: false })[0];
    first.focus();
    fireEvent.keyDown(first, { key: "ArrowDown" });
    expect(await screen.findByRole("complementary", { name: "Edit step" })).toBeInTheDocument();
    expect(promptField()).toHaveValue("Try a smaller example.");
    expect(within(steps).getByText("Student here").closest("button")).toHaveTextContent("Explore");
    await userEvent.click(screen.getByRole("link", { name: "Student simulator" }));
    await userEvent.click(screen.getByText("Test routing"));
    await userEvent.click(screen.getByRole("button", { name: "Simulate RETRY" }));
    await screen.findByRole("heading", { level: 1, name: "Revisit" });
    const transition = calls.find(call => call.path.endsWith("/transition"));
    expect(transition?.body).toMatchObject({ expected_version: 0, outcome: "RETRY" });
    expect(transition?.body?.idempotency_key).toEqual(expect.any(String));
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });
  it("saves edits before simulation and never invents grade fields", async () => {
    await openDraft();
    await openStep(/Explore/);
    fireEvent.change(promptField(), { target: { value: "New \\(x\\) prompt" } });
    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
    await startPreview();
    const putIndex = calls.findIndex(call => call.method === "PUT");
    const simulateIndex = calls.findIndex(call => call.path.endsWith("/simulate"));
    expect(putIndex).toBeGreaterThan(-1);
    expect(simulateIndex).toBeGreaterThan(putIndex);
    expect(calls[simulateIndex].body).toEqual({ expected_hash: "hash-2" });
    expect(JSON.stringify(calls)).not.toMatch(/correct_key|score|answer_key/);
  });
  it("requires an explicit click after showing the proposed rule", async () => {
    await openDraft();
    await openStep(/Explore/);
    fireEvent.change(promptField(), { target: { value: "Updated prompt" } });
    await userEvent.click(screen.getByRole("button", { name: /Ask AI/ }));
    fireEvent.change(screen.getByLabelText("Rule instruction"), { target: { value: "Send a retry to complete" } });
    await userEvent.click(screen.getByRole("button", { name: /Propose rule/ }));
    await screen.findByLabelText("Proposed edge comparison");
    expect(calls.findIndex(call => call.method === "PUT")).toBeLessThan(calls.findIndex(call => call.path.endsWith("/proposals")));
    expect(calls.some(call => call.path.endsWith("/accept"))).toBe(false);
    expect(screen.getByText("If the student needs another attempt, go to Finish.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Accept into draft" }));
    await waitFor(() => expect(calls.some(call => call.path.endsWith("/accept"))).toBe(true));
    expect(calls.find(call => call.path.endsWith("/accept"))?.body).toEqual({ expected_hash: "hash-2" });
  });
  it("supports editing a proposal before explicit server acceptance", async () => {
    await openDraft();
    await userEvent.click(screen.getByRole("button", { name: /Ask AI/ }));
    fireEvent.change(screen.getByLabelText("Rule instruction"), { target: { value: "Retry the representation" } });
    await userEvent.click(screen.getByRole("button", { name: /Propose rule/ }));
    await userEvent.click(await screen.findByText("Compare and adjust"));
    await userEvent.selectOptions(screen.getByLabelText("Proposed destination"), "remediate");
    expect(calls.some(call => call.path.endsWith("/accept"))).toBe(false);
    await userEvent.click(screen.getByRole("button", { name: "Accept into draft" }));
    await waitFor(() => expect(calls.some(call => call.path.endsWith("/accept"))).toBe(true));
    expect(calls.find(call => call.path.endsWith("/accept"))?.body).toEqual({
      expected_hash: "hash-1", candidate: { from_key: "start", to_key: "remediate", outcome: "RETRY", priority: 1 },
    });
  });
  it("blocks auto-retry after a stale save and offers explicit reload", async () => {
    await openDraft();
    conflictOnSave = true;
    await openStep(/Explore/);
    fireEvent.change(promptField(), { target: { value: "Conflicting edit" } });
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await screen.findByRole("alert");
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
    expect(promptField()).toHaveValue("Conflicting edit");
    await userEvent.click(screen.getByRole("button", { name: "Discard edits & reload" }));
    await waitFor(() => expect(screen.queryByText("Unsaved changes")).not.toBeInTheDocument());
    await openStep(/Explore/);
    expect(promptField()).toHaveValue(workflow.program.nodes[0].prompt);
    expect(calls.filter(call => call.method === "PUT")).toHaveLength(1);
  });
  it("links a source with an explicitly chosen solution revision", async () => {
    await openDraft();
    await userEvent.click(screen.getByRole("button", { name: "Workflow settings" }));
    await userEvent.click(screen.getByRole("button", { name: /Choose source/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Select source SOURCE_1" }));
    expect(screen.getByRole("button", { name: "Use in current draft" })).toBeDisabled();
    await userEvent.selectOptions(screen.getByLabelText("Reference solution revision"), "solution-1");
    await userEvent.selectOptions(screen.getByLabelText("Released route (optional)"), "route-1");
    await userEvent.click(screen.getByRole("button", { name: "Use in current draft" }));
    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(calls.some(call => call.method === "PUT")).toBe(true));
    expect((calls.find(call => call.method === "PUT")?.body?.program as Program).source).toEqual({
      problem_code: "SOURCE_1", solution_id: "solution-1", solution_revision: 3, route_release_id: "route-1",
    });
    expect(resourceQuery).toContain("limit=25&offset=0");
  });
  it("renders paginated drafts and never exposes more than 25 rows", async () => {
    const original = globalThis.fetch;
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (url.includes("/workflows?")) {
        const offset = Number(new URL(url, "http://localhost").searchParams.get("offset"));
        return new Response(JSON.stringify({
          workflows: Array.from({ length: offset === 0 ? 25 : 1 }, (_, index) => ({
            ...workflow, workflow_id: `workflow-${offset + index}`, title: `Draft ${offset + index}`,
          })), has_more: offset === 0,
        }));
      }
      return original(url, init);
    }));
    render(<App />);
    await screen.findByRole("button", { name: /Draft 0/ });
    expect(screen.getAllByRole("button", { name: /^Draft / })).toHaveLength(25);
    await userEvent.click(screen.getByRole("button", { name: "Next page" }));
    await screen.findByRole("button", { name: /Draft 25/ });
    expect(screen.getAllByRole("button", { name: /^Draft / })).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Previous page" }));
    await screen.findByRole("button", { name: /Draft 0/ });
  });
  it("edits a rule's plain-language description from the flow and the rules list", async () => {
    await openDraft();
    await userEvent.click(screen.getByRole("button", { name: "If the student needs another attempt, go to Revisit." }));
    const drawer = await screen.findByRole("complementary", { name: "Edit rule" });
    fireEvent.change(within(drawer).getByLabelText("Describe what should happen"), { target: { value: "Revisit the bijection before transfer." } });
    await userEvent.click(screen.getByRole("link", { name: "Rules by topic" }));
    await userEvent.click(screen.getByRole("button", { name: /Revisit the bijection before transfer/ }));
    expect(screen.getByLabelText("Describe what should happen")).toHaveValue("Revisit the bijection before transfer.");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(calls.some(call => call.method === "PUT")).toBe(true));
    expect((calls.find(call => call.method === "PUT")?.body?.program as Program).edges[0].annotation).toBe("Revisit the bijection before transfer.");
  });
  it("adds a step and a branching rule through the detail drawer", async () => {
    await openDraft();
    await userEvent.click(screen.getByRole("button", { name: /Add step/ }));
    fireEvent.change(screen.getByLabelText("Step title"), { target: { value: "Bijection lesson" } });
    await userEvent.click(screen.getByRole("button", { name: "Create step" }));
    expect(await screen.findByRole("complementary", { name: "Edit step" })).toHaveTextContent("bijection-lesson");
    await userEvent.click(screen.getByRole("button", { name: /Add branching rule/ }));
    await userEvent.selectOptions(screen.getByLabelText("Go to"), "complete");
    await userEvent.click(screen.getByRole("button", { name: "Add rule" }));
    expect(await screen.findByRole("complementary", { name: "Edit rule" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(calls.some(call => call.method === "PUT")).toBe(true));
    const saved = calls.find(call => call.method === "PUT")?.body?.program as Program;
    expect(saved.nodes.at(-1)).toMatchObject({ key: "bijection-lesson", label: "Bijection lesson", type: "DISCOVERY" });
    expect(saved.edges.at(-1)).toMatchObject({ from_key: "bijection-lesson", to_key: "complete", outcome: "SUCCESS" });
  });
  it("renders all five assertion–reason answers and routes only after a server response", async () => {
    currentPreview = structuredClone(assessmentPreview);
    await openDraft();
    await startPreview();
    expect(await screen.findAllByRole("radio")).toHaveLength(5);
    expect(screen.getByLabelText("Activity question")).toHaveTextContent("Judge the assertion and the reason separately.");
    expect(screen.getByRole("button", { name: "Submit answer" })).toBeDisabled();
    await userEvent.click(screen.getByRole("radio", { name: /Both false/ }));
    await userEvent.click(screen.getByRole("button", { name: "Submit answer" }));
    await screen.findByText("Review the bijection.");
    const sent = calls.find(call => call.path.endsWith("/respond"))?.body;
    expect(sent).toMatchObject({ current_node_key: "start", activity_id: "approved-ar", activity_revision: "1", response: { selected_keys: ["AR5"] }, expected_version: 0 });
    expect(sent).not.toHaveProperty("outcome");
    expect(sent).not.toHaveProperty("score");
    expect(screen.getByRole("region", { name: "Latest routing decision" })).toHaveTextContent("DETERMINISTIC");
    await userEvent.click(screen.getByRole("link", { name: "Workflow designer" }));
    expect(screen.getByRole("button", { name: /If the student needs another attempt, go to Revisit/ })).toHaveClass("sc-live");
  });
  it("requests server hints, hides/shows them, and requires confirmation for reveal", async () => {
    currentPreview = structuredClone(assessmentPreview);
    await openDraft();
    await startPreview();
    await userEvent.click(await screen.findByRole("button", { name: /Hint/ }));
    await screen.findByLabelText("Current hint");
    await userEvent.click(screen.getByRole("button", { name: "Hide hint" }));
    expect(screen.queryByLabelText("Current hint")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Show hint" }));
    expect(screen.getByLabelText("Current hint")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Reveal explanation…" }));
    expect(calls.some(call => call.path.endsWith("/reveal"))).toBe(false);
    await userEvent.click(screen.getByRole("button", { name: "Confirm reveal" }));
    await screen.findByText("Hint 5");
    expect(calls.find(call => call.path.endsWith("/reveal"))?.body).toMatchObject({ expected_version: 1 });
  });
  it("never fabricates a grade or moves the session when evaluation fails", async () => {
    currentPreview = structuredClone(assessmentPreview); failRespond = true;
    await openDraft();
    await startPreview();
    await userEvent.click(await screen.findByRole("radio", { name: /Both false/ }));
    await userEvent.click(screen.getByRole("button", { name: "Submit answer" }));
    await screen.findByRole("alert");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Stars and Bars");
    expect(screen.queryByText("Review the bijection.")).not.toBeInTheDocument();
    expect(calls.filter(call => call.path.endsWith("/respond"))).toHaveLength(1);
  });
  it("keeps written thinking while a hint changes the current state version", async () => {
    currentPreview = { ...structuredClone(assessmentPreview), activity: { activity_id: "free-form", revision: "1", kind: "FREE_FORM_REASONING" } };
    await openDraft();
    await startPreview();
    fireEvent.change(await screen.findByLabelText("Your thinking"), { target: { value: "A distribution determines one string." } });
    await userEvent.click(screen.getByRole("button", { name: /Hint/ }));
    await screen.findByLabelText("Current hint");
    expect(screen.getByLabelText("Your thinking")).toHaveValue("A distribution determines one string.");
    await userEvent.click(screen.getByRole("button", { name: "Submit thinking" }));
    await waitFor(() => expect(calls.some(call => call.path.endsWith("/respond"))).toBe(true));
    expect(calls.find(call => call.path.endsWith("/respond"))?.body).toMatchObject({
      expected_version: 1, response: { text: "A distribution determines one string." },
    });
  });
  it("creates a separate server preview from a library step", async () => {
    await openDraft();
    await userEvent.click(screen.getByRole("link", { name: "Templates & sources" }));
    await userEvent.click(screen.getByRole("button", { name: /Steps/ }));
    await userEvent.click(screen.getByRole("button", { name: "View in simulator · Revisit" }));
    await screen.findByRole("region", { name: "Synthetic simulator" });
    expect(calls.find(call => call.path.endsWith("/simulate"))?.body).toEqual({ expected_hash: "hash-1", start_node_key: "remediate" });
  });
  it("refuses transitions after saving changes to a running preview's base", async () => {
    await openDraft();
    await startPreview();
    await userEvent.click(screen.getByRole("link", { name: "Workflow designer" }));
    await openStep(/Explore/);
    fireEvent.change(promptField(), { target: { value: "Changed instruction" } });
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await screen.findByText("Draft saved.");
    await userEvent.click(screen.getByRole("link", { name: "Student simulator" }));
    await userEvent.click(screen.getByText("Test routing"));
    await userEvent.click(screen.getByRole("button", { name: "Simulate RETRY" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("restart");
    expect(calls.some(call => call.path.endsWith("/transition"))).toBe(false);
  });
});
