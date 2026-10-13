// Minimal in-memory TTL cache, scoped to this Next.js server process — good enough
// for a local single-instance deployment. Not shared across serverless invocations.
const store = new Map();
let generation = 0;

export function invalidateGraphCache() {
  generation += 1;
  for (const key of store.keys()) {
    if (key.startsWith("graph:")) store.delete(key);
  }
}

/** Returns the cached value for `key` if still within `ttlMs`, else recomputes via `fn`. */
export async function withCache(key, ttlMs, fn) {
  const hit = store.get(key);
  const now = Date.now();
  if (hit && now - hit.at < ttlMs) return hit.value;
  const startedGeneration = generation;
  const value = await fn();
  if (generation === startedGeneration) store.set(key, { value, at: now });
  return value;
}
