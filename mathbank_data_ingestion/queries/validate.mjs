// Dependency-free offline structural/schema lint, deliberately not a PostgreSQL parser.
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { categoryFiles, directory, queries } from "./library.mjs";

const migrations = resolve(directory, "../../mathbank-db/sql");
const schemas = new Map();
const errors = [];

function scrub(text) {
  // Blank literals/comments while preserving positions, including PostgreSQL dollar-quoted functions.
  return text.replace(/--[^\n]*|\/\*[\s\S]*?\*\/|\$(\w*)\$[\s\S]*?\$\1\$|'(?:''|\\.|[^'])*'/g,
    (value) => value.replace(/[^\n]/g, " "));
}

function closingParen(text, start) {
  let depth = 0;
  for (let i = start; i < text.length; i++) {
    if (text[i] === "(") depth++;
    if (text[i] === ")" && --depth === 0) return i;
  }
  throw new Error(`Unbalanced parentheses at ${start}`);
}

function splitColumns(text) {
  const pieces = [];
  let start = 0;
  let depth = 0;
  for (let i = 0; i < text.length; i++) {
    if (text[i] === "(") depth++;
    if (text[i] === ")") depth--;
    if (text[i] === "," && depth === 0) {
      pieces.push(text.slice(start, i));
      start = i + 1;
    }
  }
  pieces.push(text.slice(start));
  return pieces;
}

