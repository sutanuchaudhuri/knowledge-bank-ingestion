"use client";

import { useEffect, useRef, useState } from "react";
import { Callout, Icon, Pill } from "../../../_components/ui.jsx";

const INTERACTION_LABELS = {
  STATE_GRAPH_EXPLORER_V1: "State graph",
  RECURRENCE_EXPLORER_V1: "Recurrence",
  TRANSITION_MATRIX_EDITOR_V1: "Transition matrix",
  POLYNOMIAL_ROOT_COEFFICIENT_EXPLORER_V1: "Roots and coefficients",
  SLIDER_COMPARE_V1: "Compare values",
  FUNCTION_GRAPH_EXPLORER_V1: "Function explorer",
};
function numeric(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function readable(value) {
  return Number.isFinite(value) ? Number(value.toFixed(3)).toString() : "—";
}

function configuration(interaction) {
  return {
    ...(interaction.initial_state || {}),
    ...(interaction.instance_config || {}),
  };
}

function probability(value) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const match = /^\s*(-?(?:\d+(?:\.\d*)?|\.\d+))(?:\s*\/\s*(-?(?:\d+(?:\.\d*)?|\.\d+)))?\s*$/.exec(String(value ?? ""));
  if (!match) return null;
  const numerator = Number(match[1]);
  const denominator = match[2] === undefined ? 1 : Number(match[2]);
  return denominator === 0 ? null : numerator / denominator;
}

function sliderDefinitions(config, initialState) {
  const values = initialState?.values || initialState || {};
  return Object.entries(config.controls || {}).filter(([, spec]) => {
    const controlType = typeof spec?.control === "string" ? spec.control : "";
    return spec && typeof spec === "object"
      && (controlType.includes("SLIDER") || Number.isFinite(Number(spec.min)));
  }).map(([key, spec]) => {
    const controlType = typeof spec.control === "string" ? spec.control : "";
    return {
      key,
      label: ({
        lambda: "Weight λ",
        r1: "First root",
        r2: "Second root",
        r3: "Third root",
        x1: "First value",
        x2: "Second value",
      })[key] || key,
      min: numeric(spec.min, controlType === "PROBABILITY_SLIDER" ? 0 : controlType.includes("POSITIVE") ? 0.1 : -5),
      max: numeric(spec.max, controlType === "PROBABILITY_SLIDER" ? 1 : 5),
      step: numeric(spec.step, 0.1),
      initial: numeric(values[key], numeric(spec.initial, 0)),
    };
  });
}

