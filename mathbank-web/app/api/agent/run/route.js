import { createAgentEventMapper, readSse } from "../../../../lib/agentStream.mjs";

const AGENT_BASE_URL = process.env.MATHBANK_AGENT_BASE_URL || "http://127.0.0.1:8001";
const APP_NAME = "mathbank_tutor";

export async function POST(request) {
  let payload;
  try {
    payload = await request.json();
  } catch {
    return Response.json({ error: "Request body must be valid JSON" }, { status: 400 });
  }
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return Response.json({ error: "Request body must be a JSON object" }, { status: 400 });
  }
  const { userId, sessionId, text, stream = false } = payload;
  if (![userId, sessionId, text].every((value) => typeof value === "string" && value.trim())) {
    return Response.json({ error: "userId, sessionId and text are required" }, { status: 400 });
  }
  if (typeof stream !== "boolean") {
    return Response.json({ error: "stream must be a boolean" }, { status: 400 });
  }

  const upstreamController = new AbortController();
  const signal = AbortSignal.any([request.signal, upstreamController.signal]);
  let res;
  try {
    res = await fetch(`${AGENT_BASE_URL}/${stream ? "run_sse" : "run"}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal,
      body: JSON.stringify({
        app_name: APP_NAME,
        user_id: userId,
        session_id: sessionId,
        new_message: { role: "user", parts: [{ text }] },
        streaming: stream,
      }),
    });
  } catch (err) {
    return Response.json({ error: `Could not reach agent: ${err.message}` }, { status: 502 });
  }

  if (!res.ok) {
    return Response.json({ error: `agent run failed: ${res.status}` }, { status: res.status });
  }

  if (stream) {
    if (!res.body) return Response.json({ error: "Agent returned no stream" }, { status: 502 });
    const encoder = new TextEncoder();
    const events = readSse(res.body);
    const mapEvent = createAgentEventMapper();
    let finished = false;
    let hasAnswer = false;
    const body = new ReadableStream({
      async start(controller) {
        const emit = (event) => controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
        try {
          emit({ type: "activity", label: "Agent is preparing a response", status: "running" });
          for await (const event of events) {
            if (finished) break;
            for (const update of mapEvent(event)) {
              if (update.type === "answer") hasAnswer = true;
              emit(update);
            }
          }
          if (!finished) {
            if (!hasAnswer) throw new Error("Agent finished without an answer");
            emit({ type: "done" });
          }
        } catch (err) {
          if (!finished) emit({ type: "error", message: err.message });
        } finally {
          if (!finished) {
            finished = true;
            controller.close();
          }
        }
      },
      cancel() {
        finished = true;
        upstreamController.abort();
      },
    });
    return new Response(body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
      },
    });
  }

  const events = await res.json();
  const replyParts = [];
  for (const event of events) {
    const parts = event?.content?.parts || [];
    for (const part of parts) {
      if (part.text && !part.thought && event.author !== "user" && !event.partial) replyParts.push(part.text);
    }
  }
  if (!replyParts.length) return Response.json({ error: "Agent finished without an answer" }, { status: 502 });
  return Response.json({ reply: replyParts.join("\n") });
}
