"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Tutor" },
  { href: "/learn", label: "Guided practice" },
  { href: "/db", label: "Corpus" },
  { href: "/graph", label: "Graph" },
  { href: "/learn/conversations", label: "My conversations" },
  { href: "/profile", label: "My profile" },
  { href: "/admin", label: "Admin" },
];

export default function AppShell({ children }) {
  const pathname = usePathname();
  const [expanded, setExpanded] = useState(false);
  // Fetched after mount (initial null) so server and client render identical HTML.
  const [student, setStudent] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/rest/learner/me", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((me) => { if (!cancelled) setStudent(me && me.student_id ? me : null); })
      .catch(() => { if (!cancelled) setStudent(null); });
    return () => { cancelled = true; };
  }, [pathname]);

  return (
    <div className="app-shell">
      <nav className="navbar navbar-expand-lg bg-white border-bottom shadow-sm" aria-label="Main navigation">
        <div className="container-fluid px-3 px-lg-4">
          <Link href="/" className="navbar-brand fw-bold text-primary">MathBank</Link>
          <button className="navbar-toggler" type="button" aria-controls="app-navigation" aria-expanded={expanded}
            aria-label="Toggle navigation" onClick={() => setExpanded((value) => !value)}>
            <span className="navbar-toggler-icon" />
          </button>
          <div id="app-navigation" className={`collapse navbar-collapse${expanded ? " show" : ""}`}>
            <div className="navbar-nav ms-auto gap-lg-2">
              {links.map(({ href, label }) => {
                const matches = (h) => (h === "/" ? pathname === "/" : pathname === h || pathname.startsWith(`${h}/`));
                const active = matches(href) && !links.some((l) => l.href.length > href.length && l.href.startsWith(href) && matches(l.href));
                return (
                  <Link key={href} href={href} className={`nav-link${active ? " active fw-semibold" : ""}`}
                    aria-current={active ? "page" : undefined} onClick={() => setExpanded(false)}>
                    {label}
                  </Link>
                );
              })}
              {student ? (
                <Link href="/profile" className="btn btn-outline-success my-2 my-lg-0" data-testid="nav-student"
                  onClick={() => setExpanded(false)}>
                  Signed in · {student.first_name || student.email}
                </Link>
              ) : (
                <Link href="/login" className="btn btn-outline-primary my-2 my-lg-0" onClick={() => setExpanded(false)}>Student login</Link>
              )}
            </div>
          </div>
        </div>
      </nav>
      <main className="container-fluid px-3 px-lg-4 py-4">{children}</main>
    </div>
  );
}
