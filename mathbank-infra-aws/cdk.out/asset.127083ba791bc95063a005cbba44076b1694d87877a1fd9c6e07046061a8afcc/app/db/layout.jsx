import NavTabs from "../_components/NavTabs.jsx";
import { PageHeader } from "../_components/ui.jsx";

const NAV_ITEMS = [
  { href: "/db", label: "Competitions", icon: "trophy", exact: true },
  { href: "/db/problems", label: "Problems", icon: "file-earmark-text" },
  { href: "/db/concepts", label: "Concepts", icon: "lightbulb" },
  { href: "/db/techniques", label: "Techniques", icon: "tools" },
  { href: "/db/search", label: "Find similar", icon: "search" },
];

export default function DbLayout({ children }) {
  return (
    <>
      <PageHeader icon="database" tone="info" title="MathBank Corpus (Postgres)"
        subtitle="Browse competitions, problems, concepts and techniques. Click a row to drill in." />
      <NavTabs items={NAV_ITEMS} label="Corpus sections" />
      {children}
    </>
  );
}
