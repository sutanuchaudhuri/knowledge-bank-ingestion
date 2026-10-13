/** Split only explicitly labelled problem/source sections; never guess from prose. */
export function splitTutorProblem(text) {
  const source = String(text || "");
  const problem = /^[ \t]*(?:#{1,4}[ \t]+Problem\b|\*\*Problem(?=[ \t]*:|\*\*))[^\n]*$/im.exec(source);
  if (!problem) return null;
  const after = source.slice(problem.index + problem[0].length);
  const attribution = /^[ \t]*(?:\*\*Source(?=:|\*\*|[A-Z])|#{1,4}[ \t]+Source\b)(?:\*\*)?[ \t]*:?(?:\*\*)?[ \t]*([^\n]*)/m.exec(after);
  if (!attribution) return null;
  const inline = problem[0].replace(/^[ \t]*(?:#{1,4}[ \t]+|\*\*)Problem(?:\*\*)?[ \t]*:?(?:\*\*)?[ \t]*/i, "").replace(/\*\*[ \t]*$/, "");
  const statement = (inline + "\n" + after.slice(0, attribution.index)).trim();
  if (!statement) return null;
  const tail = after.slice(attribution.index + attribution[0].length);
  const boundary = tail.search(/\n\s*\n/);
  const continuation = boundary >= 0 ? tail.slice(0, boundary) : tail;
  return {
    intro: source.slice(0, problem.index).trim(),
    title: "Problem",
    statement,
    source: (attribution[1] + continuation).trim(),
    outro: boundary >= 0 ? tail.slice(boundary).trim() : "",
  };
}

export function geometryArtifactSource(node) {
  const code = node?.children?.find((child) => child.tagName === "code");
  const classes = code?.properties?.className || [];
  if (!(Array.isArray(classes) ? classes : [classes]).some((name) => ["language-geometry-artifact", "language-artifact-preview"].includes(name))) return null;
  const source = (code.children || []).map((child) => child.value || "").join("");
  if (source.length > 128000) return { error: "The generated diagram is too large." };
  try {
    const plan = JSON.parse(source);
    if (!["GEOMETRY", "ALGEBRA", "COMBINATORICS", "NUMBER_THEORY"].includes(plan?.subject) || !Array.isArray(plan.elements)) {
      return { error: "The generated diagram has an invalid geometry plan." };
    }
    return { plan };
  } catch { return { pending: true }; }
}
