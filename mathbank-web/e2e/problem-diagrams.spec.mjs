import { expect, test } from "@playwright/test";

const CODE = "PAPER_SMT_2010_GEOM_Q06";

test("SMT source diagrams exist and image proxy excludes the solution page", async ({ request }) => {
  const response = await request.get(`/api/rest/solve/diagrams/${CODE}`);
  expect(response.ok()).toBeTruthy();
  const images = await response.json();
  expect(images.length).toBeGreaterThan(0);
  for (const image of images) {
    expect(image.source).toBe("PDF_QUESTION_FIGURE");
    const binary = await request.get(`/api/rest/solve/images/${image.problem_image_id}`);
    expect(binary.ok()).toBeTruthy();
    expect(binary.headers()["content-type"]).toMatch(/^image\//);
  }
});

test("chat renders real SMT images without a paid agent call", async ({ page }) => {
  await page.route("**/api/agent/session", (route) => route.fulfill({
    contentType: "application/json", body: JSON.stringify({ linked: false }),
  }));
  await page.route("**/api/agent/run", (route) => route.fulfill({
    contentType: "text/event-stream",
    body: `data: ${JSON.stringify({ type: "answer", text: `Try **${CODE}**. Let $OT=25$ and $AM=MB=30$. Find $MD$.` })}\n\ndata: {"type":"done"}\n\n`,
  }));
  await page.goto("/");
  const input = page.getByRole("textbox", { name: "Your question" });
  await expect(input).toBeEnabled();
  await input.fill("A hard geometry problem to try");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const images = page.getByTestId("problem-diagrams").getByRole("img");
  await expect(images.first()).toBeVisible();
  await expect.poll(() => images.first().evaluate((img) => img.complete && img.naturalWidth)).toBeGreaterThan(0);
  const size = await images.first().evaluate((img) => ({ width: img.naturalWidth, height: img.naturalHeight }));
  expect(size.width).toBeLessThan(500);
  expect(size.height).toBeLessThan(500);
  const source = page.getByTestId("problem-source").filter({ has: page.getByRole("button", { name: "Source", exact: true }) });
  await expect(source).toHaveCount(1);
  await expect(source.locator("iframe")).toHaveCount(0);
  await source.getByRole("button", { name: "Source", exact: true }).click();
  await expect(source.locator("iframe")).toHaveAttribute("src", `/api/rest/solve/source-pdf/${CODE}`);
  const pdf = await page.request.get(`/api/rest/solve/source-pdf/${CODE}`);
  expect(pdf.ok()).toBeTruthy();
  expect(pdf.headers()["content-type"]).toContain("application/pdf");
  expect((await pdf.body()).subarray(0, 5).toString()).toBe("%PDF-");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(images.first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await source.getByRole("button", { name: "Source", exact: true }).click();
  await expect(source.locator("iframe")).toHaveCount(0);
});

test("original PDF remains available when a problem has no extracted diagram", async ({ page }) => {
  await page.route("**/api/agent/session", (route) => route.fulfill({
    contentType: "application/json", body: JSON.stringify({ linked: false }),
  }));
  await page.route("**/api/rest/solve/diagrams/**", (route) => route.fulfill({
    contentType: "application/json", body: "[]",
  }));
  await page.route("**/api/agent/run", (route) => route.fulfill({
    contentType: "text/event-stream",
    body: `data: ${JSON.stringify({ type: "answer", text: `Try **${CODE}**. No safely extracted figure is available.` })}\n\ndata: {"type":"done"}\n\n`,
  }));
  await page.goto("/");
  const input = page.getByRole("textbox", { name: "Your question" });
  await expect(input).toBeEnabled();
  await input.fill("Show the original question");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const source = page.getByTestId("problem-source");
  await source.getByRole("button", { name: "Source", exact: true }).click();
  await expect(source.locator("iframe")).toBeVisible();
  await expect(page.getByTestId("problem-diagrams")).toHaveCount(0);
});
