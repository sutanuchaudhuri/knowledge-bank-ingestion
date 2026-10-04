// Minimal in-memory TTL cache, scoped to this Next.js server process — good enough
// for a local single-instance deployment. Not shared across serverless invocations.
const store = new Map();

/** Returns the cached value for `key` if still within `ttlMs`, else recomputes via `fn`. */
export async function withCache(key, ttlMs, fn) {
  const hit = store.get(key);
  const now = Date.now();
  if (hit && now - hit.at < ttlMs) return hit.value;
  const value = await fn();
  store.set(key, { value, at: now });
  return value;
}
