export const PIPELINE_STAGES = [
  ["download", "Download"], ["parse", "Parse"], ["ingest", "Postgres"],
  ["classify", "Classify"], ["vectors", "Vectors"], ["graph", "Corpus graph"],
  ["pedagogy", "Pedagogy"], ["pedagogy_graph", "Pedagogy graph"],
  ["relationships", "Taxonomy graph"],
];

export function formatPipelineTime(value) {
  if (!value) return "Not recorded";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Invalid timestamp" : date.toISOString().replace("T", " ").replace(".000Z", " UTC");
}

export function pipelineBadgeClass(status) {
  if (["COMPLETED", "DOWNLOADED", "PARSED"].includes(status)) return "text-bg-success";
  if (status === "FAILED") return "text-bg-danger";
  if (["PARTIAL", "STALLED"].includes(status)) return "text-bg-warning";
  if (status === "IN_PROGRESS") return "text-bg-primary";
  return "text-bg-secondary";
}
