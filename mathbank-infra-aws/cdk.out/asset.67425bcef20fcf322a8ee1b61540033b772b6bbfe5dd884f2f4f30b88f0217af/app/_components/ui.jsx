// Tiny, intentionally independent UI subset for mathbank-ml-frontend — NOT a copy of
// mathbank-web's design-system kit (see README.md "what this app intentionally does not
// do"). Kept minimal on purpose: this is an internal ML-ops tool, not a second
// student/admin-facing product surface.

export function PageHeader({ title, subtitle }) {
  return (
    <header style={{ marginBottom: "1.5rem" }}>
      <h1 style={{ margin: 0, fontSize: "1.5rem" }}>{title}</h1>
      {subtitle && <p style={{ margin: ".25rem 0 0", color: "#666" }}>{subtitle}</p>}
    </header>
  );
}

export function StatusBadge({ status }) {
  const color = status === "NOT_IMPLEMENTED" ? "#b45309" : "#15803d";
  return (
    <span style={{
      display: "inline-block", padding: ".15rem .5rem", borderRadius: "999px",
      background: color, color: "white", fontSize: ".75rem", fontWeight: 600,
    }}>
      {status}
    </span>
  );
}

export function TodoPanel({ todoRef, designDocRef }) {
  // TODO: once a given endpoint is implemented, this panel is exactly what each page's
  // real content replaces — the data fetch/loading/error plumbing around it does not
  // need to change.
  return (
    <div style={{ border: "1px dashed #ccc", borderRadius: "8px", padding: "1rem" }}>
      <p style={{ margin: 0 }}>
        Not implemented yet. See <code>{todoRef}</code> (design doc:{" "}
        <code>{designDocRef}</code>).
      </p>
    </div>
  );
}
