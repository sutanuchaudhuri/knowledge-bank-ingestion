const NODE_FIELDS = [
  "canonical_code", "slug", "objective", "level", "description", "difficulty_band",
  "source", "confidence", "review_status", "approval_method", "verification_status",
  "conceptual_depth", "technical_load", "algebraic_load", "insight_required",
  "number_of_steps", "prerequisite_depth", "estimated_contest_level",
  "pedagogy_source", "pedagogy_confidence", "pedagogy_review_status", "pedagogy_approval_method",
  "problem_page_images", "solution_page_images",
];
const EDGE_FIELDS = ["role", "required_level", "importance", "confidence", "source", "assertion_source", "review_status", "approval_method", "relation_type", "strength"];

function pick(properties, fields) {
  const result = {};
  for (const field of fields) {
    const value = properties[field];
    if (value === null || value === undefined) continue;
    if (typeof value === "string" || typeof value === "boolean" || typeof value === "number") result[field] = value;
    else if (typeof value.toNumber === "function") result[field] = value.toNumber();
  }
  return result;
}

export function nodeMetadata(properties) {
  return pick(properties, NODE_FIELDS);
}

export function edgeMetadata(properties) {
  return pick(properties, EDGE_FIELDS);
}
