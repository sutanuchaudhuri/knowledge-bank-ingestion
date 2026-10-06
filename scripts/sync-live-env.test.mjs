import assert from "node:assert/strict";
import test from "node:test";
import { mergeEnv, parseEnv } from "./sync-live-env.mjs";

test("parseEnv handles export, quotes and comments", () => {
  assert.deepEqual(parseEnv('export A=1\nB="x y" # c\nC=z # note\n# D=no'), { A: "1", B: "x y", C: "z" });
});

test("mergeEnv replaces managed keys once, keeps others, is idempotent", () => {
  const first = mergeEnv("KEEP=1\nA=old\nA=dup\n", { A: "new", B: "2" });
  assert.match(first, /KEEP=1/);
  assert.equal(first.match(/^A=/gm).length, 1);
  assert.match(first, /^A=new$/m);
  assert.match(first, /^B=2$/m);
  assert.equal(mergeEnv(first, { A: "new", B: "2" }), first);
});
