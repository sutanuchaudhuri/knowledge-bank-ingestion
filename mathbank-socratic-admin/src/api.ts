import type { Job, Preview, Session, Workflow } from "./contracts";

const base = "/v1/admin/socratic";
export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); this.name = "ApiError"; }
}
export class Api {
  private csrf: string | null = null;
  private pendingWrites = new Map<string, string>();
  setSession(session: Session | null) {
    const next = session?.csrf_token || null;
    if (next !== this.csrf) this.pendingWrites.clear();
    this.csrf = next;
  }
  async request<T>(path: string, options: { method?: string; body?: unknown; signal?: AbortSignal } = {}): Promise<T> {
    const method = options.method || "GET";
    const mutation = method !== "GET";
    const login = path === "/session" && method === "POST";
    if (mutation && !login && !this.csrf) throw new ApiError(401, "Session expired. Sign in again.");
    const bodyText = options.body !== undefined ? JSON.stringify(options.body) : undefined;
    const durableWrite = (path === "/workflows" && method === "POST")
      || (/^\/workflows\/[^/]+$/.test(path) && method === "PUT");
    const receipt = durableWrite ? JSON.stringify([method, path, bodyText]) : null;
    let key = receipt ? this.pendingWrites.get(receipt) : undefined;
    if (receipt && !key) {
      if (this.pendingWrites.size >= 10) throw new Error("Too many unconfirmed saves. Retry an unchanged request or reload and inspect server drafts before continuing.");
      key = crypto.randomUUID();
      this.pendingWrites.set(receipt, key);
    }
    const response = await fetch(`${base}${path}`, {
      method, credentials: "include", cache: "no-store",
      signal: options.signal ? AbortSignal.any([options.signal, AbortSignal.timeout(30_000)]) : AbortSignal.timeout(30_000),
      headers: {
        Accept: "application/json",
        ...(options.body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(mutation && !login ? { "X-CSRF-Token": this.csrf! } : {}),
        ...(key ? { "Idempotency-Key": key } : {}),
      },
      ...(bodyText !== undefined ? { body: bodyText } : {}),
    });
    if (!response.ok) {
      if (receipt && response.status < 500) this.pendingWrites.delete(receipt);
      const body = await response.json().catch(() => null);
      const message = body?.message || body?.detail?.message || (typeof body?.detail === "string" ? body.detail : null);
      throw new ApiError(response.status, response.status === 409
        ? "This draft or preview changed on the server. Reload its current version before continuing."
        : message || `Request failed (${response.status}). No changes have been assumed.`);
    }
    if (response.status === 204) return undefined as T;
    const result = await response.json() as T;
    if (receipt) this.pendingWrites.delete(receipt);
    return result;
  }
}
export const api = new Api();
export const pathId = (id: string) => encodeURIComponent(id);

export function checkWorkflow(workflow: Workflow): Workflow {
  if (workflow.prototype_only !== true || workflow.program?.schema_version !== "socratic.prototype.v1"
    || !Array.isArray(workflow.program.nodes) || !Array.isArray(workflow.program.edges)
    || !workflow.content_hash || !workflow.program.source) {
    throw new Error("Unsupported workflow response. The Studio only edits prototype drafts.");
  }
  return workflow;
}
export function checkPreview(preview: Preview): Preview {
  if (preview.synthetic !== true || !preview.current_node || !Number.isInteger(preview.state_version)
    || !["ACTIVE", "COMPLETE"].includes(preview.status) || !Array.isArray(preview.history)) {
    throw new Error("Refused non-synthetic or malformed preview response.");
  }
  const activity = preview.activity;
  if (activity) {
    if (!activity.activity_id || !activity.revision || !["SINGLE_CHOICE", "MULTI_SELECT", "ASSERTION_REASON", "FREE_FORM_REASONING", "NUMERIC_EXACT"].includes(activity.kind)) {
      throw new Error("Unsupported current activity contract. No answer was submitted.");
    }
    if (["SINGLE_CHOICE", "MULTI_SELECT", "ASSERTION_REASON"].includes(activity.kind)) {
      const options = activity.options;
      if (!Array.isArray(options) || options.length < 2 || options.some(option => !option.key || typeof option.text !== "string")
        || new Set(options.map(option => option.key)).size !== options.length || (activity.kind === "ASSERTION_REASON" && options.length !== 5)) {
        throw new Error("Malformed choice options. No answer was submitted.");
      }
    }
  }
  if (preview.help && (!Number.isInteger(preview.help.level) || preview.help.level < 1 || preview.help.level > 5 || preview.help.assisted !== true || typeof preview.help.text !== "string")) {
    throw new Error("Invalid current-node help contract.");
  }
  return preview;
}
function pause(milliseconds: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const abort = () => { clearTimeout(timer); reject(new DOMException("Aborted", "AbortError")); };
    const timer = setTimeout(() => { signal.removeEventListener("abort", abort); resolve(); }, milliseconds);
    if (signal.aborted) abort();
    else signal.addEventListener("abort", abort, { once: true });
  });
}
export async function pollJob(
  client: Api, id: string, signal: AbortSignal, onUpdate: (job: Job) => void,
  attempts = 60, interval = 2000,
): Promise<Job> {
  const boundedSignal = AbortSignal.any([signal, AbortSignal.timeout(150_000)]);
  for (let index = 0; index < attempts; index++) {
    boundedSignal.throwIfAborted();
    const job = await client.request<Job>(`/jobs/${pathId(id)}`, { signal: boundedSignal });
    onUpdate(job);
    if (job.status === "SUCCEEDED" || job.status === "FAILED") return job;
    if (job.status !== "QUEUED" && job.status !== "RUNNING") throw new Error("Unsupported proposal job status.");
    if (index < attempts - 1) await pause(interval, boundedSignal);
  }
  throw new Error("Proposal polling paused after its time limit. Check status to resume; no patch was applied.");
}
