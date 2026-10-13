// Admin widget gallery (requirements 27/29): renders deterministic FAST-path specs from mathbank-rest
// (/v1/widgets/generate, store=false — no model call, nothing persisted) through the shared WidgetHost,
// plus a playground for the student input add-ons (math composer, quick/AI format, voice).
import { restAdminPost, restGet } from "../../../../lib/restClient.js";
import WidgetGallery from "./WidgetGallery.jsx";
import { Callout, PageHeader, Pill } from "../../../_components/ui.jsx";

export const dynamic = "force-dynamic";

const SAMPLES = [
  { intent: "power of a point", context: {} },
  { intent: "intersecting chords", context: {} },
  { intent: "triangle angle", context: {} },
  { intent: "poll", context: { prompt: "Which product equals $PT^2$?", aggregate: { option_counts: { "PA·PB": 7, "PA+PB": 2, "PB²": 1 }, option_percentages: { "PA·PB": 70, "PA+PB": 20, "PB²": 10 }, response_count: 10 } } },
  { intent: "progress", context: { steps: [{ label: "Draw the secant through $P$", status: "DONE" }, { label: "Use similar triangles $PAC \\sim PDB$", status: "DONE" }, { label: "Conclude $PA \\cdot PB = PC \\cdot PD$" }] } },
  { intent: "table", context: { columns: ["Position of $P$", "Sign of power"], rows: [["outside", "$> 0$"], ["on the circle", "$= 0$"], ["inside", "$< 0$"]] } },
];

export default async function WidgetsPage() {
  let registry = [];
  const samples = [];
  let error = null;
  try {
    registry = (await restGet("/v1/widgets/registry")).widget_types || [];
    for (const s of SAMPLES) {
      const out = await restAdminPost("/v1/widgets/generate", { ...s, store: false });
      samples.push({ intent: s.intent, spec: out.spec, valid: out.validation?.valid, errors: out.validation?.errors || [], fallback: out.fallback || false });
    }
  } catch (err) {
    error = err.message;
  }
  return (
    <div>
      <PageHeader icon="puzzle" title="Widgets & student input add-ons"
        subtitle="Whitelisted widget specs rendered by mathbank-widgets — the same renderer as the tutor chat and live classroom."
        pills={<Pill tone="neutral" icon="lightning">Fast path · nothing stored</Pill>} />
      {error && <Callout tone="danger" title="Could not load widgets">{error}</Callout>}
      <WidgetGallery registry={registry} samples={samples} />
    </div>
  );
}
