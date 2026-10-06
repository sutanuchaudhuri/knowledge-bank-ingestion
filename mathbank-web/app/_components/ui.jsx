// MathBank UI kit (requirements/30, .github/skills/modern-ui-design). Server-safe: no hooks.
import Link from "next/link";
import { avatarFor } from "../../lib/navigation.mjs";

export function Icon({ name, label, className = "" }) {
  return label
    ? <i className={`bi bi-${name} ${className}`} role="img" aria-label={label} />
    : <i className={`bi bi-${name} ${className}`} aria-hidden="true" />;
}

export function PageHeader({ icon, title, subtitle, pills, actions, tone = "primary" }) {
  return (
    <header className="mb-page-header">
      {icon && <span className={`mb-page-icon mb-tone-${tone}`}><Icon name={icon} /></span>}
      <div className="min-w-0">
        <h1 className="mb-page-title">{title}</h1>
        {subtitle && <p className="mb-page-sub">{subtitle}</p>}
        {pills && <div className="d-flex flex-wrap gap-2 mt-2">{pills}</div>}
      </div>
      {actions && <div className="mb-page-actions">{actions}</div>}
    </header>
  );
}

export function Pill({ tone = "neutral", icon, children, outline = false, title, className = "", ...rest }) {
  return (
    <span className={`mb-pill mb-pill-${tone}${outline ? " mb-pill-outline" : ""} ${className}`} title={title} {...rest}>
      {icon && <Icon name={icon} />}{children}
    </span>
  );
}

/** Icon-only action. `label` becomes aria-label and tooltip, so tests and screen readers keep the old text. */
export function IconButton({ icon, label, variant = "ghost", size, className = "", type = "button", href, ...rest }) {
  const cls = `btn btn-${variant} mb-icon-btn${size === "sm" ? " btn-sm" : ""} ${className}`;
  if (href) return <Link href={href} className={cls} aria-label={label} title={label} {...rest}><Icon name={icon} /></Link>;
  return <button type={type} className={cls} aria-label={label} title={label} {...rest}><Icon name={icon} /></button>;
}

export function Avatar({ name, size = 32, icon }) {
  const { initials, color } = avatarFor(name);
  return (
    <span className="mb-avatar" style={{ width: size, height: size, background: color, fontSize: size * 0.38 }} aria-hidden="true">
      {icon ? <Icon name={icon} /> : initials}
    </span>
  );
}

export function StatCard({ icon, label, value, hint, tone = "primary", href, progress, testId }) {
  const body = (
    <>
      <div className="mb-stat-top">
        <span>{label}</span>
        {icon && <span className={`mb-stat-icon mb-tone-${tone}`}><Icon name={icon} /></span>}
      </div>
      <div className="mb-stat-value">{value ?? "—"}</div>
      {progress !== undefined && progress !== null && (
        <div className="mb-bar-track" role="progressbar" aria-label={`${label} progress`} aria-valuenow={Math.round(progress)} aria-valuemin={0} aria-valuemax={100}>
          <div className="mb-bar-fill" style={{ width: `${Math.max(0, Math.min(100, progress))}%` }} />
        </div>
      )}
      {hint && <div className="mb-stat-hint">{hint}</div>}
    </>
  );
  return href
    ? <Link href={href} className="mb-stat" data-testid={testId}>{body}</Link>
    : <div className="mb-stat" data-testid={testId}>{body}</div>;
}

const CALLOUT_ICONS = { insight: "stars", hint: "lightbulb", warning: "exclamation-triangle", success: "check-circle", danger: "x-octagon", neutral: "info-circle" };

/** Explanation highlight for micro-lessons, hints, feedback and "why" notes. */
export function Callout({ tone = "insight", title, icon, children, className = "", role, ...rest }) {
  return (
    <div className={`mb-callout mb-callout-${tone} ${className}`} role={role} {...rest}>
      <Icon name={icon || CALLOUT_ICONS[tone] || "info-circle"} />
      <div className="mb-callout-body">
        {title && <div className="mb-callout-title">{title}</div>}
        {children}
      </div>
    </div>
  );
}

export function EmptyState({ icon = "inbox", children, action }) {
  return (
    <div className="mb-empty">
      <Icon name={icon} />
      <div>{children}</div>
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

export function SectionTitle({ icon, children, actions }) {
  return (
    <div className="d-flex align-items-center gap-2 mb-3">
      <h2 className="mb-section-title">{icon && <Icon name={icon} />}{children}</h2>
      {actions && <div className="ms-auto d-flex gap-1 align-items-center">{actions}</div>}
    </div>
  );
}

export function Bar({ label, value, max, tone = "primary", suffix = "" }) {
  const pct = max ? Math.round((value / max) * 100) : 0;
  const colors = { primary: "var(--mb-primary)", success: "var(--mb-success)", warning: "#f59e0b", danger: "var(--mb-danger)", info: "var(--mb-info)", neutral: "#94a3b8" };
  return (
    <div className="mb-bar">
      <span className="text-truncate" title={label}>{label}</span>
      <div className="mb-bar-track"><div className="mb-bar-fill" style={{ width: `${pct}%`, background: colors[tone] }} /></div>
      <span className="mb-num fw-semibold">{value}{suffix}</span>
    </div>
  );
}

/** Prev/next pager for limit+1 ("hasMore") lists; never unmounts the table. */
export function Pager({ offset, limit, hasMore, loading, onPrev, onNext, count }) {
  const shown = count ?? limit;
  return (
    <nav className="mb-pager" aria-label="Table pagination">
      <IconButton icon="chevron-left" label="Previous page" variant="outline-secondary" size="sm" disabled={offset === 0 || loading} onClick={onPrev} />
      <span className="mb-num">Page {Math.floor(offset / limit) + 1} · rows {shown ? offset + 1 : 0}–{offset + shown}</span>
      <IconButton icon="chevron-right" label="Next page" variant="outline-secondary" size="sm" disabled={!hasMore || loading} onClick={onNext} />
    </nav>
  );
}

/** In-page pill tabs (role="tab"); use NavTabs instead when each tab is its own route. */
export function TabBar({ tabs, value, onChange, counts = {}, label }) {
  return (
    <div className="mb-tabs" role="tablist" aria-label={label}>
      {tabs.map(([key, text, icon]) => (
        <button key={key} type="button" role="tab" aria-selected={value === key}
          className={`mb-tab${value === key ? " active" : ""}`} onClick={() => onChange(key)}>
          {icon && <Icon name={icon} />}{text}
          {counts[key] != null && <span className="mb-tab-count">{counts[key]}</span>}
        </button>
      ))}
    </div>
  );
}
