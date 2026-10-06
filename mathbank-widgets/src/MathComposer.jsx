"use client";
// Student math composer (requirements 29): symbol toolbar, instant deterministic formatting, optional
// agentic (✨) formatting through the host app's server route, live KaTeX preview and optional dictation.
// Slim by default: the toolbar and preview only appear when the student asks for them / types math.
import { useRef, useState } from "react";
import { SYMBOL_GROUPS, checkLatex, deterministicFormat, insertSnippet } from "./format.mjs";
import { MicButton } from "./VoiceControls.jsx";
import { WIcon, WidgetStyles } from "./icons.jsx";

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
      <WidgetStyles />
      <div className={`mbw-field${disabled ? " is-disabled" : ""}`}>
        {tools && (
          <div className="mbw-toolbar" data-testid="symbol-toolbar">
            <div className="d-flex gap-1 me-1" role="group" aria-label="symbol groups">
              {SYMBOL_GROUPS.map((g, i) => (
                <button key={g.name} type="button" className={`mbw-chip${i === group ? " is-active" : ""}`} aria-pressed={i === group}
                  onClick={() => setGroup(i)}>{g.name}</button>
              ))}
            </div>
            {SYMBOL_GROUPS[group].items.map(([label, tex]) => (
              <button key={label} type="button" className="mbw-sym" title={tex.replace("|", "…")}
                onMouseDown={(e) => e.preventDefault()} onClick={() => insert(tex)}>{label}</button>
            ))}
          </div>
        )}
        <textarea ref={ref} className="mbw-input" rows={rows} value={value || ""}
          placeholder={placeholder} onChange={(e) => { onChange(e.target.value); setNote(""); }} onKeyDown={onKeyDown}
          id={id} disabled={disabled} autoFocus={autoFocus} aria-label={ariaLabel} data-testid={`${testId}-input`} />
        <div className="mbw-actions">
          <button type="button" className="mbw-ghost" onClick={() => setTools((t) => !t)}
            title="Math symbols" aria-label="Math symbols" aria-pressed={tools} data-testid="toggle-symbols"><WIcon name="sigma" /></button>
          <button type="button" className="mbw-ghost" onClick={formatNow} disabled={disabled || !value?.trim()}
            title="Quick format: wrap math in LaTeX (instant, offline)" aria-label="Quick format" data-testid="format-quick"><WIcon name="dollar" /></button>
          {allowAgentic && (
            <button type="button" className="mbw-ghost" onClick={formatAgentic} disabled={disabled || busy || !value?.trim()}
              title="AI format: tidy the math into LaTeX without changing your words" aria-label="AI format" data-testid="format-ai">
              <WIcon name={busy ? "spinner" : "sparkles"} /></button>
          )}
          <span className="mbw-note ms-1" data-testid="composer-note" aria-live="polite">{note}</span>
          {warnings.length > 0 && <span className="mbw-warn ms-1" data-testid="composer-warnings"><WIcon name="alert" size={14} /> {warnings.join(", ")}</span>}
          <span className="mbw-spacer" />
          {voice && <MicButton endpoint={sttEndpoint} disabled={disabled}
            onTranscript={(t) => onChange(value?.trim() ? `${value.trimEnd()} ${deterministicFormat(t)}` : deterministicFormat(t))} />}
          {children}
          {onSubmit && showSubmit && (
            <button type="button" className="mbw-send" disabled={disabled || !value?.trim()} onClick={onSubmit}
              data-testid={`${testId}-submit`}><WIcon name="send" size={16} /><span>{submitLabel}</span></button>
          )}
        </div>
      </div>
      {hasMath && renderMath && (
        <div className="mbw-preview" data-testid="composer-preview" aria-live="polite">
          {renderMath(value)}
        </div>
      )}
    </div>
  );
}
