// Emits templates only. This program never opens a database or network connection.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { directory, queries } from "./library.mjs";

const selection = process.argv[2];
if (process.argv.length !== 3) {
  console.error("Usage: node emit.mjs Q001 | psql -X -v ON_ERROR_STOP=1 [connection options]\n       node emit.mjs --list");
  process.exit(1);
}
const inventory = queries();
if (selection === "--list") {
  for (const query of inventory) console.log(`${query.id}\t${query.file}\t${query.title}`);
} else {
  const query = inventory.find((item) => item.id === selection);
  if (!query) {
    console.error(`Unknown query ID: ${selection}`);
    process.exit(1);
  }
  console.log(readFileSync(join(directory, "_session.sql"), "utf8"));
  console.log(query.body);
  console.log("\nROLLBACK;");
}
