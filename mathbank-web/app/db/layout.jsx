import Link from "next/link";

const navLinkStyle = {
  padding: "6px 10px",
  borderRadius: 6,
  background: "#f1f5f9",
  color: "#111",
  textDecoration: "none",
  fontSize: 13,
};

const NAV_ITEMS = [
  { href: "/db", label: "Competitions" },
  { href: "/db/problems", label: "Problems" },
  { href: "/db/concepts", label: "Concepts" },
  { href: "/db/techniques", label: "Techniques" },
  { href: "/db/search", label: "Find Similar Questions" },
];

export default function DbLayout({ children }) {
  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: 16, fontFamily: "system-ui, sans-serif" }}>
      <p style={{ marginTop: 0 }}>
        <Link href="/" style={{ fontSize: 13, color: "#2563eb" }}>&larr; Back to chat</Link>
        {" · "}
        <Link href="/graph" style={{ fontSize: 13, color: "#2563eb" }}>Graph views</Link>
      </p>
      <h1 style={{ fontSize: 20 }}>MathBank Corpus (Postgres)</h1>
      <p style={{ color: "#666", fontSize: 13 }}>
        Paginated master/detail views over mathbank-rest → Postgres. All calls go through
        this app&apos;s own /api/rest/* routes, never directly from the browser to mathbank-rest.
      </p>
      <nav style={{ display: "flex", gap: 8, flexWrap: "wrap", margin: "12px 0 20px" }}>
        {NAV_ITEMS.map((item) => (
          <Link key={item.href} href={item.href} style={navLinkStyle}>
            {item.label}
          </Link>
        ))}
      </nav>
      {children}
    </div>
  );
}
