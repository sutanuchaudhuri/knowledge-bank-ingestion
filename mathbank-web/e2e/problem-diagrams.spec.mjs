import { expect, test } from "@playwright/test";

const CODE = "PAPER_SMT_2010_GEOM_Q06";

test("SMT source diagrams exist and image proxy excludes the solution page", async ({ request }) => {
  const response = await request.get(`/api/rest/solve/diagrams/${CODE}`);
  expect(response.ok()).toBeTruthy();
  const images = await response.json();
  expect(images.length).toBeGreaterThan(0);
  for (const image of images) {
    expect(image.source).toBe("PDF_PROBLEM_PAGE");
    const binary = await request.get(`/api/rest/solve/images/${image.problem_image_id}`);
    expect(binary.ok()).toBeTruthy();
    expect(binary.headers()["content-type"]).toMatch(/^image\//);
  }
});

test("chat renders real SMT images without a paid agent call", async ({ page }) => {
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
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(images.first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});
