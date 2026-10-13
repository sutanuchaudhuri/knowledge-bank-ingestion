// Same-origin proxy to mathbank-ml-inference (requirements/56), mirroring the pattern
// mathbank-web already uses for its own REST proxies (e.g.
// mathbank-web/app/api/rest/quiz/[[...path]]/route.js) — server-side only, so the
// inference service's base URL never needs to be exposed to the browser.
//
// TODO: add admin auth once mathbank-ml-inference enforces it (requirements/56). This
// proxy currently passes every request through unauthenticated — do not point this at a
// non-dev mathbank-ml-inference instance until that TODO is resolved.

const BASE_URL = process.env.ML_INFERENCE_BASE_URL || "http://localhost:8010";

export async function GET(request, context) {
  const { path } = await context.params;
  const search = new URL(request.url).search;
  try {
    const response = await fetch(`${BASE_URL}/v1/admin/ml/${(path || []).join("/")}${search}`, {
      cache: "no-store",
    });
    const body = await response.json().catch(() => ({}));
    return Response.json(body, { status: response.status });
  } catch (err) {
    return Response.json(
      { error: "ML_INFERENCE_UNREACHABLE", message: err.message },
      { status: 502 },
    );
  }
}
