// Write mathbank-live/.env from the root .env only (requirements 28). Copies just the keys the realtime
// gateway + live UI need; preserves any other lines already in mathbank-live/.env. Never prints values.
import { chmod, readFile, rename, unlink, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(process.argv[2] || fileURLToPath(new URL("../", import.meta.url)));
export const LIVE_KEYS = ["MATHBANK_REST_BASE_URL", "MATHBANK_ADMIN_API_KEY", "ADMIN_LOGIN_USERNAME",
  "ADMIN_LOGIN_PASSWORD", "ADMIN_SESSION_SECRET", "ELEVEN_API_KEY", "AWS_REGION",
  "COGNITO_USER_POOL_ID", "COGNITO_ADMIN_GROUP"];
// Renamed on the way in — mathbank-live gets its own App Client (COGNITO_CLIENT_ID_LIVE/
// COGNITO_CLIENT_SECRET_LIVE in the root .env), distinct from mathbank-web's and
// mathbank-exam-agent's, but lib/cognito.js in both mathbank-web and mathbank-live reads
// the same generic COGNITO_CLIENT_ID/COGNITO_CLIENT_SECRET names either way.
export const LIVE_RENAMED_KEYS = { COGNITO_CLIENT_ID_LIVE: "COGNITO_CLIENT_ID", COGNITO_CLIENT_SECRET_LIVE: "COGNITO_CLIENT_SECRET" };

export function parseEnv(text) {
  const out = {};
  for (const line of text.split(/\r?\n/)) {
    const m = /^\s*(?:export\s+)?([A-Z0-9_]+)\s*=(.*)$/.exec(line);
    if (!m) continue;
    let v = m[2].trim();
    if ((v.startsWith('"') && v.lastIndexOf('"') > 0) || (v.startsWith("'") && v.lastIndexOf("'") > 0)) v = v.slice(1, v.lastIndexOf(v[0]));
    else v = v.replace(/\s+#.*$/, "").trim();
    out[m[1]] = v;
  }
  return out;
}

export function mergeEnv(existing, values) {
  const seen = new Set();
  const lines = existing.split(/\r?\n/).filter((l, i, a) => !(i === a.length - 1 && l === "")).flatMap((line) => {
    const key = /^\s*(?:export\s+)?([A-Z0-9_]+)\s*=/.exec(line)?.[1];
    if (!key || !(key in values)) return [line];
    if (seen.has(key)) return [];
    seen.add(key);
    return [`${key}=${values[key]}`];
  });
  for (const [k, v] of Object.entries(values)) if (!seen.has(k)) lines.push(`${k}=${v}`);
  if (!lines.some((l) => l.startsWith("# mathbank-live"))) lines.unshift("# mathbank-live — server-side only (written by make sync-live-env from root .env)");
  return `${lines.join("\n")}\n`;
}

async function main() {
  const rootEnv = parseEnv(await readFile(join(root, ".env"), "utf8").catch(() => ""));
  const values = {};
  const missing = [];
  for (const k of LIVE_KEYS) (rootEnv[k] ? (values[k] = rootEnv[k]) : missing.push(k));
  for (const [sourceKey, targetKey] of Object.entries(LIVE_RENAMED_KEYS)) {
    (rootEnv[sourceKey] ? (values[targetKey] = rootEnv[sourceKey]) : missing.push(sourceKey));
  }
  values.LIVE_PORT = rootEnv.LIVE_PORT || "5174";
  const target = join(root, "mathbank-live", ".env");
  const merged = mergeEnv(await readFile(target, "utf8").catch(() => ""), values);
  const tmp = `${target}.sync-${process.pid}`;
  try {
    await writeFile(tmp, merged, { mode: 0o600, flag: "wx" });
    await chmod(tmp, 0o600);
    await rename(tmp, target);
  } finally {
    await unlink(tmp).catch(() => {});
  }
  console.log(`Synced ${Object.keys(values).length} keys to mathbank-live/.env (values hidden; permissions 0600).`);
  if (missing.length) {
    console.error(`Missing in root .env: ${missing.join(", ")}`);
    process.exitCode = 1;
  }
}

if (import.meta.url === `file://${process.argv[1]}`) main().catch((e) => { console.error(`Live env sync failed: ${e.message}`); process.exitCode = 1; });
