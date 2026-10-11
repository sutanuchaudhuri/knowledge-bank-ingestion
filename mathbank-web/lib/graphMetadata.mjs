const NODE_FIELDS = [
  "canonical_code", "slug", "objective", "level", "description", "difficulty_band",
  "source", "confidence", "review_status", "approval_method", "verification_status",
  "conceptual_depth", "technical_load", "algebraic_load", "insight_required",
  "number_of_steps", "prerequisite_depth", "estimated_contest_level",
  "pedagogy_source", "pedagogy_confidence", "pedagogy_review_status", "pedagogy_approval_method",
  "problem_page_images", "solution_page_images",
  "route_release_id", "release_version", "step_index", "asset_key", "purpose",
  "difficulty_level", "conceptual_load", "insight_load", "projection_kind",
  // requirements/51 ENR-7: rich display content for route_asset-derived nodes
  // (Claim/Misconception/TheoryItem/diagnostic LearningItem), previously limited to
  // the generic asset_key.
  "title", "symptom", "why_wrong", "correct_model", "canonical_expression",
  "question", "expected_answer",
];
const EDGE_FIELDS = ["role", "required_level", "importance", "confidence", "source", "assertion_source", "review_status", "approval_method", "relation_type", "strength", "similarity"];

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
