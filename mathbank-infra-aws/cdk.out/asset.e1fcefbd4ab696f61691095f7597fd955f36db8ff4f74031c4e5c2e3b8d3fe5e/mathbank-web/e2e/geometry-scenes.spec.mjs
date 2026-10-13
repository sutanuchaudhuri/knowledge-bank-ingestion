import { test, expect } from "@playwright/test";
import { mockAdminSession } from "./mock-auth.mjs";

const scene = { scene_id: "triangle", version: 2, caption: "Reference caption", current_math_step: "step_2" };
const answer = "```geometry-scene\n" + JSON.stringify(scene) + "\n```";
const captions = ["Draw triangle ABC.", "Mark the midpoint.", "Draw the altitude."];

async function chat(page, text = answer) {
  await page.route("**/api/rest/learner/me", (route) => route.fulfill({ json: { first_name: "Test" } }));
  await page.route("**/api/agent/session", (route) => route.fulfill({ json: { linked: true } }));
  await page.route("**/api/agent/run", (route) => route.fulfill({
    contentType: "text/event-stream",
    body: `data: ${JSON.stringify({ type: "answer", text })}\n\ndata: ${JSON.stringify({ type: "done" })}\n\n`,
  }));
  await page.goto("/");
  await page.getByRole("textbox", { name: "Your question" }).fill("Show my accepted geometry scene");
  await page.getByRole("button", { name: "Send", exact: true }).click();
}

for (const width of [1440, 390]) {
  test(`accepted geometry scene stays pinned with fetched captions at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const requested = [];
    const errors = [];
    page.on("pageerror", (err) => errors.push(err.message));
    await page.route("**/api/rest/geometry-scenes/**", (route) => {
      const path = new URL(route.request().url()).pathname;
      requested.push(path);
      if (path.endsWith("/frames")) return route.fulfill({ json: { frames: [0, 1, 2, 3, 4].map((version) => ({
        version, render_path: "https://untrusted.test/must-not-use",
      })) } });
      const match = /\/versions\/(\d+)(\/render)?$/.exec(path);
      expect(match).not.toBeNull();
      const version = Number(match[1]);
      expect(version).toBeLessThanOrEqual(2);
      if (match[2]) return route.fulfill({ contentType: "image/svg+xml",
        body: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 480"><path d="M50 400L320 50L590 400Z" fill="none" stroke="black"/></svg>' });
      return route.fulfill({ json: { scene_id: scene.scene_id, version, visual_state: { caption: captions[version] } } });
    });
    await chat(page);
    const visual = page.getByTestId("geometry-scene");
    const image = visual.getByRole("img");
    await expect(image).toHaveAttribute("alt", captions[2]);
    await expect.poll(() => image.evaluate((element) => element.naturalWidth)).toBeGreaterThan(0);
    await expect(visual.getByRole("button", { name: "Next geometry frame" })).toBeDisabled();
    await visual.getByRole("button", { name: "Previous geometry frame" }).click();
    await expect(image).toHaveAttribute("alt", captions[1]);
    await expect(visual.locator("figcaption")).toHaveText(captions[1]);
    await visual.getByRole("button", { name: "Previous geometry frame" }).click();
    await expect(image).toHaveAttribute("alt", captions[0]);
    await expect(visual.getByRole("button", { name: "Previous geometry frame" })).toBeDisabled();
    await visual.getByRole("button", { name: "Next geometry frame" }).click();
    await expect(image).toHaveAttribute("alt", captions[1]);
    expect(requested[1]).toContain("/versions/2");
    expect(requested.some((path) => /\/versions\/[34]/.test(path))).toBe(false);
    await expect(visual.locator("svg")).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(errors).toEqual([]);
  });
}

test("invalid and incomplete streamed scene fences never fetch a render", async ({ page }) => {
  let requested = false;
  await page.route("**/api/rest/geometry-scenes/**", (route) => { requested = true; return route.abort(); });
  await chat(page, "```geometry-scene\n{}\n```\n\n```geometry-scene\n{\"scene_id\":");
  await expect(page.getByRole("alert").filter({ hasText: "geometry scene reference is invalid" })).toBeVisible();
  await expect(page.getByText("Receiving geometry scene…", { exact: true })).toBeVisible();
  await expect(page.getByTestId("geometry-scene")).toHaveCount(0);
  expect(requested).toBe(false);
});

