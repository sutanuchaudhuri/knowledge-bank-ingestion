import { test, expect } from "@playwright/test";

const plan = {
  subject: "GEOMETRY", topic: "Quadrilateral incircles", title: "Generated quadrilateral",
  summary: "Construction sketch only; does not assert equal radii or right angles.",
  elements: [{ kind: "POINT", id: "A", label: "A", x: 100, y: 100 }],
};
const text = "**Problem:**\nA convex quadrilateral $ABCD$ has equal incircle radii. Prove that it is a rectangle.\n\n**Source:** Prasolov\n\n```geometry-artifact\n" + JSON.stringify(plan) + "\n```";

for (const width of [1440, 390]) {
  test(`chat problem/source and generated diagram at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.route("**/api/rest/learner/me", (route) => route.fulfill({ json: { first_name: "Test" } }));
    await page.route("**/api/agent/session", (route) => route.fulfill({ json: { linked: true } }));
    await page.route("**/api/agent/run", (route) => route.fulfill({
      contentType: "text/event-stream",
      body: `data: ${JSON.stringify({ type: "answer", text })}\n\ndata: ${JSON.stringify({ type: "done" })}\n\n`,
    }));
    await page.route("**/api/rest/artifacts/geometry-preview/content", (route) => {
      expect(route.request().postDataJSON().subject).toBe("GEOMETRY");
      return route.fulfill({ contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600"><circle cx="100" cy="100" r="4"/><text x="110" y="90">A</text></svg>' });
    });
    await page.goto("/");
    await page.getByRole("textbox", { name: "Your question" }).fill("Create the diagram");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    const problem = page.getByRole("region", { name: "Practice problem" });
    await expect(problem).toContainText("convex quadrilateral");
    const source = page.getByRole("region", { name: "Problem source" });
    await expect(source).toContainText("Prasolov");
    expect(await problem.evaluate((el) => getComputedStyle(el).backgroundColor))
      .not.toBe(await source.evaluate((el) => getComputedStyle(el).backgroundColor));
    const image = page.getByRole("img", { name: "Generated quadrilateral" });
    await expect(image).toBeVisible();
    await expect.poll(() => image.evaluate((el) => el.naturalWidth)).toBeGreaterThan(0);
    await expect(page.getByText("Generated illustration · not the source figure", { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}

test("delegated algebra preview renders LaTeX and a private generated visual", async ({ page }) => {
  const algebra = {
    subject: "ALGEBRA", topic: "Linear equation", title: "Generated algebra card",
    elements: [{ kind: "EQUATION", id: "eq1", latex: "2x+3=7", reason: "Given equation" }],
  };
  const answer = "```artifact-preview\n" + JSON.stringify(algebra) + "\n```";
  await page.route("**/api/rest/learner/me", (route) => route.fulfill({ json: { first_name: "Test" } }));
  await page.route("**/api/agent/session", (route) => route.fulfill({ json: { linked: true } }));
  await page.route("**/api/agent/run", (route) => route.fulfill({
    contentType: "text/event-stream",
    body: `data: ${JSON.stringify({ type: "answer", text: answer })}\n\ndata: ${JSON.stringify({ type: "done" })}\n\n`,
  }));
  await page.route("**/api/rest/artifacts/preview/content", (route) => {
    expect(route.request().postDataJSON().subject).toBe("ALGEBRA");
    return route.fulfill({ contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600"><text x="60" y="100">2x+3=7</text></svg>' });
  });
  await page.goto("/");
  await page.getByRole("textbox", { name: "Your question" }).fill("Show an algebra card");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByRole("img", { name: algebra.title })).toBeVisible();
  await expect(page.locator(".mb-generated-diagram .katex")).toBeVisible();
  await expect(page.getByText("Given equation", { exact: true })).toBeVisible();
});
