// Client-safe helpers shared by the browser hook and the gateway (no node: imports).

/** Merge by sequence (dedupe on replay/reconnect), ordered, capped. */
export function mergeEvents(known, incoming, cap = 400) {
  const bySeq = new Map(known.map((e) => [e.sequence, e]));
  for (const e of incoming || []) if (e && !bySeq.has(e.sequence)) bySeq.set(e.sequence, e);
  return [...bySeq.values()].sort((a, b) => a.sequence - b.sequence).slice(-cap);
}

export const lastSequence = (events) => (events.length ? events[events.length - 1].sequence : 0);

/** Live activity aggregate → POLL_RESULT widget spec rendered by mathbank-widgets/WidgetHost. */
export function pollSpec(activity, aggregate, reveal) {
  const options = (activity?.options || []).map((o) => (typeof o === "object" ? String(o.key ?? o.id ?? o.label) : String(o)));
  return {
    widget_type: "POLL_RESULT",
    title: "Class responses",
    config: { prompt: activity?.prompt || aggregate?.prompt, options, counts: aggregate?.option_counts || {},
      percentages: aggregate?.option_percentages || {}, response_count: aggregate?.response_count || 0,
      correct_option: aggregate?.correct_option ?? null, reveal: Boolean(reveal) },
  };
}

export const optionLabel = (o) => (typeof o === "object" && o ? String(o.label ?? o.key ?? o.id) : String(o));
export const optionKey = (o) => (typeof o === "object" && o ? String(o.key ?? o.id ?? o.label) : String(o));

/** Messages a participant should see in the classroom feed. */
export const MESSAGE_TYPES = new Set(["tutor.message", "instructor.message"]);
export const STATUS_TYPES = new Set(["session.started", "session.paused", "session.resumed", "session.completed",
  "scene.changed", "topic.skipped", "activity.opened", "activity.revealed", "widget.shown", "widget.hidden",
  "instructor.takeover.started", "instructor.takeover.ended", "agent.locked", "branch.selected", "time.adjusted"]);
/** Events that change the snapshot (stage/time/topic/control) — trigger a debounced state refresh. */
export const needsRefresh = (e) => !MESSAGE_TYPES.has(e.event_type) && e.event_type !== "activity.response.accepted";

export function fmtSeconds(s) {
  const v = Math.abs(Math.round(Number(s) || 0));
  return `${s < 0 ? "-" : ""}${Math.floor(v / 60)}:${String(v % 60).padStart(2, "0")}`;
}
