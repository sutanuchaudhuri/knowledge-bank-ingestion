const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export function createTutoringRoutesHandlers({ hasSession, get, post, invalidate }) {
  async function authorize(request, mutation) {
    if (!await hasSession()) return Response.json({ error: "Admin login required" }, { status: 401 });
    if (mutation && request.headers.get("origin") !== new URL(request.url).origin) {
      return Response.json({ error: "Same-origin admin requests are required" }, { status: 403 });
    }
    return null;
  }
  return {
    async GET(request) {
      const denied = await authorize(request, false);
      if (denied) return denied;
      const params = new URL(request.url).searchParams;
      if ([...params.keys()].some(key => !["release", "limit", "offset"].includes(key))) {
        return Response.json({ error: "Unknown route filter" }, { status: 400 });
      }
      const release = params.get("release");
      if (release && !UUID.test(release)) return Response.json({ error: "Invalid release ID" }, { status: 400 });
      try {
        return Response.json(await get(`/v1/admin/tutoring-routes${release ? `/${release}` : ""}`,
          release ? undefined : Object.fromEntries(params)));
      } catch (err) {
        return Response.json({ error: err.message }, { status: err.status || 502 });
      }
    },
    async POST(request) {
      const denied = await authorize(request, true);
      if (denied) return denied;
      let body;
      try { body = await request.json(); }
      catch { return Response.json({ error: "Invalid JSON" }, { status: 400 }); }
      if (!body || Array.isArray(body) || typeof body !== "object") {
        return Response.json({ error: "Expected a JSON object" }, { status: 400 });
      }
      const { action, release, ...payload } = body;
      if (!["edit", "review", "publish", "refresh-graph"].includes(action) ||
          (action !== "refresh-graph" && !UUID.test(release || ""))) {
        return Response.json({ error: "Invalid route action" }, { status: 400 });
      }
      try {
        const result = await post(`/v1/admin/tutoring-routes/${action === "refresh-graph" ? action : `${release}/${action}`}`, payload);
        if (action === "refresh-graph") invalidate();
        return Response.json(result);
      } catch (err) {
        return Response.json({ error: err.message }, { status: err.status || 502 });
      }
    },
  };
}
