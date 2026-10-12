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
  "solution-routes": { type: "HAS_ROUTE", from: "Solution", to: "RouteRelease", title: "Published solution routes", pedagogical: true },
  "route-steps": { type: "HAS_STEP", from: "RouteRelease", to: "RouteStep", title: "Route checkpoints", pedagogical: true },
  "step-requires-technique": { type: "REQUIRES", from: "RouteStep", to: "Technique", title: "Step prerequisites · techniques", pedagogical: true },
  "step-requires-skill": { type: "REQUIRES", from: "RouteStep", to: "Skill", title: "Step prerequisites · skills", pedagogical: true },
  "step-requires-concept": { type: "REQUIRES", from: "RouteStep", to: "Concept", title: "Step prerequisites · concepts", pedagogical: true },
  "step-produces": { type: "PRODUCES", from: "RouteStep", to: "Claim", title: "Step outputs", pedagogical: true },
  "step-uses-claim": { type: "USES_CLAIM", from: "RouteStep", to: "Claim", title: "Earlier claims used", pedagogical: true },
  "step-dependencies": { type: "DEPENDS_ON", from: "RouteStep", to: "RouteStep", title: "Checkpoint dependencies", pedagogical: true },
  "step-misconceptions": { type: "CAN_TRIGGER", from: "RouteStep", to: "Misconception", title: "Possible misconceptions", pedagogical: true },
  "step-checks": { type: "CHECKED_BY", from: "RouteStep", to: "LearningItem", title: "Checkpoint probes", pedagogical: true },
  "step-theory": { type: "EXPLAINED_BY", from: "RouteStep", to: "TheoryItem", title: "Checkpoint recaps", pedagogical: true },
  "misconception-remediation": { type: "REMEDIATED_BY", from: "Misconception", to: "TheoryItem", title: "Misconception recaps", pedagogical: true },
  "misconception-diagnosis": { type: "DIAGNOSED_BY", from: "Misconception", to: "LearningItem", title: "Misconception probes", pedagogical: true },
  // BUG-2 fix (requirements/50): Misconception nodes previously had zero direct edges to
  // the taxonomy (Concept/Skill/Technique) — only to the per-checkpoint process layer
  // above. ENR-1/ENR-4 (requirements/51) superseded the original derived-join workaround
  // (etl/project_misconception_relations.py) with a direct projection from the canonical
  // `knowledge.misconception_taxonomy_link` table, folded into route_projection.py itself
  // so it survives that projector's atomic rebuild instead of being wiped by it. Split
  // into three tabs (one per target label) to match this file's existing convention (see
  // step-requires-technique/-skill/-concept above) rather than one mixed-label view.
  "misconception-concepts": { type: "RELATES_TO", from: "Misconception", to: "Concept", title: "Misconception → Concept", pedagogical: true },
  "misconception-skills": { type: "RELATES_TO", from: "Misconception", to: "Skill", title: "Misconception → Skill", pedagogical: true },
  "misconception-techniques": { type: "RELATES_TO", from: "Misconception", to: "Technique", title: "Misconception → Technique", pedagogical: true },
  "theory-techniques": { type: "EXPLAINS", from: "TheoryItem", to: "Technique", title: "Theory explains technique", pedagogical: true },
  // ENR-4 (requirements/51): TheoryItem/LearningItem assets' own taxonomy_node_ids were
  // previously only wired up for TECHNIQUE-type targets, silently dropping the
  // CONCEPT/SKILL/SUBCONCEPT majority (confirmed live: ~88% of references). These four
  // new tabs surface that previously-dropped signal using the same relation type as
  // their Technique-target sibling above (EXPLAINS/PRACTICES), consistent with this
  // file's existing convention of reusing one relation type across several label pairs.
  "theory-concepts": { type: "EXPLAINS", from: "TheoryItem", to: "Concept", title: "Theory explains concept", pedagogical: true },
  "theory-skills": { type: "EXPLAINS", from: "TheoryItem", to: "Skill", title: "Theory explains skill", pedagogical: true },
  "item-techniques": { type: "PRACTICES", from: "LearningItem", to: "Technique", title: "Practice targets", pedagogical: true },
  "item-concepts": { type: "PRACTICES", from: "LearningItem", to: "Concept", title: "Practice targets (concepts)", pedagogical: true },
  "item-skills": { type: "PRACTICES", from: "LearningItem", to: "Skill", title: "Practice targets (skills)", pedagogical: true },
  "item-misconceptions": { type: "TESTS_MISCONCEPTION", from: "LearningItem", to: "Misconception", title: "Diagnostic targets", pedagogical: true },
  // ENR-2 (requirements/51): embedding-based semantic similarity — the direct fix for
  // "no similarity search happening in the graph at all". Precomputed top-K cosine-
  // similarity pairs (pgvector, text-embedding-3-small), projected as SIMILAR_TO edges
  // scoped within each label (never cross-label — comparing a Concept's embedding
  // against a Skill's is not a meaningful "similar" signal even if vectors are close).
  "misconception-similar": { type: "SIMILAR_TO", from: "Misconception", to: "Misconception", title: "Similar misconceptions", pedagogical: true },
  "concept-similar": { type: "SIMILAR_TO", from: "Concept", to: "Concept", title: "Similar concepts", pedagogical: true },
  "skill-similar": { type: "SIMILAR_TO", from: "Skill", to: "Skill", title: "Similar skills", pedagogical: true },
  "technique-similar": { type: "SIMILAR_TO", from: "Technique", to: "Technique", title: "Similar techniques", pedagogical: true },
  // BUG-3 fix (requirements/50): a "solution-approaches" entry used to live here, pointing
  // at `USES_APPROACH` — a relationship type that is never created anywhere in the graph
  // (confirmed live via `CALL db.relationshipTypes()`), so the tab was permanently dead
  // ("No relationships found" forever). Removed rather than repointed at an existing type:
  // the only real candidate (Problem -> Technique, `USES_TECHNIQUE`) is already the
  // separate "Problem → Technique" corpus view, and a second tab showing identical data
  // under a different name would just be a confusing duplicate, not a fix. Nav/overview
  // table/[rel] routing all derive from this object, so removing the key alone retires
  // the dead tab everywhere. Re-add once a real Solution-specific "approach" relationship
  // is authored and projected.
};

