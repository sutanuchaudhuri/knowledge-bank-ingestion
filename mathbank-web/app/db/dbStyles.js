// Shared inline style objects for the /db (Postgres relational views) section.
export const panel = { border: "1px solid #ddd", borderRadius: 8, padding: 12 };

export const masterDetail = { display: "grid", gridTemplateColumns: "minmax(280px, 1fr) minmax(320px, 1.4fr)", gap: 16, alignItems: "start" };

export const table = { width: "100%", borderCollapse: "collapse", fontSize: 13 };

export const th = { textAlign: "left", padding: "6px 8px", borderBottom: "2px solid #ddd", color: "#555", fontWeight: 600 };

export const td = { padding: "6px 8px", borderBottom: "1px solid #eee" };

export function rowStyle(selected) {
  return { cursor: "pointer", background: selected ? "#eff6ff" : "transparent" };
}

export const input = { padding: "6px 8px", borderRadius: 6, border: "1px solid #ccc", fontSize: 13 };

export const button = { padding: "6px 12px", borderRadius: 6, border: "1px solid #ccc", background: "#f8fafc", cursor: "pointer", fontSize: 13 };

export const primaryButton = { ...button, background: "#2563eb", color: "white", border: "1px solid #2563eb" };
