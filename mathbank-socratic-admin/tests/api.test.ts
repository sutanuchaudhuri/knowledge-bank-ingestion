import { describe, expect, it, vi } from "vitest";
import { Api, ApiError, checkPreview, checkWorkflow, pollJob } from "../src/api";
import { preview, workflow, assessmentPreview } from "./fixtures";
import { isDirty, priorEdges } from "../src/contracts";
import type { Job } from "../src/contracts";

describe("same-origin cookie and CSRF boundary", () => {
  it("never sends credentials to an alternate host and keeps CSRF in memory", async () => {
    const fetcher = vi.fn().mockImplementation(async () => new Response(JSON.stringify({ ok: true })));
    vi.stubGlobal("fetch", fetcher);
    const client = new Api();
    await client.request("/session", { method: "POST", body: { username: "admin", password: "password" } });
    expect(fetcher.mock.calls[0][0]).toBe("/v1/admin/socratic/session");
    expect(fetcher.mock.calls[0][1].credentials).toBe("include");
    expect(fetcher.mock.calls[0][1].headers).not.toHaveProperty("X-CSRF-Token");
    client.setSession({ actor: "admin", csrf_token: "memory-only-token" });
    await client.request("/workflows", { method: "POST", body: { title: "Draft", domain: "Counting" } });
    expect(fetcher.mock.calls[1][1].headers["X-CSRF-Token"]).toBe("memory-only-token");
    await client.request("/session", { method: "DELETE" });
    expect(fetcher.mock.calls[2][1].headers["X-CSRF-Token"]).toBe("memory-only-token");
    client.setSession(null);
    await expect(client.request("/workflows", { method: "POST" })).rejects.toMatchObject({ status: 401 });
    expect(fetcher).toHaveBeenCalledTimes(3);
  });
  it("surfaces stale-hash conflicts and dependency failures without mock fallback", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status: 409 })));
    await expect(new Api().request("/workflows")).rejects.toMatchObject({ status: 409, message: expect.stringContaining("Reload") });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("Unavailable", { status: 503 })));
    await expect(new Api().request("/strategies")).rejects.toBeInstanceOf(ApiError);
  });
  it("reuses a draft receipt after an unknown network outcome, not after success or logout", async () => {
    const fetcher = vi.fn().mockRejectedValueOnce(new TypeError("Connection lost"))
      .mockImplementation(async () => new Response('{"ok":true}'));
    vi.stubGlobal("fetch", fetcher);
    const client = new Api();
    client.setSession({ actor: "author", csrf_token: "csrf" });
    const options = { method: "POST", body: { title: "Synthetic receipt", domain: "Algebra" } };
    await expect(client.request("/workflows", options)).rejects.toThrow("Connection lost");
    await client.request("/workflows", options);
    const first = fetcher.mock.calls[0][1].headers["Idempotency-Key"];
    expect(fetcher.mock.calls[1][1].headers["Idempotency-Key"]).toBe(first);
    await client.request("/workflows", options);
    expect(fetcher.mock.calls[2][1].headers["Idempotency-Key"]).not.toBe(first);
    fetcher.mockRejectedValueOnce(new TypeError("Connection lost"));
    await expect(client.request("/workflows", options)).rejects.toThrow();
    client.setSession(null);
    client.setSession({ actor: "other author", csrf_token: "other-csrf" });
    await client.request("/workflows", options);
    expect(fetcher.mock.calls[4][1].headers["Idempotency-Key"]).not.toBe(fetcher.mock.calls[3][1].headers["Idempotency-Key"]);
  });
  it("refuses a production workflow or non-synthetic preview", () => {
    expect(checkWorkflow(workflow)).toBe(workflow);
    expect(() => checkWorkflow({ ...workflow, prototype_only: false } as unknown as typeof workflow)).toThrow("prototype");
    expect(() => checkPreview({ ...preview, synthetic: false } as unknown as typeof preview)).toThrow("non-synthetic");
  });
  it("does not mutate the saved program and compares matching typed edges", () => {
    const copy = structuredClone(workflow.program);
    copy.nodes[0].prompt = "Changed";
    expect(isDirty(workflow, copy)).toBe(true);
    expect(isDirty(workflow, workflow.program)).toBe(false);
    expect(priorEdges(workflow.program, { from_key: "start", to_key: "complete", outcome: "RETRY", priority: 1 })).toEqual(workflow.program.edges);
  });
  it("rejects incomplete AR choice payloads, duplicate keys and unassisted help", () => {
    expect(checkPreview(assessmentPreview)).toBe(assessmentPreview);
    expect(() => checkPreview({ ...assessmentPreview, activity: { ...assessmentPreview.activity!, options: assessmentPreview.activity!.options!.slice(0, 4) } })).toThrow("choice");
    expect(() => checkPreview({ ...assessmentPreview, activity: { ...assessmentPreview.activity!, options: Array(5).fill({ key: "a", text: "Duplicate" }) } })).toThrow("choice");
    expect(() => checkPreview({ ...preview, help: { level: 5, text: "Reveal", assisted: false } })).toThrow("help");
  });
});

describe("bounded proposal polling", () => {
  const job: Job = { job_id: "job-1", status: "RUNNING", result: null, error: null };
  it("only continues queued/running jobs and stops at success", async () => {
    const client = new Api();
    const request = vi.spyOn(client, "request").mockResolvedValueOnce(job).mockResolvedValueOnce({ ...job, status: "SUCCEEDED" });
    const update = vi.fn();
    await pollJob(client, "job-1", new AbortController().signal, update, 3, 0);
    expect(request).toHaveBeenCalledTimes(2);
    expect(update).toHaveBeenCalledTimes(2);
  });
  it("stops on failure, bounds running jobs, and aborts on unmount", async () => {
    const client = new Api();
    const request = vi.spyOn(client, "request").mockResolvedValue({ ...job, status: "FAILED", error: "Dependency unavailable" });
    await expect(pollJob(client, "job-1", new AbortController().signal, vi.fn(), 3, 0)).resolves.toMatchObject({ status: "FAILED" });
    expect(request).toHaveBeenCalledTimes(1);
    request.mockResolvedValue(job);
    await expect(pollJob(client, "job-1", new AbortController().signal, vi.fn(), 2, 0)).rejects.toThrow("time limit");
    expect(request).toHaveBeenCalledTimes(3);
    const controller = new AbortController();
    controller.abort();
    await expect(pollJob(client, "job-1", controller.signal, vi.fn())).rejects.toMatchObject({ name: "AbortError" });
    expect(request).toHaveBeenCalledTimes(3);
  });
});
