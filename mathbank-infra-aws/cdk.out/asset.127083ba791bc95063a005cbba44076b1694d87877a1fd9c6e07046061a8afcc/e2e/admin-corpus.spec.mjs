import { test, expect } from "@playwright/test";
import { mockAdminSession } from "./mock-auth.mjs";
import { watchPageErrors } from "./helpers.mjs";

const id = "11111111-1111-4111-8111-111111111111";
const code = "AIME_1985_Q04";
async function fixture(page, baseURL) {
  await mockAdminSession(page, baseURL);
  const calls = [];
  const drafts = [{ draft_id: id, kind: "NEW_PROBLEM", state: "DRAFT", origin: "AI", revision: 1,
    payload: { statement: "Find the value of $2+3$.", solution: "Addition gives $5$.", answer: "5", diagram_required: false },
    note: "Explicit AI generation: addition", canonical_code: null }];
  await page.route("**/api/rest/**", async (route) => {
    const req = route.request(), url = new URL(req.url());
    if (!url.pathname.includes("/admin/corpus/")) return route.fulfill({ json: {} });
    calls.push({ path: url.pathname, query: url.search, method: req.method(),
      body: req.method() === "GET" ? null : req.postDataJSON() });
    if (req.method() === "POST" && url.pathname.endsWith("/review")) {
      const data = req.postDataJSON();
      drafts[0].state = data.decision; drafts[0].review_note = data.note;
      drafts[0].canonical_code = "GENERATED_TEST_Q01";
      return route.fulfill({ json: { state: data.decision, canonical_code: "GENERATED_TEST_Q01" } });
    }
    if (req.method() !== "GET") return route.fulfill({ json: { draft_id: id, state: "DRAFT", revision: 2 } });
    if (url.pathname.endsWith("/drafts")) return route.fulfill({ json: { items: drafts.filter((d) => d.state === url.searchParams.get("state")), hasMore: false } });
    if (url.pathname.endsWith(`/${code}`)) return route.fulfill({ json: {
      canonical_code: code, statement_text: "Calculate the length shown in the diagram.", expected_hash: "0".repeat(64),
    } });
    return route.fulfill({ json: { items: [{ canonical_code: code, competition: "AIME",
      year: 1985, problem_number: 4, diagram_count: 0, diagram_missing: true, diagram_required: true }], hasMore: false } });
  });
  return calls;
}

test("repair filters, optimistic text draft and source image classification", async ({ page, baseURL }) => {
  const errors = watchPageErrors(page);
  const calls = await fixture(page, baseURL);
  await page.goto("/admin/corpus");
  await expect(page.getByRole("heading", { name: "Corpus repair & authoring" })).toBeVisible();
  await page.getByLabel("Competition code", { exact: true }).fill("AIME");
  await page.getByLabel("Year", { exact: true }).fill("1985");
  await page.getByLabel("Problem number", { exact: true }).fill("4");
  await page.getByRole("button", { name: "Find questions" }).click();
  await expect.poll(() => calls.some((c) => c.query.includes("competition=AIME") && c.query.includes("number=4"))).toBeTruthy();
  await page.getByRole("button", { name: "Edit or upload source" }).click();
  await page.getByLabel("Question Markdown", { exact: true }).fill("Calculate $AB$ using the source diagram.");
  await page.getByLabel("Source / repair note").fill("Restored from permitted source");
  await page.getByRole("button", { name: "Save text draft", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Text draft saved");
  const edit = calls.find((c) => c.body?.kind === "TEXT_EDIT");
  expect(edit.body.problem_code).toBe(code);
  expect(edit.body.expected_hash).toHaveLength(64);
  await page.getByLabel("Figure belongs to").selectOption("solution");
  await page.getByLabel("PNG or JPEG · maximum 5 MB").setInputFiles({
    name: "source.png", mimeType: "image/png",
    buffer: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1sAAAAASUVORK5CYII=", "base64"),
  });
  await page.getByLabel("I have permission to use this source image.").check();
  await page.getByRole("button", { name: "Upload private image draft" }).click();
  await expect(page.getByRole("status")).toContainText("Image is private");
  expect(calls.find((c) => c.path.endsWith("/images")).body.side).toBe("solution");
  expect(calls.some((c) => c.path.endsWith("/generate"))).toBeFalsy();
  errors.assertClean();
});

test("AI generation requires explicit consent and publication requires review", async ({ page, baseURL }) => {
  const errors = watchPageErrors(page);
  const calls = await fixture(page, baseURL);
  await page.goto("/admin/corpus");
  await page.getByRole("tab", { name: "New practice" }).click();
  await expect(page.getByRole("button", { name: "Generate private draft" })).toBeDisabled();
  await page.getByLabel("Theme and constraints").fill("An original simple addition exercise");
  await page.getByLabel("I authorize this paid generation request.").check();
  await page.getByRole("button", { name: "Generate private draft" }).click();
  await expect(page.getByRole("status")).toContainText("AI draft saved privately");
  expect(calls.find((c) => c.path.endsWith("/generate")).body.confirm_paid).toBe(true);
  expect(calls.some((c) => c.path.endsWith("/review"))).toBeFalsy();
  await page.getByRole("tab", { name: "Review drafts" }).click();
  await page.locator("summary").filter({ hasText: "NEW PROBLEM" }).click();
  await expect(page.getByRole("button", { name: "Approve & publish" })).toBeDisabled();
  await page.getByLabel(`Review note ${id}`).fill("Checked content and provenance");
  await page.getByRole("button", { name: "Approve & publish" }).click();
  await expect(page.getByRole("status")).toContainText("GENERATED_TEST_Q01");
  expect(calls.find((c) => c.path.endsWith("/review")).body.decision).toBe("APPROVED");
  errors.assertClean();
});

test("mobile authoring is readable and preserves AI origin while editing a pending draft", async ({ page, baseURL }) => {
  const calls = await fixture(page, baseURL);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/admin/corpus");
  await page.getByRole("tab", { name: "Review drafts" }).click();
  await page.locator("summary").filter({ hasText: "NEW PROBLEM" }).click();
  await page.getByRole("button", { name: "Edit this draft" }).click();
  await page.getByLabel("New question Markdown").fill("Find the value of $3+4$.");
  await page.getByRole("button", { name: "Save practice draft" }).click();
  await expect(page.getByRole("status")).toContainText("Original practice draft saved");
  const edit = calls.find((c) => c.method === "PUT");
  expect(edit.path).toContain(id);
  expect(edit.body.statement).toContain("3+4");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});
