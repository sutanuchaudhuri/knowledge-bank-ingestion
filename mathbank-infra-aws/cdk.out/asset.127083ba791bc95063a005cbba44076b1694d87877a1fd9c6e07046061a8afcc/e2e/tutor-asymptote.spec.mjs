import { readFile } from "node:fs/promises";
import { test, expect } from "@playwright/test";
import { renderAsymptote } from "../lib/asymptoteRenderer.mjs";

const source = await readFile(new URL("../tests/fixtures/prism.asy", import.meta.url), "utf8");
const statement = String.raw`A right prism with height \( h \) has bases that are regular hexagons with sides of length \( 12 \). A vertex \( A \) and its three adjacent vertices form a triangular pyramid. The dihedral angle measures \( 60 \) degrees. Find \( h^2 \).`;
const answer = `**Problem: ${statement}\n[asy]${source}[/asy]\n\n**SourceAIME, 2016, Problem 4. [Link to source](https://artofproblemsolving.com/wiki/index.php/2016_AIME_I_Problems/Problem_4)`;

async function mockChat(page, text) {
  await page.route("**/api/rest/learner/me", (route) => route.fulfill({ json: { first_name: "Test" } }));
  await page.route("**/api/agent/session", (route) => route.fulfill({ json: { linked: true } }));
  await page.route("**/api/agent/run", (route) => route.fulfill({
    contentType: "text/event-stream",
    body: `data: ${JSON.stringify({ type: "answer", text })}\n\ndata: ${JSON.stringify({ type: "done" })}\n\n`,
  }));
  await page.goto("/");
  await page.getByRole("textbox", { name: "Your question" }).fill("Show the prism problem");
  await page.getByRole("button", { name: "Send", exact: true }).click();
}

for (const width of [1440, 390]) {
  test(`prism LaTeX and real source-code diagram at ${width}px`, async ({ page }) => {
    test.skip(process.env.RUN_ASYMPTOTE_TESTS !== "1", "Opt in to installed isolated compiler checks");
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.setViewportSize({ width, height: 900 });
    const png = await renderAsymptote(source);
    await page.route("**/api/diagrams/asymptote", (route) => {
      expect(route.request().postDataJSON().source).toBe(source.trim());
      return route.fulfill({ contentType: "image/png", body: png });
    });
    await mockChat(page, answer);
    const problem = page.getByRole("region", { name: "Practice problem" });
    await expect(problem.locator(".katex")).toHaveCount(5);
    await expect(problem).toContainText("right prism");
    await expect(problem.locator(".mb-tutor-problem-title")).toHaveText("Problem");
    const image = problem.getByRole("img", { name: "Diagram rendered from the problem's Asymptote source" });
    await expect(image).toBeVisible();
    await expect.poll(() => image.evaluate((el) => el.naturalWidth)).toBeGreaterThan(100);
    await expect(problem.locator("pre")).not.toBeVisible();
    await expect(page.getByRole("region", { name: "Problem source" })).toContainText("AIME, 2016");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(errors).toEqual([]);
    await problem.getByText("Diagram source (Asymptote)", { exact: false }).click();
    await expect(problem.locator("pre")).toContainText("import bsp");
  });
}

test("compiler failure is visible, with no broken or unrelated image", async ({ page }) => {
  await page.route("**/api/diagrams/asymptote", (route) => route.fulfill({ status: 422, json: { error: "The embedded diagram could not be compiled safely." } }));
  await mockChat(page, answer);
  await expect(page.getByTestId("asymptote-diagram").getByRole("alert")).toContainText("could not be compiled safely");
  await expect(page.locator('[data-testid="asymptote-diagram"] img')).toHaveCount(0);
});

test("incomplete streaming Asymptote is not compiled", async ({ page }) => {
  let requests = 0;
  await page.route("**/api/diagrams/asymptote", (route) => { requests += 1; return route.abort(); });
  await mockChat(page, "**Problem:**\nFind \\(h\\).\n[asy] import bsp;");
  await expect(page.getByRole("status").filter({ hasText: "Receiving diagram source" })).toBeVisible();
  expect(requests).toBe(0);
});
