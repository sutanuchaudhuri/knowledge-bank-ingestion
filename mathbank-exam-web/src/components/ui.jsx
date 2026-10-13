import { cloneElement, isValidElement, useId } from "react";

export function PageHeader({ icon, title, subtitle, actions }) {
  return (
    <div className="mb-page-header">
      <div className="mb-icon-tile">
        <i className={`bi bi-${icon}`} aria-hidden="true" />
      </div>
      <div style={{ flex: 1 }}>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {actions && <div style={{ display: "flex", gap: "0.5rem" }}>{actions}</div>}
    </div>
  );
}

export function Pill({ tone = "neutral", icon, children, ...props }) {
  return (
    <span className={`mb-pill mb-pill-${tone}`} {...props}>
      {icon && <i className={`bi bi-${icon}`} aria-hidden="true" />}
      {children}
    </span>
  );
}

export function Callout({ tone = "primary", icon = "lightbulb", children }) {
  return (
    <div className={`mb-callout mb-callout-${tone}`}>
      <i className={`bi bi-${icon}`} aria-hidden="true" style={{ marginTop: "0.1rem" }} />
      <div>{children}</div>
    </div>
  );
}

export function Button({ tone = "primary", icon, children, ...props }) {
  return (
    <button className={`mb-btn mb-btn-${tone}`} {...props}>
      {icon && <i className={`bi bi-${icon}`} aria-hidden="true" />}
      {children}
    </button>
  );
}

export function Field({ label, children }) {
  // Clone the input/textarea child to inject a stable id, so the label is
  // properly associated for screen readers and accessible-name-based queries
  // (getByLabel), not just visually adjacent.
  const id = useId();
  const field = isValidElement(children) ? cloneElement(children, { id: children.props.id || id }) : children;
  return (
    <div className="mb-field">
      <label htmlFor={id}>{label}</label>
      {field}
    </div>
  );
}
