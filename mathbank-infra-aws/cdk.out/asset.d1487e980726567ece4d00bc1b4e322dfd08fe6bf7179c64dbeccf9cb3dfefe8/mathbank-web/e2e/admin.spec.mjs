import { expect, test } from "@playwright/test";
import { loginAdmin, watchPageErrors } from "./helpers.mjs";

test("admin pages require login", async ({ page }) => {
  await page.goto("/admin/conversations");
  await expect(page).toHaveURL(/\/admin\/login/);
});

test("textbook corpus proxy refuses anonymous callers", async ({ request }) => {
  expect((await request.get("/api/rest/admin/textbooks/coverage")).status()).toBe(401);
  expect((await request.get("/api/rest/admin/textbooks/diagrams/PRASOLOV-S-1_9-D01/image")).status()).toBe(401);
});

test("import admin proxy refuses anonymous callers", async ({ request }) => {
  expect((await request.get("/api/rest/admin/imports/packages")).status()).toBe(401);
  expect((await request.post("/api/rest/admin/imports/review-dag", { data: { code: "X", status: "APPROVED" } })).status()).toBe(401);
});

test.describe("signed-in admin", () => {
  test.beforeEach(async ({ page }) => {
    await loginAdmin(page);
  });

  const PAGES = [
    { path: "/admin", heading: "Corpus ingestion admin" },
    { path: "/admin/conversations", heading: "Student tutor conversations" },
    { path: "/admin/knowledge-gaps", heading: "Knowledge gaps & recovery" },
    { path: "/admin/pedagogy" },
    { path: "/admin/textbooks", heading: "Textbook corpus" },
    { path: "/admin/imports", heading: "Imports & reconciliation" },
  ];

  for (const { path, heading } of PAGES) {
    test(`renders ${path}`, async ({ page }) => {
      const watch = watchPageErrors(page);
      await page.goto(path);
      await expect(page).toHaveURL(new RegExp(`${path}$`));
      if (heading) await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
      watch.assertClean();
    });
  }

  test("conversation list is rebuilt from linked agent sessions", async ({ page }) => {
    const res = await page.request.get("/api/rest/admin/conversations?limit=5");
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body.linked)).toBe(true);
    expect(typeof body.unlinked_count).toBe("number");
  });

  test("textbook corpus: coverage matrix, problem list and full problem detail with diagram", async ({ page }) => {
    test.setTimeout(90_000);
    const watch = watchPageErrors(page);
    await page.goto("/admin/textbooks");
    const matrix = page.getByTestId("coverage-matrix");
    await expect(matrix.locator("tbody tr").first()).toBeVisible({ timeout: 30_000 });
    await expect(matrix).toContainText("solution step");
    await expect(page.getByTestId("chapter-table").locator("tbody tr")).toHaveCount(30);

    await page.getByRole("tab", { name: "Problems" }).click();
    await page.locator("#pf-q").fill("1.9");
    await page.locator("#pf-ch").fill("1");
    await page.getByRole("button", { name: "Filter" }).click();
    const link = page.getByTestId("problem-table").getByRole("link", { name: "1.9", exact: true });
    await expect(link).toBeVisible({ timeout: 20_000 });
    await link.click();

    await expect(page.getByRole("heading", { level: 1, name: "Problem 1.9" })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("problem-statement")).not.toBeEmpty();
    await page.getByRole("tab", { name: /Solution/ }).click();
    await expect(page.getByTestId("solution-part").first().locator("li").first()).toBeVisible();
    await page.getByRole("tab", { name: /Transformations/ }).click();
    await expect(page.getByTestId("item-cards").locator("> div").first()).toBeVisible();
    await expect(page.getByTestId("item-review").first()).toContainText("APPROVED");
    await page.getByRole("tab", { name: /Diagrams/ }).click();
    const img = page.getByTestId("diagram-image").first();
    await expect(img).toBeVisible();
    await expect.poll(() => img.evaluate((el) => el.complete && el.naturalWidth)).toBeGreaterThan(0);
    await page.getByRole("tab", { name: /Store status/ }).click();
    await expect(page.getByTestId("store-status")).toContainText("Problem node");
    watch.assertClean();
  });

  test("imports: packages reconcile and graph/vector matrix is green (read-only)", async ({ page }) => {
    test.setTimeout(90_000);
    const watch = watchPageErrors(page);
    await page.goto("/admin/imports");
    const pk = page.getByTestId("import-packages");
    await expect(pk.locator("tbody tr")).toHaveCount(2, { timeout: 30_000 });
    await expect(pk).toContainText("POSTGRES_COMPLETE");
    await page.getByRole("tab", { name: "Graph & embeddings" }).click();
    await expect(page.getByRole("cell", { name: "solution step", exact: true }).first()).toBeVisible({ timeout: 60_000 });
    watch.assertClean();
  });

  test("problem detail exposes the DAG review tab (read-only)", async ({ page }) => {
    test.setTimeout(60_000);
    const watch = watchPageErrors(page);
    await page.goto("/admin/textbooks/problems/PRASOLOV_PGV1_CH14_P021");
    await page.getByRole("tab", { name: "DAG review" }).click();
    const dag = page.getByTestId("dag-review");
    await expect(dag).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("dag-review-status")).toBeVisible();
    await expect(dag.locator("tbody tr").first()).toBeVisible();
    watch.assertClean();
  });
});
