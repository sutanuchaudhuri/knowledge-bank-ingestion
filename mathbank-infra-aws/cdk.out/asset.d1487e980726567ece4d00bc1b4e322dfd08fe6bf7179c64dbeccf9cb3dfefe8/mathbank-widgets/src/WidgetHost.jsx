"use client";
// Declarative widget renderer (fluid pack 09/10). Renders ONLY whitelisted widget_type specs produced by
// mathbank-rest (/v1/widgets/*, live sessions); it never evaluates code or raw HTML from a spec.
// Math text is rendered through the host app's `renderMath` (e.g. its KaTeX MathText) or shown as text.
import { useMemo } from "react";

const ACCENT = "#2563eb";
const MUTED = "#94a3b8";

function Caption({ text, renderMath }) {
  if (!text) return null;
  return <div className="small text-secondary mt-2">{renderMath ? renderMath(String(text)) : String(text)}</div>;
}

function opIndex(operations = []) {
  const idx = {};
  for (const op of Array.isArray(operations) ? operations : []) {
    for (const t of Array.isArray(op?.targets) ? op.targets : []) (idx[t] ||= []).push(op);
  }
  return idx;
}

const has = (ops, name) => (ops || []).some((o) => o.op === name);

function Geometry({ config, renderMath }) {
  const els = Array.isArray(config.elements) ? config.elements : [];
  const ops = useMemo(() => opIndex(config.operations), [config.operations]);
  const pts = Object.fromEntries(els.filter((e) => e.kind === "POINT").map((e) => [e.id, e]));
  const vb = Array.isArray(config.view_box) && config.view_box.length === 4 ? config.view_box : [0, 0, 100, 100];
  const unit = Math.max(vb[2], vb[3]) / 100;
  const style = (id, aux) => {
    const o = ops[id];
    const hi = has(o, "HIGHLIGHT") || has(o, "PULSE");
    return {
      stroke: hi ? ACCENT : aux ? MUTED : "#0f172a", strokeWidth: (hi ? 1.1 : 0.6) * unit, fill: "none",
      strokeDasharray: aux || has(o, "TRACE") ? `${2 * unit} ${1.4 * unit}` : undefined,
      opacity: has(o, "DIM") ? 0.25 : 1, className: has(o, "PULSE") ? "mbw-pulse" : has(o, "TRACE") ? "mbw-trace" : undefined,
    };
  };
  const hidden = (id) => has(ops[id], "HIDE") && !has(ops[id], "SHOW");
  const marks = [];
  for (const op of config.operations || []) {
    const segs = (op.targets || []).map((t) => els.find((e) => e.id === t)).filter((e) => e && pts[e.from] && pts[e.to]);
    if (op.op === "MARK_EQUAL" || op.op === "MARK_PARALLEL") {
      segs.forEach((s, i) => {
        const a = pts[s.from]; const b = pts[s.to];
        const mx = (a.x + b.x) / 2; const my = (a.y + b.y) / 2;
        const len = Math.hypot(b.x - a.x, b.y - a.y) || 1;
        const nx = (-(b.y - a.y) / len) * 1.6 * unit; const ny = ((b.x - a.x) / len) * 1.6 * unit;
        marks.push(op.op === "MARK_EQUAL"
          ? <line key={`m${op.op}${i}`} x1={mx - nx} y1={my - ny} x2={mx + nx} y2={my + ny} stroke={ACCENT} strokeWidth={0.7 * unit} />
          : <text key={`m${op.op}${i}`} x={mx} y={my} fontSize={4 * unit} fill={ACCENT} textAnchor="middle">›</text>);
      });
    }
    if (op.op === "MARK_PERPENDICULAR" && segs.length === 2) {
      const [s1, s2] = segs;
      const shared = [s1.from, s1.to].find((p) => p === s2.from || p === s2.to);
      if (shared) {
        const v = pts[shared];
        const u1 = pts[s1.from === shared ? s1.to : s1.from]; const u2 = pts[s2.from === shared ? s2.to : s2.from];
        const d = 3 * unit;
        const n = (p) => { const l = Math.hypot(p.x - v.x, p.y - v.y) || 1; return [(p.x - v.x) / l * d, (p.y - v.y) / l * d]; };
        const [ax, ay] = n(u1); const [bx, by] = n(u2);
        marks.push(<path key="perp" d={`M${v.x + ax},${v.y + ay} L${v.x + ax + bx},${v.y + ay + by} L${v.x + bx},${v.y + by}`}
          stroke={ACCENT} strokeWidth={0.5 * unit} fill="none" />);
      }
    }
    if (op.op === "SHOW_RATIO" && op.label) {
      marks.push(<text key={`ratio${marks.length}`} x={vb[0] + 2 * unit} y={vb[1] + 6 * unit} fontSize={4 * unit} fill={ACCENT}>{String(op.label)}</text>);
    }
  }
  return (
    <figure className="mb-0">
      <svg viewBox={vb.join(" ")} role="img" aria-label={config.caption ? String(config.caption) : "geometry diagram"}
        style={{ width: "100%", maxHeight: 360, background: "#fff" }}>
        <style>{".mbw-pulse{animation:mbwPulse 1.4s ease-in-out infinite}@keyframes mbwPulse{50%{opacity:.35}}" +
          ".mbw-trace{animation:mbwTrace 2s linear infinite}@keyframes mbwTrace{to{stroke-dashoffset:-20}}"}</style>
        {els.map((e) => {
          if (hidden(e.id)) return null;
          const st = style(e.id, e.kind === "AUXILIARY_CONSTRUCTION");
          const { className, ...attrs } = st;
          if (["SEGMENT", "AUXILIARY_CONSTRUCTION", "RAY", "LINE"].includes(e.kind) && pts[e.from] && pts[e.to]) {
            let a = pts[e.from]; let b = pts[e.to];
            if (e.kind !== "SEGMENT" && e.kind !== "AUXILIARY_CONSTRUCTION") {
              const k = 3; const dx = b.x - a.x; const dy = b.y - a.y;
              b = { x: a.x + dx * k, y: a.y + dy * k };
              if (e.kind === "LINE") a = { x: a.x - dx * (k - 1), y: a.y - dy * (k - 1) };
            }
            return <line key={e.id} className={className} x1={a.x} y1={a.y} x2={b.x} y2={b.y} {...attrs} />;
          }
          if (e.kind === "CIRCLE" && pts[e.center]) {
            const c = pts[e.center];
            const r = typeof e.radius === "number" ? e.radius
              : pts[e.through] ? Math.hypot(pts[e.through].x - c.x, pts[e.through].y - c.y) : 0;
            return <circle key={e.id} className={className} cx={c.x} cy={c.y} r={r} {...attrs} />;
          }
          if (e.kind === "POLYGON" && Array.isArray(e.points) && e.points.every((p) => pts[p])) {
            return <polygon key={e.id} className={className} points={e.points.map((p) => `${pts[p].x},${pts[p].y}`).join(" ")}
              {...attrs} fill={has(ops[e.id], "HIGHLIGHT") ? "rgba(37,99,235,.08)" : "none"} />;
          }
          if ((e.kind === "ANGLE" || e.kind === "ARC") && pts[e.from] && pts[e.to] && pts[e.vertex || e.center]) {
            const v = pts[e.vertex || e.center];
            const r = e.kind === "ANGLE" ? 5 * unit : Math.hypot(pts[e.from].x - v.x, pts[e.from].y - v.y);
            const p = (q) => { const l = Math.hypot(q.x - v.x, q.y - v.y) || 1; return [v.x + (q.x - v.x) / l * r, v.y + (q.y - v.y) / l * r]; };
            const [x1, y1] = p(pts[e.from]); const [x2, y2] = p(pts[e.to]);
            return <path key={e.id} className={className} d={`M${x1},${y1} A${r},${r} 0 0 1 ${x2},${y2}`} {...attrs} />;
          }
          return null;
        })}
        {marks}
        {els.filter((e) => (e.kind === "POINT" || e.kind === "LABEL") && !hidden(e.id)).map((e) => (
          <g key={`p${e.id}`} opacity={has(ops[e.id], "DIM") ? 0.25 : 1}>
            {e.kind === "POINT" && <circle cx={e.x} cy={e.y} r={1.1 * unit} fill={has(ops[e.id], "HIGHLIGHT") ? ACCENT : "#0f172a"} />}
            <text x={e.x + 1.8 * unit} y={e.y - 1.8 * unit} fontSize={4 * unit} fill="#0f172a">{String(e.label ?? (e.kind === "POINT" ? e.id : ""))}</text>
          </g>
        ))}
      </svg>
      <Caption text={config.caption} renderMath={renderMath} />
    </figure>
  );
}

