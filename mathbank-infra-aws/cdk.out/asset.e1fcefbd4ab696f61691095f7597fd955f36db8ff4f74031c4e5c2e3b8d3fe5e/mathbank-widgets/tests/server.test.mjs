import test from "node:test";
import assert from "node:assert/strict";
import { createVoiceHandlers, createFormatHandler, createLimiter } from "../src/server.mjs";
import { deterministicFormat } from "../src/format.mjs";

const URL_ = "http://localhost:5173/api/voice/tts";
const post = (body, headers = {}) => new Request(URL_, { method: "POST", headers: { "Content-Type": "application/json", origin: "http://localhost:5173", ...headers }, body: JSON.stringify(body) });

test("tts: key stays server-side, text validated, audio streamed", async () => {
  const calls = [];
  const fetchImpl = async (url, init) => { calls.push({ url, init }); return new Response("MP3", { status: 200 }); };
  const h = createVoiceHandlers({ env: { ELEVEN_API_KEY: "k-secret" }, fetchImpl });
  const res = await h.tts(post({ text: "Hello" }));
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("content-type"), "audio/mpeg");
  assert.equal(await res.text(), "MP3");
  assert.equal(calls[0].init.headers["xi-api-key"], "k-secret");
  assert.match(calls[0].url, /text-to-speech\/.+output_format=mp3/);
  assert.equal((await h.tts(post({ text: "" }))).status, 400);
  assert.equal((await h.tts(post({ text: "x".repeat(1300) }))).status, 413);
  assert.equal((await h.tts(post({ text: "hi" }, { origin: "http://evil" }))).status, 403);
});

test("tts: missing key -> 503, upstream error -> 502 without leaking body", async () => {
  assert.equal((await createVoiceHandlers({ env: {} }).tts(post({ text: "hi" }))).status, 503);
  const h = createVoiceHandlers({ env: { ELEVEN_API_KEY: "k" }, fetchImpl: async () => new Response("secret detail", { status: 401 }) });
  const res = await h.tts(post({ text: "hi" }));
  assert.equal(res.status, 502);
  assert.doesNotMatch(await res.text(), /secret detail/);
});

test("stt: multipart forwarded with scribe model; text returned", async () => {
  let sent;
  const h = createVoiceHandlers({ env: { ELEVEN_API_KEY: "k" }, fetchImpl: async (url, init) => { sent = { url, init }; return Response.json({ text: " PA times PB ", language_code: "en" }); } });
  const form = new FormData();
  form.append("file", new Blob(["abc"], { type: "audio/webm" }), "a.webm");
  const res = await h.stt(new Request("http://localhost:5173/api/voice/stt", { method: "POST", body: form }));
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { text: "PA times PB", language: "en" });
  assert.match(sent.url, /speech-to-text$/);
  assert.equal(sent.init.body.get("model_id"), "scribe_v1");
  const bad = new FormData();
  bad.append("file", new Blob(["x"], { type: "text/html" }), "x.html");
  assert.equal((await h.stt(new Request("http://localhost:5173/api/voice/stt", { method: "POST", body: bad }))).status, 415);
});

test("health never calls a paid endpoint and reports missing key", async () => {
  const urls = [];
  const h = createVoiceHandlers({ env: { ELEVEN_API_KEY: "k" }, fetchImpl: async (u) => { urls.push(u); return new Response("{}", { status: 200 }); } });
  const body = await (await h.health()).json();
  assert.equal(body.configured, true);
  assert.deepEqual(urls, ["https://api.elevenlabs.io/v1/models"]);
  assert.equal((await (await createVoiceHandlers({ env: {} }).health()).json()).configured, false);
});

test("limiter blocks after the window limit", () => {
  let t = 0;
  const lim = createLimiter({ limit: 2, windowMs: 1000, now: () => t });
  assert.deepEqual([lim("a"), lim("a"), lim("a"), lim("b")], [true, true, false, true]);
  t = 2000;
  assert.equal(lim("a"), true);
});

test("format proxy: falls back offline, forwards token otherwise", async () => {
  const anon = createFormatHandler({ getToken: async () => null, post: async () => { throw new Error("no"); }, fallback: deterministicFormat });
  const r1 = await (await anon(new Request("http://x/api/format-math", { method: "POST", body: JSON.stringify({ text: "PA*PB" }) }))).json();
  assert.equal(r1.formatted, "$PA \\cdot PB$");
  let seen;
  const authed = createFormatHandler({ getToken: async () => "tok", post: async (p, t, b) => { seen = { p, t, b }; return { formatted: "X", engine: "agentic" }; }, fallback: deterministicFormat });
  const r2 = await (await authed(new Request("http://x/api/format-math", { method: "POST", body: JSON.stringify({ text: "a", mode: "agentic" }) }))).json();
  assert.equal(r2.engine, "agentic");
  assert.deepEqual(seen, { p: "/v1/tutor/format-math", t: "tok", b: { text: "a", mode: "agentic" } });
  const failing = createFormatHandler({ getToken: async () => "tok", post: async () => { const e = new Error("x"); e.status = 503; throw e; }, fallback: deterministicFormat });
  const r3 = await (await failing(new Request("http://x/api/format-math", { method: "POST", body: JSON.stringify({ text: "a<=b" }) }))).json();
  assert.equal(r3.formatted, "$a\\le b$");
});
