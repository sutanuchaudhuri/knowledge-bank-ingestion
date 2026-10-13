// Server-only voice + format proxies shared by mathbank-web and mathbank-live (requirements 29).
// Pure factories (fetch is injected) so node tests can exercise them without network or keys.
// The ElevenLabs key is read server-side from ELEVEN_API_KEY and never returned to the browser.

export const ELEVEN_API = "https://api.elevenlabs.io";
export const TTS_MAX_CHARS = 1200;
export const STT_MAX_BYTES = 10 * 1024 * 1024;
const DEFAULT_VOICE = "JBFqnCBsd6RMkjVDRZzb";

const json = (body, status = 200) => Response.json(body, { status });

/** Very small fixed-window rate limiter keyed by caller (cookie/ip). */
export function createLimiter({ limit = 30, windowMs = 60_000, now = () => Date.now() } = {}) {
  const hits = new Map();
  return (key) => {
    const t = now();
    const entry = hits.get(key);
    if (!entry || t - entry.start > windowMs) { hits.set(key, { start: t, n: 1 }); return true; }
    entry.n += 1;
    return entry.n <= limit;
  };
}

export function callerKey(request) {
  const cookie = request.headers.get("cookie") || "";
  const tok = /mb_(?:student|live)_token=([^;]+)/.exec(cookie)?.[1];
  return tok ? `t:${tok.slice(-24)}` : `ip:${request.headers.get("x-forwarded-for") || "local"}`;
}

function sameOrigin(request) {
  const origin = request.headers.get("origin");
  return !origin || origin === new URL(request.url).origin;
}

export function createVoiceHandlers({ env = process.env, fetchImpl = fetch, limiter = createLimiter() } = {}) {
  const key = () => env.ELEVEN_API_KEY || "";
  const voice = () => env.ELEVEN_VOICE_ID || DEFAULT_VOICE;
  const ttsModel = () => env.ELEVEN_TTS_MODEL || "eleven_flash_v2_5";
  const sttModel = () => env.ELEVEN_STT_MODEL || "scribe_v1";

  async function health() {
    if (!key()) return json({ configured: false, tts: false, stt: false, reason: "ELEVEN_API_KEY not set (run make sync-eleven-key)" });
    try {
      const res = await fetchImpl(`${ELEVEN_API}/v1/models`, { headers: { "xi-api-key": key() }, cache: "no-store" });
      return json({ configured: true, reachable: res.ok, status: res.status, tts: res.ok, stt: res.ok, voice_id: voice(), tts_model: ttsModel(), stt_model: sttModel() });
    } catch {
      return json({ configured: true, reachable: false, tts: false, stt: false });
    }
  }

  async function tts(request) {
    if (!sameOrigin(request)) return json({ error: "Same-origin requests are required" }, 403);
    if (!key()) return json({ error: "Voice is not configured" }, 503);
    if (!limiter(callerKey(request))) return json({ error: "Too many voice requests; try again in a minute" }, 429);
    let body;
    try { body = await request.json(); } catch { return json({ error: "Invalid JSON" }, 400); }
    const text = typeof body?.text === "string" ? body.text.trim() : "";
    if (!text) return json({ error: "text is required" }, 400);
    if (text.length > TTS_MAX_CHARS) return json({ error: `text exceeds ${TTS_MAX_CHARS} characters` }, 413);
    const upstream = await fetchImpl(`${ELEVEN_API}/v1/text-to-speech/${encodeURIComponent(voice())}?output_format=mp3_44100_64`, {
      method: "POST", headers: { "xi-api-key": key(), "Content-Type": "application/json", Accept: "audio/mpeg" },
      body: JSON.stringify({ text, model_id: ttsModel() }), cache: "no-store",
    });
    if (!upstream.ok) return json({ error: `Voice provider returned HTTP ${upstream.status}` }, 502);
    return new Response(upstream.body, { status: 200, headers: { "Content-Type": "audio/mpeg", "Cache-Control": "no-store" } });
  }

  async function stt(request) {
    if (!sameOrigin(request)) return json({ error: "Same-origin requests are required" }, 403);
    if (!key()) return json({ error: "Voice is not configured" }, 503);
    if (!limiter(callerKey(request))) return json({ error: "Too many voice requests; try again in a minute" }, 429);
    let form;
    try { form = await request.formData(); } catch { return json({ error: "Expected multipart form data" }, 400); }
    const file = form.get("file");
    if (!file || typeof file === "string") return json({ error: "file is required" }, 400);
    if (file.size > STT_MAX_BYTES) return json({ error: "audio too large (max 10 MB)" }, 413);
    if (file.type && !/^(audio|video)\//.test(file.type)) return json({ error: "file must be audio" }, 415);
    const out = new FormData();
    out.append("model_id", sttModel());
    out.append("file", file, file.name || "speech.webm");
    const upstream = await fetchImpl(`${ELEVEN_API}/v1/speech-to-text`, { method: "POST", headers: { "xi-api-key": key() }, body: out, cache: "no-store" });
    if (!upstream.ok) return json({ error: `Voice provider returned HTTP ${upstream.status}` }, 502);
    const data = await upstream.json().catch(() => ({}));
    return json({ text: String(data.text || "").trim(), language: data.language_code || null });
  }

  return { health, tts, stt };
}

/**
 * /api/format-math proxy: deterministic mode is answered by REST without auth issues; the agentic mode
 * needs the caller's token. `post(path, token, payload)` is the host app's authenticated REST client.
 */
export function createFormatHandler({ getToken, post, fallback }) {
  return async function format(request) {
    if (!sameOrigin(request)) return json({ error: "Same-origin requests are required" }, 403);
    let body;
    try { body = await request.json(); } catch { return json({ error: "Invalid JSON" }, 400); }
    const text = typeof body?.text === "string" ? body.text.slice(0, 4000) : "";
    const mode = body?.mode === "agentic" ? "agentic" : "deterministic";
    const token = await getToken();
    if (!token) return json({ input: text, formatted: fallback(text), engine: "deterministic", warnings: ["not logged in; used quick format"] });
    try {
      return json(await post("/v1/tutor/format-math", token, { text, mode }));
    } catch (err) {
      return json({ input: text, formatted: fallback(text), engine: "deterministic", warnings: [`format service unavailable (${err.status || "error"})`] });
    }
  };
}
