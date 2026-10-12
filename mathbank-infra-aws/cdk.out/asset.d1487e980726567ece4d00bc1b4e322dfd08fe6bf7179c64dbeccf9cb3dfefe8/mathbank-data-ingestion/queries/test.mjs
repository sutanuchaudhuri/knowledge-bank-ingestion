import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { directory, queries } from "./library.mjs";

const emitter = join(directory, "emit.mjs");
const inventory = queries();

test("all 210 IDs are unique, contiguous and have distinct query text", () => {
  assert.equal(inventory.length, 210);
  assert.equal(new Set(inventory.map((query) => query.id)).size, 210);
  const normalized = inventory.map((query) => query.body.replace(/^--.*$/gm, "").replace(/\s+/g, " ").trim());
  assert.equal(new Set(normalized).size, 210);
  inventory.forEach((query, index) => assert.equal(query.id, `Q${String(index + 1).padStart(3, "0")}`));
});

test("emission guards every query and includes only the requested query", () => {
  for (const query of inventory) {
    const result = spawnSync(process.execPath, [emitter, query.id], { encoding: "utf8" });
    assert.equal(result.status, 0, result.stderr);
    assert.match(result.stdout, /BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;/);
    assert.match(result.stdout, /SET LOCAL statement_timeout = '30s';/);
    assert.match(result.stdout, /SET LOCAL lock_timeout = '2s';/);
    assert.match(result.stdout, /\\set ON_ERROR_STOP on/);
    assert.equal((result.stdout.match(/^-- Q\d{3} /gm) ?? []).length, 1);
    assert.ok(result.stdout.includes(`-- ${query.id} `));
    assert.match(result.stdout, /\nROLLBACK;\s*$/);
  }
});

test("unknown IDs and extra arguments emit no SQL", () => {
  for (const args of [["Q999"], ["Q001", "Q002"], ["SELECT 1"], []]) {
    const result = spawnSync(process.execPath, [emitter, ...args], { encoding: "utf8" });
    assert.notEqual(result.status, 0);
    assert.equal(result.stdout, "");
  }
});

test("every query variable has a guarded psql default", () => {
  const session = readFileSync(join(directory, "_session.sql"), "utf8");
  const variables = new Set(inventory.flatMap((query) => [...query.body.matchAll(/:'(\w+)'/g)].map((match) => match[1])));
  for (const variable of variables) {
    assert.ok(session.includes(`\\if :{?${variable}}`), variable);
    assert.match(session, new RegExp(`\\\\set ${variable} `));
  }
  assert.equal(variables.size, 9);
});

test("every learner-content diagnostic enforces distinct-person small-cell suppression", () => {
  for (const query of inventory.filter((item) => Number(item.id.slice(1)) >= 196)) {
    assert.match(query.body, /HAVING count\(DISTINCT (?:\w+\.)?student_id\)>=greatest\(10,:'cohort'::int\)/);
    assert.doesNotMatch(query.body.replace(/^--.*$/gm, ""),
      /\b(email|password_hash|display_name|submitted_answer|last_response_text|reason|review_note|audit_snapshot|payload|object_key|plain_text|latex_text|why|actor_id)\b/);
  }
});
