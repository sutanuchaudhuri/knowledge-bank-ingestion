export const GENERATED_COACHING_NOTICE = "Generated coaching (PENDING, not expert reviewed).";

export function hasGeneratedCoaching(event) {
  return (event.content?.parts ?? []).some((part) =>
    !part.thought && part.functionResponse?.name === "get_next_hint" &&
    part.functionResponse.response?.provenance?.review_status === "PENDING"
  );
}

const TOOL_STAGES = {
  search_problems: "Searching graph, vector and text evidence",
  search_practice_problems: "Finding complete practice problems",
  get_practice_problem: "Verifying statement, diagram and source",
  get_problem_learning_context: "Loading problem and graph-linked learning context",
  prepare_problem_guidance: "Consulting stored solutions privately to choose a teaching route",
  search_concepts: "Matching the topic to the concept taxonomy",
  get_prerequisite_path: "Checking prerequisite relationships",
  get_next_hint: "Preparing one provisional coaching hint",
  formatter_agent: "Formatting the explanation",
  pedagogy_agent: "Building a grounded teaching plan",
  report_pedagogy_feedback: "Recording the relevance report for review",
  advance_topic_lesson: "Checking the current lesson checkpoint",
  control_topic_lesson: "Updating the lesson path",
  get_topic_lesson: "Restoring the current learning stage",
  retrieval_audit_agent: "Auditing the retrieved topic evidence",
};

export function toolEvidence(name, response) {
  if (!response || typeof response !== "object" || response.error) return [];
  const evidence = [];
  const add = (label, status = "complete") => evidence.push({ type: "activity", label, status });
  const count = (value) => Array.isArray(value) ? value.length : null;
  if (["pedagogy_agent", "advance_topic_lesson", "control_topic_lesson", "get_topic_lesson"].includes(name)
      && response.progress && Array.isArray(response.progress.stages)) {
    evidence.push({ type: "progress", progress: response.progress });
  }
  if (["search_problems", "search_practice_problems"].includes(name)) {
    const retrieval = response.retrieval;
    if (retrieval?.graph === "queried") {
      const n = retrieval.graph_candidates;
      add(`Graph queried${Number.isSafeInteger(n) && n >= 0 ? ` · ${n} candidates` : ""}`);
    } else if (retrieval?.graph === "unavailable") add("Graph unavailable · degraded retrieval", "stopped");
    else if (retrieval?.graph === "disabled") add("Graph retrieval disabled", "stopped");
    if (typeof retrieval?.semantic === "boolean") add(`Vector search ${retrieval.semantic ? "enabled" : "disabled"}`, retrieval.semantic ? "complete" : "stopped");
    if (typeof retrieval?.lexical === "boolean") add(`Text search ${retrieval.lexical ? "enabled" : "disabled"}`, retrieval.lexical ? "complete" : "stopped");
    if (count(response.results) !== null) add(`${count(response.results)} ${name === "search_practice_problems" ? "complete practice problems" : "retrieval matches"} returned`);
    if (Number.isSafeInteger(response.skipped_incomplete) && response.skipped_incomplete > 0) add(`${response.skipped_incomplete} incomplete candidates excluded`);
  }
  if (name === "get_problem_learning_context") {
    if (response.problem && typeof response.problem === "object") add("Canonical problem loaded · answer-free");
    const status = response.metadata_status;
    if (["automatic", "reviewed", "unenriched"].includes(status)) {
      const n = count(response.skills);
      add(status === "unenriched" ? "No reviewed skill metadata available" :
        `${n ?? 0} graph-linked skills · ${status === "automatic" ? "machine-approved, not human verified" : "reviewed"}`,
      status === "reviewed" ? "complete" : "stopped");
    }
    for (const field of ["concepts", "techniques", "prerequisites"]) {
      if (count(response[field]) !== null) add(`${count(response[field])} ${field} returned`);
    }
  }
  if (name === "get_next_hint" && response.provenance?.review_status === "PENDING") add("Generated hint · pending expert review", "stopped");
  if (name === "prepare_problem_guidance") {
    evidence.push(...toolEvidence("get_problem_learning_context", response.context));
    if (response.status === "ready" && Array.isArray(response.stages)) {
      add(`${response.stages.length} teaching stages prepared · one checkpoint at a time`);
    }
    if (Number.isSafeInteger(response.diagram_count)) add(`${response.diagram_count} source diagrams loaded`);
  }
  if (["prepare_problem_guidance", "get_next_hint"].includes(name)) {
    const references = response.solution_evidence;
    if (references?.status === "available" && Number.isSafeInteger(references.references_considered)) {
      add(`${references.references_considered} stored solution records consulted for guidance`);
      if (Array.isArray(references.sources) && references.sources.some((source) => source.verification_status !== "VERIFIED")) {
        add("Solution references include unverified records · not correctness certification", "stopped");
      }
    } else if (references?.status === "unavailable") add("No stored solution reference available · guidance is not solution-grounded", "stopped");
  }
  if (name === "pedagogy_agent" && response.matched === true) {
    if (response.intent === "LEARN_TOPIC" && Number.isSafeInteger(response.current_unit)) {
      add(`Topic lesson · step ${response.current_unit + 1} of ${response.unit_count}`);
      if (response.artifact_status === "rendered") add("Validated instructional diagram prepared");
      if (response.artifact_status === "unavailable") add("Instructional diagram unavailable", "stopped");
    }
    if (Array.isArray(response.plan_steps)) add(`${response.plan_steps.length} teaching stages prepared`);
    if (Array.isArray(response.practice)) add(`${response.practice.length} complete step-supported candidates`);
    add("Published annotations · applicability still needs checking", "stopped");
  }
  if (name === "advance_topic_lesson" && Number.isSafeInteger(response.completed_checkpoints)) {
    add(`${response.completed_checkpoints} lesson checkpoints completed · not a mastery certification`);
  }
  if (name === "retrieval_audit_agent" && response.review_status === "PENDING") {
    add("Evidence audit pending human review · no canonical mutation", "stopped");
  }
  if (name === "report_pedagogy_feedback" && response.feedback_id) add(`Relevance report ${response.status === "PENDING" ? "queued for review" : "already recorded"} · annotations unchanged`, "stopped");
  if (Array.isArray(response.warnings) && response.warnings.length) add(`${response.warnings.length} evidence limitations reported · see tutor explanation`, "stopped");
  return evidence;
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
          updates.push({ type: "activity", label: TOOL_STAGES[part.functionCall.name] || `Calling ${part.functionCall.name}`, status: "running" });
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
        updates.push(...toolEvidence(part.functionResponse.name, response));
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
