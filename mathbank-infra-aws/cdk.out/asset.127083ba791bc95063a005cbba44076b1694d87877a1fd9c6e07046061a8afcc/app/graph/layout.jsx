import { RELATIONSHIPS } from "../../lib/graphConfig.js";
import NavTabs from "../_components/NavTabs.jsx";
import { PageHeader, Pill } from "../_components/ui.jsx";
import styles from "./graph.module.css";

const CORPUS = [
  { href: "/graph", label: "Overview", icon: "diagram-3", exact: true },
  ...Object.entries(RELATIONSHIPS).filter(([, cfg]) => !cfg.pedagogical).map(([slug, cfg]) => ({ href: `/graph/${slug}`, label: cfg.title })),
];
const PEDAGOGY = Object.entries(RELATIONSHIPS).filter(([, cfg]) => cfg.pedagogical)
  .map(([slug, cfg]) => ({ href: `/graph/${slug}`, label: cfg.title }));

export default function GraphLayout({ children }) {
  return (
    <div className={styles.shell}>
      <PageHeader icon="diagram-3" tone="success" title="MathBank Graph Views"
        subtitle="Neo4j knowledge-graph snapshots, cached for 5 minutes."
        pills={<Pill tone="neutral" icon="clock">5 min cache</Pill>} />
      <div className="d-flex flex-wrap align-items-center gap-2 mb-1">
        <span className="mb-tabs-label">Corpus</span>
        <NavTabs items={CORPUS} label="Graph views" className="mb-0" />
      </div>
      {PEDAGOGY.length > 0 && (
        <div className="d-flex flex-wrap align-items-center gap-2 mb-4 mt-2">
          <span className="mb-tabs-label">Pedagogy</span>
          <NavTabs items={PEDAGOGY} label="Pedagogy graph views" className="mb-0" />
        </div>
      )}
      {children}
    </div>
  );
}
