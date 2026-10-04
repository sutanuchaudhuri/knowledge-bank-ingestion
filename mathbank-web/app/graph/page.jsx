"use client";

import { useEffect, useState } from "react";

const tableStyle = { width: "100%", borderCollapse: "collapse", fontSize: 13 };
const cellStyle = { padding: "4px 8px", borderBottom: "1px solid #eee" };

export default function GraphOverviewPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch("/api/graph/overview")
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`status ${res.status}`))))
      .then(setData)
      .catch((err) => setError(err.message));
  }, []);

  if (error) return <p style={{ color: "#b91c1c" }}>Could not load graph overview: {error}</p>;
  if (!data) return <p>Loading…</p>;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
      <section>
        <h2 style={{ fontSize: 15 }}>Nodes</h2>
        <table style={tableStyle}>
          <tbody>
            {data.nodeCounts.map((row) => (
              <tr key={row.label}>
                <td style={cellStyle}>{row.label}</td>
                <td style={{ ...cellStyle, textAlign: "right" }}>{row.count.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section>
        <h2 style={{ fontSize: 15 }}>Relationships</h2>
        <table style={tableStyle}>
          <tbody>
            {data.relationshipCounts.map((row) => (
              <tr key={row.type}>
                <td style={cellStyle}>{row.type}</td>
                <td style={{ ...cellStyle, textAlign: "right" }}>{row.count.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
