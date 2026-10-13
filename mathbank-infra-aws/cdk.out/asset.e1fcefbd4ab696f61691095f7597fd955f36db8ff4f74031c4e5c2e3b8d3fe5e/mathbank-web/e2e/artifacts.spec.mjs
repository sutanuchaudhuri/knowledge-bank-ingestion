import { test, expect } from "@playwright/test";
import { watchPageErrors } from "./helpers.mjs";
import { mockAdminSession } from "./mock-auth.mjs";

const bundleId = "11111111-1111-4111-8111-111111111111";
const assetId = "22222222-2222-4222-8222-222222222222";
const requestId = "33333333-3333-4333-8333-333333333333";
const bundle = {
  artifact_bundle_id: bundleId, title: "Euclidean algorithm", subject: "NUMBER_THEORY", topic: "GCD", status: "PUBLISHED",
  summary: "Compare the remainder at each stage.", assets: [{ artifact_asset_id: assetId, mime_type: "image/svg+xml", render_format: "SVG" }],
  frames: [
    { ordinal: 0, step_number: 1, caption: "Identify the remainder", explanation_text: "Work within modulus 7.", actions: [{ action: "HIGHLIGHT", targets: ["remainder"] }] },
    { ordinal: 1, step_number: 2, caption: "Focus on the next divisor", actions: [{ action: "DIM", targets: ["remainder"] }] },
  ],
};
test("library searches explicitly and frames use inert sanitized images with stable layout", async ({ page }) => {
  const errors = watchPageErrors(page), calls = [];
  await page.route("**/api/rest/**", async (route) => {
    const url = new URL(route.request().url()); calls.push(url.pathname);
    if (url.pathname.endsWith("/learner/me")) return route.fulfill({ json: null });
    if (url.pathname.endsWith("/embedding-profile")) return route.fulfill({ json: { status: "AVAILABLE", model: "verified-test-model", dimensions: 1024 } });
    if (url.pathname.endsWith("/content")) return route.fulfill({ contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200" onload="alert(1)"><script>alert(2)</script><image href="https://untrusted.test/a"/><text id="remainder" x="10" y="50">17 mod 7 = 3</text></svg>' });
    if (url.pathname.includes("/search")) return route.fulfill({ json: { items: [bundle] } });
    if (url.pathname.endsWith("/assets")) return route.fulfill({ json: { assets: bundle.assets } });
    if (url.pathname.endsWith("/frames")) return route.fulfill({ json: { base_asset_id: assetId, frames: bundle.frames } });
    return route.fulfill({ json: { ...bundle, assets: undefined, frames: undefined } });
  });
  await page.goto("/artifacts");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Artifact library");
  expect(calls.some((p) => /search|generate|requests/.test(p))).toBe(false);
  await page.getByLabel("Search library", { exact: true }).fill("Euclidean algorithm");
  await page.getByRole("button", { name: "Search metadata", exact: true }).click();
  await page.getByRole("button", { name: /Euclidean algorithm.*GCD/ }).click();
  const preview = page.getByRole("img", { name: /Euclidean algorithm/ });
  await expect(preview).toBeVisible();
  const svg = await preview.evaluate(async (image) => (await fetch(image.src)).text());
  expect(svg).not.toMatch(/script|onload|untrusted/);
  expect(svg).toContain('font-weight="700"');
  await page.getByRole("button", { name: "Next artifact frame", exact: true }).click();
  await expect(page.getByText("Frame 2 / 2", { exact: true })).toBeVisible();
  await page.getByLabel("Compare previous state").check();
  await expect(page.getByRole("img", { name: /Euclidean algorithm/ })).toHaveCount(2);
  await page.reload();
  await expect(page.getByText("Frame 1 / 2", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  errors.assertClean();
});
test("requests save first and generation and semantic retrieval never run implicitly", async ({ page, baseURL }) => {
  const calls = [];
  await page.route("**/api/rest/**", async (route) => {
    const url = new URL(route.request().url());
    calls.push({ path: url.pathname, data: route.request().postDataJSON() });
    if (url.pathname.endsWith("/learner/me")) return route.fulfill({ json: null });
    if (url.pathname.endsWith("/embedding-profile")) return route.fulfill({ json: { status: "AVAILABLE", model: "verified-test-model", dimensions: 1024 } });
    if (url.pathname.endsWith("/content")) return route.fulfill({ contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200"><text id="remainder">Modulus 7</text></svg>' });
    if (url.pathname.endsWith("/generate")) return route.fulfill({ json: { artifact_bundle_id: bundleId } });
    if (url.pathname.endsWith("/assets")) return route.fulfill({ json: { assets: bundle.assets } });
    if (url.pathname.endsWith("/frames")) return route.fulfill({ json: { base_asset_id: assetId, frames: bundle.frames } });
    if (url.pathname.includes("/bundles/")) return route.fulfill({ json: { ...bundle, assets: undefined, frames: undefined } });
    if (url.pathname.includes("/search")) return route.fulfill({ json: [] });
    return route.fulfill({ json: { artifact_request_id: requestId, artifact_bundle_id: bundleId, status: "PLANNED" } });
  });
  await mockAdminSession(page, baseURL);
  await page.goto("/artifacts");
  await page.getByText("Request a subject-aware artifact", { exact: true }).click();
  await page.getByLabel("Artifact topic", { exact: true }).fill("GCD");
  await page.getByLabel("Artifact title", { exact: true }).fill("Euclidean algorithm");
  await page.getByRole("button", { name: "Save artifact request", exact: true }).click();
  await expect(page.getByText("PLANNED", { exact: true })).toBeVisible();
  expect(calls.some((c) => /generate|semantic/.test(c.path))).toBe(false);
  await page.getByRole("button", { name: "Generate and publish validated artifact", exact: true }).click();
  await expect(page.getByText("Frame 1 / 2", { exact: true })).toBeVisible();
  expect(calls.filter((c) => c.path.endsWith("/generate"))).toHaveLength(1);
  await page.getByLabel("Search library", { exact: true }).fill("modular");
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Semantic search", exact: true }).click();
  await expect.poll(() => calls.filter((c) => c.path.endsWith("/search/semantic")).length).toBe(1);
  expect(calls.find((c) => c.path.endsWith("/search/semantic")).data.generate_embedding).toBe(true);
  expect(calls.find((c) => c.path.endsWith("/search/semantic")).data.dimensions).toBe(1024);
  expect(calls.find((c) => c.path.endsWith("/search/semantic")).data.model).toBe("verified-test-model");
});
test("older bounded search contracts still paginate without hidden paid calls", async ({ page }) => {
  let searches = 0;
  await page.route("**/api/rest/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/learner/me")) return route.fulfill({ json: null });
    if (url.pathname.endsWith("/embedding-profile")) return route.fulfill({ json: { status: "UNAVAILABLE", reason: "UNVERIFIED_DIMENSIONS" } });
    if (url.pathname.endsWith("/search")) {
      searches++;
      if ("offset" in route.request().postDataJSON()) return route.fulfill({ status: 422, json: { detail: "Unknown offset field" } });
      return route.fulfill({ json: { results: Array.from({ length: 40 }, (_, index) => ({ ...bundle, artifact_bundle_id: String(index), title: `Visual ${index + 1}` })) } });
    }
    throw new Error(`Unexpected request ${url.pathname}`);
  });
  await page.goto("/artifacts");
  await page.getByRole("button", { name: "Search metadata", exact: true }).click();
  await expect(page.getByRole("button", { name: "Next page", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Next page", exact: true }).click();
  await expect(page.getByText("Page 2 · rows 26–40", { exact: true })).toBeVisible();
  expect(searches).toBe(2);
});
test("staff indexing requires confirmation and includes the current source hash", async ({ page, baseURL }) => {
  const hash = "a".repeat(64), calls = [];
  await mockAdminSession(page, baseURL);
  await page.route("**/api/rest/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/learner/me")) return route.fulfill({ json: null });
    if (url.pathname.endsWith("/embedding-profile")) return route.fulfill({ json: { status: "AVAILABLE", model: "verified-test-model", dimensions: 1024 } });
    if (url.pathname.endsWith("/content")) return route.fulfill({ contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200"><text id="remainder">Modulus 7</text></svg>' });
    if (url.pathname.endsWith("/assets")) return route.fulfill({ json: { assets: bundle.assets } });
    if (url.pathname.endsWith("/frames")) return route.fulfill({ json: { base_asset_id: assetId, frames: bundle.frames } });
    if (url.pathname.endsWith("/index")) {
      calls.push(route.request().postDataJSON());
      return route.fulfill({ json: { status: "INDEXED" } });
    }
    return route.fulfill({ json: { ...bundle, search_text_sha256: hash } });
  });
  await page.goto(`/artifacts?bundle_id=${bundleId}`);
  await page.getByText("Metadata and reuse", { exact: true }).click();
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.getByRole("button", { name: "Index artifact for semantic search · uses AI", exact: true }).click();
  expect(calls).toHaveLength(0);
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Index artifact for semantic search · uses AI", exact: true }).click();
  await expect(page.getByText("Artifact indexed for semantic retrieval.", { exact: true })).toBeVisible();
  expect(calls).toEqual([{ generate_embedding: true, search_text_sha256: hash, model: "verified-test-model", dimensions: 1024 }]);
});
test("server frame content uses canonical private proxy paths instead of supplied URLs", async ({ page }) => {
  const paths = [], serverFrames = bundle.frames.map((frame) => ({ ...frame, content_path: "https://untrusted.test/frame.svg" }));
  await page.route("**/api/rest/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    paths.push(path);
    if (path.endsWith("/learner/me")) return route.fulfill({ json: null });
    if (path.endsWith("/embedding-profile")) return route.fulfill({ json: { status: "UNAVAILABLE" } });
    if (/\/frames\/\d+\/content$/.test(path)) return route.fulfill({ contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200"><text id="remainder" font-weight="700">Server-highlighted modulus 7</text></svg>' });
    if (path.endsWith("/assets")) return route.fulfill({ json: { assets: bundle.assets } });
    if (path.endsWith("/frames")) return route.fulfill({ json: { base_asset_id: assetId, frames: serverFrames } });
    return route.fulfill({ json: bundle });
  });
  await page.goto(`/artifacts?bundle_id=${bundleId}`);
  await expect(page.getByRole("img", { name: /Euclidean algorithm/ })).toBeVisible();
  expect(paths).toContain(`/api/rest/artifacts/bundles/${bundleId}/frames/0/content`);
  await page.getByRole("button", { name: "Next artifact frame", exact: true }).click();
  await expect.poll(() => paths.includes(`/api/rest/artifacts/bundles/${bundleId}/frames/1/content`)).toBe(true);
});
