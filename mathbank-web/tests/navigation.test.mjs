import assert from "node:assert/strict";
import test from "node:test";
import { NAV_GROUPS, activeHref, avatarFor, breadcrumbs } from "../lib/navigation.mjs";

test("every nav item has a unique href, a label and an icon", () => {
  const items = NAV_GROUPS.flatMap((g) => g.items);
  assert.equal(new Set(items.map((i) => i.href)).size, items.length);
  for (const item of items) {
    assert.ok(item.label && item.icon, item.href);
  }
});

test("activeHref picks the most specific item and keeps home exact", () => {
  assert.equal(activeHref("/"), "/");
  assert.equal(activeHref("/learn"), "/learn");
  assert.equal(activeHref("/learn/conversations"), "/learn/conversations");
  assert.equal(activeHref("/learn/solve/PRASOLOV_PGV1_CH03_P050"), "/learn");
  assert.equal(activeHref("/db/search"), "/db/search");
  assert.equal(activeHref("/db/problems/X"), "/db");
  assert.equal(activeHref("/admin/textbooks/problems/X"), "/admin/textbooks");
  assert.equal(activeHref("/admin"), "/admin");
  assert.equal(activeHref("/dbx"), null);
});

test("breadcrumbs label known segments, keep codes verbatim and title-case slugs", () => {
  assert.deepEqual(breadcrumbs("/"), [{ href: "/", label: "Home" }]);
  assert.deepEqual(breadcrumbs("/admin/knowledge-gaps"), [
    { href: "/", label: "Home" },
    { href: "/admin", label: "Admin" },
    { href: "/admin/knowledge-gaps", label: "Knowledge gaps" },
  ]);
  const solve = breadcrumbs("/learn/solve/PRASOLOV_PGV1_CH03_P050");
  assert.deepEqual(solve.map((c) => c.label), ["Home", "Practice", "Solve", "PRASOLOV_PGV1_CH03_P050"]);
  assert.equal(solve[2].href, "/learn", "/learn/solve has no page of its own");
  assert.equal(breadcrumbs("/graph/some-view").at(-1).label, "Some View");
  assert.equal(breadcrumbs("/graph/uses-technique", { "uses-technique": "Problem → Technique" }).at(-1).label,
    "Problem → Technique");
});

test("avatarFor is deterministic with sensible initials", () => {
  assert.equal(avatarFor("Ada Lovelace").initials, "AL");
  assert.equal(avatarFor("ada.lovelace@example.com").initials, "AL");
  assert.equal(avatarFor("Admin").initials, "AD");
  assert.equal(avatarFor("").initials, "?");
  assert.deepEqual(avatarFor("Ada Lovelace"), avatarFor("Ada Lovelace"));
  assert.match(avatarFor("x").color, /^#[0-9a-f]{6}$/);
});
