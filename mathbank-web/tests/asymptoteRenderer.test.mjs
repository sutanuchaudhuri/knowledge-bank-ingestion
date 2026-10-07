import assert from "node:assert/strict";
import test from "node:test";
import { readFile, mkdtemp, rm, writeFile, realpath } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import path from "node:path";
import { renderAsymptote, sandboxProfile, validateAsymptote } from "../lib/asymptoteRenderer.mjs";
import { createAsymptoteHandler } from "../lib/asymptoteProxy.mjs";

test("rejects unsafe/compiler configuration operations and oversized sources", () => {
  for (const source of ["", "x".repeat(32001), 'system("id");', 'import settings;', 'import "../../../file";', 'label("\\input{secret}");']) {
    assert.throws(() => validateAsymptote(source), /source|unsupported/);
  }
  assert.doesNotThrow(() => validateAsymptote('draw((0,0)--(1,1)); //shipout(format="pdf");'));
  assert.throws(() => validateAsymptote('label("\\input{secret}"); // harmless comment'), /unsupported/);
});

test("proxy verifies origin and authentication before starting the compiler", async () => {
  let rendered = 0;
  const render = async () => { rendered += 1; return Buffer.from("synthetic"); };
  const request = (origin = "http://localhost:5173", body = '{"source":"draw((0,0)--(1,1));"}') =>
    new Request("http://localhost:5173/api/diagrams/asymptote", { method: "POST", headers: { origin }, body });
  const denied = createAsymptoteHandler({ authenticate: async () => false, render });
  assert.equal((await denied(request("https://untrusted.example"))).status, 403);
  assert.equal((await denied(request())).status, 401);
  const invalidToken = createAsymptoteHandler({ authenticate: async () => { throw Object.assign(new Error("invalid token"), { status: 401 }); }, render });
  assert.equal((await invalidToken(request())).status, 401);
  assert.equal(rendered, 0);
  const allowed = createAsymptoteHandler({ authenticate: async () => true, render });
  assert.equal((await allowed(request(undefined, "{"))).status, 400);
  assert.equal((await allowed(request(undefined, "x".repeat(200000)))).status, 413);
  const response = await allowed(request());
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("content-type"), "image/png");
  assert.equal(response.headers.get("cache-control"), "no-store");
});

test("isolated compiler renders the supplied 3D prism as a PNG", { skip: process.env.RUN_ASYMPTOTE_TESTS !== "1" }, async () => {
  const source = await readFile(new URL("./fixtures/prism.asy", import.meta.url), "utf8");
  const png = await renderAsymptote(source);
  assert.ok(png.length > 500);
  assert.equal(png.readUInt32BE(16) > 100, true);
  assert.equal(png.readUInt32BE(20) > 100, true);
});

test("OS sandbox denies outside reads/writes and network even without source filtering", { skip: process.env.RUN_ASYMPTOTE_TESTS !== "1" }, async () => {
  const directory = await realpath(await mkdtemp(path.join(tmpdir(), "mathbank-sandbox-test-")));
  const outside = await realpath(await mkdtemp(path.join(tmpdir(), "mathbank-outside-test-")));
  try {
    await writeFile(path.join(outside, "synthetic.txt"), "invented sandbox canary");
    for (const script of [
      'cat "$1/synthetic.txt"',
      'echo altered > "$1/new.txt"',
      '/usr/bin/curl --max-time 2 -s http://127.0.0.1:5173/',
    ]) {
      const result = spawnSync("/usr/bin/sandbox-exec", [
        "-p", sandboxProfile(directory), "/bin/sh", "-c", script, "test", outside,
      ], { encoding: "utf8", env: { PATH: "/usr/bin:/bin", HOME: directory }, timeout: 5000 });
      assert.notEqual(result.status, 0);
      assert.ok(!result.stdout?.includes("invented sandbox canary"));
    }
  } finally {
    await rm(directory, { recursive: true, force: true });
    await rm(outside, { recursive: true, force: true });
  }
});
