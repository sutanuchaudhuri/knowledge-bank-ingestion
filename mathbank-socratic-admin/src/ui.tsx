import type { ReactNode } from "react";
export { MathText } from "../../mathbank-exam-web/src/components/MathText.jsx";

export function Icon({ name }: { name: string }) {
  return <i className={`bi bi-${name}`} aria-hidden="true" />;
}
export function Pill({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "warning" | "success" | "primary" }) {
  return <span className={`mb-pill mb-pill-${tone}`}>{children}</span>;
}
export function IconButton({ icon, label, onClick, disabled = false, active = false, className = "" }: {
  icon: string; label: string; onClick: () => void; disabled?: boolean; active?: boolean; className?: string;
}) {
  return <button type="button" className={`sc-icon-button${active ? " sc-active" : ""} ${className}`} aria-label={label} title={label}
    aria-pressed={active || undefined} disabled={disabled} onClick={onClick}><Icon name={icon} /></button>;
}
export function Hero({ kicker, title, description, actions }: {
  kicker: string; title: ReactNode; description?: ReactNode; actions?: ReactNode;
}) {
  return <div className="sc-hero-row">
    <div><div className="sc-kicker">{kicker}</div><h1 className="sc-hero">{title}</h1>
      {description && <p className="sc-desc">{description}</p>}</div>
    {actions && <div className="sc-row">{actions}</div>}
  </div>;
}
export function Segmented<T extends string>({ label, value, options, onChange }: {
  label: string; value: T; options: { value: T; label: string; icon?: string }[]; onChange: (value: T) => void;
}) {
  return <div className="sc-seg" role="group" aria-label={label}>
    {options.map(option => <button key={option.value} type="button" aria-pressed={value === option.value}
      className={value === option.value ? "sc-active" : ""} onClick={() => onChange(option.value)}>
      {option.icon && <Icon name={option.icon} />}{option.label}
    </button>)}
  </div>;
}
export function Drawer({ title, onClose, children, footer }: {
  title: string; onClose: () => void; children: ReactNode; footer?: ReactNode;
}) {
  return <aside className="sc-drawer" aria-label={title}>
    <div className="sc-drawer-head"><strong>{title}</strong><IconButton icon="x-lg" label="Close pane" onClick={onClose} /></div>
    <div className="sc-drawer-body">{children}</div>
    {footer && <div className="sc-drawer-foot">{footer}</div>}
  </aside>;
}
export function Empty({ icon, children, action }: { icon: string; children: ReactNode; action?: ReactNode }) {
  return <div className="sc-empty"><Icon name={icon} /><p>{children}</p>{action}</div>;
}
export function Pager({ page, hasMore, onChange, disabled = false }: {
  page: number; hasMore: boolean; onChange: (page: number) => void; disabled?: boolean;
}) {
  if (page === 0 && !hasMore) return null;
  return <nav className="sc-row sc-pager" aria-label="Pagination">
    <IconButton icon="chevron-left" label="Previous page" disabled={disabled || page === 0} onClick={() => onChange(page - 1)} />
    <span className="sc-tiny">Page {page + 1}</span>
    <IconButton icon="chevron-right" label="Next page" disabled={disabled || !hasMore} onClick={() => onChange(page + 1)} />
  </nav>;
}
