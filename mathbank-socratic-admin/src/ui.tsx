import type { ReactNode } from "react";
export { MathText } from "../../mathbank-exam-web/src/components/MathText.jsx";

export function Icon({ name }: { name: string }) {
  return <i className={`bi bi-${name}`} aria-hidden="true" />;
}
export function Pill({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "warning" | "success" | "primary" }) {
  return <span className={`mb-pill mb-pill-${tone}`}>{children}</span>;
}
export function PageHeader({ title, icon, subtitle }: { title: string; icon: string; subtitle: string }) {
  return <header className="mb-page-header">
    <span className="mb-page-icon mb-tone-primary"><Icon name={icon} /></span>
    <div><h1 className="mb-page-title">{title}</h1><p className="mb-page-sub">{subtitle}</p>
      <div className="sc-toolbar"><Pill tone="warning">Synthetic-only prototype</Pill><Pill>Human-reviewed workflows · Draft authoring</Pill></div>
    </div>
  </header>;
}
export function Pager({ page, hasMore, onChange, disabled = false }: {
  page: number; hasMore: boolean; onChange: (page: number) => void; disabled?: boolean;
}) {
  return <nav className="sc-toolbar sc-pager" aria-label="Pagination">
    <button disabled={disabled || page === 0} aria-label="Previous page" title="Previous page" onClick={() => onChange(page - 1)}><Icon name="chevron-left" /></button>
    <span>Page {page + 1} · up to 25 rows</span>
    <button disabled={disabled || !hasMore} aria-label="Next page" title="Next page" onClick={() => onChange(page + 1)}><Icon name="chevron-right" /></button>
  </nav>;
}
