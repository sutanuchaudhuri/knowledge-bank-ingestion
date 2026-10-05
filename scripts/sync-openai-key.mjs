import { chmod, mkdir, readFile, rename, stat, unlink, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(process.argv[2] || fileURLToPath(new URL("../", import.meta.url)));
const assignment = /^\s*(?:export\s+)?OPENAI_API_KEY\s*=/;

function keyFromFile(text) {
  const line = text.split(/\r?\n/).filter((line) => assignment.test(line)).at(-1);
  if (!line) return "";
  let value = line.slice(line.indexOf("=") + 1).trim();
  if (value.startsWith('"') || value.startsWith("'")) {
    const quote = value[0];
    const end = value.indexOf(quote, 1);
    if (end < 0 || !/^\s*(?:#.*)?$/.test(value.slice(end + 1))) {
      throw new Error("Invalid OPENAI_API_KEY quoting in root .env.");
    }
    value = value.slice(1, end);
  } else {
    value = value.replace(/\s+#.*$/, "").trim();
  }
  return value;
}

async function exists(path) {
  try {
    await stat(path);
    return true;
  } catch (error) {
    if (error.code === "ENOENT") return false;
    throw error;
  }
}

async function main() {
  let rootEnv = "";
  try {
    rootEnv = await readFile(join(root, ".env"), "utf8");
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
  const fromRoot = keyFromFile(rootEnv);
  const key = fromRoot;
  if (!key || /[\s"'`\\#$]/.test(key) || /^(?:change-me|your[-_]|<)/i.test(key)) {
    throw new Error("Set a valid OPENAI_API_KEY in root .env before syncing; shell keys are ignored.");
  }
  const required = ["mathbank-rest", "mathbank-agent", "mathbank_data_ingestion"];
  const candidates = [...required, "mathbank-db", "mathbank-graph", "mathbank-web"];
  for (const service of candidates) {
    const target = join(root, service, ".env");
    if (!required.includes(service) && !await exists(target)) continue;
    let text = "";
    try {
      text = await readFile(target, "utf8");
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
    }
    let replaced = false;
    const lines = text.split(/\r?\n/).filter((line) => {
      if (!assignment.test(line)) return true;
      if (replaced) return false;
      replaced = true;
      return true;
    }).map((line) => assignment.test(line) ? `OPENAI_API_KEY=${key}` : line);
    let updated = lines.join("\n");
    if (!replaced) {
      updated += `${updated && !updated.endsWith("\n") ? "\n" : ""}OPENAI_API_KEY=${key}\n`;
    }
    if (!updated.endsWith("\n")) updated += "\n";
    await mkdir(dirname(target), { recursive: true });
    const temporary = `${target}.sync-${process.pid}`;
    try {
      await writeFile(temporary, updated, { mode: 0o600, flag: "wx" });
      await chmod(temporary, 0o600);
      await rename(temporary, target);
    } finally {
      try {
        await unlink(temporary);
      } catch (error) {
        if (error.code !== "ENOENT") throw error;
      }
    }
    console.log(`Synced OPENAI_API_KEY to ${service}/.env (value hidden; permissions 0600).`);
  }
  console.log("Key source: root .env only. Restart existing services to load it.");
}

main().catch((error) => {
  console.error(`Environment sync failed: ${error.message}`);
  process.exitCode = 1;
});
