export function parseProblemReference(input) {
  const value = input.trim();
  if (!value) throw new Error("Enter a topic, question text, contest reference or problem code.");
  if (/^[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+$/.test(value)) {
    return { code: value.toUpperCase() };
  }
  const match = /^(?:please\s+)?(amc\s*(8|10|12)|aime)\s*([ab]|ii|i)?\s+(\d{4})\s*([ab]|ii|i)?\s*(?:problem|question|q|#)\s*(\d{1,3})$/i.exec(value);
  if (!match) return { query: value };
  const competition = match[2] ? `AMC${match[2]}` : "AIME";
  const before = match[3]?.toUpperCase(), after = match[5]?.toUpperCase();
  if (before && after && before !== after) throw new Error("Use one paper version, such as AMC 10A or AMC 10B.");
  const paper = before || after || null;
  const year = Number(match[4]), number = Number(match[6]);
  if (year < 1900 || year > 2200 || number < 1 || number > (competition === "AIME" ? 15 : 25)) {
    throw new Error("Check the contest year and problem number.");
  }
  if (paper && !(competition === "AIME" ? ["I", "II"] : competition === "AMC8" ? [] : ["A", "B"]).includes(paper)) {
    throw new Error("Use A/B for AMC 10 or 12, I/II for AIME, or no paper version for AMC 8.");
  }
  return { competition, year, number, paper };
}

export async function resolveProblemReference(input, { signal, fetchPage }) {
  const reference = parseProblemReference(input);
  signal?.throwIfAborted();
  if (reference.code) return { kind: "exact", candidates: [{ canonical_code: reference.code }], warnings: [] };
  if (reference.query) {
    const result = await fetchPage("/api/rest/search", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: reference.query, limit: 10,
        retrieval: { semantic: false, lexical: true, graph: true },
      }),
      signal,
    });
    if (!Array.isArray(result?.results) || result.results.some((item) => !item || typeof item.canonical_code !== "string" || !item.canonical_code)
        || (result.warnings != null && (!Array.isArray(result.warnings) || result.warnings.some((warning) => typeof warning !== "string")))) {
      throw new Error("Problem search returned invalid data. Please retry.");
    }
    const candidates = [...new Map(result.results.map((item) => [item.canonical_code, {
      canonical_code: item.canonical_code, competition: item.competition, year: item.year,
      problem_number: item.problem_number, paper_code: item.paper_code,
    }])).values()];
    return { kind: "search", candidates, warnings: result.warnings || [] };
  }
  const matches = [];
  for (let page = 0; page < 10; page += 1) {
    const query = new URLSearchParams({
      competition: reference.competition, year_min: String(reference.year),
      year_max: String(reference.year), limit: "100", offset: String(page * 100),
    });
    signal?.throwIfAborted();
    const result = await fetchPage(`/api/rest/problems?${query}`, { signal });
    if (!Array.isArray(result?.items) || typeof result.hasMore !== "boolean"
        || result.items.some((item) => !item || typeof item.canonical_code !== "string" || !item.canonical_code)) {
      throw new Error("Problem lookup returned invalid data. Please retry.");
    }
    for (const problem of result.items) {
      if (Number(problem.problem_number) === reference.number
          && (!reference.paper || problem.paper_code?.toUpperCase() === reference.paper)) {
        matches.push({
          canonical_code: problem.canonical_code, competition: problem.competition,
          year: problem.year, paper_code: problem.paper_code, problem_number: problem.problem_number,
        });
      }
    }
    if (!result.hasMore) {
      const unique = [...new Map(matches.map((item) => [item.canonical_code, item])).values()];
      if (!unique.length) throw new Error("No matching problem was found. Check the year, paper version and problem number.");
      return { kind: "reference", candidates: unique, warnings: [] };
    }
  }
  throw new Error("Problem lookup exceeded its search limit. Choose a problem from the corpus instead.");
}
