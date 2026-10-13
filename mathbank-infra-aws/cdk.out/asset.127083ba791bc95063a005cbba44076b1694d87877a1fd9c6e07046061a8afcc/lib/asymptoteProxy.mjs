import { MAX_ASYMPTOTE_CHARS } from "./asymptoteRenderer.mjs";

export function createAsymptoteHandler({ authenticate, render }) {
  return async function POST(request) {
    if (request.headers.get("origin") !== new URL(request.url).origin) {
      return Response.json({ error: "Same-origin requests are required." }, { status: 403 });
    }
    try {
      if (!await authenticate()) {
        return Response.json({ error: "Sign in to render embedded diagrams." }, { status: 401 });
      }
    } catch (error) {
      console.error("Diagram authentication failed:", error.status || error.name);
      return Response.json({ error: "Diagram authentication could not be verified." }, { status: error.status || 503 });
    }
    let payload;
    try {
      const reader = request.body?.getReader();
      if (!reader) return Response.json({ error: "Provide diagram source." }, { status: 400 });
      const chunks = [];
      let length = 0;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        length += value.length;
        if (length > MAX_ASYMPTOTE_CHARS * 6 + 128) {
          await reader.cancel();
          return Response.json({ error: "Diagram request is too large." }, { status: 413 });
        }
        chunks.push(Buffer.from(value));
      }
      payload = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    } catch {
      return Response.json({ error: "Provide a valid JSON diagram request." }, { status: 400 });
    }
    try {
      const image = await render(payload?.source);
      return new Response(image, { headers: {
        "Content-Type": "image/png", "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "default-src 'none'; sandbox",
      } });
    } catch (error) {
      return Response.json({ error: error.message }, { status: error.status || 500 });
    }
  };
}
