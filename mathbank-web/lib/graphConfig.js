// Whitelisted relationship views for /api/graph/relationship/[rel]. The slug is the
// URL segment; type/from/to are literal Cypher identifiers we control (never built
// from request input), so interpolating them into queries is safe.
// Shape confirmed live against the mathbank Neo4j instance (see mathbank-graph).
export const RELATIONSHIPS = {
  "has-paper": { type: "HAS_PAPER", from: "Competition", to: "Paper", title: "Competition → Paper" },
  "has-problem": { type: "HAS_PROBLEM", from: "Paper", to: "Problem", title: "Paper → Problem" },
  "has-solution": { type: "HAS_SOLUTION", from: "Problem", to: "Solution", title: "Problem → Solution" },
  "tests": { type: "TESTS", from: "Problem", to: "Concept", title: "Problem → Concept (tests)" },
  "uses-technique": { type: "USES_TECHNIQUE", from: "Problem", to: "Technique", title: "Problem → Technique" },
  "concept-relation": { type: "CONCEPT_RELATION", from: "Concept", to: "Concept", title: "Concept → Concept" },
  "requires-skill": { type: "REQUIRES", from: "Problem", to: "Skill", title: "Required skills", pedagogical: true },
  "practices-skill": { type: "PRACTICES", from: "Problem", to: "Skill", title: "Practiced skills", pedagogical: true },
  "tests-skill": { type: "TESTS", from: "Problem", to: "Skill", title: "Tested skills", pedagogical: true },
  "skill-concepts": { type: "PART_OF", from: "Skill", to: "Concept", title: "Skill → Concept", pedagogical: true },
  "skill-prerequisites": { type: "PREREQUISITE_OF", from: "Skill", to: "Skill", title: "Skill prerequisites", pedagogical: true },
  "skill-hierarchy": { type: "PART_OF", from: "Skill", to: "Skill", title: "Skill hierarchy", pedagogical: true },
  "concept-hierarchy": { type: "PART_OF", from: "Concept", to: "Concept", title: "Concept hierarchy", pedagogical: true },
  "concept-prerequisites": { type: "PREREQUISITE_OF", from: "Concept", to: "Concept", title: "Concept prerequisites", pedagogical: true },
  "skill-builds-on": { type: "BUILDS_ON", from: "Skill", to: "Skill", title: "Useful prior skills", pedagogical: true },
};

export const GRAPH_DEFAULT_LIMIT = 1000;
export const GRAPH_LIMIT_OPTIONS = [150, 500, 1000, 2500, 5000];
export const GRAPH_MAX_LIMIT = 5000;

/** Picks a human-readable display string per node label from its Neo4j properties. */
export function labelOf(label, props) {
  switch (label) {
    case "Competition":
      return props.name || props.external_code || "Competition";
    case "Paper":
      return props.external_code || props.paper_code || "Paper";
    case "Problem":
      return props.canonical_code || "Problem";
    case "Solution":
      return `${props.solution_kind || "Solution"} (rev ${props.revision ?? "?"})`;
    case "Concept":
    case "Skill":
      return props.name || "Concept";
    case "Technique":
      return props.name || "Technique";
    default:
      return props.canonical_id || label;
  }
}