function Bars({ rows, max, correct, reveal }) {
  const top = max || Math.max(1, ...rows.map((r) => Number(r.value) || 0));
  return (
    <div className="d-grid gap-2">
      {rows.map((r) => {
        const pct = Math.round(((Number(r.value) || 0) / top) * 100);
        const good = reveal && correct != null && String(r.label) === String(correct);
        return (
          <div key={String(r.label)}>
            <div className="d-flex justify-content-between small"><span>{String(r.label)}{good ? " ✓" : ""}</span><span className="text-secondary">{r.text ?? r.value}</span></div>
            <div className="progress" style={{ height: 8 }} role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
              <div className={`progress-bar ${good ? "bg-success" : ""}`} style={{ width: `${pct}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function asText(v) { return typeof v === "object" && v !== null ? (v.label ?? v.text ?? v.title ?? JSON.stringify(v)) : String(v ?? ""); }

function Graph({ config, renderMath }) {
  const nodes = (config.nodes || []).map((n) => (typeof n === "object" ? n : { id: n, label: n }));
  const edges = (config.edges || []).map((e) => (Array.isArray(e) ? { from: e[0], to: e[1] } : { from: e.from ?? e.source, to: e.to ?? e.target, label: e.label ?? e.type }));
  const level = {};
  nodes.forEach((n) => { level[n.id] = 0; });
  for (let i = 0; i < nodes.length; i += 1) for (const e of edges) if (e.from in level && e.to in level) level[e.to] = Math.max(level[e.to], level[e.from] + 1);
  const layers = {};
  nodes.forEach((n) => { (layers[level[n.id]] ||= []).push(n); });
  const depth = Object.keys(layers).length || 1;
  const pos = {};
  Object.entries(layers).forEach(([l, ns]) => ns.forEach((n, i) => { pos[n.id] = { x: ((i + 1) * 100) / (ns.length + 1), y: 8 + (Number(l) * 84) / Math.max(1, depth - 1) }; }));
  return (
    <figure className="mb-0">
      <svg viewBox="0 0 100 100" style={{ width: "100%", maxHeight: 320 }} role="img" aria-label="graph">
        {edges.filter((e) => pos[e.from] && pos[e.to]).map((e, i) => (
          <line key={i} x1={pos[e.from].x} y1={pos[e.from].y} x2={pos[e.to].x} y2={pos[e.to].y} stroke={MUTED} strokeWidth={0.5} />
        ))}
        {nodes.map((n) => (
          <g key={n.id}>
            <circle cx={pos[n.id].x} cy={pos[n.id].y} r={2.4} fill={n.id === config.current ? ACCENT : "#e2e8f0"} stroke={ACCENT} strokeWidth={0.4} />
            <text x={pos[n.id].x} y={pos[n.id].y + 6} fontSize={3.2} textAnchor="middle">{asText(n.label ?? n.id).slice(0, 28)}</text>
          </g>
        ))}
      </svg>
      <Caption text={config.caption} renderMath={renderMath} />
    </figure>
  );
}

function NumberLine({ config }) {
  const min = Number(config.min ?? 0); const max = Number(config.max ?? 10); const span = max - min || 1;
  const X = (v) => 5 + ((Number(v) - min) / span) * 90;
  const points = (config.points || []).map((p) => (typeof p === "object" ? p : { x: p }));
  return (
    <svg viewBox="0 0 100 24" style={{ width: "100%" }} role="img" aria-label="number line">
      <line x1={5} y1={12} x2={95} y2={12} stroke="#0f172a" strokeWidth={0.4} />
      {(config.intervals || []).map((iv, i) => <line key={i} x1={X(iv.from ?? iv[0])} y1={12} x2={X(iv.to ?? iv[1])} y2={12} stroke={ACCENT} strokeWidth={1.6} />)}
      {[min, max].map((v) => <text key={v} x={X(v)} y={20} fontSize={3} textAnchor="middle">{v}</text>)}
      {points.map((p, i) => <g key={i}><circle cx={X(p.x ?? p.value)} cy={12} r={1.2} fill={ACCENT} /><text x={X(p.x ?? p.value)} y={8} fontSize={3} textAnchor="middle">{asText(p.label ?? p.x ?? p.value)}</text></g>)}
    </svg>
  );
}

function CoordinateGraph({ config, renderMath }) {
  const [x0, x1] = Array.isArray(config.x_range) ? config.x_range : [-10, 10];
  const [y0, y1] = Array.isArray(config.y_range) ? config.y_range : [-10, 10];
  const X = (x) => ((x - x0) / (x1 - x0 || 1)) * 100; const Y = (y) => 100 - ((y - y0) / (y1 - y0 || 1)) * 100;
  return (
    <figure className="mb-0">
      <svg viewBox="0 0 100 100" style={{ width: "100%", maxHeight: 320 }} role="img" aria-label="coordinate graph">
        <line x1={0} y1={Y(0)} x2={100} y2={Y(0)} stroke={MUTED} strokeWidth={0.3} />
        <line x1={X(0)} y1={0} x2={X(0)} y2={100} stroke={MUTED} strokeWidth={0.3} />
        {(config.curves || []).map((c, i) => (
          <polyline key={i} fill="none" stroke={ACCENT} strokeWidth={0.6}
            points={(c.points || []).map(([x, y]) => `${X(x)},${Y(y)}`).join(" ")} />
        ))}
        {(config.points || []).map((p, i) => <g key={i}><circle cx={X(p.x)} cy={Y(p.y)} r={1} fill="#0f172a" /><text x={X(p.x) + 1.5} y={Y(p.y) - 1.5} fontSize={3}>{asText(p.label ?? "")}</text></g>)}
      </svg>
      <Caption text={config.caption} renderMath={renderMath} />
    </figure>
  );
}

/** Render one validated widget spec. Unknown types fall back to a neutral card (never executed). */
export default function WidgetHost({ spec, renderMath, className = "" }) {
  if (!spec || typeof spec !== "object") return null;
  const config = spec.config || {};
  const M = (t) => (renderMath ? renderMath(String(t ?? "")) : String(t ?? ""));
  let body;
  switch (spec.widget_type) {
    case "GEOMETRY_DIAGRAM":
    case "GEOMETRY_OVERLAY":
      body = <Geometry config={config} renderMath={renderMath} />; break;
    case "POLL_RESULT":
      body = (<>
        {config.prompt && <div className="fw-semibold mb-2">{M(config.prompt)}</div>}
        <Bars rows={(config.options || []).map((o) => ({ label: o, value: config.counts?.[o] ?? 0,
          text: `${config.counts?.[o] ?? 0}${config.percentages?.[o] != null ? ` · ${config.percentages[o]}%` : ""}` }))}
          correct={config.correct_option} reveal={config.reveal} />
        <div className="small text-secondary mt-2">{config.response_count ?? 0} responses</div>
      </>); break;
    case "BAR_CHART":
      body = <Bars rows={(config.bars || []).map((b) => ({ label: b.label, value: b.value }))} max={config.max} />; break;
    case "STEP_PROGRESS":
      body = (
        <ol className="list-group list-group-numbered">
          {(config.steps || []).map((s, i) => {
            const st = String(s.status || "PENDING").toUpperCase();
            return (
              <li key={i} className={`list-group-item d-flex justify-content-between align-items-start ${i === config.current ? "active" : ""}`}>
                <span className="ms-2 me-auto">{M(s.label)}</span>
                <span className={`badge ${st === "DONE" || st === "PASSED" ? "text-bg-success" : st === "FAILED" ? "text-bg-danger" : "text-bg-light"}`}>{st.toLowerCase()}</span>
              </li>
            );
          })}
        </ol>
      ); break;
    case "TABLE":
      body = (
        <div className="table-responsive"><table className="table table-sm mb-0">
          {Array.isArray(config.columns) && <thead><tr>{config.columns.map((c, i) => <th key={i}>{M(c)}</th>)}</tr></thead>}
          <tbody>{(config.rows || []).map((r, i) => <tr key={i}>{(Array.isArray(r) ? r : Object.values(r || {})).map((c, j) => <td key={j}>{M(c)}</td>)}</tr>)}</tbody>
        </table></div>
      ); break;
    case "COMPARISON":
      body = (
        <div className="table-responsive"><table className="table table-sm mb-0">
          <thead><tr><th>{M(config.left)}</th><th>{M(config.right)}</th></tr></thead>
          <tbody>{(config.rows || []).map((r, i) => <tr key={i}><td>{M(Array.isArray(r) ? r[0] : r.left)}</td><td>{M(Array.isArray(r) ? r[1] : r.right)}</td></tr>)}</tbody>
        </table></div>
      ); break;
    case "FORMULA_CARD":
      body = (<div className="d-grid gap-2">
        {config.latex && <div className="fs-5 text-center">{M(String(config.latex).includes("$") ? config.latex : `$$${config.latex}$$`)}</div>}
        {(config.items || []).map((it, i) => <div key={i}>{M(asText(it))}</div>)}
      </div>); break;
    case "TIMELINE":
      body = <ul className="list-unstyled mb-0 border-start ps-3">{(config.items || []).map((it, i) => <li key={i} className="mb-2"><span className="fw-semibold">{M(asText(it))}</span>{it?.detail && <div className="small text-secondary">{M(it.detail)}</div>}</li>)}</ul>; break;
    case "KNOWLEDGE_GRAPH":
    case "REASONING_DAG":
      body = <Graph config={config} renderMath={renderMath} />; break;
    case "NUMBER_LINE":
      body = <NumberLine config={config} />; break;
    case "COORDINATE_GRAPH":
      body = <CoordinateGraph config={config} renderMath={renderMath} />; break;
    default:
      body = <div className="text-secondary small">Unsupported widget “{String(spec.widget_type)}”.</div>;
  }
  const showCaption = !["GEOMETRY_DIAGRAM", "GEOMETRY_OVERLAY", "KNOWLEDGE_GRAPH", "REASONING_DAG", "COORDINATE_GRAPH"].includes(spec.widget_type);
  return (
    <div className={`card shadow-sm ${className}`} data-widget-type={spec.widget_type}>
      <div className="card-body">
        {spec.title && <h6 className="card-title mb-3">{M(spec.title)}</h6>}
        {body}
        {showCaption && <Caption text={config.caption} renderMath={renderMath} />}
      </div>
    </div>
  );
}