for (const file of readdirSync(migrations).filter((name) => /^\d{3}_.*\.sql$/.test(name)).sort()) {
  const sql = scrub(readFileSync(join(migrations, file), "utf8"));
  for (const match of sql.matchAll(/CREATE TABLE IF NOT EXISTS (\w+\.\w+)\s*\(/gi)) {
    const start = match.index + match[0].length - 1;
    const body = sql.slice(start + 1, closingParen(sql, start));
    const columns = schemas.get(match[1]) ?? new Set();
    for (const piece of splitColumns(body)) {
      const name = piece.trim().match(/^(\w+)\s/);
      if (name && !/^(PRIMARY|UNIQUE|CHECK|FOREIGN|CONSTRAINT|EXCLUDE)$/i.test(name[1])) columns.add(name[1]);
    }
    schemas.set(match[1], columns);
  }
  for (const match of sql.matchAll(/ALTER TABLE (\w+\.\w+)([\s\S]*?);/gi)) {
    const columns = schemas.get(match[1]);
    for (const addition of match[2].matchAll(/ADD COLUMN(?: IF NOT EXISTS)? (\w+)\s/gi)) {
      if (!columns) errors.push(`${file}: ALTER references untracked table ${match[1]}`);
      else columns.add(addition[1]);
    }
    for (const removal of match[2].matchAll(/DROP COLUMN(?: IF EXISTS)? (\w+)/gi)) columns?.delete(removal[1]);
  }
}
// Migration 008 adds these through a dynamic FOREACH/EXECUTE, not literal ALTER TABLE statements.
for (const table of ["skill", "skill_concept", "skill_relation", "problem_skill", "problem_pedagogy",
  "problem_concept", "problem_technique", "concept_relation"]) {
  schemas.get(`knowledge.${table}`).add("approval_method");
}

const reserved = new Set(["where", "join", "left", "right", "full", "inner", "cross", "on", "using",
  "group", "order", "limit", "having", "union", "offset", "filter"]);
const appSchemas = new Set([...schemas.keys()].map((key) => key.split(".")[0]));
const inventory = queries();
let tableReferences = 0;
let checkedColumns = 0;
let singleTableChecks = 0;

for (let i = 0; i < inventory.length; i++) {
  const query = inventory[i];
  if (query.id !== `Q${String(i + 1).padStart(3, "0")}`) errors.push(`Unexpected ID/order: ${query.id}`);
  if (!query.body.includes("-- Purpose/output:") || !query.body.includes("-- Inputs:") ||
      !query.body.includes("Risk: READ ONLY;")) errors.push(`${query.id}: missing documentation`);
  const sql = scrub(query.body).replace(/:'\w+'/g, "'parameter'");
  const nonblank = sql.trim();
  if (!/^(SELECT|WITH)\b/i.test(nonblank)) errors.push(`${query.id}: not SELECT/WITH`);
  if (/\b(INSERT|UPDATE|DELETE|MERGE|TRUNCATE|CREATE|ALTER|DROP|GRANT|REVOKE|COPY|CALL|DO)\b/i.test(sql)) {
    errors.push(`${query.id}: mutation keyword`);
  }
  if (/\bSELECT\s+INTO\b|\bFOR\s+(UPDATE|SHARE)\b|\bpg_(sleep|terminate_backend|cancel_backend)\s*\(/i.test(sql)) {
    errors.push(`${query.id}: unsafe statement`);
  }
  if ((sql.match(/;/g) ?? []).length !== 1 || !nonblank.endsWith(";")) {
    errors.push(`${query.id}: expected exactly one terminated statement`);
  }
  try {
    let depth = 0;
    for (const ch of sql) {
      if (ch === "(") depth++;
      if (ch === ")" && --depth < 0) throw new Error("closing parenthesis");
    }
    if (depth) throw new Error("opening parenthesis");
  } catch (error) { errors.push(`${query.id}: unmatched ${error.message}`); }

  const aliases = new Map();
  const tables = new Set();
  for (const match of sql.matchAll(/\b(?:FROM|JOIN)\s+(\w+\.\w+)(?:\s+(?:AS\s+)?(\w+))?/gi)) {
    const table = match[1];
    if (!appSchemas.has(table.split(".")[0])) continue; // PostgreSQL catalogs handled by PostgreSQL itself.
    tableReferences++;
    if (!schemas.has(table)) { errors.push(`${query.id}: unknown table ${table}`); continue; }
    tables.add(table);
    const alias = match[2] && !reserved.has(match[2].toLowerCase()) ? match[2] : table.split(".")[1];
    const options = aliases.get(alias) ?? new Set();
    options.add(table);
    aliases.set(alias, options);
  }
  for (const match of sql.matchAll(/\b(\w+)\.(\w+)\b/g)) {
    const candidates = aliases.get(match[1]);
    if (!candidates) continue; // CTEs, series and catalog aliases have derived/external columns.
    checkedColumns++;
    if (![...candidates].some((table) => schemas.get(table).has(match[2]))) {
      errors.push(`${query.id}: unknown qualified column ${match[0]} (${[...candidates].join(", ")})`);
    }
  }
  // Single-table queries are also checked for unqualified columns, allowing functions, output aliases,
  // PostgreSQL grammar, cast types and parameter replacement literals. Joins require manual scope review.
  if (tables.size === 1 && !/\bWITH\b|\bUNION\b|\bJOIN\b/i.test(sql)) {
    const columns = schemas.get([...tables][0]);
    const grammar = new Set(("select from where group by order asc desc nulls first last having limit offset " +
      "distinct filter within count sum avg min max array as case when then else end is not null and or true false " +
      "between in like ilike int integer bigint numeric text uuid boolean date interval timestamptz double precision " +
      "extract epoch now current_date all exists any some parameter").split(" "));
    const outputs = new Set([...sql.matchAll(/\bAS\s+(\w+)/gi)].map((m) => m[1]));
    const tokens = sql.matchAll(/\b[a-z_]\w*\b/gi);
    for (const token of tokens) {
      const word = token[0];
      const before = sql[token.index - 1];
      const after = sql.slice(token.index + word.length).trimStart();
      if (before === "." || after.startsWith(".") || after.startsWith("(") || after.startsWith("=>") || grammar.has(word.toLowerCase()) ||
          outputs.has(word) || aliases.has(word) || columns.has(word)) continue;
      errors.push(`${query.id}: unrecognized single-table identifier ${word}`);
    }
    singleTableChecks++;
  }
}

for (const file of categoryFiles) {
  const text = readFileSync(join(directory, file), "utf8");
  assert(text.startsWith("\\ir _session.sql\n"), `${file}: missing safety preamble`);
  assert(text.trimEnd().endsWith("ROLLBACK;"), `${file}: missing rollback`);
  const starts = [...text.matchAll(/^-- Q\d{3} /gm)].length;
  assert.equal(starts, inventory.filter((query) => query.file === file).length, `${file}: malformed query blocks`);
}
assert.equal(inventory.length, 210, "Expected 210 documented query templates");
if (errors.length) {
  console.error(errors.join("\n"));
  process.exit(1);
}
console.log(`PASS: ${inventory.length} sequential unique queries across ${categoryFiles.length} category files.`);
console.log(`Composite migrations: ${schemas.size} tables; ${tableReferences} table references and ${checkedColumns} qualified column references checked.`);
console.log(`Additional unqualified-identifier checks: ${singleTableChecks} single-table queries.`);
console.log("All templates are one SELECT/WITH statement, documented READ ONLY, balanced, guarded by read-only transactions.");
console.log("LIMITATION: lexical/schema lint is not PostgreSQL parsing or execution; derived scopes, catalog columns, functions, operators and semantics require PostgreSQL validation.");
