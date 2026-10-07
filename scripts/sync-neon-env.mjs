// Root-file-only, server-side Neon credentials. Never prints credential values.
import { chmod, mkdir, readFile, rename, unlink, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseEnv } from "./sync-live-env.mjs";

export const STORAGE_KEYS = ["AWS_ENDPOINT_URL_S3", "AWS_REGION", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"];
export const GATEWAY_KEYS = ["NEON_AI_GATEWAY_BASE_URL", "NEON_AI_GATEWAY_TOKEN"];

export function configuration(text) {
  const source = parseEnv(text);
  const required = [...STORAGE_KEYS, ...GATEWAY_KEYS];
  const missing = required.filter((key) => !source[key] || /^(?:\.\.\.|change-me|your[-_]|<)/i.test(source[key]));
  if (missing.length) throw new Error(`Missing Neon settings in root .env: ${missing.join(", ")}`);
  for (const key of ["AWS_ENDPOINT_URL_S3", "NEON_AI_GATEWAY_BASE_URL"]) {
    let url;
    try { url = new URL(source[key]); } catch { throw new Error(`${key} must be an HTTPS URL`); }
    if (url.protocol !== "https:" || url.username || url.password || url.search || url.hash) {
      throw new Error(`${key} must be a credential-free HTTPS URL`);
    }
  }
  if (!/^[a-z0-9-]+$/.test(source.AWS_REGION)) throw new Error("Invalid AWS_REGION");
  const bucket = source.MATHBANK_OBJECT_BUCKET || "mathbank-runtime";
  if (!/^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$/.test(bucket)) throw new Error("Invalid MATHBANK_OBJECT_BUCKET");
  const provider = source.MATHBANK_RUNTIME_AI_PROVIDER || "openai";
  if (!["openai", "neon"].includes(provider)) throw new Error("MATHBANK_RUNTIME_AI_PROVIDER must be openai or neon");
  return { ...Object.fromEntries(required.map((key) => [key, source[key]])),
    MATHBANK_OBJECT_BUCKET: bucket, MATHBANK_OBJECT_BACKEND: "s3", MATHBANK_RUNTIME_AI_PROVIDER: provider };
}

export function merge(existing, values) {
  const seen = new Set();
  const lines = existing.trimEnd().split(/\r?\n/).flatMap((line) => {
    const key = /^\s*(?:export\s+)?([A-Z0-9_]+)\s*=/.exec(line)?.[1];
    if (!key || !(key in values)) return [line];
    if (seen.has(key)) return [];
    seen.add(key);
    return [`${key}=${JSON.stringify(values[key])}`];
  });
  for (const [key, value] of Object.entries(values)) if (!seen.has(key)) lines.push(`${key}=${JSON.stringify(value)}`);
  return `${lines.filter((line, index) => index || line).join("\n")}\n`;
}

export async function sync(root) {
  const values = configuration(await readFile(join(root, ".env"), "utf8"));
  // Agent tools use REST rather than object-store master credentials.
  for (const service of ["mathbank-rest", "mathbank-web", "mathbank-live", "mathbank-agent"]) {
    const selected = service === "mathbank-agent"
      ? Object.fromEntries(GATEWAY_KEYS.map((key) => [key, values[key]])) : values;
    const target = join(root, service, ".env");
    let existing = "";
    try { existing = await readFile(target, "utf8"); } catch (error) { if (error.code !== "ENOENT") throw error; }
    await mkdir(dirname(target), { recursive: true });
    const tmp = `${target}.neon-sync-${process.pid}`;
    try {
      await writeFile(tmp, merge(existing, selected), { mode: 0o600, flag: "wx" });
      await chmod(tmp, 0o600);
      await rename(tmp, target);
    } finally {
      try { await unlink(tmp); } catch (error) { if (error.code !== "ENOENT") throw error; }
    }
    console.log(`Synced Neon ${service === "mathbank-agent" ? "AI Gateway" : "S3 + AI Gateway"} settings to ${service}/.env (values hidden; permissions 0600).`);
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const root = resolve(process.argv[2] || fileURLToPath(new URL("../", import.meta.url)));
  sync(root).catch(() => {
    console.error("Neon credential sync failed. Check required root .env settings and writable service folders; values hidden.");
    process.exitCode = 1;
  });
}
