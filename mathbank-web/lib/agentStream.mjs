export const GENERATED_COACHING_NOTICE = "Generated coaching (PENDING, not expert reviewed).";

export function hasGeneratedCoaching(event) {
  return (event.content?.parts ?? []).some((part) =>
    !part.thought && part.functionResponse?.name === "get_next_hint" &&
    part.functionResponse.response?.provenance?.review_status === "PENDING"
  );
}

export async function* readSse(body) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let data = [];
  function parseLine(line) {
    if (line.endsWith("\r")) line = line.slice(0, -1);
    if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
    if (line === "" && data.length) {
      const value = data.join("\n");
      data = [];
      return value;
    }
    return null;
  }
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      let index;
      while ((index = buffer.indexOf("\n")) !== -1) {
        const event = parseLine(buffer.slice(0, index));
        buffer = buffer.slice(index + 1);
        if (event !== null && event !== "[DONE]") yield JSON.parse(event);
      }
      if (done) {
        if (buffer) parseLine(buffer);
        if (data.length && data.join("\n") !== "[DONE]") yield JSON.parse(data.join("\n"));
        break;
      }
    }
  } finally {
    await reader.cancel();
    reader.releaseLock();
  }
}

// ADK final events repeat accumulated partial text. Replace that draft rather
// than appending it, and never forward thought parts or raw tool payloads.
export function createAgentEventMapper() {
  const completed = [];
  const toolCalls = new Set();
  const toolResponses = new Set();
  let draft = "";
  let generatedCoaching = false;
  return (event) => {
    if (event.errorCode || event.errorMessage || event.error) {
      throw new Error(event.errorMessage || (typeof event.error === "string" ? event.error : event.error?.message) || `Agent error: ${event.errorCode || "stream failed"}`);
    }
    const updates = [];
    generatedCoaching ||= hasGeneratedCoaching(event);
    const parts = event.content?.parts ?? [];
    for (const part of parts) {
      if (part.thought) continue;
      if (part.functionCall) {
        const key = part.functionCall.id || part.functionCall.name;
        if (!toolCalls.has(key)) {
          toolCalls.add(key);
          if (!part.functionCall.id) toolResponses.delete(part.functionCall.name);
          updates.push({ type: "activity", label: `Calling ${part.functionCall.name}`, status: "running" });
        }
      }
      if (part.functionResponse) {
        const key = part.functionResponse.id || part.functionResponse.name;
        if (toolResponses.has(key)) continue;
        toolResponses.add(key);
        if (!part.functionResponse.id) toolCalls.delete(part.functionResponse.name);
        const response = part.functionResponse.response;
        const failed = response && typeof response === "object" && Boolean(response.error);
        updates.push({ type: "activity", label: `${part.functionResponse.name} ${failed ? "reported an error" : "completed"}`, status: failed ? "error" : "complete" });
      }
    }
    const text = event.author === "user" ? "" : parts.filter((p) => !p.thought && typeof p.text === "string").map((p) => p.text).join("");
    if (text) {
      if (event.partial) draft += text;
      else {
        completed.push(text);
        draft = "";
      }
      const answer = [...completed, draft].filter(Boolean).join("\n\n");
      updates.push({ type: "answer", text: generatedCoaching ? `${GENERATED_COACHING_NOTICE}\n\n${answer}` : answer });
    }
    return updates;
  };
}
