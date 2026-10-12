"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV_GROUPS, activeHref, breadcrumbs } from "../lib/navigation.mjs";
import { RELATIONSHIPS } from "../lib/graphConfig.js";
import { Avatar, Icon } from "./_components/ui.jsx";

const REL_TITLES = Object.fromEntries(Object.entries(RELATIONSHIPS).map(([slug, cfg]) => [slug, cfg.title]));

function UserMenu({ student, admin }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => { if (!ref.current?.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  if (!student && !admin) {
    return (
      <Link href="/login" className="btn btn-sm btn-primary">
        <Icon name="box-arrow-in-right" />Student login
      </Link>
    );
  }
  // Protected /admin routes are gated server-side, so reaching one implies an admin session.
  const name = admin ? "Admin" : [student.first_name, student.last_name].filter(Boolean).join(" ") || student.email;
  const short = admin ? "Admin" : student.first_name || student.email;
  async function signOut() {
    await fetch(admin ? "/api/auth/admin-logout" : "/api/auth/student-logout", { method: "POST" });
    window.location.href = admin ? "/admin/login" : "/login";
  }
  return (
    <div className="position-relative" ref={ref}>
      <button type="button" className="mb-user" data-testid={admin ? "nav-admin" : "nav-student"} aria-expanded={open} aria-haspopup="menu"
        onClick={() => setOpen((v) => !v)} title={`Signed in · ${short}`}>
        <Avatar name={name} size={28} icon={admin ? "shield-lock" : undefined} />
        <span className="d-none d-md-inline">{short}</span>
        <span className="visually-hidden">Signed in · {short}</span>
        <Icon name="chevron-down" className="small text-secondary" />
      </button>
      {open && (
        <div className="dropdown-menu dropdown-menu-end show shadow border-0 mt-2 p-2" style={{ right: 0, left: "auto", minWidth: 220 }} role="menu">
          <div className="px-2 py-1 small text-secondary text-truncate">{admin ? "Corpus administrator" : student.email}</div>
          <hr className="dropdown-divider" />
          <button type="button" className="dropdown-item rounded-2 text-danger" role="menuitem" onClick={signOut}><Icon name="box-arrow-right" className="me-2" />Sign out</button>
        </div>
      )}
    </div>
  );
}

export default function AppShell({ children }) {
  const pathname = usePathname() || "/";
  const isAdminArea = pathname.startsWith("/admin") && !pathname.startsWith("/admin/login");
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
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

  useEffect(() => { setCollapsed(window.localStorage.getItem("mb-sidebar") === "rail"); }, []);
  useEffect(() => { setOpen(false); }, [pathname]);

  function toggleRail() {
    setCollapsed((value) => {
      window.localStorage.setItem("mb-sidebar", value ? "full" : "rail");
      return !value;
    });
  }

  const current = activeHref(pathname);
  const inAdmin = pathname.startsWith("/admin");
  const crumbs = breadcrumbs(pathname, REL_TITLES);

  return (
    <div className={`app-shell${open ? " is-open" : ""}${collapsed ? " is-collapsed" : ""}`}>
      <aside className="mb-sidebar" id="app-navigation">
        <Link href="/" className="mb-brand" aria-label="MathBank home">
          <span className="mb-brand-mark"><Icon name="infinity" /></span>
          <span className="mb-brand-text">MathBank</span>
        </Link>
        <nav className="mb-nav" aria-label="Main navigation">
          {NAV_GROUPS.map((group) => {
            const items = group.label === "Admin" && !inAdmin ? [{ href: "/admin", label: "Admin", icon: "shield-lock" }] : group.items;
            return (
              <div key={group.label}>
                <div className="mb-nav-group-label">{group.label}</div>
                {items.map(({ href, label, icon }) => {
                  const active = href === current;
                  return (
                    <Link key={href} href={href} className={`mb-nav-link${active ? " active" : ""}`}
                      aria-current={active ? "page" : undefined} title={label}>
                      <Icon name={icon} />
                      <span className="mb-nav-text">{label}</span>
                    </Link>
                  );
                })}
              </div>
            );
          })}
        </nav>
        <div className="mb-sidebar-foot">
          <button type="button" className="mb-nav-link border-0 bg-transparent d-none d-lg-flex" onClick={toggleRail}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} title={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
            <Icon name={collapsed ? "layout-sidebar" : "layout-sidebar-inset"} />
            <span className="mb-nav-text">Collapse</span>
          </button>
        </div>
      </aside>
      <button type="button" className="mb-backdrop" aria-label="Close navigation" onClick={() => setOpen(false)} tabIndex={-1} />
      <div className="mb-main">
        <header className="mb-topbar">
          <button type="button" className="btn btn-ghost mb-icon-btn d-lg-none" aria-controls="app-navigation" aria-expanded={open}
            aria-label="Toggle navigation" onClick={() => setOpen((v) => !v)}>
            <Icon name="list" />
          </button>
          <nav aria-label="Breadcrumb" className="min-w-0 flex-grow-1">
            <ol className="mb-crumbs">
              {crumbs.map((c, i) => (
                <li key={`${c.href}-${i}`}>
                  {i === crumbs.length - 1
                    ? <span aria-current="page">{i === 0 ? <Icon name="house-door" label="Home" /> : c.label}</span>
                    : <Link href={c.href}>{i === 0 ? <Icon name="house-door" label="Home" /> : c.label}</Link>}
                </li>
              ))}
            </ol>
          </nav>
          {pathname !== "/" && (
            <Link href="/" className="btn btn-ghost mb-icon-btn" aria-label="Ask the tutor" title="Ask the tutor"><Icon name="chat-dots" /></Link>
          )}
          <UserMenu student={student} admin={isAdminArea} />
        </header>
        <main className="mb-content">{children}</main>
      </div>
    </div>
  );
}
