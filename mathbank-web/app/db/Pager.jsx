"use client";

import { button } from "./dbStyles.js";

/** Prev/Next pager for the grid pages — uses a hasMore flag (limit+1 fetch trick) instead of a total count. */
export default function Pager({ offset, limit, hasMore, loading, onPrev, onNext }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 10, fontSize: 13 }}>
      <button type="button" style={button} disabled={offset === 0 || loading} onClick={onPrev}>
        ← Prev
      </button>
      <span style={{ color: "#666" }}>
        Rows {offset + 1}–{offset + limit}
      </span>
      <button type="button" style={button} disabled={!hasMore || loading} onClick={onNext}>
        Next →
      </button>
    </div>
  );
}
