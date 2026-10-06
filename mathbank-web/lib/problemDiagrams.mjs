export function mentionedProblemCodes(text, { includeEmbedded = false } = {}) {
  if (!includeEmbedded && /!\[[^\]]*\]\([^)]*\/api\/rest\/solve\/images\//.test(text)) return [];
  const pattern = /\b(?:PAPER_[A-Z0-9_]+_Q\d+|PRASOLOV_PGV1_CH\d+_P\d+|(?:AMC10|AMC12|AIME|HMMT|SMT|PUMAC|CHMMC|CMM|MPG|ARML|PURPLE)[A-Z0-9_]*_\d{4}_[A-Z0-9_]*Q\d+)\b/g;
  return [...new Set(text.match(pattern) || [])];
}

export function problemImageUrl(id, version = "2") {
  return `/api/rest/solve/images/${encodeURIComponent(id)}?v=${encodeURIComponent(version)}`;
}
