import Link from "next/link";

const NAV_ITEMS = [
  { href: "/db", label: "Competitions" },
  { href: "/db/problems", label: "Problems" },
  { href: "/db/concepts", label: "Concepts" },
  { href: "/db/techniques", label: "Techniques" },
  { href: "/db/search", label: "Find Similar Questions" },
  { href: "/admin", label: "Admin: Ingestion" },
];

export default function DbLayout({ children }) {
  return (
    <div>
      <header className="mb-4">
        <h1 className="h3 fw-bold">MathBank Corpus (Postgres)</h1>
        <p className="text-secondary">
          Paginated master/detail views over mathbank-rest → Postgres. All calls go through
          this app&apos;s own /api/rest/* routes, never directly from the browser to mathbank-rest.
        </p>
        <nav className="d-flex flex-wrap gap-2" aria-label="Corpus sections">
          {NAV_ITEMS.map((item) => (
            <Link key={item.href} href={item.href} className="btn btn-outline-primary bg-white">
              {item.label}
            </Link>
          ))}
        </nav>
      </header>
      {children}
    </div>
  );
}
