// Single source for the sidebar menu and breadcrumbs (requirements/30).

export const NAV_GROUPS = [
  {
    label: "Learn",
    items: [
      { href: "/", label: "Tutor", icon: "chat-dots" },
      { href: "/learn", label: "Guided practice", icon: "signpost-split" },
      { href: "/learn/attempt-media", label: "My submitted work", icon: "file-earmark-richtext" },
      { href: "/learn/conversations", label: "My conversations", icon: "chat-left-text" },
      { href: "/profile", label: "My progress", icon: "graph-up-arrow" },
    ],
  },
  {
    label: "Explore",
    items: [
      { href: "/db", label: "Corpus", icon: "database" },
      { href: "/db/search", label: "Find similar", icon: "stars" },
      { href: "/artifacts", label: "Artifact library", icon: "collection" },
      { href: "/graph", label: "Knowledge graph", icon: "bezier2" },
    ],
  },
  {
    label: "Admin",
    items: [
      { href: "/admin", label: "Dashboard", icon: "speedometer2" },
      { href: "/admin/corpus", label: "Corpus repair", icon: "database" },
      { href: "/admin/attempt-media", label: "Attempt media review", icon: "clipboard-check" },
      { href: "/admin/textbooks", label: "Textbooks", icon: "book" },
      { href: "/admin/pedagogy", label: "Pedagogy review", icon: "patch-check" },
      { href: "/admin/tutoring-routes", label: "Teaching routes", icon: "list-check" },
      { href: "/admin/knowledge-gaps", label: "Knowledge gaps", icon: "exclamation-diamond" },
      { href: "/admin/imports", label: "Imports", icon: "box-arrow-in-down" },
      { href: "/admin/conversations", label: "Conversations", icon: "people" },
      { href: "/admin/widgets", label: "Widgets", icon: "puzzle" },
      { href: "/admin/geometry-scenes", label: "Geometry diagnostics", icon: "activity" },
    ],
  },
];

const ALL_ITEMS = NAV_GROUPS.flatMap((g) => g.items);

function matches(href, pathname) {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

/** The single most specific nav item for a pathname (longest matching href). */
export function activeHref(pathname = "/") {
  return ALL_ITEMS.filter((item) => matches(item.href, pathname))
    .sort((a, b) => b.href.length - a.href.length)[0]?.href ?? null;
}

const SEGMENT_LABELS = {
  db: "Corpus", problems: "Problems", concepts: "Concepts", techniques: "Techniques", search: "Find similar",
  graph: "Knowledge graph", learn: "Practice", solve: "Solve", conversations: "Conversations",
  profile: "My progress", admin: "Admin", textbooks: "Textbooks", pedagogy: "Pedagogy review",
  "knowledge-gaps": "Knowledge gaps", imports: "Imports", widgets: "Widgets", login: "Sign in",
  "attempt-media": "My submitted work", artifacts: "Artifact library", corpus: "Corpus repair",
  "geometry-scenes": "Geometry diagnostics",
  "tutoring-routes": "Teaching routes",
};

const titleCase = (s) => s.replace(/[-_]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

/**
 * Breadcrumb trail for a pathname: [{ href, label }]. The last crumb is the current page.
 * Codes such as PRASOLOV_PGV1_CH03_P050 are kept verbatim; slugs are title-cased.
 */
export function breadcrumbs(pathname = "/", relationshipTitles = {}) {
  const parts = pathname.split("/").filter(Boolean);
  const crumbs = [{ href: "/", label: "Home" }];
  let href = "";
  parts.forEach((part, index) => {
    href += `/${part}`;
    const decoded = decodeURIComponent(part);
    const previous = parts[index - 1];
    let label = SEGMENT_LABELS[decoded];
    if (decoded === "attempt-media" && previous === "admin") label = "Attempt media review";
    if (previous === "graph" && relationshipTitles[decoded]) label = relationshipTitles[decoded];
    if (!label) label = /^[A-Z0-9_.-]+$/.test(decoded) ? decoded : titleCase(decoded);
    // "/learn/solve" has no page of its own; link it back to guided practice.
    crumbs.push({ href: decoded === "solve" && previous === "learn" ? "/learn" : href, label });
  });
  return crumbs;
}

/** Initials and a deterministic tone for an avatar (same output on server and client). */
export function avatarFor(name = "") {
  const clean = String(name || "").trim();
  const words = clean.split(/[\s@._-]+/).filter(Boolean);
  const initials = (words.length > 1 ? words[0][0] + words[1][0] : (words[0] || "?").slice(0, 2)).toUpperCase();
  let hash = 0;
  for (const ch of clean) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  const tones = ["#6366f1", "#0ea5e9", "#10b981", "#f59e0b", "#ec4899", "#8b5cf6", "#14b8a6", "#ef4444"];
  return { initials, color: tones[hash % tones.length] };
}
