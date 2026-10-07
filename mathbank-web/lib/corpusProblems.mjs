export function tutorProblemHref(code) {
  return `/?problem=${encodeURIComponent(code)}`;
}

export function problemDiscussionPrompt(code) {
  return `Help me think through ${code}. Load the canonical problem and its diagrams first, then guide me without revealing the full solution.`;
}

export function hasQuestionText(problem) {
  return typeof problem.statement_text === "string" && Boolean(problem.statement_text.trim())
    && !problem.statement_text.trim().startsWith("[Placeholder]");
}

export function relatedProblemRequest(problem) {
  const tags = [...(problem.concepts || []), ...(problem.techniques || [])]
    .map((tag) => tag.name).filter(Boolean);
  const query = (tags.length ? [...new Set(tags)].join(" ") : hasQuestionText(problem) ? problem.statement_text : "").trim().slice(0, 2000);
  return query ? {
    query, limit: 7, retrieval: { semantic: false, lexical: true, graph: true },
  } : null;
}

export function relatedCandidates(results, code) {
  const seen = new Set([code]);
  return results.filter((problem) => {
    if (!problem.canonical_code || seen.has(problem.canonical_code)) return false;
    seen.add(problem.canonical_code);
    return true;
  }).slice(0, 6);
}

export async function corpusJson(url, options) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || `Could not load corpus data (${response.status}).`);
  return body;
}
