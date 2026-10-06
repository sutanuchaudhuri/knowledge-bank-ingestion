"use client";
// Student math composer (requirements 29): symbol toolbar, instant deterministic formatting, optional
// agentic (✨) formatting through the host app's server route, live KaTeX preview and optional dictation.
// Slim by default: the toolbar and preview only appear when the student asks for them / types math.
import { useRef, useState } from "react";
import { SYMBOL_GROUPS, checkLatex, deterministicFormat, insertSnippet } from "./format.mjs";
import { MicButton } from "./VoiceControls.jsx";

export default function MathComposer({
  value, onChange, onSubmit, renderMath, placeholder = "Type your answer… e.g. PA*PB = PT^2",
  formatEndpoint = "/api/format-math", allowAgentic = true, voice = true, sttEndpoint = "/api/voice/stt",
  disabled = false, submitLabel = "Send", showSubmit = true, rows = 2, autoFocus = false, testId = "math-composer",
  id, ariaLabel = "Message", children,
}) {
  const ref = useRef(null);
  const [tools, setTools] = useState(false);
  const [group, setGroup] = useState(0);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const warnings = value ? checkLatex(value) : [];
  const hasMath = /\$|\\\(|\\\[/.test(value || "");

  function insert(snippet) {
    const el = ref.current;
    const start = el?.selectionStart ?? (value || "").length;
    const end = el?.selectionEnd ?? start;
    const next = insertSnippet(value || "", start, end, snippet);
    onChange(next.value);
    requestAnimationFrame(() => { el?.focus(); el?.setSelectionRange(next.cursor, next.cursor); });
  }

  function formatNow() {
    const out = deterministicFormat(value || "");
    setNote(out === value ? "Already formatted" : "Formatted");
    onChange(out);
  }

  async function formatAgentic() {
    setBusy(true);
    setNote("");
    try {
      const res = await fetch(formatEndpoint, { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: value || "", mode: "agentic" }) });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.error || `format ${res.status}`);
      onChange(body.formatted ?? value);
      setNote(body.engine === "agentic" ? "AI formatted (your words kept)" : "Formatted (AI unavailable, used quick format)");
    } catch {
      onChange(deterministicFormat(value || ""));
      setNote("Formatted offline");
    } finally {
      setBusy(false);
    }
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); if (!disabled && value?.trim()) onSubmit?.(); return; }
    if (e.key === "Enter" && !e.shiftKey && rows <= 1) { e.preventDefault(); if (!disabled && value?.trim()) onSubmit?.(); }
  }

  return (
    <div className="mbw-composer" data-testid={testId}>
      {tools && (
        <div className="border rounded-top bg-body-tertiary px-2 py-1 d-flex flex-wrap gap-1 align-items-center" data-testid="symbol-toolbar">
          <div className="btn-group btn-group-sm me-1" role="group" aria-label="symbol groups">
            {SYMBOL_GROUPS.map((g, i) => (
              <button key={g.name} type="button" className={`btn ${i === group ? "btn-secondary" : "btn-outline-secondary"}`} onClick={() => setGroup(i)}>{g.name}</button>
            ))}
          </div>
          {SYMBOL_GROUPS[group].items.map(([label, tex]) => (
            <button key={label} type="button" className="btn btn-sm btn-light border" title={tex.replace("|", "…")}
              onMouseDown={(e) => e.preventDefault()} onClick={() => insert(tex)}>{label}</button>
          ))}
        </div>
      )}
      <div className="input-group">
        <textarea ref={ref} className={`form-control ${tools ? "rounded-top-0" : ""}`} rows={rows} value={value || ""}
          placeholder={placeholder} onChange={(e) => { onChange(e.target.value); setNote(""); }} onKeyDown={onKeyDown}
          id={id} disabled={disabled} autoFocus={autoFocus} aria-label={ariaLabel} data-testid={`${testId}-input`} />
        {children}
      </div>
      <div className="d-flex flex-wrap align-items-center gap-1 mt-1">
        <button type="button" className={`btn btn-sm ${tools ? "btn-secondary" : "btn-outline-secondary"}`} onClick={() => setTools((t) => !t)}
          title="Math symbols" aria-pressed={tools} data-testid="toggle-symbols">∑</button>
        <button type="button" className="btn btn-sm btn-outline-secondary" onClick={formatNow} disabled={disabled || !value?.trim()}
          title="Quick format: wrap math in LaTeX (instant, offline)" data-testid="format-quick">$x$</button>
        {allowAgentic && (
          <button type="button" className="btn btn-sm btn-outline-secondary" onClick={formatAgentic} disabled={disabled || busy || !value?.trim()}
            title="AI format: tidy the math into LaTeX without changing your words" data-testid="format-ai">{busy ? "…" : "✨"}</button>
        )}
        {voice && <MicButton endpoint={sttEndpoint} disabled={disabled}
          onTranscript={(t) => onChange(value?.trim() ? `${value.trimEnd()} ${deterministicFormat(t)}` : deterministicFormat(t))} />}
        <span className="small text-secondary ms-1" data-testid="composer-note">{note}</span>
        {warnings.length > 0 && <span className="small text-warning ms-1" data-testid="composer-warnings">⚠ {warnings.join(", ")}</span>}
        {onSubmit && showSubmit && (
          <button type="button" className="btn btn-sm btn-primary ms-auto" disabled={disabled || !value?.trim()} onClick={onSubmit}
            data-testid={`${testId}-submit`}>{submitLabel}</button>
        )}
      </div>
      {hasMath && renderMath && (
        <div className="border rounded px-2 py-1 mt-1 small bg-body-tertiary" data-testid="composer-preview" aria-live="polite">
          {renderMath(value)}
        </div>
      )}
    </div>
  );
}
