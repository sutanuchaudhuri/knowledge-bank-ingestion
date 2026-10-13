export function createAdminPedagogyHandlers({ hasSession, get, post, invalidate }) {
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
      if ([...params.keys()].some(key => !["kind", "status", "limit", "offset", "view"].includes(key))) {
        return Response.json({ error: "Unknown queue filter" }, { status: 400 });
      }
      try {
        const view = params.get("view");
        if (view && !["feedback", "retrieval-examples"].includes(view)) return Response.json({ error: "Unknown queue view" }, { status: 400 });
        params.delete("view");
        return Response.json(await get(`/v1/admin/pedagogy/${view || "queue"}`, Object.fromEntries(params)));
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
      if (!body || typeof body !== "object" || Array.isArray(body)) {
        return Response.json({ error: "Expected a JSON object" }, { status: 400 });
      }
      const { action, ...payload } = body;
      if (!["review", "history", "publish", "bulk-review", "approve-starter", "edit", "reclassify", "feedback-review"].includes(action)) {
        return Response.json({ error: "Unknown review action" }, { status: 400 });
      }
      try {
        const result = await post(`/v1/admin/pedagogy/${action}`, payload);
        if (action === "publish") invalidate();
        return Response.json(result);
      } catch (err) {
        return Response.json({ error: err.message }, { status: err.status || 502 });
      }
    },
  };
}
