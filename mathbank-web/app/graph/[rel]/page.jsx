"use client";

import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { useParams } from "next/navigation";

// force-graph renders to <canvas>; must stay client-only (no SSR).
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

const NODE_COLORS = {
  Competition: "#2563eb",
  Paper: "#7c3aed",
  Problem: "#059669",
  Solution: "#d97706",
  Concept: "#dc2626",
  Technique: "#0891b2",
};

export default function GraphRelationshipPage() {
  const { rel } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setData(null);
    setError(null);
    fetch(`/api/graph/relationship/${rel}`)
      .then((res) =>
        res.ok ? res.json() : res.json().then((body) => Promise.reject(new Error(body.error || `status ${res.status}`)))
      )
      .then(setData)
      .catch((err) => setError(err.message));
  }, [rel]);

  const graphData = useMemo(() => ({ nodes: data?.nodes ?? [], links: data?.links ?? [] }), [data]);

  if (error) return <p style={{ color: "#b91c1c" }}>Could not load view: {error}</p>;
  if (!data) return <p>Loading…</p>;

  return (
    <div>
      <p style={{ color: "#666", fontSize: 13 }}>
        {data.nodes.length} nodes · {data.links.length} relationships
        {data.truncated ? " (cached sample, truncated)" : ""}
      </p>
      <div style={{ border: "1px solid #ddd", borderRadius: 8, overflow: "hidden" }}>
        <ForceGraph2D
          graphData={graphData}
          width={900}
          height={560}
          nodeLabel="name"
          nodeColor={(n) => NODE_COLORS[n.label] || "#64748b"}
          linkColor={() => "#cbd5e1"}
          nodeRelSize={4}
        />
      </div>
    </div>
  );
}