function StateGraph({ config, instanceId }) {
  const states = Array.isArray(config.states) ? config.states : [];
  const transitions = Array.isArray(config.transitions) ? config.transitions : [];
  if (!states.length) {
    return <Callout tone="warning">This approved graph does not contain any state definitions.</Callout>;
  }
  const positions = new Map(states.map((state, index) => {
    if (states.length === 1) return [state.id, { x: 160, y: 90 }];
    if (states.length === 2) return [state.id, { x: index === 0 ? 88 : 232, y: 90 }];
    const angle = (2 * Math.PI * index) / states.length - Math.PI / 2;
    return [state.id, { x: 160 + 66 * Math.cos(angle), y: 90 + 54 * Math.sin(angle) }];
  }));
  const labels = new Map(states.map((state, index) => [state.id, state.label || state.name || `State ${index + 1}`]));
  const markerId = `course-state-arrow-${String(instanceId).replace(/[^A-Za-z0-9_-]/g, "") || "default"}`;
  return (
    <div className="row g-3">
      <div className="col-12">
        <svg className="mb-course-state-graph" viewBox="0 0 320 180" role="img" aria-label="State transition diagram">
          <title>State transition diagram</title>
          <defs>
            <marker id={markerId} markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 z" className="mb-course-graph-arrow" />
            </marker>
          </defs>
          {transitions.map((transition, index) => {
            const from = positions.get(transition.from);
            const to = positions.get(transition.to);
            if (!from || !to) return null;
            if (transition.from === transition.to) {
              return <path key={`${transition.from}-${transition.to}-${index}`}
                d={`M ${from.x - 12} ${from.y - 17} C ${from.x - 38} ${from.y - 51}, ${from.x + 38} ${from.y - 51}, ${from.x + 12} ${from.y - 17}`}
                className="mb-course-graph-edge" markerEnd={`url(#${markerId})`} />;
            }
            const dx = to.x - from.x;
            const dy = to.y - from.y;
            const distance = Math.hypot(dx, dy) || 1;
            const ux = dx / distance;
            const uy = dy / distance;
            const start = { x: from.x + ux * 25, y: from.y + uy * 25 };
            const end = { x: to.x - ux * 25, y: to.y - uy * 25 };
            const hasReverse = transitions.some(edge => edge.from === transition.to && edge.to === transition.from);
            const path = hasReverse
              ? `M ${start.x} ${start.y} Q ${(start.x + end.x) / 2 - uy * 24} ${(start.y + end.y) / 2 + ux * 24} ${end.x} ${end.y}`
              : `M ${start.x} ${start.y} L ${end.x} ${end.y}`;
            return <path key={`${transition.from}-${transition.to}-${index}`} d={path}
              className="mb-course-graph-edge" markerEnd={`url(#${markerId})`} />;
          })}
          {states.map((state, index) => {
            const point = positions.get(state.id);
            return (
              <g key={state.id}>
                <circle cx={point.x} cy={point.y} r="23" className="mb-course-graph-node" />
                <text x={point.x} y={point.y + 4} textAnchor="middle" className="mb-course-graph-label">State {index + 1}</text>
              </g>
            );
          })}
        </svg>
      </div>
      <div className="col-lg-5">
        <h3 className="h6">States</h3>
        <ul className="list-group">
          {states.map((state, index) => (
            <li className="list-group-item d-flex justify-content-between gap-2" key={state.id}>
              <Pill tone="neutral">State {index + 1}</Pill>
              <strong>{labels.get(state.id)}</strong>
            </li>
          ))}
        </ul>
      </div>
      <div className="col-lg-7">
        <h3 className="h6">Possible transitions</h3>
        {!transitions.length ? <Callout tone="hint">No transitions are configured for this graph.</Callout> : (
          <ul className="list-group" aria-label="State transitions">
            {transitions.map((transition, index) => (
              <li className="list-group-item d-flex flex-wrap justify-content-between gap-2" key={`${transition.from}-${transition.to}-${index}`}>
                <span>{labels.get(transition.from) || "Unknown state"} <span aria-hidden="true">→</span> {labels.get(transition.to) || "Unknown state"}</span>
                <Pill tone="info">p = {transition.p ?? "—"}</Pill>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function Recurrence({ config }) {
  const recurrence = String(config.recurrence || "");
  const match = /p\[n\+1\]\s*=\s*([0-9.]+)\s*\*\s*\(\s*1\s*-\s*p\[n\]\s*\)/i.exec(recurrence);
  const initial = /p\[0\]\s*=\s*([0-9.]+)/i.exec(String(config.initial || ""));
  if (!match || !initial) return <Callout tone="warning">The recurrence is not in a supported display form.</Callout>;
  const multiplier = Number(match[1]);
  let value = Number(initial[1]);
  const sequence = [value];
  for (let index = 0; index < 6; index += 1) {
    value = multiplier * (1 - value);
    sequence.push(value);
  }
  return (
    <div className="d-flex flex-column gap-3">
      <Callout tone="insight" title="Rule">
        <code>{recurrence}</code>
        {config.fixed_point && <Pill className="ms-2" tone="success">Fixed point {config.fixed_point}</Pill>}
      </Callout>
      <div className="d-flex flex-wrap gap-2" aria-label="First recurrence values">
        {sequence.map((term, index) => <Pill key={index} tone={index === 0 ? "primary" : "neutral"}>p[{index}] = {readable(term)}</Pill>)}
      </div>
    </div>
  );
}

function TransitionMatrix({ config, values, update }) {
  const states = Array.isArray(config.states) ? config.states : [];
  const transitions = Array.isArray(config.transitions) ? config.transitions : [];
  const matrix = config.matrix || config.transition_matrix || (
    states.length && transitions.length
      ? states.map(from => states.map(to => transitions
        .filter(transition => transition.from === from.id && transition.to === to.id)
        .reduce((sum, transition) => sum + (probability(transition.p) ?? 0), 0)))
      : []
  );
  if (!Array.isArray(matrix) || !matrix.length || !matrix.every(Array.isArray)) {
    return <Callout tone="hint">Explore the transition graph above, then use the matrix task configured for this interaction.</Callout>;
  }
  const labels = states.map((state, index) => state.label || state.name || `State ${index + 1}`);
  return (
    <div className="table-responsive">
      <table className="table table-hover align-middle">
        <caption className="caption-top">Transition probabilities by source and destination state</caption>
        <thead><tr><th scope="col">From / to</th>{matrix[0].map((_, column) => <th scope="col" key={column}>{labels[column] || column + 1}</th>)}<th scope="col">Row total</th></tr></thead>
        <tbody>
          {matrix.map((row, rowIndex) => {
            const total = row.reduce((sum, value, columnIndex) => sum + numeric(values[`m${rowIndex}_${columnIndex}`], numeric(value, 0)), 0);
            return (
              <tr key={rowIndex}>
                <th scope="row">{labels[rowIndex] || rowIndex + 1}</th>
                {row.map((cell, columnIndex) => {
                  const key = `m${rowIndex}_${columnIndex}`;
                  const value = numeric(values[key], numeric(cell, 0));
                  return (
                    <td key={key}>
                      <label className="visually-hidden" htmlFor={`${key}-${rowIndex}`}>Probability from {labels[rowIndex] || rowIndex + 1} to {labels[columnIndex] || columnIndex + 1}</label>
                      <input id={`${key}-${rowIndex}`} className="form-control form-control-sm mb-num" type="number"
                        min="0" max="1" step="0.01" value={value}
                        onChange={event => update(key, numeric(event.target.value, 0))} />
                    </td>
                  );
                })}
                <td><Pill tone={Math.abs(total - 1) < 0.000001 ? "success" : "warning"}>{readable(total)}</Pill></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function SliderControls({ definitions, values, update }) {
  if (!definitions.length) return null;
  return (
    <div className="row g-3 mb-3">
      {definitions.map(control => (
        <div className="col-sm-6 col-lg-4" key={control.key}>
          <label className="form-label d-flex justify-content-between gap-2" htmlFor={`interaction-${control.key}`}>
            <span>{control.label}</span><Pill tone="neutral">{readable(values[control.key])}</Pill>
          </label>
          <input id={`interaction-${control.key}`} className="form-range" type="range"
            min={control.min} max={control.max} step={control.step} value={values[control.key]}
            onChange={event => update(control.key, Number(event.target.value))} />
        </div>
      ))}
    </div>
  );
}

function Calculations({ interaction, config, values }) {
  const key = interaction.template_key;
  if (key === "POLYNOMIAL_ROOT_COEFFICIENT_EXPLORER_V1") {
    const roots = ["r1", "r2", "r3"].filter(name => Number.isFinite(values[name])).map(name => values[name]);
    if (roots.length !== 3) return null;
    const [a, b, c] = roots;
    const e1 = a + b + c;
    const e2 = a * b + a * c + b * c;
    const e3 = a * b * c;
    return <Callout tone="insight" title="Roots to coefficients"><p className="mb-1">e₁ = {readable(e1)} · e₂ = {readable(e2)} · e₃ = {readable(e3)}</p><code>x³ − ({readable(e1)})x² + ({readable(e2)})x − ({readable(e3)})</code></Callout>;
  }
  if (key === "SLIDER_COMPARE_V1") {
    const lambda = numeric(values.lambda, 0.5);
    if (Number.isFinite(values.a) && Number.isFinite(values.b)) {
      const arithmetic = (values.a + values.b) / 2;
      const geometric = Math.sqrt(Math.max(0, values.a * values.b));
      return <Callout tone="insight" title="Arithmetic mean and geometric mean"><p className="mb-0">AM = {readable(arithmetic)} · GM = {readable(geometric)} · gap = {readable(arithmetic - geometric)}</p></Callout>;
    }
    if (Number.isFinite(values.x) && Number.isFinite(values.y)) {
      if (values.x <= 0 || values.y <= 0) {
        return <Callout tone="warning">Weighted geometric means require positive inputs.</Callout>;
      }
      const arithmetic = lambda * values.x + (1 - lambda) * values.y;
      const geometric = Math.pow(values.x, lambda) * Math.pow(values.y, 1 - lambda);
      return <Callout tone="insight" title="Weighted means"><p className="mb-0">Weighted AM = {readable(arithmetic)} · weighted GM = {readable(geometric)}</p></Callout>;
    }
  }
  if (key === "FUNCTION_GRAPH_EXPLORER_V1" && config.function?.expression === "x^2") {
    const lambda = numeric(values.lambda, 0.5);
    const x1 = numeric(values.x1, 0);
    const x2 = numeric(values.x2, 0);
    const weightedX = lambda * x1 + (1 - lambda) * x2;
    const functionAtMean = weightedX ** 2;
    const meanOfValues = lambda * x1 ** 2 + (1 - lambda) * x2 ** 2;
    const xPosition = value => 30 + ((value + 4) / 8) * 280;
    const yPosition = value => 150 - (value / 16) * 125;
    const curve = Array.from({ length: 33 }, (_, index) => {
      const x = -4 + index * 0.25;
      return `${index === 0 ? "M" : "L"} ${xPosition(x)} ${yPosition(x ** 2)}`;
    }).join(" ");
    const chordMean = meanOfValues;
    return (
      <>
        <svg className="mb-course-function-plot" viewBox="0 0 320 180" role="img"
          aria-label={`Graph of x squared and a weighted chord for x values ${readable(x1)} and ${readable(x2)}`}>
          <title>Convex curve and weighted chord</title>
          <line x1="30" y1="150" x2="310" y2="150" className="mb-course-graph-axis" />
          <line x1="30" y1="20" x2="30" y2="150" className="mb-course-graph-axis" />
          <path d={curve} className="mb-course-function-curve" />
          <line x1={xPosition(x1)} y1={yPosition(x1 ** 2)} x2={xPosition(x2)} y2={yPosition(x2 ** 2)}
            className="mb-course-function-chord" />
          <circle cx={xPosition(x1)} cy={yPosition(x1 ** 2)} r="4" className="mb-course-function-point" />
          <circle cx={xPosition(x2)} cy={yPosition(x2 ** 2)} r="4" className="mb-course-function-point" />
          <circle cx={xPosition(weightedX)} cy={yPosition(functionAtMean)} r="5" className="mb-course-function-mean" />
          <circle cx={xPosition(weightedX)} cy={yPosition(chordMean)} r="4" className="mb-course-function-chord-mean" />
          <text x="305" y="170" textAnchor="end" className="mb-course-graph-axis-label">x</text>
          <text x="13" y="24" className="mb-course-graph-axis-label">f(x)</text>
        </svg>
        <Callout tone="insight" title="Jensen's inequality">
          <p className="mb-0">f(λx₁ + (1−λ)x₂) = {readable(functionAtMean)} · λf(x₁) + (1−λ)f(x₂) = {readable(meanOfValues)}</p>
        </Callout>
      </>
    );
  }
  return null;
}

export default function InteractionTemplateRenderer({ interaction, onRecordInteractionEvent }) {
  const config = configuration(interaction);
  const definitions = sliderDefinitions(config, interaction.initial_state);
  const [values, setValues] = useState(() => Object.fromEntries(
    definitions.map(control => [control.key, control.initial]),
  ));
  const update = (key, value) => setValues(current => ({ ...current, [key]: value }));
  const hasMounted = useRef(false);

  // Debounced silent telemetry: once a control "settles" (no change for 700ms), record one
  // interaction_event instead of one per pixel of a drag — see requirements/44 §4.1/MCX-7.
  // Skips the very first render so mounting with default values never looks like a real edit.
  useEffect(() => {
    if (!hasMounted.current) {
      hasMounted.current = true;
      return undefined;
    }
    if (!onRecordInteractionEvent || definitions.length === 0) return undefined;
    const timer = setTimeout(() => {
      onRecordInteractionEvent({
        interactionInstanceId: interaction.interaction_instance_id,
        eventType: "CONTROL_SETTLED",
        semanticAction: "ADJUST_CONTROL",
        actionPayload: values,
      });
    }, 700);
    return () => clearTimeout(timer);
    // Only the settled values matter for this debounce, not the callback/definitions identity.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [values]);

  const known = new Set([
    "STATE_GRAPH_EXPLORER_V1",
    "RECURRENCE_EXPLORER_V1",
    "TRANSITION_MATRIX_EDITOR_V1",
    "POLYNOMIAL_ROOT_COEFFICIENT_EXPLORER_V1",
    "SLIDER_COMPARE_V1",
    "FUNCTION_GRAPH_EXPLORER_V1",
  ]);

  return (
    <section className="mb-3 rounded-3 border bg-white p-3 p-lg-4" aria-label={`Interactive ${interaction.title}`}>
      <h4 className="h6 d-flex align-items-center gap-2 mb-3">
        <Icon name="puzzle" />
        {interaction.title}
      </h4>
      <div className="d-flex flex-wrap gap-2 mb-3">
        <Pill tone="primary">{INTERACTION_LABELS[interaction.template_key] || "Interactive exploration"}</Pill>
      </div>
      {interaction.learning_objective && (
        <p className="small text-secondary mb-course-reading">{interaction.learning_objective}</p>
      )}
      <SliderControls definitions={definitions} values={values} update={update} />
      {interaction.template_key === "STATE_GRAPH_EXPLORER_V1" && <StateGraph config={config} instanceId={interaction.interaction_instance_id} />}
      {interaction.template_key === "RECURRENCE_EXPLORER_V1" && <Recurrence config={config} />}
      {interaction.template_key === "TRANSITION_MATRIX_EDITOR_V1" && <TransitionMatrix config={config} values={values} update={update} />}
      <Calculations interaction={interaction} config={config} values={values} />
      {!known.has(interaction.template_key) && (
        <Callout tone="hint">This approved interaction is available as an instructor-authored lesson resource.</Callout>
      )}
    </section>
  );
}
