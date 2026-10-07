export function orderedSteps(steps = []) {
  return [...steps].sort((a, b) => a.ordinal - b.ordinal).map((s, i) => ({ ...s, ordinal: i + 1, evidence_ids: s.evidence_ids || [] }));
}
export const STEP_TYPES = ["SETUP", "OBSERVATION", "CONSTRUCTION", "THEOREM_SELECTION", "THEOREM_APPLICATION", "ANGLE_RELATION", "LENGTH_RELATION", "SIMILARITY_CLAIM", "CONGRUENCE_CLAIM", "RATIO", "ALGEBRA", "CASE", "INTERMEDIATE_RESULT", "CONCLUSION", "QUESTION_OR_UNCERTAINTY"];
export function transcriptionPayload(version, steps, regions) {
  return {
    expected_version: version,
    steps: orderedSteps(steps).map(({ step_id, ordinal, plain_text = "", latex_text = "", step_type = "OBSERVATION", confidence, evidence_ids }) => ({
      ...(step_id ? { step_id } : {}), ordinal, plain_text, latex_text, step_type, confidence: confidence ?? 1, evidence_ids,
    })),
    regions: regions.map(({ region_id, media_asset_id, page_number, x_norm, y_norm, width_norm, height_norm, start_ms, end_ms, region_type, reading_order, confidence }) => ({
      ...(region_id ? { region_id } : {}), media_asset_id, page_number, x_norm, y_norm, width_norm, height_norm, start_ms, end_ms, region_type, reading_order, confidence: confidence ?? 1,
    })),
  };
}
export function intervalLabel(region) {
  const format = (ms) => {
    const seconds = Math.max(0, Number(ms)) / 1000;
    return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${(seconds % 60).toFixed(1).padStart(4, "0")}`;
  };
  return `${format(region.start_ms)}–${format(region.end_ms)}`;
}
export function isApprovedCurrent(submission) {
  if (!submission) return false;
  // Approval ordinals and transcription versions are independent counters.
  return (submission.approvals || []).some((a) => a.transcription_version === submission.transcription_version)
    || (submission.approved_transcription_version != null && submission.approved_transcription_version === submission.transcription_version);
}
export function currentAssessment(submission, stepId, dirty = false) {
  if (dirty || !isApprovedCurrent(submission)) return null;
  return [...(submission.assessments || [])].reverse().find((a) =>
    a.step_id === stepId && a.transcription_version === submission.transcription_version) || null;
}
export function runtimeErrorMessage(code) {
  const messages = {
    TRANSCRIPTION_UNAVAILABLE: "Transcription is unavailable right now. Your original is saved; add evidence regions and enter the transcription manually, or retry later.",
    ANALYSIS_UNAVAILABLE: "Analysis is unavailable right now. Your approved attempt is still saved; you can continue reviewing it and retry analysis later.",
    STUDENT_WORK_UNRELATED_TO_PROBLEM: "This work appears to address a different problem. MathBank will not critique it under the current problem; choose the matching problem and upload it there.",
    WORK_CONTEXT_UNVERIFIED: "MathBank could not verify that this work matches the current problem, so it did not critique it. Verify the problem and start a new submission.",
    MEDIA_SIZE_LIMIT: "Choose a file under 20 MB.",
    ASSET_COUNT_LIMIT: "A submission can hold up to 10 original assets.",
    UNSUPPORTED_MEDIA_TYPE: "Choose a PNG, JPEG, PDF, or supported short audio/video file.",
    PDF_PAGE_OR_PASSWORD_LIMIT: "Choose an unencrypted PDF with at most 10 pages.",
    RAW_MEDIA_PURGED: "The original media was purged. Your approved structured attempt is retained.",
    OBJECT_STORE_UNAVAILABLE: "Private media storage is unavailable. Your structured work is unchanged; try again later.",
    OBJECT_STORAGE_UNAVAILABLE: "Private media storage is unavailable. Your structured work is unchanged; try again later.",
  };
  return messages[code];
}
export async function runtimeJson(url, method = "GET", payload) {
  const response = await fetch(url, {
    method, cache: "no-store",
    ...(payload !== undefined ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) } : {}),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body?.detail;
    const message = response.status === 409 ? "This submission changed. Reload the saved version before editing again."
      : runtimeErrorMessage(detail?.code) || (typeof detail === "string" ? detail : detail?.message || "The request could not be completed.");
    const error = new Error(message);
    error.status = response.status;
    error.code = detail?.code;
    throw error;
  }
  return body;
}
