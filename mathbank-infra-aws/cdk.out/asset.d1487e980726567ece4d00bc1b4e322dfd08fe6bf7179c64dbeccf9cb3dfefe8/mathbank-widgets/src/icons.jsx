// Dependency-free inline SVG icons for the shared widgets (no icon font required in host apps).
const PATHS = {
  mic: "M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0M12 17v4m-3 0h6",
  stop: "M7 7h10v10H7z",
  send: "M4 12 20 4l-4 16-4-7-8-1Zm8 1 8-9",
  speaker: "M4 9v6h4l5 4V5L8 9H4Zm12.5-.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12",
  sparkles: "M12 3l1.8 4.7L18.5 9.5 13.8 11.3 12 16l-1.8-4.7L5.5 9.5l4.7-1.8L12 3Zm6.5 11 .8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8.8-2Z",
  sigma: "M17 5H7l6 7-6 7h10",
  dollar: "M8 16c0 1.7 1.8 3 4 3s4-1.3 4-3-1.8-2.6-4-3-4-1.3-4-3 1.8-3 4-3 4 1.3 4 3M12 4v2m0 13v2",
  alert: "M12 4 2.5 20h19L12 4Zm0 6v4m0 3h.01",
  spinner: "M12 3a9 9 0 1 0 9 9",
};

export function WIcon({ name, size = 18, className = "", title }) {
  const d = PATHS[name] || PATHS.alert;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" className={`mbw-icon ${name === "spinner" ? "mbw-spin " : ""}${className}`}
      aria-hidden={title ? undefined : true} role={title ? "img" : undefined} focusable="false">
      {title && <title>{title}</title>}
      <path d={d} />
    </svg>
  );
}

// Scoped composer/voice styles, injected inline so every host renders identically on server and client.
export const COMPOSER_CSS = `
.mbw-icon{display:inline-block;vertical-align:-.2em;flex:none}
.mbw-spin{animation:mbwSpin 1s linear infinite}@keyframes mbwSpin{to{transform:rotate(360deg)}}
.mbw-field{border:1px solid var(--bs-border-color,#dee2e6);border-radius:16px;background:var(--bs-body-bg,#fff);transition:border-color .15s,box-shadow .15s;overflow:hidden}
.mbw-field:focus-within{border-color:var(--bs-primary,#4f46e5);box-shadow:0 0 0 4px rgba(79,70,229,.12)}
.mbw-field.is-disabled{opacity:.7}
.mbw-input{display:block;width:100%;border:0;outline:0;resize:none;background:transparent;padding:.7rem .9rem .3rem;font:inherit;line-height:1.5;color:inherit;min-height:2.6rem}
.mbw-input::placeholder{color:#94a3b8}
.mbw-actions{display:flex;align-items:center;gap:.25rem;padding:.25rem .4rem .4rem}
.mbw-actions .mbw-spacer{flex:1 1 auto;min-width:.5rem}
.mbw-ghost{display:inline-flex;align-items:center;justify-content:center;min-width:32px;height:32px;padding:0 .45rem;border:0;border-radius:10px;background:transparent;color:#64748b;font-size:.9rem;font-weight:600;line-height:1;cursor:pointer;transition:background .12s,color .12s}
.mbw-ghost:hover:not(:disabled){background:rgba(79,70,229,.08);color:var(--bs-primary,#4f46e5)}
.mbw-ghost[aria-pressed=true]{background:rgba(79,70,229,.12);color:var(--bs-primary,#4f46e5)}
.mbw-ghost:disabled{opacity:.4;cursor:default}
.mbw-ghost.is-live{background:#fee2e2;color:#dc2626;animation:mbwPulse 1.4s ease-in-out infinite}
@keyframes mbwPulse{50%{opacity:.55}}
.mbw-send{display:inline-flex;align-items:center;gap:.35rem;height:34px;padding:0 .8rem;border:0;border-radius:11px;background:var(--bs-primary,#4f46e5);color:#fff;font-weight:600;font-size:.88rem;cursor:pointer}
.mbw-send:disabled{opacity:.45;cursor:default}
.mbw-send.is-danger{background:#dc2626}
.mbw-note{font-size:.78rem;color:#64748b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mbw-warn{font-size:.78rem;color:#b45309}
.mbw-toolbar{display:flex;flex-wrap:wrap;gap:.25rem;align-items:center;padding:.4rem .5rem;border-bottom:1px solid var(--bs-border-color,#e2e8f0);background:rgba(148,163,184,.08)}
.mbw-toolbar .mbw-chip{border:1px solid transparent;border-radius:999px;background:transparent;padding:.15rem .6rem;font-size:.78rem;font-weight:600;color:#64748b;cursor:pointer}
.mbw-toolbar .mbw-chip.is-active{background:var(--bs-primary,#4f46e5);color:#fff}
.mbw-toolbar .mbw-sym{min-width:32px;height:30px;border:1px solid var(--bs-border-color,#e2e8f0);border-radius:8px;background:var(--bs-body-bg,#fff);font-size:.9rem;cursor:pointer}
.mbw-toolbar .mbw-sym:hover{border-color:var(--bs-primary,#4f46e5);color:var(--bs-primary,#4f46e5)}
.mbw-preview{margin-top:.4rem;padding:.45rem .75rem;border-radius:12px;background:rgba(79,70,229,.05);border:1px dashed rgba(79,70,229,.25);font-size:.9rem}
.mbw-speak{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border:0;border-radius:8px;background:transparent;color:#64748b;cursor:pointer}
.mbw-speak:hover{background:rgba(79,70,229,.08);color:var(--bs-primary,#4f46e5)}
.mbw-speak.is-live{color:var(--bs-primary,#4f46e5)}
`;

/** Hoisted and de-duplicated by React 19 (href + precedence), so many widgets share one sheet. */
export function WidgetStyles() {
  return <style href="mathbank-widgets-composer" precedence="default">{COMPOSER_CSS}</style>;
}