export const GRAPH_DEFAULT_LIMIT = 1000;
export const GRAPH_LIMIT_OPTIONS = [150, 500, 1000, 2500, 5000];
export const GRAPH_MAX_LIMIT = 5000;

/** Short, single-line label from a long free-text field (question/description); used
 * where the node's own `title` is a hardcoded positional boilerplate, not real content
 * (requirements/51 ENR-7). */
function truncate(text, max = 80) {
  if (!text) return null;
  const flat = String(text).replace(/\s+/g, " ").trim();
  return flat.length > max ? `${flat.slice(0, max - 1)}…` : flat;
}

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
    case "RouteRelease":
      return `${props.canonical_code || "Route"} · v${props.release_version ?? "?"}`;
    case "RouteStep":
      return `Checkpoint ${props.step_index ?? "?"}`;
    case "Claim":
    case "Misconception":
      // ENR-7 fix (requirements/51): these two kinds' `title` is a hardcoded positional
      // boilerplate ("Step 4 common error"/"Step 1 result", confirmed live — not real
      // content); the actual LLM-generated text is in `description`. TheoryItem's title
      // (handled below) is genuinely descriptive, so it is treated differently.
      return truncate(props.description) || props.title || props.asset_key || label;
    case "TheoryItem":
      return props.title || props.asset_key || label;
    case "LearningItem":
      // Two different LearningItem populations share this label: the textbook-import one
      // (external_id/book_code, no title) and the route-diagnostic one (title is
      // genuinely descriptive here, e.g. "Step 4 diagnostic" is boilerplate too — prefer
      // the actual question text instead).
      return truncate(props.question) || props.title || props.external_id || props.asset_key || label;
    default:
      return props.canonical_id || label;
  }
}
