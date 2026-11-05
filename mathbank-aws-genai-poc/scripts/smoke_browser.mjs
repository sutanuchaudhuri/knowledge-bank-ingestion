/*
 * Paid end-to-end smoke test: real Chromium page -> WebSocket -> BidiAgent -> Nova Sonic -> S3 Vectors.
 *
 * Chromium's fake microphone plays a synthesized spoken question once (``%noloop``), followed by silence so Nova Sonic
 * detects the end of the turn. Evidence (non-audio events, transcripts, audio chunk count) is written to
 * ``.runtime/smoke-<UTC>.json``. Requires the server to be running (``make start``) and costs at most one session.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const project = resolve(here, "..");
const playwrightPath = process.env.PLAYWRIGHT_MODULE
  || resolve(project, "..", "mathbank-socratic-admin", "node_modules", "playwright", "index.mjs");
const { chromium } = await import(pathToFileURL(playwrightPath).href);

const [wav] = process.argv.slice(2);
const url = process.env.SMOKE_URL || "http://127.0.0.1:8040/";
const maxWaitMs = Number(process.env.SMOKE_WAIT_MS || 70_000);
if (!wav) throw new Error("usage: node scripts/smoke_browser.mjs <question.wav>");

const health = await fetch(new URL("/health", url)).then((r) => r.json());
if (health.budget_remaining_s < 30) throw new Error(`Refusing: only ${health.budget_remaining_s}s of POC budget left`);

const browser = await chromium.launch({
  args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
    `--use-file-for-fake-audio-capture=${resolve(wav)}%noloop`, "--autoplay-policy=no-user-gesture-required"],
});
const started = Date.now();
let evidence;
try {
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(url);
  await page.getByRole("button", { name: "Start talking" }).click();
  // Done when the tutor has spoken after a grounded search, or when the server ends the session.
  await page.waitForFunction(() => {
    const t = window.__tutor;
    const spoke = t.events.some((e) => e.type === "transcript" && e.role === "assistant" && (e.delta || e.text));
    const searched = t.events.some((e) => e.type === "sources");
    const responded = t.events.filter((e) => e.type === "status" && e.state === "listening").length > 0;
    return t.ended || (spoke && searched && responded && t.audioChunks > 0);
  }, null, { timeout: maxWaitMs, polling: 500 }).catch(() => {});
  if (!(await page.evaluate(() => window.__tutor.ended))) {
    await page.getByRole("button", { name: "End session" }).click().catch(() => {});
    await page.waitForFunction(() => window.__tutor.ended, null, { timeout: 15_000 }).catch(() => {});
  }
  const state = await page.evaluate(() => window.__tutor);
  const lines = await page.locator("#transcript li").allInnerTexts();
  evidence = {
    url, model: health.model, at: new Date().toISOString(), wall_seconds: (Date.now() - started) / 1000,
    audio_chunks_received: state.audioChunks, ended: state.ended, page_errors: errors, transcript: lines,
    events: state.events.filter((e) => e.type !== "transcript"),
  };
} finally {
  await browser.close();
}

const out = resolve(project, ".runtime", `smoke-${new Date().toISOString().replace(/[:.]/g, "-")}.json`);
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, JSON.stringify(evidence, null, 2));
const ok = evidence.audio_chunks_received > 0
  && evidence.events.some((e) => e.type === "sources" && e.grounded)
  && evidence.transcript.some((l) => l.startsWith("TUTOR"))
  && evidence.page_errors.length === 0;
console.log(JSON.stringify({ ok, evidence: out, audio_chunks: evidence.audio_chunks_received,
  ended: evidence.ended, transcript: evidence.transcript }, null, 2));
process.exit(ok ? 0 : 1);
