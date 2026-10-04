import Link from "next/link";
import { RELATIONSHIPS } from "../../lib/graphConfig.js";
import GraphNav from "./_components/GraphNav.jsx";
import styles from "./graph.module.css";

const NAV_ITEMS = [
  { href: "/graph", title: "Overview" },
  ...Object.entries(RELATIONSHIPS).map(([slug, cfg]) => ({ href: `/graph/${slug}`, title: cfg.title })),
];

export default function GraphLayout({ children }) {
  return (
    <div className={styles.shell}>
      <div className="d-flex flex-wrap align-items-baseline justify-content-between gap-2">
        <div>
          <h1 className="h4 mb-1">MathBank Graph Views</h1>
          <p className="text-body-secondary small mb-0" style={{ color: "#64748b" }}>
            Cached snapshots of the Neo4j corpus graph (5 min TTL).
          </p>
        </div>
        <Link href="/" className="link-primary small">&larr; Back to chat</Link>
      </div>
      <GraphNav items={NAV_ITEMS} />
      {children}
    </div>
  );
}
