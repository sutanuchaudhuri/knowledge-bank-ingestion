import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, rm, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { configuration, merge, sync } from "./sync-neon-env.mjs";

const fixture = 'AWS_ENDPOINT_URL_S3=https://branch.storage.neon.tech\nAWS_REGION=us-east-2\nAWS_ACCESS_KEY_ID=synthetic-access\nAWS_SECRET_ACCESS_KEY=synthetic-secret\nNEON_AI_GATEWAY_BASE_URL=https://branch.ai.neon.tech\nNEON_AI_GATEWAY_TOKEN=synthetic-token\n';

test("validates all settings before writes and never falls back to shell credentials", () => {
  assert.throws(() => configuration(""), /Missing Neon settings/);
  assert.throws(() => configuration(fixture.replace("https://branch.storage.neon.tech", "http://bad")), /HTTPS/);
  assert.throws(() => configuration(fixture.replace("https://branch.storage.neon.tech", "https://user:password@host")), /credential-free/);
  assert.equal(configuration(fixture).MATHBANK_OBJECT_BACKEND, "s3");
});
test("merge removes managed duplicates, preserves unrelated settings and is repeatable", () => {
  const values = configuration(fixture);
  const first = merge("KEEP=yes\nAWS_REGION=old\nAWS_REGION=duplicate\n", values);
  assert.equal(first.match(/^AWS_REGION=/gm).length, 1);
  assert.match(first, /^KEEP=yes$/m);
  assert.equal(merge(first, values), first);
});
test("sync uses private permissions and never gives agent tools S3 master credentials", async () => {
  const root = await mkdtemp(join(tmpdir(), "mb-neon-env-"));
  try {
    await writeFile(join(root, ".env"), fixture);
    await mkdir(join(root, "mathbank-rest"));
    await writeFile(join(root, "mathbank-rest", ".env"), "KEEP=yes\n");
    await sync(root);
    const rest = await readFile(join(root, "mathbank-rest", ".env"), "utf8");
    assert.match(rest, /^KEEP=yes$/m);
    assert.equal((await stat(join(root, "mathbank-rest", ".env"))).mode & 0o777, 0o600);
    const agent = await readFile(join(root, "mathbank-agent", ".env"), "utf8");
    assert.match(agent, /NEON_AI_GATEWAY_TOKEN/);
    assert.doesNotMatch(agent, /AWS_SECRET_ACCESS_KEY/);
  } finally { await rm(root, { recursive: true, force: true }); }
});