test("failed image MIME does not show an accepted frame", async ({ page }) => {
  await page.route("**/api/rest/geometry-scenes/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/frames")) return route.fulfill({ json: { frames: [{ version: 2 }] } });
    if (path.endsWith("/render")) return route.fulfill({ contentType: "text/html", body: "<h1>unsafe</h1>" });
    return route.fulfill({ json: { scene_id: scene.scene_id, version: 2, visual_state: { caption: captions[2] } } });
  });
  await chat(page);
  await expect(page.getByTestId("geometry-scene").getByRole("alert")).toHaveText("Unexpected diagram response.");
  await expect(page.getByTestId("geometry-scene").getByRole("img")).toHaveCount(0);
});

test("mismatched version metadata never exposes a later caption", async ({ page }) => {
  await page.route("**/api/rest/geometry-scenes/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/frames")) return route.fulfill({ json: { frames: [{ version: 2 }] } });
    if (path.endsWith("/render")) return route.fulfill({ contentType: "image/svg+xml",
      body: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 480"/>' });
    return route.fulfill({ json: { scene_id: scene.scene_id, version: 3, visual_state: { caption: "Future proof step" } } });
  });
  await chat(page);
  const visual = page.getByTestId("geometry-scene");
  await expect(visual.getByRole("alert")).toHaveText("Unexpected diagram frame.");
  await expect(visual).not.toContainText("Future proof step");
  await expect(visual.getByRole("img")).toHaveCount(0);
});

for (const prefix of ["run", "failed"]) {
test(`protected staff ${prefix} receipt view uses only the read-only diagnostics proxy`, async ({ page, baseURL }) => {
  const run = `${prefix}_0123456789abcdef0123456789abcdef`;
  await mockAdminSession(page, baseURL);
  await page.route("**/api/rest/learner/me", (route) => route.fulfill({ json: {} }));
  await page.route(`**/api/rest/geometry-scenes/debug/runs/${run}?owner=admin`, (route) => {
    expect(route.request().method()).toBe("GET");
    expect(new URL(route.request().url()).searchParams.get("owner")).toBe("admin");
    return route.fulfill({ json: { run_id: run, status: prefix === "failed" ? "rejected" : "accepted", diagnostics: { attempts: 1 } } });
  });
  await page.goto(`/admin/geometry-scenes?run=${run}&owner=admin`);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Geometry scene diagnostics");
  await expect(page.getByTestId("geometry-run-diagnostics")).toContainText(run);
  await expect(page.getByRole("link", { name: "Geometry diagnostics", exact: true })).toHaveAttribute("aria-current", "page");
});
}

test("run view rejects unauthenticated users and invalid identifiers", async ({ page, baseURL }) => {
  await page.goto("/admin/geometry-scenes?run=run_123");
  await expect(page).toHaveURL(/\/admin\/login/);
  await mockAdminSession(page, baseURL);
  await page.goto("/admin/geometry-scenes?run=..%2Fsecret");
  await expect(page.getByRole("alert").filter({ hasText: "Invalid run identifier." })).toBeVisible();
  await page.goto("/admin/geometry-scenes?run=run_123");
  await expect(page.getByRole("alert").filter({ hasText: "A valid diagnostics owner is required." })).toBeVisible();
  await page.goto("/admin/geometry-scenes?run=run_123&owner=..%2Fother");
  await expect(page.getByRole("alert").filter({ hasText: "A valid diagnostics owner is required." })).toBeVisible();
});
