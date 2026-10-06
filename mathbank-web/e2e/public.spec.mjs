import { expect, test } from "@playwright/test";
import { watchPageErrors } from "./helpers.mjs";

// Public pages must render without hydration or runtime errors.
const PAGES = [
  { path: "/", heading: "MathBank Tutor" },
  { path: "/db", heading: "MathBank Corpus (Postgres)" },
  { path: "/db/problems" },
  { path: "/db/concepts" },
  { path: "/db/techniques" },
  { path: "/db/search" },
  { path: "/graph" },
  { path: "/learn" },
  { path: "/login" },
  { path: "/admin/login", heading: "Admin login" },
];

for (const { path, heading } of PAGES) {
  test(`renders ${path} without hydration errors`, async ({ page }) => {
    const watch = watchPageErrors(page);
    const response = await page.goto(path);
    expect(response.status()).toBeLessThan(400);
    await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
    if (heading) await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
    await page.waitForLoadState("networkidle").catch(() => {});
    watch.assertClean();
  });
}

test("anonymous visitor sees the student login entry point", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: "Student login" })).toBeVisible();
  await expect(page.getByTestId("chat-saved-state")).toContainText(/sign in/i);
});

test("corpus lists the Prasolov textbook", async ({ page }) => {
  await page.goto("/db");
  const row = page.getByRole("row", { name: /PRASOLOV_PGV1/ });
  await expect(row).toBeVisible();
  await expect(row).toContainText("1697");
});
