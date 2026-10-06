// Check ElevenLabs connectivity using ELEVEN_API_KEY from the root .env only (never printed).
//   node scripts/check-eleven.mjs          free: list models + voices (no characters billed)
//   node scripts/check-eleven.mjs --tts    also synthesises one tiny phrase (bills ~20 characters)
import { readFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("../", import.meta.url)));
const API = "https://api.elevenlabs.io";
const DEFAULT_VOICE = "JBFqnCBsd6RMkjVDRZzb";
const TTS_MODEL = "eleven_flash_v2_5";

async function key() {
  const text = await readFile(join(root, ".env"), "utf8").catch(() => "");
  const line = text.split(/\r?\n/).filter((l) => /^\s*(?:export\s+)?ELEVEN_API_KEY\s*=/.test(l)).at(-1);
  const value = line ? line.slice(line.indexOf("=") + 1).trim().replace(/^["']|["']$/g, "").replace(/\s+#.*$/, "") : "";
  if (!value) throw new Error("ELEVEN_API_KEY is not set in root .env");
  return value;
}

async function call(path, init, apiKey) {
  const res = await fetch(`${API}${path}`, { ...init, headers: { "xi-api-key": apiKey, ...(init?.headers || {}) },
                                             signal: AbortSignal.timeout(20000) });
  return res;
}

async function main() {
  const apiKey = await key();
  const models = await call("/v1/models", {}, apiKey);
  console.log(`models endpoint: HTTP ${models.status}${models.ok ? ` (${(await models.json()).length} models)` : ""}`);
  const voices = await call("/v1/voices", {}, apiKey);
  let voice = process.env.ELEVEN_VOICE_ID || DEFAULT_VOICE;
  if (voices.ok) {
    const list = (await voices.json()).voices || [];
    console.log(`voices endpoint: HTTP 200 (${list.length} voices available)`);
    if (!process.env.ELEVEN_VOICE_ID && list.length && !list.some((v) => v.voice_id === voice)) voice = list[0].voice_id;
  } else {
    console.log(`voices endpoint: HTTP ${voices.status} (key may lack voices_read; TTS can still work)`);
  }
  if (process.argv.includes("--tts")) {
    console.log(`TTS check (paid, ~20 chars) with ${TTS_MODEL} ...`);
    const tts = await call(`/v1/text-to-speech/${voice}?output_format=mp3_22050_32`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ text: "MathBank voice check.", model_id: TTS_MODEL }) }, apiKey);
    const bytes = tts.ok ? (await tts.arrayBuffer()).byteLength : 0;
    console.log(`text-to-speech: HTTP ${tts.status}${tts.ok ? `, ${bytes} bytes of audio/mpeg` : ""}`);
    if (!tts.ok) process.exitCode = 1;
  } else {
    console.log("Skipped paid TTS; run `make check-eleven TTS=1` to synthesise one short phrase.");
  }
  if (!models.ok && !voices.ok) process.exitCode = 1;
}

main().catch((error) => {
  console.error(`ElevenLabs check failed: ${error.message}`);
  process.exitCode = 1;
});
