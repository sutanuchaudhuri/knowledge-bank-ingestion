import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const directory = dirname(fileURLToPath(import.meta.url));
export const categoryFiles = readdirSync(directory).filter((name) => /^\d\d_.*\.sql$/.test(name)).sort();

export function queries() {
  const result = [];
  for (const file of categoryFiles) {
    const text = readFileSync(join(directory, file), "utf8");
    for (const match of text.matchAll(/^-- (Q\d{3}) (.+)\n([\s\S]*?)^-- END \1$/gm)) {
      result.push({ id: match[1], title: match[2], body: match[0], file });
    }
  }
  return result;
}
