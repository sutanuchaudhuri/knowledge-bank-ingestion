import { expect, test } from "@playwright/test";
import { POWER_POINT_PROBLEM, loginAdmin, loginStudent, watchPageErrors } from "./helpers.mjs";

// Student input add-ons (requirements 29) and shared widgets (requirements 27). No paid calls:
// ElevenLabs TTS/STT and the agentic formatter are intercepted with page.route; only the free
// voice health probe and the deterministic formatter reach real services.

test("home chat composer: symbols, quick format and KaTeX preview", async ({ page }) => {
  const watch = watchPageErrors(page);
  await page.goto("/");
  const input = page.getByLabel("Your question");
  await expect(input).toBeEnabled({ timeout: 30_000 });
  await input.fill("PA*PB = PT^2");
  await page.getByTestId("format-quick").click();
  await expect(input).toHaveValue("$PA \\cdot PB = PT^2$");
  await expect(page.getByTestId("composer-preview").locator(".katex").first()).toBeVisible();
  await page.getByTestId("toggle-symbols").click();
  await expect(page.getByTestId("symbol-toolbar")).toBeVisible();
  await input.fill("");
  await page.getByTestId("symbol-toolbar").getByRole("button", { name: "∠" }).click();
  await expect(input).toHaveValue("$\\angle $");
  watch.assertClean();
});

test("format-math proxy: deterministic for anonymous callers, same-origin enforced", async ({ page }) => {
  const ok = await page.request.post("/api/format-math", { data: { text: "angle ABC = 90 deg" }, headers: { Origin: "http://localhost:5173" } });
  expect(ok.status()).toBe(200);
  expect((await ok.json()).formatted).toBe("$\\angle ABC = 90^\\circ$");
  const foreign = await page.request.post("/api/format-math", { data: { text: "x" }, headers: { Origin: "http://evil.example" } });
  expect(foreign.status()).toBe(403);
});

test("voice routes: free health probe and request validation (no characters billed)", async ({ page }) => {
  const health = await (await page.request.get("/api/voice/health")).json();
  expect(health).toHaveProperty("configured");
  const origin = { Origin: "http://localhost:5173" };
  expect((await page.request.post("/api/voice/tts", { data: { text: "" }, headers: origin })).status()).toBeGreaterThanOrEqual(400);
  expect((await page.request.post("/api/voice/tts", { data: { text: "hi" }, headers: { Origin: "http://evil.example" } })).status()).toBe(403);
  expect((await page.request.post("/api/voice/tts", { data: { text: "x".repeat(1300) }, headers: origin })).status()).toBeGreaterThanOrEqual(400);
});

test("solve workspace composer: AI format (mocked) keeps the student's words", async ({ page }) => {
  await loginStudent(page);
  const watch = watchPageErrors(page);
  await page.route("**/api/format-math", (route) => route.fulfill({ json: { formatted: "Since $PA \\cdot PB = PT^2$ we are done", engine: "agentic", warnings: [] } }));
  await page.goto(`/learn/solve/${POWER_POINT_PROBLEM}`);
  const leave = page.getByRole("button", { name: "Leave the detour and go back now" });
  if (await leave.isVisible().catch(() => false)) await leave.click();
  const input = page.getByLabel("Your reasoning for this step");
  await expect(input).toBeVisible();
  await input.fill("Since PA*PB = PT^2 we are done");
  await page.getByTestId("step-composer").getByTestId("format-ai").click();
  await expect(input).toHaveValue("Since $PA \\cdot PB = PT^2$ we are done");
  await expect(page.getByTestId("composer-note")).toContainText("AI formatted");
  watch.assertClean();
});

test("admin widget gallery renders server specs; speak button sends speakable text (TTS mocked)", async ({ page }) => {
  await loginAdmin(page);
  const watch = watchPageErrors(page);
  let spoken = null;
  await page.route("**/api/voice/tts", async (route) => {
    spoken = route.request().postDataJSON().text;
    await route.fulfill({ status: 503, json: { error: "mocked" } });
  });
  await page.goto("/admin/widgets");
  const gallery = page.getByTestId("widget-gallery");
  await expect(gallery.locator('[data-widget-type="GEOMETRY_DIAGRAM"]').first()).toBeVisible();
  await expect(gallery.locator('[data-widget-type="GEOMETRY_DIAGRAM"] svg circle').first()).toBeVisible();
  await expect(gallery.locator('[data-widget-type="POLL_RESULT"] .progress-bar').first()).toBeVisible();
  await expect(gallery.locator('[data-widget-type="STEP_PROGRESS"] .katex').first()).toBeVisible();
  await expect(gallery.locator('[data-widget-type="TABLE"]')).toBeVisible();
  await expect(page.getByText(/invalid:/)).toHaveCount(0);
  await page.getByLabel("Playground input").fill("PA*PB = PT^2");
  await page.getByTestId("playground-composer").getByTestId("format-quick").click();
  await page.getByTestId("speak-button").click();
  await expect.poll(() => spoken).toBe("P A times P B equals P T squared");
  watch.assertClean();
});
