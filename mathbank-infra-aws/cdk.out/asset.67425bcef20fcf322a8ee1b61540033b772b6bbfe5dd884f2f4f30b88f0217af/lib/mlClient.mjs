// Same-origin fetch helper for calling this app's own /api/ml/* proxy (not
// mathbank-ml-inference directly) from client components — matches mathbank-web's own
// `lib/restClient.js` convention of "pages call the same-origin proxy, the proxy calls
// the real service," so credentials/base-URL config stay server-side only.

export async function fetchMl(path) {
  const response = await fetch(`/api/ml/${path}`, { cache: "no-store" });
  const body = await response.json().catch(() => ({}));
  return { status: response.status, body };
}
