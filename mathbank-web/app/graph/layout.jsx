import Link from "next/link";
import { RELATIONSHIPS } from "../../lib/graphConfig.js";

const navLinkStyle = {
  padding: "6px 10px",
  borderRadius: 6,
  background: "#f1f5f9",
  color: "#111",
  textDecoration: "none",
  fontSize: 13,
};

export default function GraphLayout({ children }) {
  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: 16, fontFamily: "system-ui, sans-serif" }}>
      <p style={{ marginTop: 0 }}>
        <Link href="/" style={{ fontSize: 13, color: "#2563eb" }}>&larr; Back to chat</Link>
      </p>
      <h1 style={{ fontSize: 20 }}>MathBank Graph Views</h1>
      <p style={{ color: "#666", fontSize: 13 }}>
        Cached snapshots of the Neo4j corpus graph (5 min TTL) — see mathbank-graph.
      </p>
      <nav style={{ display: "flex", gap: 8, flexWrap: "wrap", margin: "12px 0 20px" }}>
        <Link href="/graph" style={navLinkStyle}>Overview</Link>
        {Object.entries(RELATIONSHIPS).map(([slug, cfg]) => (
          <Link key={slug} href={`/graph/${slug}`} style={navLinkStyle}>
            {cfg.title}
          </Link>
        ))}
      </nav>
      {children}
    </div>
  );
}
