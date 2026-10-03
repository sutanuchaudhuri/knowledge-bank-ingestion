// Server-side proxy to mathbank-agent's /run endpoint (same CORS rationale as ./session).
const AGENT_BASE_URL = process.env.MATHBANK_AGENT_BASE_URL || "http://127.0.0.1:8001";
const APP_NAME = "mathbank_tutor";

export async function POST(request) {
  const { userId, sessionId, text } = await request.json();

  const res = await fetch(`${AGENT_BASE_URL}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      app_name: APP_NAME,
      user_id: userId,
      session_id: sessionId,
      new_message: { role: "user", parts: [{ text }] },
    }),
  });

  if (!res.ok) {
    return Response.json({ error: `agent run failed: ${res.status}` }, { status: res.status });
  }

  const events = await res.json();
  const replyParts = [];
  for (const event of events) {
    const parts = event?.content?.parts || [];
    for (const part of parts) {
      if (part.text && event.author !== "user") replyParts.push(part.text);
    }
  }
  return Response.json({ reply: replyParts.join("\n") || "(no response)" });
}
