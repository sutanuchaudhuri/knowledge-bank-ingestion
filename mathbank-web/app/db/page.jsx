"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { table, th, td, rowStyle, masterDetail, panel } from "./dbStyles.js";

export default function CompetitionsPage() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    fetch("/api/rest/competitions")
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`status ${res.status}`))))
      .then((data) => setItems(data.items))
      .catch((err) => setError(err.message));
  }, []);

  if (error) return <p style={{ color: "#b91c1c" }}>Could not load competitions: {error}</p>;
  if (!items) return <p>Loading…</p>;

  return (
    <div style={masterDetail}>
      <div>
        <table style={table}>
          <thead>
            <tr>
              <th style={th}>Code</th>
              <th style={th}>Name</th>
              <th style={th}>Level</th>
              <th style={{ ...th, textAlign: "right" }}>Papers</th>
              <th style={{ ...th, textAlign: "right" }}>Problems</th>
            </tr>
          </thead>
          <tbody>
            {items.map((c) => (
              <tr key={c.competition_id} style={rowStyle(selected?.competition_id === c.competition_id)} onClick={() => setSelected(c)}>
                <td style={td}>{c.external_code}</td>
                <td style={td}>{c.name}</td>
                <td style={td}>{c.level}</td>
                <td style={{ ...td, textAlign: "right" }}>{c.papers ?? "–"}</td>
                <td style={{ ...td, textAlign: "right" }}>{c.problems ?? "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={panel}>
        {!selected ? (
          <p style={{ color: "#666" }}>Select a competition to see coverage details.</p>
        ) : (
          <>
            <h3 style={{ marginTop: 0, fontSize: 15 }}>{selected.name} ({selected.external_code})</h3>
            <p style={{ fontSize: 13 }}>Level: {selected.level}</p>
            <ul style={{ fontSize: 13 }}>
              <li>Papers (HAS_PAPER): {selected.papers ?? "–"}</li>
              <li>Problems (HAS_PROBLEM): {selected.problems ?? "–"}</li>
              <li>Problems with a concept (TESTS): {selected.problems_with_concept ?? "–"}</li>
              <li>Problems with a technique (USES_TECHNIQUE): {selected.problems_with_technique ?? "–"}</li>
            </ul>
            <p>
              <Link href={`/db/problems?competition=${encodeURIComponent(selected.external_code)}`} style={{ color: "#2563eb", fontSize: 13 }}>
                View all {selected.name} problems →
              </Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
