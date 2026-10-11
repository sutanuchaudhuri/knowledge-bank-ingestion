// Admin Manim Video Studio catalog-promotion proxy (requirements/60 §7): review
// candidate render jobs from the standalone mathbank-manim-studio service, promote one
// into the canonical visual.scene_spec catalog, then validate/approve it. Admin session
// required for every operation (write-capable, unlike the read-only knowledge-gaps proxy).

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function requireUuid(id) {
  return typeof id === "string" && UUID_RE.test(id) ? id : null;
}

export function createAdminManimStudioHandlers({ hasSession, get, post, video }) {
  async function withSession(handler) {
    if (!(await hasSession())) return Response.json({ error: "Admin login required" }, { status: 401 });
    try {
      return await handler();
    } catch (err) {
      return Response.json({ error: err.message }, { status: err.status || 502 });
    }
  }

  return {
    async getCandidates() {
      return withSession(async () =>
        Response.json(await get("/v1/admin/interaction-templates/scenes/promotable-candidates"))
      );
    },
    async getScenes() {
      return withSession(async () =>
        Response.json(await get("/v1/admin/interaction-templates/scenes"))
      );
    },
    async getScene(id) {
      const sceneId = requireUuid(id);
      if (!sceneId) return Response.json({ error: "id must be a uuid" }, { status: 400 });
      return withSession(async () =>
        Response.json(await get(`/v1/admin/interaction-templates/scenes/${sceneId}`))
      );
    },
    async getSceneVideo(id) {
      const sceneId = requireUuid(id);
      if (!sceneId) return Response.json({ error: "id must be a uuid" }, { status: 400 });
      if (!(await hasSession())) return Response.json({ error: "Admin login required" }, { status: 401 });
      try {
        const upstream = await video(`/v1/admin/interaction-templates/scenes/${sceneId}/video`);
        return new Response(upstream.body, {
          headers: { "Content-Type": "video/mp4", "Cache-Control": "private, no-store" },
        });
      } catch (err) {
        return Response.json({ error: err.message }, { status: err.status || 502 });
      }
    },
    async promote(request) {
      return withSession(async () => {
        const body = await request.json();
        if (!body.render_job_id || !body.canonical_code) {
          return Response.json({ error: "render_job_id and canonical_code are required" }, { status: 400 });
        }
        return Response.json(await post("/v1/admin/interaction-templates/scenes/promote", body));
      });
    },
    async validate(id) {
      const sceneId = requireUuid(id);
      if (!sceneId) return Response.json({ error: "id must be a uuid" }, { status: 400 });
      return withSession(async () =>
        Response.json(await post(`/v1/admin/interaction-templates/scenes/${sceneId}/validate`, {}))
      );
    },
    async approve(id) {
      const sceneId = requireUuid(id);
      if (!sceneId) return Response.json({ error: "id must be a uuid" }, { status: 400 });
      return withSession(async () =>
        Response.json(await post(`/v1/admin/interaction-templates/scenes/${sceneId}/approve`, {}))
      );
    },
  };
}
